# Streamlit Compliance Bot (GigaChat, RAG → Guardrails → Log)
import os
import re
import csv
import time
import json
import hashlib
from typing import List, Dict, Tuple

import streamlit as st
import pandas as pd

from src.providers.gigachat import GigaChat
from src.rag.tfidf import TfidfIndex, load_markdown_corpus

# -----------------------------
# Env / secrets
# -----------------------------
AUTH_KEY  = os.getenv("GIGACHAT_AUTH_KEY", "")
SCOPE     = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
MODEL     = os.getenv("GIGACHAT_MODEL", "GigaChat-Pro")
VERIFY    = os.getenv("GIGACHAT_VERIFY", "true").lower() != "false"

# Fixed provider (per your request)
def get_chat() -> GigaChat:
    return GigaChat(auth_key=AUTH_KEY, scope=SCOPE, model=MODEL, verify=VERIFY)

# -----------------------------
# Guardrails: simple but practical
# -----------------------------
PII_PATTERNS = [
    (r"\b\d{16}\b", "Найден возможный номер карты"),
    (r"\b\d{3}-\d{3}-\d{3} \d{2}\b", "Найден возможный ИНН/СНИЛС/ИНН-фрагмент"),
    (r"\b\d{4}\s?\d{6}\b", "Найден возможный паспортный номер"),
    (r"\b\d{11}\b", "Найден возможный телефон"),
    (r"\b[А-Яа-яA-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "Найден возможный email"),
]

BANNED_TOPICS = [
    "как обойти проверку личности",
    "как обойти kyc",
    "как обойти aml",
    "как подделать документы",
    "как скрыть источник средств",
]

def run_guardrails(prompt: str, llm_answer: str) -> Tuple[bool, List[str]]:
    """Return (ok, messages)."""
    violations = []
    low = (prompt + " " + llm_answer).lower()

    for pat, msg in PII_PATTERNS:
        if re.search(pat, prompt) or re.search(pat, llm_answer):
            violations.append(f"PII: {msg}")

    for topic in BANNED_TOPICS:
        if topic in low:
            violations.append(f"Запрещённая тема: «{topic}»")

    # LLM assert: должен быть раздел «Источники:» и хотя бы одна ссылка вида [1], [2], ...
    if "источники" not in llm_answer.lower() or not re.search(r"\[\d+\]", llm_answer):
        violations.append("ЛЛМ-ассерт: отсутствуют обязательные цитаты источников ([1], [2], …)")

    return (len(violations) == 0, violations)

# -----------------------------
# Prompt templates
# -----------------------------
SYSTEM_PROMPT = """Ты — помощник комплаенс-офицера банка.
Отвечай строго по фактам, кратко и в деловом стиле.
Всегда **обязательно** добавляй раздел:
«Источники: [1] file://...; [2] file://...». Номер соответствует позициям из контекста.
Если нет релевантных фрагментов — честно напиши: «Не нашёлся ответ на ваш вопрос.».
"""
USER_PROMPT_TEMPLATE = """Вопрос пользователя: {question}

Контекст (релевантные фрагменты из базы знаний):
{context}

Инструкция:
1) Ответь по пунктам, опираясь **только** на контекст.
2) В конце обязательно добавь раздел «Источники: [1] …; [2] …»,
   где укажи номера и пути документов из контекста, которые ты использовал.
"""

# -----------------------------
# Load corpus & build index
# -----------------------------
@st.cache_data(show_spinner=False)
def cached_index() -> Tuple[TfidfIndex, List[Dict]]:
    corpus = load_markdown_corpus("samples/knowledge")
    index = TfidfIndex([c["content"] for c in corpus])
    return index, corpus

# -----------------------------
# UI
# -----------------------------
st.set_page_config(page_title="Compliance Bot (GigaChat)", layout="wide")
st.title("Demo: Комплаенс-бот")
st.caption("RAG → LLM (GigaChat) → Guardrails → Log")

with st.sidebar:
    st.header("Провайдер и параметры")
    st.selectbox("Провайдер", ["GigaChat"], index=0, disabled=True)
    st.selectbox("Модель", [MODEL], index=0, disabled=True)
    top_k = st.slider("Top-k пассажей", 1, 8, 4)
    use_llm = st.toggle("Использовать LLM для финального ответа", True,
                        help="Если отключить — покажем только найденные пассажи.")
    st.divider()
    st.subheader("Лог")
    dl = st.session_state.get("log_rows", [])
    if dl:
        df = pd.DataFrame(dl)
        st.download_button("Скачать лог (CSV)", df.to_csv(index=False).encode("utf-8"),
                           file_name="compliance_log.csv", mime="text/csv")

question = st.text_input("Вопрос", "Можно ли открыть счёт нерезиденту и какие нужны документы?")
col1, col2 = st.columns([1,3])
with col1:
    run_btn = st.button("Искать")
with col2:
    st.write("")

if run_btn:
    index, corpus = cached_index()
    docs = index.top_k(question, top_k=top_k)
    st.subheader("Найденные пассажи")
    ctx_lines = []
    for i, (score, idx) in enumerate(docs, start=1):
        meta = corpus[idx]
        st.markdown(f"**[{i}] {meta['title']}** — `file://{meta['path']}`  \nрейтйнг: {score:.3f}")
        st.write(meta["content"][:1000] + ("..." if len(meta["content"])>1000 else ""))
        ctx_lines.append(f"[{i}] file://{meta['path']}\n{meta['content']}\n")

    if use_llm:
        st.subheader("Ответ")
        chat = get_chat()
        ctx_str = "\n\n".join(ctx_lines)
        prompt = USER_PROMPT_TEMPLATE.format(question=question, context=ctx_str)
        try:
            answer = chat.chat(
                system=SYSTEM_PROMPT,
                user=prompt,
                temperature=0.2,
                max_tokens=700
            )
        except Exception as e:
            st.error(f"Ошибка обращения к GigaChat: {e}")
            answer = "Не удалось получить ответ от модели."

        ok, rails = run_guardrails(question, answer)
        if not ok:
            with st.expander("Нарушения (guardrails)", expanded=True):
                st.error("\n".join(f"• {r}" for r in rails))
            st.warning("Ответ заблокирован правилами безопасности.")
        else:
            st.markdown(answer)

        # Log
        row = {
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "question": question,
            "top_k": top_k,
            "use_llm": use_llm,
            "ok": ok,
            "violations": "; ".join(rails) if rails else "",
            "doc_ids": "; ".join([f"file://{corpus[i]['path']}" for _, i in docs]) if docs else ""
        }
        st.session_state.setdefault("log_rows", []).append(row)
