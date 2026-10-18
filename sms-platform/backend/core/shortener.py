"""
shortener.py - Encurtador de Links Nativo com Rastreamento de Cliques.
Permite criar links curtos do tipo https://sms.ideiasmkt.com.br/r/{code}
evitando filtros anti-spam de encurtadores públicos (bit.ly, tinyurl, etc.).
"""

import os
import json
import secrets
import datetime
from typing import Dict, Any, List, Optional


class LinkShortener:
    def __init__(self, storage_path: str = "data/links.json"):
        self.storage_path = storage_path
        os.makedirs(os.path.dirname(self.storage_path) if os.path.dirname(self.storage_path) else ".", exist_ok=True)
        self.links: Dict[str, Dict[str, Any]] = self._load()

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
                json.dump(self.links, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Erro ao salvar links: {e}")

    def create_short_link(
        self,
        target_url: str,
        custom_slug: Optional[str] = None,
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        """Cria um novo link encurtado com código aleatório ou personalizado."""
        if not target_url.startswith(("http://", "https://")):
            target_url = f"https://{target_url}"

        # Se especificou slug customizado
        if custom_slug and custom_slug.strip():
            code = custom_slug.strip().lower()
            # Substitui espaços por traços
            code = "".join([c if c.isalnum() or c in "-_" else "" for c in code])
        else:
            # Gera código aleatório curto de 5 caracteres
            code = secrets.token_urlsafe(4)[:5].lower()

        # Evita sobrescrever se for gerado aleatório
        attempts = 0
        while code in self.links and attempts < 10:
            code = secrets.token_urlsafe(4)[:5].lower()
            attempts += 1

        entry = {
            "code": code,
            "target_url": target_url,
            "title": title or target_url[:40],
            "clicks": 0,
            "created_at": datetime.datetime.now().isoformat(),
            "last_clicked_at": None,
        }

        self.links[code] = entry
        self._save()
        return entry

    def get_and_record_click(self, code: str) -> Optional[str]:
        """Recupera a URL de destino e contabiliza o clique."""
        code = code.lower()
        if code in self.links:
            self.links[code]["clicks"] += 1
            self.links[code]["last_clicked_at"] = datetime.datetime.now().isoformat()
            self._save()
            return self.links[code]["target_url"]
        return None

    def list_links(self) -> List[Dict[str, Any]]:
        return list(self.links.values())[::-1]

    def delete_link(self, code: str) -> bool:
        code = code.lower()
        if code in self.links:
            del self.links[code]
            self._save()
            return True
        return False
