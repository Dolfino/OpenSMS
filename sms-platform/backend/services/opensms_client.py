"""
opensms_client.py - Cliente HTTP assincrono para comunicacao com o servidor OpenSMS.
"""

import os
import httpx
from typing import Dict, Any, Tuple


class OpenSmsClient:
    def __init__(
        self,
        base_url: str = os.getenv("OPENSMS_URL", "http://localhost:9292"),
        api_key: str = os.getenv("OPENSMS_API_KEY", ""),
        timeout: float = 15.0
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def update_credentials(self, api_key: str | None = None, base_url: str | None = None):
        """Atualiza a chave de API ou URL em tempo de execução."""
        if api_key is not None:
            self.api_key = api_key.strip()
        if base_url is not None:
            self.base_url = base_url.strip().rstrip("/")

    async def check_health(self) -> Tuple[bool, str]:
        """Verifica se o servidor OpenSMS no celular esta alcancavel e respondendo."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
                resp = await client.get(f"{self.base_url}/docs", headers=headers)
                if resp.status_code == 200:
                    return True, "Servidor OpenSMS online e alcançável via Tailscale."
                return False, f"Servidor respondeu com status {resp.status_code}."
        except httpx.ConnectError:
            return False, "Conexão recusada na porta 9292. Abra o app OpenSMS no celular e inicie o serviço."
        except httpx.ConnectTimeout:
            return False, "Timeout ao conectar ao celular. Verifique se o OpenSMS e o Tailscale estão ativos."
        except Exception as e:
            return False, f"Erro de conexão com o celular: {str(e)}"

    async def send_sms(self, phone: str, message: str) -> Dict[str, Any]:
        """
        Dispara um SMS via OpenSMS.
        Retorna dict com status de sucesso e detalhes.
        """
        url = f"{self.base_url}/sms/"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "number": phone,
            "text": message
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": data.get("stat", False),
                        "status_code": 200,
                        "data": data,
                        "error": None
                    }
                elif response.status_code == 401:
                    return {
                        "success": False,
                        "status_code": 401,
                        "data": None,
                        "error": "Chave de API do OpenSMS invalida ou expirada."
                    }
                else:
                    return {
                        "success": False,
                        "status_code": response.status_code,
                        "data": None,
                        "error": f"Erro do servidor OpenSMS: {response.text}"
                    }
        except httpx.RequestError as exc:
            return {
                "success": False,
                "status_code": 0,
                "data": None,
                "error": f"Falha de rede/transporte: {str(exc)}"
            }
