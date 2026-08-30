from leafroute import LeafRoute


def test_incremental_diff(sample_md, tmp_path):
    first = LeafRoute.compile(sample_md)
    changed = tmp_path / "changed.md"
    text = sample_md.read_text(encoding="utf-8").replace("$120 million", "$125 million")
    changed.write_text(text, encoding="utf-8")
    updated, diff = first.update(changed)
    assert diff.changed_nodes or diff.added_nodes or diff.removed_nodes
    assert diff.unchanged_nodes
    assert 0 < diff.reuse_ratio < 1
    first.close()
    updated.close()
