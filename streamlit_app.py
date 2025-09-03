
import os, io, json, textwrap
import streamlit as st

from src.providers.gigachat import GigaChat
from src.rag.hybrid import HybridIndex, read_text_from_file, chunk_text
from src.guardrails.rules import detect_pii, load_policy, violates_policy

# --- UI ---
st.set_page_config(page_title="Compliance Bot Pro", layout="wide")
st.title("Compliance Bot Pro — GigaChat (RAG + Guardrails + Judge)")

with st.sidebar:
    st.header("Ингест и параметры")
    alpha = st.slider("Вес TF-IDF (0 = только эмбеддинги)", 0.0, 1.0, 0.5, 0.05)
    topk = st.slider("Top‑k пассажей", 1, 10, 5, 1)
    uploaded = st.file_uploader("Добавить PDF/MD/TXT", type=["pdf","md","txt"], accept_multiple_files=True)
    build = st.button("Переиндексировать")
    export = st.button("Экспорт отчёта (Markdown)")

# --- Data / Index ---
if "index" not in st.session_state:
    st.session_state.index = HybridIndex(alpha=alpha)
    # preload samples
    base = os.path.join(os.path.dirname(__file__), "samples", "knowledge")
    docs = []
    for fn in os.listdir(base):
        p = os.path.join(base, fn)
        text = read_text_from_file(p)
        for i,ch in enumerate(chunk_text(text)):
            docs.append({"id": f"{fn}-{i}", "title": fn, "text": ch, "source": f"file://{p}"})
    st.session_state.index.add_docs(docs)
    st.session_state.index.build()
    st.session_state.history = []

# apply changed alpha
st.session_state.index.alpha = alpha

# handle uploads
if uploaded:
    new_docs = []
    up_base = os.path.join(os.path.dirname(__file__), "uploaded")
    os.makedirs(up_base, exist_ok=True)
    for f in uploaded:
        path = os.path.join(up_base, f.name)
        with open(path, "wb") as out:
            out.write(f.read())
        txt = read_text_from_file(path)
        for i,ch in enumerate(chunk_text(txt)):
            new_docs.append({"id": f"{f.name}-{i}", "title": f.name, "text": ch, "source": f"file://{path}"})
    st.session_state.index.add_docs(new_docs)

if build:
    st.session_state.index.build()
    st.success("Индекс обновлён.")

# --- Query ---
q = st.text_input("Вопрос", placeholder="Например: какие ограничения по санкциям действуют для переводов?")
use_llm = st.toggle("Собрать финальный ответ LLM (иначе покажем пассажа)", value=True)

def call_llm(messages):
    prov = GigaChat()
    return prov.chat(messages, temperature=0.2, max_tokens=800)

def format_citations(passages):
    lines = []
    for i,p in enumerate(passages, start=1):
        lines.append(f"[{i}] {p['title']} — {p['source']}")
    return "\n".join(lines)

def llm_answer(q, passages):
    with open(os.path.join(os.path.dirname(__file__), "prompts", "system.txt"), "r", encoding="utf-8") as f:
        system = f.read()
    ctx = "\n\n".join([f"Пассаж [{i+1}]: {p['text']}" for i,p in enumerate(passages)])
    user = f"Вопрос: {q}\n\nИспользуй приведённые пассажа, указывай источники строго по номерам.\n{ctx}\n\nОтветь кратко и по делу."
    return call_llm([{"role":"system","content":system},{"role":"user","content":user}])

def llm_judge(answer, passages):
    with open(os.path.join(os.path.dirname(__file__), "prompts", "judge.txt"), "r", encoding="utf-8") as f:
        judge = f.read()
    src = "\n".join([f"[{i+1}] {p['text'][:400]}" for i,p in enumerate(passages)])
    ask = f"{judge}\n\nПассажи:\n{src}\n\nОтвет ассистента:\n{answer}"
    try:
        raw = call_llm([{"role":"system","content":"Ты строгий арбитр."},{"role":"user","content":ask}])
        j = json.loads(raw)
    except Exception:
        j = {"ok": False, "needs_fix": True, "violations": ["parse_error"], "critique":"Не удалось распарсить JSON."}
    return j

def repair_answer(q, passages, critique):
    prompt = textwrap.dedent(f"""
    Перепиши ответ строго по правилам:
    - Ссылайся на пассажа только по номерам в конце (раздел "Источники:").
    - Ничего не выдумывай вне пассажей.
    - Избегай PII и нарушений политики.
    - Если сведений мало — напиши, что данных недостаточно.
    Вопрос: {q}
    Пассажи: {" | ".join(str(i+1) for i in range(len(passages)))}
    """).strip()
    return call_llm([{"role":"system","content":"Собери безопасный ответ по правилам."},
                     {"role":"user","content":prompt}])

if st.button("Искать"):
    if not q.strip():
        st.warning("Введите вопрос.")
    else:
        results = st.session_state.index.search(q, top_k=topk)
        if not results:
            st.info("Ничего не найдено.")
        else:
            if not use_llm:
                st.subheader("Найденные пассажи")
                for r in results:
                    st.markdown(f"**{r['title']}** — _{r['source']}_  \nрейтинґ: `{r['score']:.3f}`  \n\n> {r['text']}")
            else:
                answer = llm_answer(q, results)
                # Guardrails
                policy = load_policy(os.path.join(os.path.dirname(__file__), "src", "guardrails", "policy.yml"))
                pii = detect_pii(answer)
                violations = violates_policy(answer, policy)
                judge = llm_judge(answer, results)
                need_fix = bool(pii or violations or judge.get("needs_fix") or not judge.get("ok"))
                if need_fix:
                    answer = repair_answer(q, results, judge.get("critique",""))
                # Добавим источники, если их нет
                if "Источники" not in answer:
                    answer += "\n\nИсточники:\n" + format_citations(results)
                st.markdown("### Ответ")
                st.write(answer)
                st.caption("Guardrails: PII=%s, policy=%s, judge=%s" % (",".join(pii) or "-", ",".join(violations) or "-", json.dumps(judge)))
                # History
                st.session_state.history.append({"q":q, "answer":answer, "citations":format_citations(results)})
                # Показать пассажа
                with st.expander("Показать использованные пассажа"):
                    for r in results:
                        st.markdown(f"**{r['title']}** — _{r['source']}_  \nрейтинґ: `{r['score']:.3f}`  \n\n> {r['text']}")

# Export
if export:
    lines = ["# Отчёт Compliance Bot Pro\n"]
    for i,item in enumerate(st.session_state.history or []):
        lines += [f"## Запрос #{i+1}", f"**Вопрос:** {item['q']}", "", "**Ответ:**", item['answer'], "", "**Источники:**", item['citations'], "\n---\n"]
    md = "\n".join(lines) if lines else "# Пусто"
    st.download_button("Скачать отчёт.md", md, file_name="report.md")
