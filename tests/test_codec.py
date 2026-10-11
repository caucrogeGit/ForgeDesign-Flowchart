"""Codec Flowchart V0.1 : décodage strict, encodage canonique, diagnostics bornés,
validation de domaine (au plus un début)."""

import json
from pathlib import Path
from typing import Any

import pytest
from flow_support import EXAMPLE, PATH, document, edge, flow, make_project, node, simple
from forge_design.modules import activate_modules
from forge_design.modules.host import ModuleHost
from forge_design.specialized import (
    MAX_SPECIALIZED_ISSUES,
    SpecializedFormatError,
    SpecializedIssue,
)

from forge_design_flowchart import FLOWCHART_RESOURCE_TYPE, FlowCodec, FlowDocument
from forge_design_flowchart.limits import MAX_FLOWCHART_RESOURCE_BYTES

CODEC = FlowCodec()


def encoded(data: dict[str, Any]) -> bytes:
    return json.dumps(data, ensure_ascii=False).encode()


def issues(data: bytes) -> tuple[SpecializedIssue, ...]:
    with pytest.raises(SpecializedFormatError) as caught:
        CODEC.decode(data)
    return caught.value.issues


def one(data: dict[str, Any]) -> tuple[str, tuple[str | int, ...]]:
    (issue,) = issues(encoded(data))
    assert issue.severity == "error" and issue.level == "structure"
    return issue.code, issue.location


def test_decode_the_example() -> None:
    value = CODEC.decode(EXAMPLE.read_bytes())
    assert isinstance(value, FlowDocument)
    assert value == document()


def test_encode_is_canonical_and_round_trips() -> None:
    raw = EXAMPLE.read_bytes()
    value = CODEC.decode(raw)
    assert CODEC.encode(value) == raw
    assert CODEC.decode(CODEC.encode(value)) == value
    # Indentation de 2, UTF-8 sans échappement, fin de ligne, ordre du modèle.
    text = raw.decode()
    assert text.endswith("}\n") and '"label": "Début"' in text
    assert list(json.loads(text)) == ["format_version", "nodes", "edges"]
    assert list(json.loads(text)["nodes"][0]) == ["id", "kind", "label", "x", "y"]
    # Un libellé absent est omis, jamais écrit null ni vide.
    assert json.loads(text)["edges"][0] == {
        "id": "t1",
        "source": "debut",
        "target": "verifier",
    }


def test_compact_or_reordered_input_is_normalised_on_encode() -> None:
    data = simple()
    data["nodes"][0] = dict(reversed(list(data["nodes"][0].items())))
    value = CODEC.decode(json.dumps(data, separators=(",", ":")).encode())
    assert CODEC.encode(value) == EXAMPLE.read_bytes()


def test_detect_version() -> None:
    assert CODEC.detect_version(EXAMPLE.read_bytes()) == "0.1"
    assert CODEC.detect_version(b'{"format_version": "9.9"}') == "9.9"
    for raw in (
        b"",
        b"[]",
        b'{"format_version": 1}',
        b"\xff",
        b'{"format_version": "0.1", "format_version": "0.1"}',
        b"{" * 100_000,
    ):
        assert CODEC.detect_version(raw) is None


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"\xff\xfe",
        b"{",
        b'{"format_version": "0.1", "nodes": [], "edges": []} x',
        b'{"format_version": "0.1", "nodes": [], "nodes": [], "edges": []}',
        b'{"format_version": "0.1", "nodes": [{"x": NaN}], "edges": []}',
        b'{"format_version": "0.1", "nodes": [{"x": Infinity}], "edges": []}',
        b"[" * 100_000,
    ],
)
def test_strict_json_errors(raw: bytes) -> None:
    (issue,) = issues(raw)
    assert issue.code == "flowchart.json-invalid"
    assert issue.message.startswith("JSON invalide : ")


def test_structure_diagnostics_are_located() -> None:
    data = simple()
    data["nodes"][1]["shape"] = "x"
    assert one(data) == ("flowchart.validation-error", ("nodes", 1, "shape"))
    data = simple()
    data["nodes"][2]["kind"] = "loop"
    assert one(data) == ("flowchart.validation-error", ("nodes", 2, "kind"))
    data = simple()
    data["nodes"][0]["id"] = "1x"
    assert one(data) == ("flowchart.identity-invalid", ("nodes", 0, "id"))
    data = simple()
    data["edges"][3]["source"] = "a b"
    assert one(data) == ("flowchart.identity-invalid", ("edges", 3, "source"))
    data = simple()
    data["edges"][1]["id"] = "debut"
    assert one(data) == ("flowchart.identity-duplicate", ("edges", 1, "id"))
    data = simple()
    data["edges"][4]["target"] = "ghost"
    code, location = one(data)
    assert (code, location) == ("flowchart.endpoint-unknown", ("edges", 4, "target"))
    data = simple()
    data["edges"][2]["source"] = data["edges"][2]["target"]
    assert one(data) == ("flowchart.self-loop", ("edges", 2, "target"))
    data = simple()
    data["nodes"][3]["label"] = "a\nb"
    assert one(data) == ("flowchart.label-invalid", ("nodes", 3, "label"))
    data = simple()
    data["edges"][2]["label"] = ""
    assert one(data) == ("flowchart.label-invalid", ("edges", 2, "label"))
    data = simple()
    data["nodes"][0]["x"] = 100_001
    assert one(data) == ("flowchart.limit-exceeded", ("nodes", 0, "x"))
    data = simple()
    data["nodes"][0]["y"] = -100_001
    assert one(data) == ("flowchart.limit-exceeded", ("nodes", 0, "y"))
    data = simple()
    data["nodes"][0]["id"] = "x" * 65
    assert one(data) == ("flowchart.limit-exceeded", ("nodes", 0, "id"))
    data = simple()
    data["nodes"] = [node(f"n{i}") for i in range(501)]
    data["edges"] = []
    assert one(data) == ("flowchart.limit-exceeded", ("nodes",))
    data = simple()
    del data["edges"]
    assert one(data) == ("flowchart.validation-error", ("edges",))


def test_messages_name_the_problem() -> None:
    data = simple()
    data["edges"][4]["target"] = "ghost"
    (issue,) = issues(encoded(data))
    assert issue.message == (
        "Extrémité inconnue : Edge t5 target ghost is not a node of the document"
    )
    data = simple()
    data["nodes"][3]["label"] = "a\nb"
    (issue,) = issues(encoded(data))
    assert issue.message == (
        "Libellé invalide : Le libellé ne peut contenir ni retour à la ligne ni "
        "caractère de contrôle."
    )


def test_many_errors_are_bounded() -> None:
    data = flow([node(f"n{i}", label="") for i in range(MAX_SPECIALIZED_ISSUES + 50)])
    found = issues(encoded(data))
    assert len(found) == MAX_SPECIALIZED_ISSUES + 1
    assert {issue.code for issue in found} == {"flowchart.label-invalid"}


def test_validation_of_the_example_is_clean() -> None:
    result = CODEC.validate(document())
    assert result.issues == () and not result.truncated


def test_zero_start_and_zero_end_are_valid_in_construction() -> None:
    assert CODEC.validate(document(flow([]))).issues == ()
    assert CODEC.validate(document(flow([node("a"), node("b")]))).issues == ()
    many_ends = flow([node("s", "start"), node("e1", "end"), node("e2", "end")])
    assert CODEC.validate(document(many_ends)).issues == ()


def test_at_most_one_start() -> None:
    data = flow([node("a", "start"), node("b"), node("c", "start"), node("d", "start")])
    result = CODEC.validate(document(data))
    assert [(i.code, i.level, i.severity, i.location) for i in result.issues] == [
        ("flowchart.start-duplicate", "graph", "error", ("nodes", 2)),
        ("flowchart.start-duplicate", "graph", "error", ("nodes", 3)),
    ]
    assert result.issues[0].message == (
        "Nœud de début supplémentaire « c » : « a » est déjà le début."
    )
    # Le niveau « graph » bloque l'écriture comme la structure.
    assert FLOWCHART_RESOURCE_TYPE.blocking_validation_levels == {"structure", "graph"}


def test_validate_rechecks_the_format_of_an_unchecked_document() -> None:
    broken = FlowDocument.model_construct(
        format_version="0.1",
        nodes=(document().nodes[0].model_copy(update={"label": " x"}),),
        edges=(),
    )
    result = CODEC.validate(broken)
    assert [(i.code, i.location) for i in result.issues] == [
        ("flowchart.label-invalid", ("nodes", 0, "label"))
    ]
    unserialisable = FlowDocument.model_construct(
        format_version="0.1", nodes=(object(),), edges=()
    )
    (issue,) = CODEC.validate(unserialisable).issues
    assert issue.code == "flowchart.validation-error"


def test_resource_size_is_bounded_by_the_type(tmp_path: Path) -> None:
    assert FLOWCHART_RESOURCE_TYPE.max_size == MAX_FLOWCHART_RESOURCE_BYTES
    root = make_project(tmp_path / "project")
    big = simple()
    big["nodes"][0]["label"] = "x" * 200
    raw = json.dumps(big, indent=1).encode()
    padding = MAX_FLOWCHART_RESOURCE_BYTES - len(raw) + 1
    (root / PATH).write_bytes(raw[:-1] + b" " * padding + raw[-1:])
    assert (root / PATH).stat().st_size == MAX_FLOWCHART_RESOURCE_BYTES + 1
    host = ModuleHost(activate_modules(["forge_design_flowchart"]))
    view = host.read_resource("flowchart", "flowchart", root, PATH)
    assert view.read is not None and view.read.resource is None
    assert view.read.error is not None and view.scene is None
    # Juste au plafond : lu normalement.
    (root / PATH).write_bytes(raw[:-1] + b" " * (padding - 1) + raw[-1:])
    view = host.read_resource("flowchart", "flowchart", root, PATH)
    assert view.read is not None and view.read.error is None
    assert view.scene is not None


def test_decode_never_returns_partial_documents() -> None:
    data = simple()
    data["edges"].append(edge("t7", "fin", "fin"))
    with pytest.raises(SpecializedFormatError):
        CODEC.decode(encoded(data))
