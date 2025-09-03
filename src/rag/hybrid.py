
import os, io, re, math
from typing import List, Dict, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Optional deps
_EMB = None
try:
    from sentence_transformers import SentenceTransformer
    _EMB = SentenceTransformer("all-MiniLM-L6-v2")
except Exception:
    _EMB = None

def read_text_from_file(path: str) -> str:
    text = ""
    if path.lower().endswith(".pdf"):
        try:
            from pypdf import PdfReader
            r = PdfReader(path)
            text = "\n".join([p.extract_text() or "" for p in r.pages])
        except Exception:
            text = ""
    elif path.lower().endswith(".md"):
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    else:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    return text

def chunk_text(text: str, max_chars: int=900, overlap: int=120) -> List[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text: return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        # try cut on sentence boundary
        cut = text.rfind(". ", start, end)
        if cut == -1 or cut - start < max_chars*0.5:
            cut = end
        chunks.append(text[start:cut].strip())
        start = max(cut - overlap, start + 1)
    return [c for c in chunks if c]

class HybridIndex:
    def __init__(self, alpha: float = 0.5):
        self.alpha = alpha
        self.docs: List[Dict] = []
        self._tfidf = None
        self._X = None
        self._E = None  # embeddings

    def add_docs(self, items: List[Dict]):
        # item: {id, title, text, source}
        self.docs.extend(items)

    def build(self):
        texts = [d["text"] for d in self.docs]
        if not texts:
            self._tfidf = None; self._X = None; self._E = None; return
        self._tfidf = TfidfVectorizer(ngram_range=(1,2), min_df=1)
        self._X = self._tfidf.fit_transform(texts)
        if _EMB:
            self._E = _EMB.encode(texts, convert_to_tensor=False, show_progress_bar=False)
        else:
            self._E = None

    def search(self, query: str, top_k: int = 5):
        if not self.docs: return []
        scores = []
        # tfidf
        qv = self._tfidf.transform([query]) if self._tfidf is not None else None
        tfidf_scores = (qv @ self._X.T).toarray()[0] if qv is not None else [0.0]*len(self.docs)
        # embeddings
        emb_scores = [0.0]*len(self.docs)
        if self._E is not None and _EMB is not None:
            import numpy as np
            qe = _EMB.encode([query], convert_to_tensor=False, show_progress_bar=False)[0]
            # cosine
            def cos(a,b): 
                na = math.sqrt((a*a).sum()); nb = math.sqrt((b*b).sum())
                return float((a@b)/(na*nb + 1e-8))
            for i, e in enumerate(self._E):
                emb_scores[i] = cos(qe, e)
        # hybrid
        for i,_ in enumerate(self.docs):
            s = self.alpha*tfidf_scores[i] + (1-self.alpha)*emb_scores[i]
            scores.append((s,i))
        scores.sort(reverse=True)
        result = []
        for s,i in scores[:top_k]:
            d = self.docs[i].copy(); d["score"] = float(s); result.append(d)
        # Lightweight fuzzy rerank
        try:
            from rapidfuzz import fuzz
            result.sort(key=lambda d: fuzz.partial_ratio(query, d["text"]), reverse=True)
        except Exception:
            pass
        return result
