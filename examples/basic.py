from leafroute import LeafRoute
from leafroute.config import LeafRouteConfig

engine = LeafRoute.compile(
    "sample_financial.md",
    output="sample_financial.leaf",
    config=LeafRouteConfig(domain_pack="finance"),
)

result = engine.search("What was revenue in FY2025?", mode="fast")
print("Confidence:", result.evidence_pack.confidence)
print("Retrieval LLM calls:", result.trace.llm_calls)

for evidence in result.evidence_pack.evidence:
    print(evidence.section, evidence.score)
    print(evidence.text)

engine.close()
