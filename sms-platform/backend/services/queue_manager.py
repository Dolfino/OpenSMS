"""
queue_manager.py - Gerenciador de Fila Assincrona e Execucao de Campanhas em Background.
Orquestra o rate limiting estocastico, pausas e protecoes anti-spam.
"""

import os
import json
import asyncio
import uuid
import datetime
from typing import Dict, Any, List, Optional

from core.gsm import sanitize_for_gsm7, calculate_sms_segments
from core.spintax import render_message, analyze_template_variations
from core.anti_spam import AntiSpamPolicy
from core.opt_out import OptOutManager, normalize_phone_br
from services.opensms_client import OpenSmsClient
from models.schemas import CampaignCreateRequest, ContactItem


class QueueManager:
    def __init__(self, client: OpenSmsClient, opt_out: OptOutManager, storage_path: str = "data/logs.json"):
        self.client = client
        self.opt_out = opt_out
        self.policy = AntiSpamPolicy()
        self.storage_path = storage_path

        os.makedirs(os.path.dirname(self.storage_path) if os.path.dirname(self.storage_path) else ".", exist_ok=True)
        self.campaigns: Dict[str, Dict[str, Any]] = {}
        self.logs: List[Dict[str, Any]] = self._load_logs()
        self.active_tasks: Dict[str, asyncio.Task] = {}

        # Sincroniza contador de envios do dia atual da política anti-spam
        self.policy.daily_sent_count = self.get_today_sent_count()

    def _load_logs(self) -> List[Dict[str, Any]]:
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save_logs(self):
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                # Armazena até os últimos 2000 disparos para histórico persistente
                json.dump(self.logs[-2000:], f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Erro ao salvar logs: {e}")

    def add_log(self, entry: Dict[str, Any]):
        if not entry.get("timestamp"):
            entry["timestamp"] = datetime.datetime.now().isoformat()
        self.logs.append(entry)
        self._save_logs()

    def get_today_sent_count(self) -> int:
        today_prefix = datetime.date.today().isoformat()
        count = 0
        for log in self.logs:
            if log.get("status") == "sent":
                ts = log.get("timestamp", "")
                if ts and ts.startswith(today_prefix):
                    count += 1
        return count

    def get_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self.logs[-limit:][::-1]

    def get_campaigns(self) -> List[Dict[str, Any]]:
        return list(self.campaigns.values())[::-1]

    def get_campaign(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        return self.campaigns.get(campaign_id)

    async def cancel_campaign(self, campaign_id: str) -> bool:
        if campaign_id in self.active_tasks:
            self.active_tasks[campaign_id].cancel()
            del self.active_tasks[campaign_id]
        if campaign_id in self.campaigns:
            self.campaigns[campaign_id]["status"] = "cancelled"
            return True
        return False

    async def enqueue_campaign(self, req: CampaignCreateRequest) -> Dict[str, Any]:
        campaign_id = str(uuid.uuid4())[:8]

        # Validar se o template pode ultrapassar 160 caracteres em alguma variacao
        if req.enforce_160_limit:
            analysis = analyze_template_variations(
                req.template,
                {"nome": "Exemplo", "cupom": "TESTE123", "codigo": "12345"},
                max_samples=50
            )
            if not analysis["safe_within_160"]:
                raise ValueError(
                    f"O template ultrapassa 160 caracteres em algumas variacoes (Max: {analysis['max_length']} chars). "
                    "Reduza o tamanho da mensagem ou desative o limite estrito."
                )

        campaign = {
            "id": campaign_id,
            "name": req.name,
            "template": req.template,
            "total": len(req.contacts),
            "sent": 0,
            "failed": 0,
            "blacklisted": 0,
            "status": "queued",
            "current_status_msg": "Aguardando inicio...",
            "created_at": datetime.datetime.now().isoformat(),
            "updated_at": datetime.datetime.now().isoformat()
        }
        self.campaigns[campaign_id] = campaign

        # Dispara task em background
        task = asyncio.create_task(self._process_campaign(campaign_id, req))
        self.active_tasks[campaign_id] = task

        return campaign

    async def _process_campaign(self, campaign_id: str, req: CampaignCreateRequest):
        camp = self.campaigns[campaign_id]
        camp["status"] = "running"

        try:
            for idx, contact in enumerate(req.contacts):
                # 1. Normaliza telefone
                norm_phone = normalize_phone_br(contact.phone)

                # 2. Verifica se esta na Blacklist (Opt-out)
                if self.opt_out.is_blacklisted(norm_phone):
                    camp["blacklisted"] += 1
                    self.add_log({
                        "id": str(uuid.uuid4())[:8],
                        "phone": norm_phone,
                        "text": "[BLOQUEADO PELA BLACKLIST / OPT-OUT]",
                        "char_count": 0,
                        "segments": 0,
                        "status": "blacklisted",
                        "error": "Contato presente na lista de descadastro (LGPD)",
                        "campaign_id": campaign_id,
                        "timestamp": datetime.datetime.now().isoformat()
                    })
                    continue

                # 3. Interpola Spintax e variaveis do lead
                lead_data = {"nome": contact.name or "Cliente"}
                if contact.extra_fields:
                    lead_data.update(contact.extra_fields)

                msg_text = render_message(
                    req.template,
                    lead_data,
                    auto_sanitize_gsm7=req.auto_sanitize_gsm7,
                    opt_out_suffix=req.opt_out_suffix
                )

                # Metricas de tamanho
                metrics = calculate_sms_segments(msg_text)

                # 4. Verifica horario comercial
                is_allowed_time, time_msg = self.policy.check_working_hours()
                if not is_allowed_time:
                    camp["current_status_msg"] = f"Pausado: {time_msg}"
                    # Aguarda 15 minutos antes de rechecar
                    await asyncio.sleep(900)

                # 5. Calcula delay estocástico anti-spam
                delay, is_long_pause, delay_reason = self.policy.calculate_next_delay()
                camp["current_status_msg"] = f"Aguardando {round(delay, 1)}s ({delay_reason})"
                await asyncio.sleep(delay)

                # 6. Dispara via OpenSMS
                camp["current_status_msg"] = f"Enviando {idx + 1}/{camp['total']} para {norm_phone}..."
                result = await self.client.send_sms(norm_phone, msg_text)

                if result["success"]:
                    camp["sent"] += 1
                    status_str = "sent"
                    error_msg = None
                    self.policy.record_send()
                else:
                    camp["failed"] += 1
                    status_str = "failed"
                    error_msg = result.get("error", "Falha de envio desconhecida")

                # Registra no log
                self.add_log({
                    "id": str(uuid.uuid4())[:8],
                    "phone": norm_phone,
                    "text": msg_text,
                    "char_count": metrics["char_count"],
                    "segments": metrics["segments"],
                    "status": status_str,
                    "error": error_msg,
                    "campaign_id": campaign_id,
                    "timestamp": datetime.datetime.now().isoformat()
                })

                camp["updated_at"] = datetime.datetime.now().isoformat()

            camp["status"] = "completed"
            camp["current_status_msg"] = "Campanha finalizada com sucesso!"

        except asyncio.CancelledError:
            camp["status"] = "cancelled"
            camp["current_status_msg"] = "Campanha cancelada pelo usuario."
        except Exception as e:
            camp["status"] = "failed"
            camp["current_status_msg"] = f"Erro na execucao: {str(e)}"
        finally:
            if campaign_id in self.active_tasks:
                del self.active_tasks[campaign_id]
