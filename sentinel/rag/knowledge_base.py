import hashlib
import json
from pathlib import Path

from sentinel.rag.vector_store import TfidfVectorStore


def chunk_code(text, min_chars=100, max_chars=2000):
    lines = text.split("\n")
    chunks = []
    buf = []
    start_line = 1
    char_count = 0

    for i, line in enumerate(lines, 1):
        buf.append(line)
        char_count += len(line) + 1
        stripped = line.strip()
        is_break = (
            stripped.startswith(("def ", "class ", "async def ", "@"))
            and char_count >= min_chars
            and len(buf) > 1
        )
        if is_break or char_count >= max_chars:
            chunk_text = "\n".join(buf)
            chunks.append((chunk_text, start_line, i))
            buf = []
            start_line = i + 1
            char_count = 0

    if buf:
        chunks.append(("\n".join(buf), start_line, len(lines)))

    return chunks if chunks else [(text, 1, len(lines))]


def _content_hash(text):
    return hashlib.sha256(text.encode()).hexdigest()[:12]


class KnowledgeBase:
    def __init__(self, store=None):
        self.store = store or TfidfVectorStore()
        self.findings = {}
        self.chunk_map = {}

    def add_finding(self, code_snippet, finding, file_path=None):
        content_id = _content_hash(code_snippet)
        self.chunk_map[content_id] = code_snippet

        self.store.add_document(
            doc_id=content_id,
            text=code_snippet,
            metadata={"file": file_path or "", "content_hash": content_id},
        )

        if content_id not in self.findings:
            self.findings[content_id] = []
        self.findings[content_id].append(finding)

        return content_id

    def search_similar(self, code, top_k=5):
        results = self.store.search(code, top_k=top_k)
        for r in results:
            content_id = r["id"]
            r["findings"] = self.findings.get(content_id, [])
            r["code_snippet"] = self.chunk_map.get(content_id, r.get("text", ""))
        return results

    def ingest_findings(self, file_path, source, findings):
        chunks = chunk_code(source)
        count = 0
        for chunk_text, start, end in chunks:
            related = [
                f
                for f in findings
                if f.get("line") is None
                or (isinstance(f.get("line"), int) and start <= f["line"] <= end)
            ]
            if not related:
                related = findings
            for finding in related:
                enriched = {
                    **finding,
                    "_source_file": file_path,
                    "_chunk_lines": f"{start}-{end}",
                }
                self.add_finding(chunk_text, enriched, file_path)
                count += 1
        return count

    def save(self, path):
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        self.store.save(p / "vector_store.json")
        kb_data = {
            "findings": self.findings,
            "chunk_map": self.chunk_map,
        }
        (p / "knowledge_base.json").write_text(json.dumps(kb_data, indent=2))

    @classmethod
    def load(cls, path):
        p = Path(path)
        store = TfidfVectorStore.load(p / "vector_store.json")
        kb = cls(store=store)
        kb_data_path = p / "knowledge_base.json"
        if kb_data_path.exists():
            kb_data = json.loads(kb_data_path.read_text())
            kb.findings = kb_data.get("findings", {})
            kb.chunk_map = kb_data.get("chunk_map", {})
        return kb
