from typing import List, Dict, Tuple
import os, glob
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()

class TfidfIndex:
    def __init__(self, docs: List[str]):
        self.vectorizer = TfidfVectorizer(stop_words=None, max_df=0.9)
        self.doc_vectors = self.vectorizer.fit_transform([normalize(x) for x in docs])

    def top_k(self, query: str, k: int = 5) -> List[Tuple[float, int]]:
        q_vec = self.vectorizer.transform([normalize(query)])
        sims = cosine_similarity(q_vec, self.doc_vectors)[0]
        order = sims.argsort()[::-1]
        return [(float(sims[i]), int(i)) for i in order[:k]]

def load_markdown_corpus(root: str) -> List[Dict]:
    paths = sorted(glob.glob(os.path.join(root, "*.md")))
    corpus = []
    for p in paths:
        try:
            with open(p, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            content = ""
        title = os.path.basename(p).replace(".md", "").replace("_", " ").title()
        corpus.append({"title": title, "path": os.path.relpath(p, start=os.getcwd()), "content": content})
    return corpus
