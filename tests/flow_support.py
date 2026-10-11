"""Données Flowchart synthétiques pour les tests ; aucune donnée réelle.

SIMPLE reprend examples/simple-flow.flow.json : six nœuds (un début, une
décision, une fin), six transitions dont trois libellées.
"""

import copy
import json
from pathlib import Path
from typing import Any

from forge_design_flowchart import FlowDocument

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/simple-flow.flow.json"
PATH = "mvc/flowchart/simple.flow.json"


def simple() -> dict[str, Any]:
    """Copie neuve du document exemple, modifiable par le test."""
    return copy.deepcopy(_SIMPLE)


def document(data: dict[str, Any] | None = None) -> FlowDocument:
    return FlowDocument.model_validate_json(
        json.dumps(simple() if data is None else data)
    )


def node(
    identity: str, kind: str = "step", label: str = "Étape", x: int = 0, y: int = 0
) -> dict[str, Any]:
    return {"id": identity, "kind": kind, "label": label, "x": x, "y": y}


def edge(
    identity: str, source: str, target: str, label: str | None = None
) -> dict[str, Any]:
    data: dict[str, Any] = {"id": identity, "source": source, "target": target}
    if label is not None:
        data["label"] = label
    return data


def flow(
    nodes: list[dict[str, Any]], edges: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    return {"format_version": "0.1", "nodes": nodes, "edges": edges or []}


def to_bytes(data: object) -> bytes:
    return json.dumps(data, ensure_ascii=False).encode()


def make_project(root: Path) -> Path:
    """Signatures Forge minimales ; l'espace mvc/flowchart est créé explicitement."""
    root.mkdir(parents=True)
    for name in ("app.py", "config.py", "bootstrap.py"):
        (root / name).write_text("raise AssertionError('never execute')")
    (root / "mvc/routes").mkdir(parents=True)
    (root / "mvc/views").mkdir(parents=True)
    (root / "mvc/flowchart").mkdir(parents=True)
    (root / "requirements.txt").write_text("forge-mvc==1.0.0rc9")
    return root.resolve()


def history(root: Path) -> list[dict[str, Any]]:
    log = root / ".forge-design/history.jsonl"
    return (
        [json.loads(line) for line in log.read_text().splitlines()]
        if log.exists()
        else []
    )


_SIMPLE: dict[str, Any] = json.loads(EXAMPLE.read_text(encoding="utf-8"))
