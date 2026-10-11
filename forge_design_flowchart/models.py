"""Modèles de la ressource Flowchart V0.1 : FlowDocument, FlowNode, FlowEdge.

Format minimal d'un organigramme pédagogique : des nœuds typés (``start``,
``step``, ``decision``, ``end``) positionnés en entiers et des arêtes orientées,
éventuellement libellées. Les points des arêtes ne sont pas persistés : la
projection les calcule. Le modèle refuse tout ce qui rend le document
inutilisable (champ inconnu, type inconnu, identité invalide ou dupliquée,
extrémité inconnue, boucle sur soi-même, coordonnée ou libellé hors bornes) ;
les règles de domaine qui laissent le document lisible (au plus un ``start``)
appartiennent à la validation (validation.py).
"""

import re
from typing import Annotated, Literal, TypeVar

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    model_validator,
)
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import PydanticCustomError

from forge_design_flowchart.limits import (
    MAX_FLOWCHART_COORDINATE,
    MAX_FLOWCHART_EDGES,
    MAX_FLOWCHART_ID_CHARS,
    MAX_FLOWCHART_LABEL_CHARS,
    MAX_FLOWCHART_NODES,
)

FORMAT_VERSION = "0.1"
NODE_KINDS = ("start", "step", "decision", "end")
FlowNodeKind = Literal["start", "step", "decision", "end"]

_T = TypeVar("_T")
ID_PATTERN = r"^[A-Za-z][A-Za-z0-9_-]*$"
# Contrôles C0 et C1, DEL, séparateurs de ligne et de paragraphe Unicode : un
# libellé tient sur une ligne.
_FORBIDDEN = re.compile(r"[\x00-\x1f\x7f-\x9f\u2028\u2029]")


def label_problem(value: str) -> str | None:
    """Raison du refus d'un libellé non vide, ou None s'il est acceptable.

    Partagée par le modèle et par les actions (même règle, même message).
    """
    if not value:
        return "Le libellé ne peut pas être vide."
    if len(value) > MAX_FLOWCHART_LABEL_CHARS:
        return f"Le libellé dépasse {MAX_FLOWCHART_LABEL_CHARS} caractères."
    if _FORBIDDEN.search(value):
        return (
            "Le libellé ne peut contenir ni retour à la ligne ni caractère de contrôle."
        )
    if value != value.strip():
        return "Le libellé ne peut ni commencer ni finir par un espace."
    return None


def _check_label(value: str) -> str:
    problem = label_problem(value)
    if problem is not None:
        raise PydanticCustomError("flowchart_label", "{reason}", {"reason": problem})
    return value


def _reject_null(value: object) -> object:
    if value is None:
        raise ValueError("Omit the property instead of providing null")
    return value


def _omission_schema(schema: JsonSchemaValue) -> None:
    # None n'est que le défaut Python interne ; null fourni est refusé.
    schema.pop("default", None)
    for branch in schema.pop("anyOf", []):
        if branch != {"type": "null"}:
            schema.update(branch)


_Omissible = Annotated[
    _T | None, BeforeValidator(_reject_null), Field(json_schema_extra=_omission_schema)
]
FlowId = Annotated[
    str,
    Field(min_length=1, max_length=MAX_FLOWCHART_ID_CHARS, pattern=ID_PATTERN),
]
FlowLabel = Annotated[str, AfterValidator(_check_label)]
_Coordinate = Annotated[
    int, Field(ge=-MAX_FLOWCHART_COORDINATE, le=MAX_FLOWCHART_COORDINATE)
]


class _FlowModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, allow_inf_nan=False
    )


class FlowNode(_FlowModel):
    """Nœud typé ; ``x`` et ``y`` : coin supérieur gauche, en unités de scène."""

    id: FlowId
    kind: FlowNodeKind
    label: FlowLabel
    x: _Coordinate
    y: _Coordinate


class FlowEdge(_FlowModel):
    """Arête orientée ``source → target`` ; libellé facultatif, omis s'il est absent."""

    id: FlowId
    source: FlowId
    target: FlowId
    label: _Omissible[FlowLabel] = None


class FlowDocument(_FlowModel):
    """Seule source de vérité persistante d'un organigramme.

    L'ordre des collections est conservé (il fixe l'ordre de rendu et de
    tabulation) mais n'est jamais une identité. Identités uniques dans un seul
    espace de noms, nœuds et arêtes confondus.
    """

    format_version: Literal["0.1"]
    nodes: Annotated[tuple[FlowNode, ...], Field(max_length=MAX_FLOWCHART_NODES)]
    edges: Annotated[tuple[FlowEdge, ...], Field(max_length=MAX_FLOWCHART_EDGES)]

    @model_validator(mode="after")
    def _references(self) -> "FlowDocument":
        seen: dict[str, tuple[str, int]] = {}
        for collection, items in (("nodes", self.nodes), ("edges", self.edges)):
            for index, item in enumerate(items):
                first = seen.setdefault(item.id, (collection, index))
                if first != (collection, index):
                    raise PydanticCustomError(
                        "flowchart_identity_duplicate",
                        "Identity {identity} already used at {first}",
                        {
                            "identity": item.id,
                            "first": f"{first[0]}[{first[1]}]",
                            "collection": collection,
                            "index": index,
                        },
                    )
        nodes = {node.id for node in self.nodes}
        for index, edge in enumerate(self.edges):
            for end in ("source", "target"):
                if getattr(edge, end) not in nodes:
                    raise PydanticCustomError(
                        "flowchart_endpoint_unknown",
                        "Edge {edge} {end} {node} is not a node of the document",
                        {"edge": edge.id, "end": end, "node": getattr(edge, end)}
                        | {"index": index},
                    )
            if edge.source == edge.target:
                raise PydanticCustomError(
                    "flowchart_self_loop",
                    "Edge {edge} loops on node {node}",
                    {"edge": edge.id, "node": edge.source, "index": index},
                )
        return self


def new_flow_document() -> FlowDocument:
    """Document V0.1 vide : en construction, sans nœud ni arête."""
    return FlowDocument(format_version=FORMAT_VERSION, nodes=(), edges=())
