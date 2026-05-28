class Retriever:
    def __init__(self, knowledge_base):
        self.kb = knowledge_base

    def retrieve_context(self, code, top_k=5):
        results = self.kb.search_similar(code, top_k=top_k)
        return self._format_context(results)

    def _format_context(self, results):
        formatted = []
        for r in results:
            formatted.append(
                {
                    "code_snippet": r["code_snippet"],
                    "findings": r["findings"],
                    "score": r["score"],
                    "file": r["metadata"].get("file", ""),
                }
            )
        return formatted

    def build_prompt_context(self, results):
        if not results:
            return ""
        parts = ["Relevant past findings for similar code patterns:"]
        for i, r in enumerate(results, 1):
            if r["code_snippet"]:
                snippet = r["code_snippet"][:200]
                parts.append(
                    "\n[{}] Similar code snippet (score: {}):\n```python\n{}\n```".format(
                        i, r["score"], snippet
                    )
                )
            for f in r["findings"][:3]:
                parts.append(
                    "    - [{}] {} ({})".format(
                        f.get("rule_id", "?"), f.get("message", ""), f.get("severity", "")
                    )
                )
        return "\n".join(parts)
