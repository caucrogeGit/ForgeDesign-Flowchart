"""Modèle Flowchart V0.1 : forme stricte, identités, libellés, coordonnées, arêtes."""

import json
from typing import Any

import pytest
from flow_support import document, edge, flow, node, simple
from pydantic import ValidationError

from forge_design_flowchart import FlowDocument, FlowEdge, FlowNode, new_flow_document
from forge_design_flowchart.limits import (
    MAX_FLOWCHART_COORDINATE,
    MAX_FLOWCHART_EDGES,
    MAX_FLOWCHART_ID_CHARS,
    MAX_FLOWCHART_LABEL_CHARS,
    MAX_FLOWCHART_NODES,
)
from forge_design_flowchart.models import NODE_KINDS, label_problem


def parse(data: dict[str, Any]) -> FlowDocument:
    return FlowDocument.model_validate_json(json.dumps(data))


def refused(data: dict[str, Any]) -> list[str]:
    with pytest.raises(ValidationError) as caught:
        parse(data)
    return [error["type"] for error in caught.value.errors()]


def test_minimal_document_is_valid_and_empty() -> None:
    empty = new_flow_document()
    assert empty == parse(flow([]))
    assert empty.format_version == "0.1"
    assert empty.nodes == () and empty.edges == ()


def test_example_document() -> None:
    value = document()
    assert [n.kind for n in value.nodes] == [
        "start",
        "step",
        "decision",
        "step",
        "step",
        "end",
    ]
    assert [e.label for e in value.edges] == [None, None, "Oui", "Non", "suite", None]
    assert value.nodes[2] == FlowNode(
        id="valide", kind="decision", label="Valeur valide ?", x=0, y=200
    )


@pytest.mark.parametrize("kind", NODE_KINDS)
def test_each_node_kind_is_accepted(kind: str) -> None:
    assert parse(flow([node("a", kind)])).nodes[0].kind == kind


@pytest.mark.parametrize("kind", ["Start", "process", "", "decision ", 1, None])
def test_unknown_node_kind_is_refused(kind: object) -> None:
    data = flow([node("a")])
    data["nodes"][0]["kind"] = kind
    assert refused(data)


@pytest.mark.parametrize(
    "identity",
    ["a", "A", "z9", "node_1", "n-2", "x" * MAX_FLOWCHART_ID_CHARS],
)
def test_valid_identities(identity: str) -> None:
    data = flow([node(identity), node("other")], [edge("e", identity, "other")])
    assert parse(data).nodes[0].id == identity


@pytest.mark.parametrize(
    "identity",
    [
        "",
        "1a",
        "_a",
        "-a",
        "a b",
        "a.b",
        "é",
        "a/b",
        "x" * (MAX_FLOWCHART_ID_CHARS + 1),
    ],
)
def test_invalid_identities_are_refused(identity: str) -> None:
    assert refused(flow([node(identity)]))
    assert refused(flow([node("a"), node("b")], [edge(identity, "a", "b")]))


def test_identities_are_unique_across_nodes_and_edges() -> None:
    assert refused(flow([node("a"), node("a")])) == ["flowchart_identity_duplicate"]
    data = flow([node("a"), node("b")], [edge("e", "a", "b"), edge("e", "b", "a")])
    assert refused(data) == ["flowchart_identity_duplicate"]
    data = flow([node("a"), node("b")], [edge("a", "a", "b")])
    assert refused(data) == ["flowchart_identity_duplicate"]


@pytest.mark.parametrize(
    "label",
    [
        "A",
        "Début",
        "Valeur valide ?",
        "x" * MAX_FLOWCHART_LABEL_CHARS,
        "a  b",
        "日本 ✓",
    ],
)
def test_valid_labels(label: str) -> None:
    assert parse(flow([node("a", label=label)])).nodes[0].label == label
    data = flow([node("a"), node("b")], [edge("e", "a", "b", label)])
    assert parse(data).edges[0].label == label


@pytest.mark.parametrize(
    ("label", "reason"),
    [
        ("", "vide"),
        ("x" * (MAX_FLOWCHART_LABEL_CHARS + 1), "200"),
        ("a\nb", "retour à la ligne"),
        ("a\rb", "retour à la ligne"),
        ("a\tb", "retour à la ligne"),
        ("a\x00b", "retour à la ligne"),
        ("a\x7fb", "retour à la ligne"),
        ("a\x85b", "retour à la ligne"),
        ("a\u2028b", "retour à la ligne"),
        ("a\u2029b", "retour à la ligne"),
        (" a", "espace"),
        ("a ", "espace"),
        ("\u00a0a", "espace"),
        ("   ", "espace"),
    ],
)
def test_invalid_labels_are_refused(label: str, reason: str) -> None:
    problem = label_problem(label)
    assert problem is not None and reason in problem
    assert refused(flow([node("a", label=label)])) == ["flowchart_label"]
    data = flow([node("a"), node("b")], [edge("e", "a", "b", label)])
    assert refused(data) == ["flowchart_label"]


def test_edge_label_is_omitted_never_null() -> None:
    data = flow([node("a"), node("b")], [edge("e", "a", "b")])
    assert parse(data).edges[0].label is None
    data["edges"][0]["label"] = None
    assert refused(data)
    with pytest.raises(ValidationError):
        FlowEdge(id="e", source="a", target="b", label=None)


@pytest.mark.parametrize(
    "value", [0, -1, 1, MAX_FLOWCHART_COORDINATE, -MAX_FLOWCHART_COORDINATE]
)
def test_coordinates_within_bounds(value: int) -> None:
    parsed = parse(flow([node("a", x=value, y=-value)])).nodes[0]
    assert (parsed.x, parsed.y) == (value, -value)


@pytest.mark.parametrize(
    "value",
    [
        MAX_FLOWCHART_COORDINATE + 1,
        -MAX_FLOWCHART_COORDINATE - 1,
        1.5,
        1.0,
        "1",
        True,
        None,
    ],
)
def test_invalid_coordinates_are_refused(value: object) -> None:
    for axis in ("x", "y"):
        data = flow([node("a")])
        data["nodes"][0][axis] = value
        assert refused(data)


def test_valid_edges_including_parallel_and_reverse() -> None:
    data = flow(
        [node("a"), node("b"), node("c")],
        [
            edge("e1", "a", "b", "Oui"),
            edge("e2", "a", "b", "Non"),
            edge("e3", "b", "a"),
            edge("e4", "b", "c"),
        ],
    )
    value = parse(data)
    assert [(e.source, e.target) for e in value.edges] == [
        ("a", "b"),
        ("a", "b"),
        ("b", "a"),
        ("b", "c"),
    ]


@pytest.mark.parametrize("end", ["source", "target"])
def test_unknown_endpoint_is_refused(end: str) -> None:
    data = flow([node("a"), node("b")], [edge("e", "a", "b")])
    data["edges"][0][end] = "ghost"
    with pytest.raises(ValidationError) as caught:
        parse(data)
    (error,) = caught.value.errors()
    assert error["type"] == "flowchart_endpoint_unknown"
    assert error.get("ctx") == {"edge": "e", "end": end, "node": "ghost", "index": 0}


def test_self_loop_is_refused() -> None:
    data = flow([node("a"), node("b")], [edge("e0", "a", "b"), edge("e1", "b", "b")])
    with pytest.raises(ValidationError) as caught:
        parse(data)
    (error,) = caught.value.errors()
    assert error["type"] == "flowchart_self_loop"
    assert error.get("ctx") == {"edge": "e1", "node": "b", "index": 1}


@pytest.mark.parametrize(
    "where",
    ["document", "node", "edge"],
)
def test_unknown_fields_are_refused(where: str) -> None:
    data = simple()
    target: dict[str, Any] = {
        "document": data,
        "node": data["nodes"][0],
        "edge": data["edges"][0],
    }[where]
    target["shape"] = "diamond"
    assert refused(data) == ["extra_forbidden"]


@pytest.mark.parametrize(
    ("where", "field"),
    [
        ("document", "format_version"),
        ("document", "nodes"),
        ("document", "edges"),
        ("node", "id"),
        ("node", "kind"),
        ("node", "label"),
        ("node", "x"),
        ("node", "y"),
        ("edge", "id"),
        ("edge", "source"),
        ("edge", "target"),
    ],
)
def test_required_fields(where: str, field: str) -> None:
    data = simple()
    target = {"document": data, "node": data["nodes"][0], "edge": data["edges"][0]}
    del target[where][field]
    assert refused(data)


@pytest.mark.parametrize("version", ["0.2", "1", 0.1, None])
def test_format_version_is_exact(version: object) -> None:
    data = simple()
    data["format_version"] = version
    assert refused(data)


def test_collection_limits() -> None:
    nodes = [node(f"n{i}") for i in range(MAX_FLOWCHART_NODES)]
    assert len(parse(flow(nodes)).nodes) == MAX_FLOWCHART_NODES
    assert refused(flow([*nodes, node("extra")])) == ["too_long"]
    pair = [node("a"), node("b")]
    edges = [edge(f"e{i}", "a", "b") for i in range(MAX_FLOWCHART_EDGES)]
    assert len(parse(flow(pair, edges)).edges) == MAX_FLOWCHART_EDGES
    assert refused(flow(pair, [*edges, edge("extra", "a", "b")])) == ["too_long"]


def test_models_are_frozen() -> None:
    value = document()
    with pytest.raises(ValidationError):
        value.nodes[0].label = "Autre"  # pyright: ignore[reportAttributeAccessIssue]
    with pytest.raises(ValidationError):
        value.nodes = ()  # pyright: ignore[reportAttributeAccessIssue]
