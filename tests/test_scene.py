"""Projection FlowDocument → GraphicScene : exacte, déterministe, pure, validée par le
Graphic Core réel."""

import builtins
import json
import math
import shutil
import subprocess
from importlib.resources import files
from pathlib import Path
from typing import Any

import pytest
from flow_support import EXAMPLE, document, edge, flow, node

from forge_design_flowchart import FlowCodec, flow_scene, new_flow_document
from forge_design_flowchart.limits import (
    MAX_FLOWCHART_COORDINATE,
    MAX_FLOWCHART_LABEL_CHARS,
)
from forge_design_flowchart.scene import (
    EDGE_LABEL_RISE,
    LINE_CHARS,
    MAX_PARALLEL_OFFSET,
    NODE_WIDTH,
    PARALLEL_SPACING,
    SCENE_MARGIN,
    edge_points,
    node_height,
    wrap_label,
)

HOSTILE = "</script><svg onload=alert(1)>"


def by_id(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in items}


def xy(point: dict[str, float]) -> tuple[float, float]:
    return point["x"], point["y"]


def three() -> dict[str, Any]:
    """Trois nœuds, une transition libellée."""
    return flow(
        [
            node("s", "start", "Début", 0, 0),
            node("d", "decision", "Valeur valide ?", 0, 120),
            node("e", "end", "Fin", 300, 120),
        ],
        [edge("oui", "d", "e", "Oui")],
    )


def test_three_nodes_one_edge() -> None:
    scene = flow_scene(document(three()))
    assert [n["id"] for n in scene["nodes"]] == ["s", "d", "e"]
    assert [n["label"] for n in scene["nodes"]] == ["Début", "Valeur valide ?", "Fin"]
    nodes = by_id(scene["nodes"])
    # Repère : le nœud le plus à gauche et le plus haut commence à la marge.
    assert nodes["s"]["rect"] == {"x": 40, "y": 40, "width": NODE_WIDTH, "height": 48}
    assert nodes["d"]["rect"] == {"x": 40, "y": 160, "width": NODE_WIDTH, "height": 48}
    assert nodes["e"]["rect"] == {"x": 340, "y": 160, "width": NODE_WIDTH, "height": 48}
    (projected,) = scene["edges"]
    assert projected == {
        "id": "oui",
        "source": "d",
        "target": "e",
        # Bord droit de la décision → bord gauche de la fin, sur la droite des centres.
        "points": [{"x": 248.0, "y": 184.0}, {"x": 340.0, "y": 184.0}],
        "label": "Oui",
        "labelAt": {"x": 294.0, "y": 184.0 - EDGE_LABEL_RISE},
        "presentation": {"arrow": "end"},
    }
    assert scene["width"] == 340 + NODE_WIDTH + SCENE_MARGIN
    assert scene["height"] == 160 + 48 + SCENE_MARGIN
    assert scene["title"] == "Organigramme"
    assert scene["description"] == "3 nœuds, 1 transitions."


def test_node_kinds_are_distinguished_with_generic_presentation() -> None:
    scene = flow_scene(document())
    nodes = by_id(scene["nodes"])
    assert {key: n["presentation"] for key, n in nodes.items()} == {
        "debut": {"variant": "category-3"},
        "verifier": {"variant": "default"},
        "valide": {"variant": "category-4"},
        "continuer": {"variant": "default"},
        "signaler": {"variant": "default"},
        "fin": {"variant": "category-5"},
    }
    assert {key: n["data"] for key, n in nodes.items()} == {
        "debut": {"kind": "start"},
        "verifier": {"kind": "step"},
        "valide": {"kind": "decision"},
        "continuer": {"kind": "step"},
        "signaler": {"kind": "step"},
        "fin": {"kind": "end"},
    }
    # Texte central : le libellé, précédé d'une marque hors des étapes.
    assert [n["lines"] for n in scene["nodes"]] == [
        ["▶ Début"],
        ["Vérifier la valeur"],
        ["◇ Valeur valide ?"],
        ["Continuer"],
        ["Signaler l'erreur"],
        ["■ Fin"],
    ]


def test_example_edges_are_oriented_and_labelled() -> None:
    scene = flow_scene(document())
    nodes = by_id(scene["nodes"])
    edges = by_id(scene["edges"])
    assert list(edges) == ["t1", "t2", "t3", "t4", "t5", "t6"]
    assert {key: e.get("label") for key, e in edges.items()} == {
        "t1": None,
        "t2": None,
        "t3": "Oui",
        "t4": "Non",
        "t5": "suite",
        "t6": None,
    }
    for projected in scene["edges"]:
        assert projected["presentation"] == {"arrow": "end"}
        assert "labelAt" in projected
        source = nodes[projected["source"]]["rect"]
        target = nodes[projected["target"]]["rect"]
        start, end = (xy(p) for p in projected["points"])
        # Direction : départ sur le bord de la source, arrivée sur le bord de la cible.
        assert on_border(source, start) and on_border(target, end)
    # Transition verticale : bas de « Début » → haut de « Vérifier ».
    assert edges["t1"]["points"] == [{"x": 304.0, "y": 88.0}, {"x": 304.0, "y": 140.0}]
    assert edges["t1"]["labelAt"] == {"x": 304.0, "y": 114.0}


def on_border(rect: dict[str, float], point: tuple[float, float]) -> bool:
    x, y = point
    left, top = rect["x"], rect["y"]
    right, bottom = left + rect["width"], top + rect["height"]
    inside = left - 1e-6 <= x <= right + 1e-6 and top - 1e-6 <= y <= bottom + 1e-6
    edge_x = math.isclose(x, left) or math.isclose(x, right)
    edge_y = math.isclose(y, top) or math.isclose(y, bottom)
    return inside and (edge_x or edge_y)


def test_label_anchor_beside_a_vertical_edge() -> None:
    data = flow(
        [node("a", x=0, y=0), node("b", x=0, y=200)],
        [edge("e", "a", "b", "Oui")],
    )
    (projected,) = flow_scene(document(data))["edges"]
    # Milieu (144, 164), à droite du trait d'une demi-largeur de libellé estimée.
    assert projected["labelAt"] == {"x": 144 + 8 + 3 * 6.5 / 2, "y": 164 + 3.0}


def test_parallel_and_reverse_edges_are_separated_deterministically() -> None:
    data = flow(
        [node("a", x=0, y=0), node("b", x=400, y=0)],
        [
            edge("e1", "a", "b", "Oui"),
            edge("e2", "a", "b", "Non"),
            edge("e3", "b", "a"),
        ],
    )
    edges = by_id(flow_scene(document(data))["edges"])
    ys = {key: [p["y"] for p in e["points"]] for key, e in edges.items()}
    # Centres à y = 64 ; décalages -16, 0, +16 par rang, exprimés dans le sens
    # canonique a → b : la transition retour e3 passe de l'autre côté de e1.
    assert ys["e1"] == [64 - PARALLEL_SPACING] * 2
    assert ys["e2"] == [64.0, 64.0]
    assert ys["e3"] == [64 + PARALLEL_SPACING] * 2
    # La transition retour part bien de b vers a.
    assert edges["e3"]["points"][0]["x"] > edges["e3"]["points"][1]["x"]
    # Même document, même scène, octet pour octet.
    again = flow_scene(document(data))
    assert json.dumps(again) == json.dumps(flow_scene(document(data)))


def test_parallel_offset_is_clamped_inside_the_nodes() -> None:
    edges = [edge(f"e{i}", "a", "b") for i in range(9)]
    data = flow([node("a", x=0, y=0), node("b", x=400, y=0)], edges)
    ys = [e["points"][0]["y"] for e in flow_scene(document(data))["edges"]]
    assert min(ys) == 64 - MAX_PARALLEL_OFFSET and max(ys) == 64 + MAX_PARALLEL_OFFSET
    assert all(40 < y < 88 for y in ys)


def test_overlapping_and_coincident_nodes_still_project() -> None:
    data = flow(
        [node("a", x=0, y=0), node("b", x=50, y=10), node("c", x=0, y=0)],
        [edge("ab", "a", "b"), edge("ac", "a", "c")],
    )
    edges = by_id(flow_scene(document(data))["edges"])
    # Superposés : la droite des centres entière plutôt qu'un segment vide.
    assert edges["ab"]["points"] == [{"x": 144.0, "y": 64.0}, {"x": 194.0, "y": 74.0}]
    # Confondus : deux points égaux (le moteur n'y dessine pas de flèche).
    assert edges["ac"]["points"] == [{"x": 144.0, "y": 64.0}, {"x": 144.0, "y": 64.0}]


def test_edge_points_function() -> None:
    a = (0.0, 0.0, 100.0, 50.0)
    b = (300.0, 0.0, 100.0, 50.0)
    assert edge_points(a, b, 0) == ((100.0, 25.0), (300.0, 25.0))
    assert edge_points(a, b, 10) == ((100.0, 35.0), (300.0, 35.0))
    assert edge_points(b, a, 10) == ((300.0, 15.0), (100.0, 15.0))
    diagonal = edge_points(a, (200.0, 200.0, 100.0, 50.0), 0)
    assert diagonal == ((75.0, 50.0), (225.0, 200.0))


def test_wrap_label() -> None:
    assert wrap_label("Vérifier la valeur") == ["Vérifier la valeur"]
    assert wrap_label("a " * 20) == ["a a a a a a a a a a a a a", "a a a a a a a"]
    assert wrap_label("x" * 30) == ["x" * LINE_CHARS, "x" * 5]
    long = wrap_label("mot " * 60)
    assert len(long) == 3 and long[-1].endswith("…")
    assert all(len(line) <= LINE_CHARS for line in long)
    assert wrap_label("x" * 200) == ["x" * 25, "x" * 25, "x" * 24 + "…"]
    assert node_height(1) == 48 and node_height(2) == 66 and node_height(3) == 92


def test_long_labels_grow_the_node_and_keep_the_exact_label() -> None:
    label = "Demander confirmation à l'utilisateur avant d'envoyer"
    scene = flow_scene(document(flow([node("a", "decision", label)])))
    (projected,) = scene["nodes"]
    assert projected["label"] == label
    assert projected["lines"] == [
        "◇ Demander confirmation à",
        "l'utilisateur avant",
        "d'envoyer",
    ]
    assert projected["rect"]["height"] == 92


def test_empty_document_has_an_empty_scene() -> None:
    scene = flow_scene(new_flow_document())
    assert scene == {
        "width": 480,
        "height": 240,
        "title": "Organigramme",
        "description": "0 nœuds, 0 transitions.",
        "nodes": [],
        "edges": [],
    }


def test_projection_is_pure(monkeypatch: pytest.MonkeyPatch) -> None:
    value = document()
    before = FlowCodec().encode(value)
    dumped = value.model_dump()

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("la projection n'ouvre aucun fichier")

    monkeypatch.setattr(builtins, "open", forbidden)
    first = flow_scene(value)
    monkeypatch.undo()
    assert FlowCodec().encode(value) == before and value.model_dump() == dumped
    # Un résultat neuf à chaque appel : le modifier ne touche ni le document ni la
    # projection suivante.
    first["nodes"][0]["label"] = "modifié"
    first["edges"].clear()
    assert flow_scene(value)["nodes"][0]["label"] == "Début"
    assert len(flow_scene(value)["edges"]) == 6


def test_extreme_coordinates_stay_inside_the_graphic_bounds() -> None:
    limit = MAX_FLOWCHART_COORDINATE
    data = flow(
        [node("a", x=-limit, y=-limit), node("b", x=limit, y=limit)],
        [edge("e", "a", "b")],
    )
    scene = flow_scene(document(data))
    assert scene["width"] == 2 * limit + NODE_WIDTH + 2 * SCENE_MARGIN
    assert scene["width"] <= 1_000_000 and scene["height"] <= 1_000_000


def test_scenes_pass_the_real_graphic_core_validation(tmp_path: Path) -> None:
    executable = shutil.which("node")
    if executable is None:
        pytest.skip("Node indisponible.")
    hostile = three()
    hostile["nodes"][0]["label"] = HOSTILE
    hostile["edges"][0]["label"] = HOSTILE
    full = flow(
        [
            node(f"n{i}", "step", "x" * MAX_FLOWCHART_LABEL_CHARS, i * 10, i * 7)
            for i in range(500)
        ],
        [
            edge(f"e{i}", f"n{i % 499}", f"n{i % 499 + 1}", "y" * 200)
            for i in range(2000)
        ],
    )
    scenes = [
        flow_scene(new_flow_document()),
        flow_scene(document()),
        flow_scene(document(hostile)),
        flow_scene(document(full)),
    ]
    payload = tmp_path / "scenes.json"
    payload.write_text(json.dumps(scenes))
    model = files("forge_design.web").joinpath("static/graphics/model.js")
    script = (
        f'import {{ validateScene }} from "{Path(str(model)).as_uri()}";'
        'import { readFileSync } from "node:fs";'
        "const all = JSON.parse(readFileSync(process.argv[1], 'utf8'));"
        "console.log(JSON.stringify(all.map((s) => {"
        "  const v = validateScene(s);"
        "  const shown = v.edges.filter((e) => e.label !== null && e.labelAt !== null);"
        "  return [v.nodes.length, v.edges.length, shown.length];"
        "})));"
    )
    result = subprocess.run(
        [executable, "--input-type=module", "-e", script, str(payload)],
        capture_output=True,
        check=True,
        text=True,
        timeout=60,
    )
    # Chaque libellé d'arête est affichable : label et labelAt présents ensemble.
    assert json.loads(result.stdout) == [
        [0, 0, 0],
        [6, 6, 3],
        [3, 1, 1],
        [500, 2000, 2000],
    ]


def test_example_file_is_the_documented_scenario() -> None:
    labels = [n["label"] for n in json.loads(EXAMPLE.read_text())["nodes"]]
    assert labels == [
        "Début",
        "Vérifier la valeur",
        "Valeur valide ?",
        "Continuer",
        "Signaler l'erreur",
        "Fin",
    ]
