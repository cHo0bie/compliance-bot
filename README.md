# Compliance Bot (GigaChat) — RAG → Guardrails → Log

Демо‑приложение на **Streamlit**: вопрос пользователя → поиск релевантных пассажей в базе знаний →
ответ LLM (**GigaChat**) с **обязательными цитатами источников** → **guardrails** (PII/запрещённые темы, LLM‑asserts) → **логирование**.

![flow](https://user-images.githubusercontent.com/000/placeholder.png)

## Возможности
- 🔎 TF‑IDF RAG по Markdown‑базе (`samples/knowledge/*.md`).
- 🤖 GigaChat (фиксированный провайдер/модель).
- 🛡️ Guardrails: PII‑шаблоны, запретные темы, LLM‑assert «в ответе должны быть источники [1], [2], …».
- 🧾 Экспорт лога (CSV).
- ⚙️ Лёгкие зависимости — дружит со Streamlit Cloud.

## Быстрый старт (локально)
```bash
pip install -r requirements.txt
export GIGACHAT_AUTH_KEY="base64(ClientID:ClientSecret)"
export GIGACHAT_SCOPE="GIGACHAT_API_PERS"
export GIGACHAT_MODEL="GigaChat-Pro"
export GIGACHAT_VERIFY="false"   # если ругается TLS в вашей среде

streamlit run streamlit_app.py
```

## Деплой в Streamlit Cloud
1. Залейте репозиторий на GitHub.
2. **New app** → `streamlit_app.py`.
3. В **Secrets** добавьте:
```toml
GIGACHAT_AUTH_KEY = "base64(ClientID:ClientSecret)"
GIGACHAT_SCOPE    = "GIGACHAT_API_PERS"
GIGACHAT_MODEL    = "GigaChat-Pro"
GIGACHAT_VERIFY   = "false"
```
4. Откройте приложение — индексация займёт 1–2 секунды.

## Структура
```
.
├─ streamlit_app.py
├─ requirements.txt
├─ src/
│  ├─ providers/gigachat.py
│  └─ rag/tfidf.py
└─ samples/knowledge/*.md
```

## Расширения
- Подключить эмбеддинги вместо TF‑IDF (например, `sentence-transformers`) — можно, но на Streamlit Cloud это увеличит размер/время билда.
- Заменить rule‑based rails на NeMo Guardrails — потребуется Docker/внешний сервис. Текущие правила простые, быстрые и запускаются в облаке без дополнительных сервисов.

## Лицензия
MIT
