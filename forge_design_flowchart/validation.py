"""Validation de domaine Flowchart V0.1, sur un document au format valide.

Un document en cours de construction doit rester enregistrable : aucun ``start``
ni aucun ``end`` n'est exigé, et aucune analyse de chemins (accessibilité,
cycles, dominance) n'est faite. Seule règle : au plus un nœud ``start``. Elle
appartient au niveau « graph », bloquant, distinct de la structure du format
(models.py). Ordre déterministe : ordre du document.
"""

from collections.abc import Iterator

from forge_design.specialized import SpecializedIssue, SpecializedValidationResult

from forge_design_flowchart.models import FlowDocument

STRUCTURE = "structure"
GRAPH = "graph"
FLOWCHART_VALIDATION_LEVELS = (STRUCTURE, GRAPH)


def flowchart_issues(document: FlowDocument) -> Iterator[SpecializedIssue]:
    first: str | None = None
    for index, node in enumerate(document.nodes):
        if node.kind != "start":
            continue
        if first is None:
            first = node.id
            continue
        yield SpecializedIssue(
            "flowchart.start-duplicate",
            "error",
            f"Nœud de début supplémentaire « {node.id} » : « {first} » est déjà "
            "le début.",
            GRAPH,
            ("nodes", index),
        )


def validate_flowchart(document: FlowDocument) -> SpecializedValidationResult:
    """Validation pure d'un document au format valide ; ne le modifie jamais."""
    return SpecializedValidationResult.bounded(flowchart_issues(document))
