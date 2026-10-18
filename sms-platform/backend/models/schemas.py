"""
schemas.py - Modelos de Dados Pydantic para a API da Plataforma SMS.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import datetime


class SingleSmsRequest(BaseModel):
    phone: str = Field(..., example="+5585999125992", description="Telefone com DDD")
    text: str = Field(..., example="Ola! Seu codigo de acesso e 1234. P/ sair envie SAIR", description="Conteudo da mensagem")
    auto_sanitize_gsm7: bool = Field(True, description="Converte caracteres nao-GSM e remove emojis automaticamente")
    enforce_160_limit: bool = Field(True, description="Rejeita envio se ultrapassar 160 caracteres (1 SMS)")


class ContactItem(BaseModel):
    phone: str
    name: Optional[str] = "Cliente"
    extra_fields: Optional[Dict[str, Any]] = None


class CampaignCreateRequest(BaseModel):
    name: str = Field(..., example="Campanha Promocional Outubro")
    template: str = Field(..., example="{Ola|Oi|Prezado} {nome}, seu cupom exclusivo e {cupom}. P/ sair envie SAIR")
    contacts: List[ContactItem] = Field(..., min_items=1)
    auto_sanitize_gsm7: bool = Field(True, description="Normaliza texto para GSM-7")
    enforce_160_limit: bool = Field(True, description="Bloqueia se qualquer variacao ultrapassar 160 caracteres")
    opt_out_suffix: str = Field(" P/ sair responda SAIR", description="Sufixo legal LGPD")


class SpintaxAnalysisRequest(BaseModel):
    template: str = Field(..., example="{Ola|Oi} {nome}, {seu pedido|sua encomenda} saiu para entrega!")
    sample_lead: Optional[Dict[str, Any]] = Field(default_factory=lambda: {"nome": "Maria", "codigo": "ABC1234"})


class BlacklistAddRequest(BaseModel):
    phone: str = Field(..., example="+5585999125992")
    reason: Optional[str] = "Solicitacao do cliente (Opt-out)"


class SmsLogEntry(BaseModel):
    id: str
    phone: str
    text: str
    char_count: int
    segments: int
    status: str  # sent, failed, blacklisted, pending
    error: Optional[str] = None
    campaign_id: Optional[str] = None
    timestamp: str
