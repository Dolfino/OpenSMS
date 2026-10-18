"""
main.py - Servidor FastAPI para a Plataforma de Disparos SMS de Alta Entregabilidade.
"""

import os
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse

from core.gsm import sanitize_for_gsm7, calculate_sms_segments
from core.spintax import analyze_template_variations
from core.opt_out import OptOutManager, normalize_phone_br
from core.shortener import LinkShortener
from services.opensms_client import OpenSmsClient
from services.queue_manager import QueueManager
from models.schemas import (
    SingleSmsRequest,
    CampaignCreateRequest,
    SpintaxAnalysisRequest,
    BlacklistAddRequest,
    LinkCreateRequest,
)

# Inicializacao
app = FastAPI(
    title="OpenSMS Bulk Messaging Gateway",
    description="Plataforma de alta entregabilidade para SMS unitario e em massa com protecao anti-spam e LGPD.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servicos Compartilhados
opensms_url = os.getenv("OPENSMS_URL", "http://localhost:9292")
opensms_key = os.getenv("OPENSMS_API_KEY", "")

sms_client = OpenSmsClient(base_url=opensms_url, api_key=opensms_key)
opt_out_mgr = OptOutManager(storage_path="data/blacklist.json")
queue_mgr = QueueManager(client=sms_client, opt_out=opt_out_mgr)
shortener_mgr = LinkShortener(storage_path="data/links.json")


# ---------------------------------------------
# Rotas de Status e Diagnostico
# ---------------------------------------------
@app.get("/api/health")
async def health_check():
    is_online, msg = await sms_client.check_health()
    return {
        "status": "online" if is_online else "degraded",
        "opensms_reachable": is_online,
        "opensms_url": sms_client.base_url,
        "detail": msg,
        "daily_sent_count": queue_mgr.policy.daily_sent_count,
        "daily_limit": queue_mgr.policy.daily_limit,
    }


# ---------------------------------------------
# Envio Unitario
# ---------------------------------------------
@app.post("/api/sms/send-single")
async def send_single_sms(req: SingleSmsRequest):
    norm_phone = normalize_phone_br(req.phone)

    # 1. Checa Blacklist
    if opt_out_mgr.is_blacklisted(norm_phone):
        raise HTTPException(
            status_code=400,
            detail="Este numero esta cadastrado na lista de Opt-out / Não Perturbe (LGPD)."
        )

    # 2. Sanitizacao
    text = req.text
    if req.auto_sanitize_gsm7:
        text = sanitize_for_gsm7(text)

    # 3. Metricas
    metrics = calculate_sms_segments(text)
    if req.enforce_160_limit and metrics["exceeds_160_chars"]:
        raise HTTPException(
            status_code=400,
            detail=f"A mensagem ultrapassa 160 caracteres ({metrics['char_count']} chars). Reduza o texto ou desative o limite estrito."
        )

    # 4. Envio
    result = await sms_client.send_sms(norm_phone, text)

    status_str = "sent" if result["success"] else "failed"
    queue_mgr.logs.append({
        "id": "single",
        "phone": norm_phone,
        "text": text,
        "char_count": metrics["char_count"],
        "segments": metrics["segments"],
        "status": status_str,
        "error": result.get("error"),
        "campaign_id": None,
        "timestamp": os.getenv("FAKE_TIME", "")
    })

    if not result["success"]:
        raise HTTPException(status_code=502, detail=result.get("error", "Falha de envio via OpenSMS"))

    return {
        "success": True,
        "phone": norm_phone,
        "char_count": metrics["char_count"],
        "segments": metrics["segments"],
        "encoding": metrics["encoding"]
    }


# ---------------------------------------------
# Rotas de Campanhas em Massa
# ---------------------------------------------
@app.post("/api/campaigns")
async def create_campaign(req: CampaignCreateRequest):
    try:
        camp = await queue_mgr.enqueue_campaign(req)
        return camp
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/campaigns")
async def list_campaigns():
    return queue_mgr.get_campaigns()


@app.get("/api/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str):
    camp = queue_mgr.get_campaign(campaign_id)
    if not camp:
        raise HTTPException(status_code=404, detail="Campanha nao encontrada")
    return camp


@app.post("/api/campaigns/{campaign_id}/cancel")
async def cancel_campaign(campaign_id: str):
    success = await queue_mgr.cancel_campaign(campaign_id)
    if not success:
        raise HTTPException(status_code=404, detail="Campanha nao encontrada ou ja concluida")
    return {"success": True, "message": "Campanha cancelada com sucesso"}


# ---------------------------------------------
# Analise de Spintax & Segmentacao
# ---------------------------------------------
@app.post("/api/spintax/analyze")
async def analyze_spintax_endpoint(req: SpintaxAnalysisRequest):
    analysis = analyze_template_variations(req.template, req.sample_lead)
    return analysis


# ---------------------------------------------
# Gestao de Blacklist (Opt-out)
# ---------------------------------------------
@app.get("/api/blacklist")
async def get_blacklist():
    return opt_out_mgr.list_blacklist()


@app.post("/api/blacklist")
async def add_to_blacklist(req: BlacklistAddRequest):
    added = opt_out_mgr.add_to_blacklist(req.phone, req.reason)
    return {"success": added, "phone": normalize_phone_br(req.phone)}


@app.delete("/api/blacklist/{phone}")
async def remove_from_blacklist(phone: str):
    removed = opt_out_mgr.remove_from_blacklist(phone)
    return {"success": removed, "phone": normalize_phone_br(phone)}


# ---------------------------------------------
# Logs de Envios
# ---------------------------------------------
@app.get("/api/logs")
async def get_logs(limit: int = 50):
    return queue_mgr.get_logs(limit=limit)


# ---------------------------------------------
# Encurtador de Links Próprio com Rastreamento
# ---------------------------------------------
@app.post("/api/links")
async def create_link(req: LinkCreateRequest, request: Request):
    entry = shortener_mgr.create_short_link(
        target_url=req.target_url,
        custom_slug=req.custom_slug,
        title=req.title
    )
    # Constrói a URL completa pública usando o Host da requisição
    host = request.headers.get("host", "sms.ideiasmkt.com.br")
    proto = request.headers.get("x-forwarded-proto", "https")
    entry["short_url"] = f"{proto}://{host}/r/{entry['code']}"
    return entry


@app.get("/api/links")
async def list_links(request: Request):
    host = request.headers.get("host", "sms.ideiasmkt.com.br")
    proto = request.headers.get("x-forwarded-proto", "https")
    links = shortener_mgr.list_links()
    for l in links:
        l["short_url"] = f"{proto}://{host}/r/{l['code']}"
    return links


@app.delete("/api/links/{code}")
async def delete_link(code: str):
    removed = shortener_mgr.delete_link(code)
    if not removed:
        raise HTTPException(status_code=404, detail="Link não encontrado")
    return {"success": True, "code": code}


@app.get("/r/{code}")
async def redirect_short_link(code: str):
    target_url = shortener_mgr.get_and_record_click(code)
    if not target_url:
        raise HTTPException(status_code=404, detail="Link encurtado não encontrado ou expirado")
    return RedirectResponse(url=target_url, status_code=307)


# Montagem do Frontend estatico
candidates = [
    os.path.join(os.path.dirname(__file__), "frontend/dist"),
    os.path.join(os.path.dirname(__file__), "../frontend/dist"),
    "/app/frontend/dist"
]
frontend_dir = next((c for c in candidates if os.path.exists(c)), None)
if frontend_dir:
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

