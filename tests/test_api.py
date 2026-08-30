from fastapi.testclient import TestClient

from leafroute import LeafRoute
from leafroute.api.app import create_app


def test_api(sample_md, tmp_path):
    artifact = tmp_path / "api.leaf"
    engine = LeafRoute.compile(sample_md, output=artifact)
    engine.close()
    with TestClient(create_app(artifact)) as client:
        assert client.get("/health").status_code == 200
        response = client.post("/v1/search", json={"query": "What was revenue in FY2025?", "top_k": 3})
        assert response.status_code == 200
        data = response.json()
        assert data["evidence_pack"]["evidence"]
        assert client.get("/studio").status_code == 200
