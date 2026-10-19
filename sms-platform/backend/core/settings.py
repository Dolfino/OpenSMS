"""
settings.py - Gerenciador de configurações persistentes da plataforma (API Key, URL OpenSMS, etc.)
Armazenado em data/settings.json no volume persistente PVC.
"""

import os
import json
from typing import Dict, Any, Optional

DEFAULT_SETTINGS_PATH = "data/settings.json"
DEFAULT_OPENSMS_URL = "http://100.72.103.36:9292"
DEFAULT_API_KEY = "osms_Ns-4NPsAN7nRMTiOAzoQgUMnVn2b0z0JixqB1Gdo5ZA"


class SettingsManager:
    def __init__(self, storage_path: str = DEFAULT_SETTINGS_PATH):
        self.storage_path = storage_path
        os.makedirs(os.path.dirname(self.storage_path) if os.path.dirname(self.storage_path) else ".", exist_ok=True)
        self.settings: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        # Garante que tenha os campos essenciais
                        if "api_key" not in data or not data["api_key"]:
                            data["api_key"] = DEFAULT_API_KEY
                        if "opensms_url" not in data or not data["opensms_url"]:
                            data["opensms_url"] = DEFAULT_OPENSMS_URL
                        return data
            except Exception as e:
                print(f"Erro ao carregar settings: {e}")

        # Se não existe, inicializa com o novo token fornecido
        initial = {
            "api_key": os.getenv("OPENSMS_API_KEY") or DEFAULT_API_KEY,
            "opensms_url": os.getenv("OPENSMS_URL") or DEFAULT_OPENSMS_URL
        }
        self._save_data(initial)
        return initial

    def _save_data(self, data: Dict[str, Any]):
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Erro ao salvar settings: {e}")

    def get_settings(self) -> Dict[str, Any]:
        return {
            "api_key": self.settings.get("api_key", DEFAULT_API_KEY),
            "opensms_url": self.settings.get("opensms_url", DEFAULT_OPENSMS_URL)
        }

    def update_settings(self, api_key: Optional[str] = None, opensms_url: Optional[str] = None) -> Dict[str, Any]:
        if api_key is not None and api_key.strip():
            self.settings["api_key"] = api_key.strip()
        if opensms_url is not None and opensms_url.strip():
            self.settings["opensms_url"] = opensms_url.strip().rstrip("/")

        self._save_data(self.settings)
        return self.get_settings()
