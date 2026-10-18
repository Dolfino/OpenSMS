"""
opt_out.py - Gestao de Consentimento, Lista Negra (Blacklist) e Conformidade LGPD.
Garante que usuarios que solicitaram saida nunca mais recebam mensagens.
"""

import re
import os
import json
from typing import Set, Dict, Any, List
import datetime

BLACKLIST_FILE = "blacklist.json"


def normalize_phone_br(phone: str) -> str:
    """
    Padroniza telefones brasileiros para o formato internacional E.164 (+55DDD9XXXXXXXX).
    Remove parenteses, tracos, espacos e caracteres nao numericos.
    """
    digits = re.sub(r"\D", "", phone)

    # Se comecar com 0, remove
    if digits.startswith("0"):
        digits = digits[1:]

    # Se ja tiver 55 no inicio (12 ou 13 digitos)
    if digits.startswith("55") and len(digits) in (12, 13):
        return f"+{digits}"

    # Se tiver 10 digitos (DDD + 8 digitos fixo/antigo), adiciona 55
    if len(digits) == 10:
        return f"+55{digits}"

    # Se tiver 11 digitos (DDD + 9 digitos celular), adiciona 55
    if len(digits) == 11:
        return f"+55{digits}"

    # Retorna padronizado
    return f"+{digits}" if not digits.startswith("+") else digits


class OptOutManager:
    def __init__(self, storage_path: str = "data/blacklist.json"):
        self.storage_path = storage_path
        os.makedirs(os.path.dirname(self.storage_path) if os.path.dirname(self.storage_path) else ".", exist_ok=True)
        self.blacklist: Dict[str, Dict[str, Any]] = self._load()

    def _load(self) -> Dict[str, Dict[str, Any]]:
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save(self):
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self.blacklist, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Erro salvando blacklist: {e}")

    def is_blacklisted(self, phone: str) -> bool:
        normalized = normalize_phone_br(phone)
        return normalized in self.blacklist

    def add_to_blacklist(self, phone: str, reason: str = "Solicitacao de descadastro (Opt-out)") -> bool:
        normalized = normalize_phone_br(phone)
        if normalized not in self.blacklist:
            self.blacklist[normalized] = {
                "phone": normalized,
                "added_at": datetime.datetime.now().isoformat(),
                "reason": reason
            }
            self._save()
            return True
        return False

    def remove_from_blacklist(self, phone: str) -> bool:
        normalized = normalize_phone_br(phone)
        if normalized in self.blacklist:
            del self.blacklist[normalized]
            self._save()
            return True
        return False

    def list_blacklist(self) -> List[Dict[str, Any]]:
        return list(self.blacklist.values())
