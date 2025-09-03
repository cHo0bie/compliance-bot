import os
import time
import base64
import requests
from typing import Optional

NGW_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
CHAT_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"

class GigaChat:
    def __init__(self, auth_key: str, scope: str = "GIGACHAT_API_PERS",
                 model: str = "GigaChat-Pro", verify: bool = True):
        self.auth_key = auth_key
        self.scope = scope
        self.model = model
        self.verify = verify
        self._token = None
        self._exp = 0

    def _headers(self):
        return {"Accept": "application/json", "Content-Type": "application/json"}

    def _get_token(self) -> str:
        now = time.time()
        if self._token and now < self._exp - 60:
            return self._token

        if not self.auth_key:
            raise RuntimeError("GIGACHAT_AUTH_KEY is missing")

        headers = {
            "Authorization": f"Basic {self.auth_key}",
            "RqUID": "compliance-bot",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {"scope": self.scope}
        resp = requests.post(NGW_URL, headers=headers, data=data, timeout=20, verify=self.verify)
        resp.raise_for_status()
        j = resp.json()
        self._token = j.get("access_token")
        expires_in = int(j.get("expires_in", 1800))
        self._exp = now + expires_in
        if not self._token:
            raise RuntimeError(f"Cannot get access_token: {j}")
        return self._token

    def chat(self, system: str, user: str, temperature: float = 0.2, max_tokens: int = 700) -> str:
        token = self._get_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": float(temperature),
            "max_tokens": int(max_tokens)
        }
        r = requests.post(CHAT_URL, json=payload, headers=headers, timeout=60, verify=self.verify)
        r.raise_for_status()
        data = r.json()
        try:
            return data["choices"][0]["message"]["content"]
        except Exception:
            return str(data)
