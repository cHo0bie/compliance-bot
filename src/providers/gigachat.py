
import os, time, uuid, requests

NGW = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
CHAT = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"

class GigaChat:
    def __init__(self):
        self.key = os.getenv("GIGACHAT_AUTH_KEY", "").strip()
        self.scope = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
        self.model = os.getenv("GIGACHAT_MODEL", "GigaChat-Pro")
        self.verify = os.getenv("GIGACHAT_VERIFY", "true").lower() not in ("0","false","no")
        if not self.key:
            raise RuntimeError("GIGACHAT_AUTH_KEY is missing")
        self._token = None
        self._expires = 0.0

    def _auth(self):
        if self._token and time.time() < self._expires - 30:
            return self._token
        headers = {
            "Authorization": f"Basic {self.key}",
            "RqUID": str(uuid.uuid4()),
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {"scope": self.scope}
        resp = requests.post(NGW, headers=headers, data=data, timeout=30, verify=self.verify)
        resp.raise_for_status()
        j = resp.json()
        self._token = j.get("access_token")
        ttl = j.get("expires_at") or j.get("expires_in") or 540
        self._expires = time.time() + (int(ttl) if isinstance(ttl, int) else 540)
        return self._token

    def chat(self, messages, temperature=0.2, max_tokens=700):
        token = self._auth()
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": float(temperature),
            "max_tokens": int(max_tokens)
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        resp = requests.post(CHAT, headers=headers, json=payload, timeout=60, verify=self.verify)
        resp.raise_for_status()
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except Exception:
            return str(data)
