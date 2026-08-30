from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Iterable

try:
    import zstandard as zstd
except ImportError:
    zstd = None
import zlib

from leafroute.errors import ArtifactVersionError
from leafroute.models import TreeIR
from leafroute.utils import meaningful_terms, normalize_key

SCHEMA_VERSION = "1"

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
CREATE TABLE IF NOT EXISTS manifest (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS blobs (
  key TEXT PRIMARY KEY,
  value BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS nodes (
  node_id TEXT PRIMARY KEY,
  parent_id TEXT,
  depth INTEGER NOT NULL,
  title TEXT NOT NULL,
  normalized_title TEXT NOT NULL,
  path TEXT NOT NULL,
  page_start INTEGER NOT NULL,
  page_end INTEGER NOT NULL,
  node_type TEXT NOT NULL,
  keywords TEXT NOT NULL,
  entities TEXT NOT NULL,
  dates TEXT NOT NULL,
  metrics TEXT NOT NULL,
  importance REAL NOT NULL,
  content_hash TEXT NOT NULL,
  subtree_hash TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(
  node_id UNINDEXED,
  title,
  path,
  keywords,
  entities,
  metrics,
  text,
  tokenize='unicode61 remove_diacritics 2'
);
CREATE TABLE IF NOT EXISTS entities (
  normalized TEXT NOT NULL,
  name TEXT NOT NULL,
  node_id TEXT,
  page INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_entities_normalized ON entities(normalized);
CREATE INDEX IF NOT EXISTS idx_entities_node ON entities(node_id);
CREATE TABLE IF NOT EXISTS numeric_facts (
  node_id TEXT,
  page INTEGER NOT NULL,
  raw TEXT NOT NULL,
  value REAL,
  unit TEXT,
  label TEXT,
  period TEXT,
  context TEXT
);
CREATE INDEX IF NOT EXISTS idx_numeric_label ON numeric_facts(label);
CREATE INDEX IF NOT EXISTS idx_numeric_node ON numeric_facts(node_id);
CREATE TABLE IF NOT EXISTS dates (
  normalized TEXT,
  raw TEXT NOT NULL,
  node_id TEXT,
  page INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dates_normalized ON dates(normalized);
CREATE TABLE IF NOT EXISTS tables_data (
  table_id TEXT PRIMARY KEY,
  node_id TEXT NOT NULL,
  page INTEGER NOT NULL,
  payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS route_cache (
  document_id TEXT NOT NULL,
  root_hash TEXT NOT NULL,
  query_signature TEXT NOT NULL,
  node_ids TEXT NOT NULL,
  hit_count INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(document_id, root_hash, query_signature)
);
"""


class SQLiteIndex:
    def __init__(self, connection: sqlite3.Connection, path: Path | None = None):
        self.connection = connection
        self.connection.row_factory = sqlite3.Row
        self.path = path
        self._lock = threading.RLock()  # serializes cache writes across API worker threads

    @classmethod
    def memory(cls, tree: TreeIR) -> "SQLiteIndex":
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        idx = cls(conn)
        idx.initialize(tree)
        return idx

    @classmethod
    def create(cls, path: str | Path, tree: TreeIR, overwrite: bool = True) -> "SQLiteIndex":
        target = Path(path)
        if target.exists() and overwrite:
            target.unlink()
        target.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(target, check_same_thread=False)
        idx = cls(conn, target)
        idx.initialize(tree)
        return idx

    @classmethod
    def open(cls, path: str | Path) -> "SQLiteIndex":
        target = Path(path)
        conn = sqlite3.connect(target, check_same_thread=False)
        idx = cls(conn, target)
        row = conn.execute("SELECT value FROM manifest WHERE key='schema_version'").fetchone()
        if not row or row[0] != SCHEMA_VERSION:
            raise ArtifactVersionError(f"Unsupported LeafRoute artifact schema: {row[0] if row else 'missing'}")
        return idx

    def initialize(self, tree: TreeIR) -> None:
        self.connection.executescript(SCHEMA)
        self.connection.execute("DELETE FROM manifest")
        self.connection.execute("DELETE FROM blobs")
        self.connection.execute("DELETE FROM nodes")
        self.connection.execute("DELETE FROM nodes_fts")
        self.connection.execute("DELETE FROM entities")
        self.connection.execute("DELETE FROM numeric_facts")
        self.connection.execute("DELETE FROM dates")
        self.connection.execute("DELETE FROM tables_data")

        manifest = {
            "schema_version": SCHEMA_VERSION,
            "format_version": tree.format_version,
            "compiler_version": tree.compiler_version,
            "document_id": tree.document_id,
            "title": tree.title,
            "root_id": tree.root_id,
            "root_hash": tree.nodes[tree.root_id].subtree_hash,
        }
        self.connection.executemany(
            "INSERT INTO manifest(key,value) VALUES(?,?)",
            list(manifest.items()),
        )

        payload = tree.model_dump_json().encode("utf-8")
        compressed = zstd.ZstdCompressor(level=6).compress(payload) if zstd is not None else zlib.compress(payload, level=6)
        self.connection.execute("INSERT INTO blobs(key,value) VALUES('treeir',?)", (compressed,))

        for node in tree.nodes.values():
            path = " > ".join(node.path)
            self.connection.execute(
                """INSERT INTO nodes(
                    node_id,parent_id,depth,title,normalized_title,path,page_start,page_end,node_type,
                    keywords,entities,dates,metrics,importance,content_hash,subtree_hash
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    node.id, node.parent_id, node.depth, node.title, node.normalized_title, path,
                    node.page_start, node.page_end, node.node_type.value,
                    json.dumps(node.keywords), json.dumps(node.entities), json.dumps(node.dates),
                    json.dumps(node.metrics), node.routing_signature.importance,
                    node.content_hash, node.subtree_hash,
                ),
            )
            self.connection.execute(
                "INSERT INTO nodes_fts(node_id,title,path,keywords,entities,metrics,text) VALUES(?,?,?,?,?,?,?)",
                (
                    node.id,
                    node.title,
                    path,
                    " ".join(node.keywords),
                    " ".join(node.entities),
                    " ".join(node.metrics),
                    node.text,
                ),
            )

        self.connection.executemany(
            "INSERT INTO entities(normalized,name,node_id,page) VALUES(?,?,?,?)",
            [(e.normalized, e.name, e.node_id, e.page) for e in tree.entity_mentions],
        )
        self.connection.executemany(
            "INSERT INTO numeric_facts(node_id,page,raw,value,unit,label,period,context) VALUES(?,?,?,?,?,?,?,?)",
            [(n.node_id, n.page, n.raw, n.value, n.unit, n.label, n.period, n.context) for n in tree.numeric_facts],
        )
        self.connection.executemany(
            "INSERT INTO dates(normalized,raw,node_id,page) VALUES(?,?,?,?)",
            [(d.normalized, d.raw, d.node_id, d.page) for d in tree.date_mentions],
        )
        for table in tree.tables:
            self.connection.execute(
                "INSERT INTO tables_data(table_id,node_id,page,payload) VALUES(?,?,?,?)",
                (table.id, table.node_id, table.page, table.model_dump_json()),
            )
        self.connection.commit()

    def load_tree(self) -> TreeIR:
        row = self.connection.execute("SELECT value FROM blobs WHERE key='treeir'").fetchone()
        if not row:
            raise ArtifactVersionError("LeafRoute artifact is missing TreeIR")
        payload = zstd.ZstdDecompressor().decompress(row[0]) if zstd is not None else zlib.decompress(row[0])
        return TreeIR.model_validate_json(payload)

    def lexical_search(self, query: str, limit: int = 50) -> list[tuple[str, float]]:
        terms = meaningful_terms(query)
        if not terms:
            return []
        expression = " OR ".join(f'"{t.replace(chr(34), "")}"' for t in terms[:16])
        try:
            rows = self.connection.execute(
                "SELECT node_id, bm25(nodes_fts, 0.0, 4.0, 2.0, 2.0, 2.0, 2.0, 1.0) AS rank FROM nodes_fts WHERE nodes_fts MATCH ? ORDER BY rank LIMIT ?",
                (expression, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        if not rows:
            return []
        raw = [(r["node_id"], float(r["rank"])) for r in rows]
        min_rank = min(score for _, score in raw)
        max_rank = max(score for _, score in raw)
        spread = max(1e-9, max_rank - min_rank)
        # FTS bm25 is lower-is-better and often negative. Normalize to 0..1, best=1.
        return [(node_id, 1.0 - ((score - min_rank) / spread) if spread else 1.0) for node_id, score in raw]

    def entity_search(self, entities: Iterable[str]) -> dict[str, float]:
        scores: dict[str, float] = {}
        for entity in entities:
            key = normalize_key(entity)
            rows = self.connection.execute(
                "SELECT node_id FROM entities WHERE normalized LIKE ? LIMIT 100",
                (f"%{key}%",),
            ).fetchall()
            for row in rows:
                if row["node_id"]:
                    scores[row["node_id"]] = scores.get(row["node_id"], 0.0) + 1.0
        return scores

    def date_search(self, dates: Iterable[str]) -> dict[str, float]:
        scores: dict[str, float] = {}
        for date in dates:
            key = normalize_key(date)
            rows = self.connection.execute(
                "SELECT node_id FROM dates WHERE normalized LIKE ? LIMIT 100",
                (f"%{key}%",),
            ).fetchall()
            for row in rows:
                if row["node_id"]:
                    scores[row["node_id"]] = scores.get(row["node_id"], 0.0) + 1.0
        return scores

    def numeric_label_search(self, metrics: Iterable[str]) -> dict[str, float]:
        scores: dict[str, float] = {}
        for metric in metrics:
            key = normalize_key(metric)
            rows = self.connection.execute(
                "SELECT node_id FROM numeric_facts WHERE lower(label) LIKE ? OR lower(context) LIKE ? LIMIT 200",
                (f"%{key}%", f"%{key}%"),
            ).fetchall()
            for row in rows:
                if row["node_id"]:
                    scores[row["node_id"]] = scores.get(row["node_id"], 0.0) + 1.0
        return scores

    def table_search(self, query: str, limit: int = 100) -> dict[str, float]:
        terms = meaningful_terms(query)
        if not terms:
            return {}
        scores: dict[str, float] = {}
        for term in terms[:12]:
            rows = self.connection.execute(
                "SELECT node_id FROM tables_data WHERE lower(payload) LIKE ? LIMIT ?",
                (f"%{term.lower()}%", limit),
            ).fetchall()
            for row in rows:
                scores[row["node_id"]] = scores.get(row["node_id"], 0.0) + 1.0
        peak = max(scores.values(), default=1.0)
        return {node_id: value / peak for node_id, value in scores.items()}

    def cache_get(self, document_id: str, root_hash: str, signature: str) -> list[str] | None:
        with self._lock:
            row = self.connection.execute(
                "SELECT node_ids FROM route_cache WHERE document_id=? AND root_hash=? AND query_signature=?",
                (document_id, root_hash, signature),
            ).fetchone()
            if not row:
                return None
            self.connection.execute(
                "UPDATE route_cache SET hit_count=hit_count+1, updated_at=CURRENT_TIMESTAMP WHERE document_id=? AND root_hash=? AND query_signature=?",
                (document_id, root_hash, signature),
            )
            self.connection.commit()
            return json.loads(row["node_ids"])

    def cache_put(self, document_id: str, root_hash: str, signature: str, node_ids: list[str]) -> None:
        with self._lock:
            self.connection.execute(
                """INSERT INTO route_cache(document_id,root_hash,query_signature,node_ids)
                   VALUES(?,?,?,?)
                   ON CONFLICT(document_id,root_hash,query_signature)
                   DO UPDATE SET node_ids=excluded.node_ids, updated_at=CURRENT_TIMESTAMP""",
                (document_id, root_hash, signature, json.dumps(node_ids)),
            )
            self.connection.commit()

    def close(self) -> None:
        self.connection.close()
