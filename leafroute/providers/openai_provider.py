from __future__ import annotations

import json

from leafroute.models import EvidencePack, QueryIR, TreeIR
from leafroute.providers.base import ReasoningProvider


class OpenAIReasoningProvider(ReasoningProvider):
    """Optional provider using the OpenAI Python SDK.

    The core LeafRoute package never imports the SDK unless this adapter is constructed.
    """

    def __init__(self, model: str = "gpt-5-mini", api_key: str | None = None):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Install LeafRoute with `pip install leafroute[openai]`") from exc
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def verify(self, query: QueryIR, candidate_node_ids: list[str], tree: TreeIR) -> list[str]:
        candidates = []
        for node_id in candidate_node_ids[:8]:
            node = tree.nodes[node_id]
            candidates.append({
                "id": node.id,
                "path": " > ".join(node.path),
                "text": node.text[:2500],
            })
        prompt = (
            "Select and rank only the node ids that contain evidence for the question. "
            "Return strict JSON as {\"node_ids\":[...]}. Do not answer the question.\n\n"
            f"Question: {query.query}\nCandidates:\n{json.dumps(candidates, ensure_ascii=False)}"
        )
        response = self.client.responses.create(model=self.model, input=prompt)
        text = response.output_text.strip()
        try:
            payload = json.loads(text)
            ordered = [x for x in payload.get("node_ids", []) if x in candidate_node_ids]
            return ordered or candidate_node_ids
        except Exception:
            return candidate_node_ids

    def answer(self, query: str, evidence: EvidencePack) -> str:
        context = [
            {
                "section": item.section,
                "pages": [item.page_start, item.page_end],
                "text": item.text,
            }
            for item in evidence.evidence
        ]
        prompt = (
            "Answer the question using only the provided evidence. If the evidence is insufficient, say so. "
            "Cite page numbers inline like [p. 12] or [pp. 12-13].\n\n"
            f"Question: {query}\nEvidence:\n{json.dumps(context, ensure_ascii=False)}"
        )
        response = self.client.responses.create(model=self.model, input=prompt)
        return response.output_text.strip()
