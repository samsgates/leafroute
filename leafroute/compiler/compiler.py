from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from leafroute.version import __version__
from leafroute.compiler.enrich import (
    digest,
    extract_dates,
    extract_entities,
    extract_metrics,
    extract_numeric_facts,
)
from leafroute.compiler.structure import StructureDetector
from leafroute.config import LeafRouteConfig
from leafroute.models import (
    CompiledTable,
    NodeType,
    RoutingSignature,
    TableCell,
    TreeIR,
    TreeNode,
)
from leafroute.parsers import get_parser
from leafroute.utils import content_hash, file_hash, meaningful_terms, normalize_key

REFERENCE_RE = re.compile(r"\b(?:see|refer to|as discussed in)\s+(?:section|note|appendix|table)?\s*([A-Z]?\d+(?:\.\d+)*)", re.I)


class DocumentCompiler:
    def __init__(self, config: LeafRouteConfig | None = None):
        self.config = config or LeafRouteConfig()

    def compile(self, path: str | Path) -> TreeIR:
        parser = get_parser(path)
        parsed = parser.parse(path)
        decisions = StructureDetector(self.config.structure).detect(parsed)
        doc_hash = file_hash(path)
        root_id = "n_root"
        title = parsed.title or Path(path).stem
        nodes: dict[str, TreeNode] = {
            root_id: TreeNode(
                id=root_id,
                title=title,
                normalized_title=normalize_key(title),
                path=[title],
                node_type=NodeType.ROOT,
                page_start=1,
                page_end=max(1, parsed.page_count),
                depth=0,
                structure_confidence=1.0,
            )
        }

        level_stack: list[str] = [root_id]
        current_id = root_id
        node_counter = 0

        def new_node(title_: str, level: int, page: int, confidence: float, source_block_id: str) -> str:
            nonlocal node_counter
            node_counter += 1
            node_id = f"n_{node_counter:06d}"
            while len(level_stack) > level:
                level_stack.pop()
            parent_id = level_stack[-1] if level_stack else root_id
            parent = nodes[parent_id]
            path_parts = parent.path + [title_]
            node_type = NodeType.SECTION if level <= 1 else NodeType.SUBSECTION
            nodes[node_id] = TreeNode(
                id=node_id,
                parent_id=parent_id,
                depth=parent.depth + 1,
                title=title_,
                normalized_title=normalize_key(title_),
                path=path_parts,
                node_type=node_type,
                page_start=page,
                page_end=page,
                structure_confidence=confidence,
                source_block_ids=[source_block_id],
            )
            parent.child_ids.append(node_id)
            if len(level_stack) == level:
                level_stack.append(node_id)
            else:
                level_stack[level] = node_id
            return node_id

        for page in parsed.pages:
            for block in page.blocks:
                decision = decisions.get(block.id)
                if decision and decision.is_heading:
                    current_id = new_node(
                        decision.title,
                        max(1, decision.level),
                        page.number,
                        decision.confidence,
                        block.id,
                    )
                    continue
                node = nodes[current_id]
                node.text = (node.text + "\n\n" + block.text).strip() if node.text else block.text
                node.page_end = max(node.page_end, page.number)
                node.source_block_ids.append(block.id)

        # Flat documents still need a searchable non-root node because the root is used
        # as a routing container. Preserve root text by materializing a fallback leaf.
        if not nodes[root_id].child_ids and nodes[root_id].text.strip():
            node_counter += 1
            fallback_id = f"n_{node_counter:06d}"
            root = nodes[root_id]
            nodes[fallback_id] = TreeNode(
                id=fallback_id, parent_id=root_id, depth=1, title="Document Content",
                normalized_title="document content", path=root.path + ["Document Content"],
                node_type=NodeType.SECTION, page_start=1, page_end=max(1, parsed.page_count),
                text=root.text, structure_confidence=0.5, source_block_ids=list(root.source_block_ids),
            )
            root.child_ids.append(fallback_id)
            root.text = ""
            root.source_block_ids = []

        self._close_page_ranges(nodes, root_id)
        self._split_oversized_leaves(nodes)

        numeric_facts = []
        entity_mentions = []
        date_mentions = []
        compiled_tables: list[CompiledTable] = []
        tables_by_page = defaultdict(list)
        for page in parsed.pages:
            tables_by_page[page.number].extend(page.tables)

        for node in nodes.values():
            keywords, important = digest(node.text)
            entities = extract_entities(node.text, node.page_start, node.id) if self.config.enable_entities else []
            dates = extract_dates(node.text, node.page_start, node.id)
            numbers = extract_numeric_facts(node.text, node.page_start, node.id) if self.config.enable_numeric else []
            metrics = extract_metrics(" ".join([node.title, node.text]))
            node.keywords = keywords
            node.important_sentences = important
            node.entities = sorted({e.name for e in entities})[:30]
            node.dates = sorted({d.raw for d in dates})[:30]
            node.metrics = metrics
            node.content_hash = content_hash(node.title + "\n" + node.text)
            token_count = max(1, len(meaningful_terms(node.text)))
            node.routing_signature = RoutingSignature(
                title_terms=meaningful_terms(node.title)[:20],
                path_terms=meaningful_terms(" ".join(node.path))[:40],
                keywords=keywords,
                entities=node.entities[:20],
                metrics=metrics,
                periods=node.dates[:20],
                numeric_density=min(1.0, len(numbers) / max(1, token_count / 40)),
                table_density=0.0,
                importance=self._importance(node),
            )
            numeric_facts.extend(numbers)
            entity_mentions.extend(entities)
            date_mentions.extend(dates)

        if self.config.enable_tables:
            for page_num, tables in tables_by_page.items():
                owner = self._best_node_for_page(nodes, page_num)
                for table in tables:
                    cells: list[TableCell] = []
                    headers = table.rows[0] if table.rows else []
                    for r_idx, row in enumerate(table.rows):
                        row_header = row[0] if row else None
                        for c_idx, value in enumerate(row):
                            cells.append(
                                TableCell(
                                    row=r_idx,
                                    column=c_idx,
                                    row_header=row_header if c_idx > 0 else None,
                                    column_header=headers[c_idx] if r_idx > 0 and c_idx < len(headers) else None,
                                    value=value,
                                )
                            )
                    compiled_tables.append(
                        CompiledTable(id=table.id, node_id=owner.id, page=page_num, cells=cells, raw_rows=table.rows)
                    )
                    owner.routing_signature.table_density = min(1.0, owner.routing_signature.table_density + 0.2)

        references = self._compile_references(nodes)
        self._subtree_hashes(nodes, root_id)

        return TreeIR(
            compiler_version=__version__,
            document_id=doc_hash,
            title=title,
            source_type=parsed.source_type,
            page_count=parsed.page_count,
            root_id=root_id,
            nodes=nodes,
            numeric_facts=numeric_facts,
            entity_mentions=entity_mentions,
            date_mentions=date_mentions,
            tables=compiled_tables,
            references=references,
            metadata={
                **parsed.metadata,
                "source_path": str(path),
                "bookmarks": len(parsed.bookmarks),
                "node_count": len(nodes),
            },
        )

    def _split_oversized_leaves(self, nodes: dict[str, TreeNode]) -> None:
        max_chars = self.config.structure.max_leaf_chars
        additions: list[TreeNode] = []
        for node in list(nodes.values()):
            if node.child_ids or len(node.text) <= max_chars:
                continue
            chunks = self._paragraph_chunks(node.text, max_chars)
            if len(chunks) <= 1:
                continue
            original = node.text
            node.text = ""
            for idx, chunk in enumerate(chunks, start=1):
                child_id = f"{node.id}_c{idx}"
                child = TreeNode(
                    id=child_id,
                    parent_id=node.id,
                    depth=node.depth + 1,
                    title=f"{node.title} [{idx}]",
                    normalized_title=node.normalized_title,
                    path=node.path + [f"Part {idx}"],
                    node_type=NodeType.PARAGRAPH,
                    page_start=node.page_start,
                    page_end=node.page_end,
                    text=chunk,
                    structure_confidence=node.structure_confidence,
                )
                additions.append(child)
                node.child_ids.append(child_id)
            if not additions:
                node.text = original
        for child in additions:
            nodes[child.id] = child

    @staticmethod
    def _paragraph_chunks(text: str, max_chars: int) -> list[str]:
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks: list[str] = []
        current = ""
        for paragraph in paragraphs:
            if current and len(current) + len(paragraph) + 2 > max_chars:
                chunks.append(current)
                current = paragraph
            else:
                current = (current + "\n\n" + paragraph).strip()
        if current:
            chunks.append(current)
        return chunks

    @staticmethod
    def _close_page_ranges(nodes: dict[str, TreeNode], root_id: str) -> tuple[int, int]:
        def walk(node_id: str) -> tuple[int, int]:
            node = nodes[node_id]
            low, high = node.page_start, node.page_end
            for child_id in node.child_ids:
                c_low, c_high = walk(child_id)
                low = min(low, c_low)
                high = max(high, c_high)
            node.page_start, node.page_end = low, high
            return low, high
        return walk(root_id)

    @staticmethod
    def _importance(node: TreeNode) -> float:
        score = 0.35
        if node.depth <= 2:
            score += 0.20
        if node.metrics:
            score += 0.15
        if node.entities:
            score += 0.10
        if len(node.text) > 500:
            score += 0.10
        return min(1.0, score)

    @staticmethod
    def _best_node_for_page(nodes: dict[str, TreeNode], page: int) -> TreeNode:
        candidates = [n for n in nodes.values() if n.page_start <= page <= n.page_end]
        if not candidates:
            return nodes["n_root"]
        return max(candidates, key=lambda n: (n.depth, -max(1, n.page_end - n.page_start)))

    @staticmethod
    def _compile_references(nodes: dict[str, TreeNode]) -> dict[str, list[str]]:
        title_map = {normalize_key(n.title): n.id for n in nodes.values()}
        refs: dict[str, list[str]] = defaultdict(list)
        for node in nodes.values():
            for match in REFERENCE_RE.finditer(node.text):
                key = normalize_key(match.group(1))
                for title, target in title_map.items():
                    if title.startswith(key + " ") or title == key or title.endswith(" " + key):
                        refs[node.id].append(target)
                        break
        return {k: sorted(set(v)) for k, v in refs.items()}

    @staticmethod
    def _subtree_hashes(nodes: dict[str, TreeNode], root_id: str) -> str:
        def walk(node_id: str) -> str:
            node = nodes[node_id]
            child_hashes = [walk(child_id) for child_id in node.child_ids]
            node.subtree_hash = content_hash(node.content_hash + "|" + "|".join(child_hashes))
            return node.subtree_hash
        return walk(root_id)
