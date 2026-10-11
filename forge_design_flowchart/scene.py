"""Projection FlowDocument → GraphicScene : pure, déterministe, runtime seulement.

La scène n'est jamais persistée : elle est recalculée à chaque lecture depuis le
document. Aucune donnée n'est inventée ; la géométrie des arêtes est dérivée des
seules positions des nœuds.

Nœuds. Un ``FlowNode`` devient un nœud graphique de largeur fixe ; ``label`` est
le libellé exact du document (nom accessible, info-bulle, valeur de départ de
l'édition) ; ``lines`` en est l'affichage replié (au plus trois lignes, points
de suspension au-delà), précédé d'une marque pour les types autres que
``step``. Le Graphic Core ne dessine que des rectangles : début, décision et
fin se distinguent par une variante de couleur générique et par leur marque
(``▶``, ``◇``, ``■``), jamais par une forme propre (limite documentée).

Arêtes. Une ``FlowEdge`` devient une arête graphique orientée (flèche à
l'arrivée), segment droit entre les bords des deux rectangles, sur la droite des
centres. Les arêtes d'une même paire de nœuds (dans un sens ou dans l'autre)
sont décalées perpendiculairement selon leur rang dans le document, par rapport
au sens canonique de la paire (identité la plus petite → la plus grande) :
même document, même scène. Le libellé est projeté avec ``labelAt`` (sans lui, le
moteur ne l'afficherait pas), au milieu du segment ; ``labelAt`` existe aussi
pour une arête sans libellé, comme point d'ancrage de l'édition.

Repère. Les coordonnées du document sont translatées pour que la scène commence
à une marge fixe de son nœud le plus à gauche et le plus haut.
"""

import math
from typing import Any

from forge_design_flowchart.models import FlowDocument, FlowEdge, FlowNode

NODE_WIDTH = 208
# Texte des nœuds : 12 px monospace du Graphic Core, environ 7,2 px par caractère,
# 12 px de retrait de chaque côté.
LINE_CHARS = 25
MAX_LINES = 3
LINE_STEP = 26
MIN_NODE_HEIGHT = 48
NODE_PADDING = 40
SCENE_MARGIN = 40
EMPTY_SCENE = (480, 240)
PARALLEL_SPACING = 16
# Le décalage reste à l'intérieur des nœuds : au plus la demi-hauteur minimale
# moins une petite garde.
MAX_PARALLEL_OFFSET = MIN_NODE_HEIGHT / 2 - 4
# Libellé d'arête : 12 px sans empattement, environ 6,5 px par caractère.
EDGE_LABEL_CHAR_WIDTH = 6.5
EDGE_LABEL_GAP = 8
EDGE_LABEL_RISE = 6

MARKERS = {"start": "▶", "decision": "◇", "end": "■"}
VARIANTS = {
    "start": "category-3",
    "step": "default",
    "decision": "category-4",
    "end": "category-5",
}

Point = tuple[float, float]
Rect = tuple[float, float, float, float]


def wrap_label(text: str, width: int = LINE_CHARS, limit: int = MAX_LINES) -> list[str]:
    """Repli par mots, coupure des mots trop longs, « … » au-delà de ``limit``."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        while len(word) > width:
            if current:
                lines.append(current)
                current = ""
            lines.append(word[:width])
            word = word[width:]
        candidate = f"{current} {word}" if current else word
        if len(candidate) <= width:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    if len(lines) > limit:
        lines = lines[:limit]
        lines[-1] = lines[-1][: width - 1].rstrip() + "…"
    return lines


def node_lines(node: FlowNode) -> list[str]:
    marker = MARKERS.get(node.kind)
    return wrap_label(f"{marker} {node.label}" if marker else node.label)


def node_height(line_count: int) -> int:
    return max(MIN_NODE_HEIGHT, NODE_PADDING + LINE_STEP * (line_count - 1))


def _number(value: float) -> float:
    # Arrondi stable, sans « -0.0 ».
    return round(value, 2) + 0.0


def _span(rect: Rect, origin: Point, direction: Point) -> tuple[float, float] | None:
    """Intervalle du paramètre t où ``origin + t × direction`` est dans ``rect``."""
    low, high = -math.inf, math.inf
    for start, step, minimum, maximum in (
        (origin[0], direction[0], rect[0], rect[0] + rect[2]),
        (origin[1], direction[1], rect[1], rect[1] + rect[3]),
    ):
        if step == 0:
            if not minimum <= start <= maximum:
                return None
            continue
        a, b = (minimum - start) / step, (maximum - start) / step
        low, high = max(low, min(a, b)), min(high, max(a, b))
    return (low, high) if low <= high else None


def _center(rect: Rect) -> Point:
    return rect[0] + rect[2] / 2, rect[1] + rect[3] / 2


def edge_points(source: Rect, target: Rect, offset: float) -> tuple[Point, Point]:
    """Segment entre les bords de ``source`` et ``target``, décalé de ``offset``
    perpendiculairement à la droite des centres (sens source → cible)."""
    (sx, sy), (tx, ty) = _center(source), _center(target)
    dx, dy = tx - sx, ty - sy
    length = math.hypot(dx, dy)
    if length == 0:
        return (sx, sy), (tx, ty)
    nx, ny = -dy / length * offset, dx / length * offset
    origin = (sx + nx, sy + ny)
    direction = (dx, dy)
    leave = _span(source, origin, direction)
    enter = _span(target, origin, direction)
    start = min(max(leave[1], 0.0), 1.0) if leave else 0.0
    end = min(max(enter[0], 0.0), 1.0) if enter else 1.0
    if start >= end:
        # Nœuds superposés : droite des centres entière plutôt qu'un segment vide.
        start, end = 0.0, 1.0
    return (
        (origin[0] + start * dx, origin[1] + start * dy),
        (origin[0] + end * dx, origin[1] + end * dy),
    )


def label_anchor(points: tuple[Point, Point], label: str | None) -> Point:
    """Milieu du segment ; libellé au-dessus d'un segment plutôt horizontal, à
    droite d'un segment plutôt vertical."""
    (ax, ay), (bx, by) = points
    mx, my = (ax + bx) / 2, (ay + by) / 2
    if label is None:
        return mx, my
    if abs(bx - ax) >= abs(by - ay):
        return mx, my - EDGE_LABEL_RISE
    half = len(label) * EDGE_LABEL_CHAR_WIDTH / 2
    return mx + EDGE_LABEL_GAP + half, my + EDGE_LABEL_RISE / 2


def parallel_offsets(edges: tuple[FlowEdge, ...]) -> list[float]:
    """Décalage de chaque arête dans sa paire de nœuds, dans l'ordre du document."""
    groups: dict[tuple[str, str], list[int]] = {}
    for index, edge in enumerate(edges):
        key = (min(edge.source, edge.target), max(edge.source, edge.target))
        groups.setdefault(key, []).append(index)
    offsets = [0.0] * len(edges)
    for (low, _), members in groups.items():
        middle = (len(members) - 1) / 2
        for rank, index in enumerate(members):
            value = (rank - middle) * PARALLEL_SPACING
            value = max(-MAX_PARALLEL_OFFSET, min(MAX_PARALLEL_OFFSET, value))
            # Décalage exprimé dans le sens canonique de la paire.
            offsets[index] = value if edges[index].source == low else -value
    return offsets


def flow_scene(document: FlowDocument) -> dict[str, Any]:
    """GraphicScene runtime d'un organigramme ; ne modifie jamais le document."""
    lines = {node.id: node_lines(node) for node in document.nodes}
    if document.nodes:
        left = min(node.x for node in document.nodes) - SCENE_MARGIN
        top = min(node.y for node in document.nodes) - SCENE_MARGIN
    else:
        left = top = 0
    rects: dict[str, Rect] = {
        node.id: (
            node.x - left,
            node.y - top,
            NODE_WIDTH,
            node_height(len(lines[node.id])),
        )
        for node in document.nodes
    }
    nodes = [
        {
            "id": node.id,
            "label": node.label,
            "rect": dict(zip(("x", "y", "width", "height"), rects[node.id])),
            "lines": lines[node.id],
            "presentation": {"variant": VARIANTS[node.kind]},
            "data": {"kind": node.kind},
        }
        for node in document.nodes
    ]
    edges: list[dict[str, Any]] = []
    for edge, offset in zip(document.edges, parallel_offsets(document.edges)):
        points = edge_points(rects[edge.source], rects[edge.target], offset)
        anchor = label_anchor(points, edge.label)
        projected: dict[str, Any] = {
            "id": edge.id,
            "source": edge.source,
            "target": edge.target,
            "points": [{"x": _number(x), "y": _number(y)} for x, y in points],
        }
        if edge.label is not None:
            projected["label"] = edge.label
        projected["labelAt"] = {"x": _number(anchor[0]), "y": _number(anchor[1])}
        projected["presentation"] = {"arrow": "end"}
        edges.append(projected)
    if rects:
        width = max(x + w for x, _, w, _ in rects.values()) + SCENE_MARGIN
        height = max(y + h for _, y, _, h in rects.values()) + SCENE_MARGIN
    else:
        width, height = EMPTY_SCENE
    return {
        "width": width,
        "height": height,
        "title": "Organigramme",
        "description": f"{len(nodes)} nœuds, {len(edges)} transitions.",
        "nodes": nodes,
        "edges": edges,
    }
