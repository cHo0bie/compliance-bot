# Compliance Bot Pro (GigaChat, hybrid RAG, guardrails)

Streamlit‑прототип комплаенс‑бота: гибридный поиск (TF‑IDF + эмбеддинги), обязательные цитаты,
PII‑фильтры, политика (guardrails) и **LLM‑Judge** на GigaChat c автопочинкой ответа.

## Быстрый старт (Streamlit Cloud)

1. Залейте репозиторий и укажите entry point: `streamlit_app.py`.
2. В **Settings → Secrets** добавьте:
   ```toml
   GIGACHAT_AUTH_KEY = "base64(ClientID:ClientSecret)"
   GIGACHAT_SCOPE    = "GIGACHAT_API_PERS"
   GIGACHAT_MODEL    = "GigaChat-Pro"
   GIGACHAT_VERIFY   = "false"
   ```
3. Запустите приложение. Семпловые статьи лежат в `samples/knowledge`.

## Возможности
- Ингест PDF/MD/TXT → чанкинг → индексация.
- Гибридный поиск: TF‑IDF + `all-MiniLM-L6-v2` (вес на слайдере) + RapidFuzz‑rerank.
- Обязательные цитаты: бот всегда завершает ответ разделом **Источники**.
- Guardrails: PII‑детектор, простая политика (`guardrails/policy.yml`), LLM‑Judge.
- Автопочинка: при нарушении политика/PII/нет цитат — одна попытка re‑ask.

## Секреты и TLS
Если в среде строгая проверка TLS мешает OAuth, задайте `GIGACHAT_VERIFY="false"`.

## Лицензия
MIT.
