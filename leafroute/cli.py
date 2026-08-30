from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from leafroute.config import LeafRouteConfig
from leafroute.engine import LeafRoute
from leafroute.benchmark import BenchmarkRunner

app = typer.Typer(help="LeafRoute. Compiled hierarchical retrieval for RAG.", no_args_is_help=True)
console = Console()


def _default_output(source: Path) -> Path:
    return source.with_suffix(".leaf")


@app.command()
def compile(
    source: Path = typer.Argument(..., exists=True, readable=True),
    output: Path | None = typer.Option(None, "--output", "-o"),
    offline: bool = typer.Option(False, help="Disable all network-capable behavior."),
) -> None:
    """Compile a document into a portable .leaf artifact."""
    output = output or _default_output(source)
    config = LeafRouteConfig(mode="offline" if offline else "fast", offline=offline)
    engine = LeafRoute.compile(source, output=output, config=config)
    info = engine.inspect()
    engine.close()
    console.print(f"[bold green]Compiled[/bold green] {source} -> {output}")
    console.print_json(json.dumps(info))


@app.command()
def search(
    artifact: Path = typer.Argument(..., exists=True, readable=True),
    query: str = typer.Argument(...),
    mode: str = typer.Option("fast", help="fast, balanced, deep, or offline"),
    top_k: int = typer.Option(5, min=1, max=100),
    trace: bool = typer.Option(False, help="Print execution trace."),
) -> None:
    """Search a compiled artifact and return evidence."""
    config = LeafRouteConfig(mode=mode)  # type: ignore[arg-type]
    engine = LeafRoute.open(artifact, config=config)
    result = engine.search(query, mode=mode, top_k=top_k)  # type: ignore[arg-type]
    table = Table(title=f"Evidence. confidence={result.evidence_pack.confidence:.3f}")
    table.add_column("Score")
    table.add_column("Pages")
    table.add_column("Section")
    table.add_column("Excerpt")
    for item in result.evidence_pack.evidence:
        pages = str(item.page_start) if item.page_start == item.page_end else f"{item.page_start}-{item.page_end}"
        table.add_row(f"{item.score:.3f}", pages, item.section, " ".join(item.text.split())[:240])
    console.print(table)
    if trace:
        console.print_json(result.trace.model_dump_json(indent=2))
    engine.close()


@app.command()
def ask(
    artifact: Path = typer.Argument(..., exists=True, readable=True),
    query: str = typer.Argument(...),
    mode: str = typer.Option("fast"),
) -> None:
    """Produce an extractive answer. Configure a provider in Python for generative answers."""
    engine = LeafRoute.open(artifact, config=LeafRouteConfig(mode=mode))  # type: ignore[arg-type]
    result = engine.ask(query, mode=mode)  # type: ignore[arg-type]
    console.print(result.answer)
    engine.close()


@app.command()
def inspect(artifact: Path = typer.Argument(..., exists=True, readable=True)) -> None:
    """Inspect artifact metadata."""
    engine = LeafRoute.open(artifact)
    console.print_json(json.dumps(engine.inspect()))
    engine.close()


@app.command("tree")
def tree_cmd(
    artifact: Path = typer.Argument(..., exists=True, readable=True),
    max_depth: int = typer.Option(4, min=1, max=20),
) -> None:
    """Render the compiled hierarchy."""
    engine = LeafRoute.open(artifact)
    root_node = engine.tree.root()
    rich_root = Tree(f"[bold]{root_node.title}[/bold] [dim](pp. {root_node.page_start}-{root_node.page_end})[/dim]")

    def add(parent, node_id: str, depth: int) -> None:
        if depth >= max_depth:
            return
        node = engine.tree.nodes[node_id]
        for child_id in node.child_ids:
            child = engine.tree.nodes[child_id]
            branch = parent.add(f"{child.title} [dim](pp. {child.page_start}-{child.page_end}, c={child.structure_confidence:.2f})[/dim]")
            add(branch, child_id, depth + 1)

    add(rich_root, root_node.id, 0)
    console.print(rich_root)
    engine.close()


@app.command()
def explain(
    artifact: Path = typer.Argument(..., exists=True, readable=True),
    query: str = typer.Argument(...),
) -> None:
    """Explain QueryIR, retrieval plan, and route decisions."""
    engine = LeafRoute.open(artifact)
    result = engine.search(query, debug=True)
    console.print("[bold]QueryIR[/bold]")
    console.print_json(result.query_ir.model_dump_json(indent=2))
    console.print("[bold]Retrieval Plan[/bold]")
    console.print_json(result.plan.model_dump_json(indent=2))
    console.print("[bold]Trace[/bold]")
    console.print_json(result.trace.model_dump_json(indent=2))
    engine.close()


@app.command()
def update(
    artifact: Path = typer.Argument(..., exists=True, readable=True),
    source: Path = typer.Argument(..., exists=True, readable=True),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Compile a new document version and report incremental structural reuse."""
    engine = LeafRoute.open(artifact)
    output = output or artifact.with_name(artifact.stem + "-updated.leaf")
    updated, diff = engine.update(source, output=output)
    console.print(f"[bold green]Updated artifact[/bold green] -> {output}")
    console.print_json(diff.model_dump_json(indent=2))
    updated.close()
    engine.close()


@app.command()
def benchmark(
    artifact: Path = typer.Argument(..., exists=True, readable=True),
    cases: Path = typer.Argument(..., exists=True, readable=True),
    output: Path = typer.Option(Path("benchmark-report.json"), "--output", "-o"),
    top_k: int = typer.Option(5, min=1, max=100),
) -> None:
    """Run a retrieval benchmark from a JSON case file."""
    engine = LeafRoute.open(artifact)
    runner = BenchmarkRunner(engine)
    records = runner.run(runner.load_cases(cases), top_k=top_k)
    runner.save_report(output, records)
    console.print_json(json.dumps(runner.summary(records), indent=2))
    console.print(f"[green]Report written to[/green] {output}")
    engine.close()


@app.command()
def serve(
    artifact: Path = typer.Argument(..., exists=True, readable=True),
    host: str = typer.Option("127.0.0.1"),
    port: int = typer.Option(8000),
) -> None:
    """Serve one compiled artifact through the FastAPI application."""
    try:
        import uvicorn
    except ImportError as exc:
        raise typer.BadParameter("Install API extras: pip install leafroute[api]") from exc
    from leafroute.api.app import create_app

    uvicorn.run(create_app(default_artifact=artifact), host=host, port=port)


if __name__ == "__main__":
    app()
