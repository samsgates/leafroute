"""Optional example. Requires: pip install 'leafroute[openai]' and OPENAI_API_KEY."""

from leafroute import LeafRoute
from leafroute.config import LeafRouteConfig
from leafroute.providers.openai_provider import OpenAIReasoningProvider

provider = OpenAIReasoningProvider(model="gpt-5-mini")
engine = LeafRoute.open(
    "sample_financial.leaf",
    config=LeafRouteConfig(mode="balanced"),
    reasoning_provider=provider,
)

answer = engine.ask("Why did operating margin decline?", mode="balanced")
print(answer.answer)
engine.close()
