from __future__ import annotations

from contextlib import asynccontextmanager
import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from leafroute.config import LeafRouteConfig
from leafroute.engine import LeafRoute
from leafroute.api.studio import STUDIO_HTML


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    mode: Literal["fast", "balanced", "deep", "offline"] = "fast"
    top_k: int = Field(5, ge=1, le=100)
    include_trace: bool = True


class AskRequest(SearchRequest):
    pass


def create_app(default_artifact: str | Path | None = None) -> FastAPI:
    state: dict[str, LeafRoute] = {}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if default_artifact:
            state["engine"] = LeafRoute.open(default_artifact)
        yield
        if "engine" in state:
            state["engine"].close()

    app = FastAPI(
        title="LeafRoute API",
        version="0.1.0",
        description="Compiled hierarchical retrieval runtime",
        lifespan=lifespan,
    )

    def engine() -> LeafRoute:
        if "engine" not in state:
            raise HTTPException(status_code=503, detail="No artifact is loaded")
        return state["engine"]


    @app.get("/studio", response_class=HTMLResponse)
    def studio():
        return STUDIO_HTML

    @app.get("/health")
    def health():
        return {"status": "ok", "loaded": "engine" in state}

    @app.get("/v1/document")
    def document_info():
        return engine().inspect()

    @app.get("/v1/document/tree")
    def document_tree():
        return engine().tree

    @app.post("/v1/search")
    def search(request: SearchRequest):
        e = engine()
        e.config = LeafRouteConfig(mode=request.mode)
        result = e.search(request.query, mode=request.mode, top_k=request.top_k)
        payload = result.model_dump(mode="json")
        if not request.include_trace:
            payload.pop("trace", None)
        return payload

    @app.post("/v1/ask")
    def ask(request: AskRequest):
        e = engine()
        e.config = LeafRouteConfig(mode=request.mode)
        return e.ask(request.query, mode=request.mode, top_k=request.top_k).model_dump(mode="json")

    return app


app = create_app(os.getenv("LEAFROUTE_ARTIFACT"))
