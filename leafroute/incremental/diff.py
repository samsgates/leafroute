from __future__ import annotations

from pydantic import BaseModel, Field

from leafroute.models import TreeIR


class TreeDiff(BaseModel):
    unchanged_nodes: list[str] = Field(default_factory=list)
    changed_nodes: list[str] = Field(default_factory=list)
    added_nodes: list[str] = Field(default_factory=list)
    removed_nodes: list[str] = Field(default_factory=list)
    affected_ancestors: list[str] = Field(default_factory=list)

    @property
    def reuse_ratio(self) -> float:
        total = len(self.unchanged_nodes) + len(self.changed_nodes) + len(self.removed_nodes)
        return len(self.unchanged_nodes) / total if total else 1.0


def diff_trees(old: TreeIR, new: TreeIR) -> TreeDiff:
    old_by_signature = _signature_map(old)
    new_by_signature = _signature_map(new)
    unchanged: list[str] = []
    changed: list[str] = []
    added: list[str] = []
    removed: list[str] = []

    for sig, new_id in new_by_signature.items():
        old_id = old_by_signature.get(sig)
        if not old_id:
            added.append(new_id)
            continue
        if old.nodes[old_id].content_hash == new.nodes[new_id].content_hash:
            unchanged.append(new_id)
        else:
            changed.append(new_id)

    for sig, old_id in old_by_signature.items():
        if sig not in new_by_signature:
            removed.append(old_id)

    affected: set[str] = set()
    for node_id in changed + added:
        current = new.nodes.get(node_id)
        while current and current.parent_id:
            affected.add(current.parent_id)
            current = new.nodes.get(current.parent_id)

    return TreeDiff(
        unchanged_nodes=unchanged,
        changed_nodes=changed,
        added_nodes=added,
        removed_nodes=removed,
        affected_ancestors=sorted(affected),
    )


def _signature_map(tree: TreeIR) -> dict[str, str]:
    # Path + approximate page start is more resilient than generated node ids.
    return {("__root__" if node.id == tree.root_id else " > ".join(node.path[1:]).lower()) + f"@{node.page_start}": node.id for node in tree.nodes.values()}
