import json
import math
import re
from collections import Counter
from pathlib import Path


def tokenize(text: str) -> list:
    tokens = re.findall(r"[a-zA-Z_]\w*", text.lower())
    return [t for t in tokens if len(t) > 1 and not t.isdigit()]


class TfidfVectorStore:
    def __init__(self):
        self.documents = []
        self.doc_freq = Counter()
        self.num_docs = 0
        self.idf = {}
        self._dirty = True

    def add_document(self, doc_id, text, metadata=None):
        tokens = tokenize(text)
        if not tokens:
            return
        unique_tokens = set(tokens)
        self.documents.append(
            {
                "id": doc_id,
                "text": text,
                "tokens": tokens,
                "metadata": metadata or {},
            }
        )
        self.num_docs += 1
        for t in unique_tokens:
            self.doc_freq[t] += 1
        self._dirty = True

    def _ensure_index(self):
        if not self._dirty:
            return
        self.idf = {}
        for term, df in self.doc_freq.items():
            self.idf[term] = math.log((self.num_docs + 1) / (df + 1)) + 1.0
        self._dirty = False

    def _tfidf_vector(self, tokens):
        self._ensure_index()
        if not tokens:
            return {}
        tf = Counter(tokens)
        max_tf = max(tf.values())
        vec = {}
        for term, count in tf.items():
            tf_norm = count / max_tf
            vec[term] = tf_norm * self.idf.get(term, 1.0)
        return vec

    def _cosine_similarity(self, a, b):
        keys = set(a) & set(b)
        if not keys:
            return 0.0
        dot = sum(a[k] * b[k] for k in keys)
        norm_a = math.sqrt(sum(v * v for v in a.values()))
        norm_b = math.sqrt(sum(v * v for v in b.values()))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def search(self, query, top_k=5):
        query_tokens = tokenize(query)
        if not query_tokens:
            return []
        query_vec = self._tfidf_vector(query_tokens)
        scored = []
        for doc in self.documents:
            doc_vec = self._tfidf_vector(doc["tokens"])
            score = self._cosine_similarity(query_vec, doc_vec)
            if score > 0:
                scored.append(
                    {
                        "id": doc["id"],
                        "text": doc["text"],
                        "metadata": doc["metadata"],
                        "score": round(score, 4),
                    }
                )
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def remove_document(self, doc_id):
        self.documents = [d for d in self.documents if d["id"] != doc_id]
        self._rebuild_index()

    def _rebuild_index(self):
        self.doc_freq = Counter()
        self.num_docs = len(self.documents)
        for doc in self.documents:
            for t in set(doc["tokens"]):
                self.doc_freq[t] += 1
        self._dirty = True

    def save(self, path):
        data = {
            "documents": [
                {
                    "id": d["id"],
                    "text": d["text"],
                    "metadata": d["metadata"],
                }
                for d in self.documents
            ]
        }
        Path(path).write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text())
        store = cls()
        for doc in data.get("documents", []):
            store.add_document(doc["id"], doc["text"], doc.get("metadata"))
        return store
