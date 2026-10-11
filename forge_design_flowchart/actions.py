"""Actions bornées de Flowchart : renommer un nœud (rename-node) ou une arête
(rename-edge).

Fonctions pures sur le contrat FD-EDIT-001 : le handler reçoit le document
décodé et le payload borné, jamais de chemin, de requête ni d'hôte, et rend un
nouveau document. Forge Design relit, vérifie la révision, valide, écrit
atomiquement et journalise ; un document inchangé n'est pas écrit (no-op de
l'hôte, aucun historique).

Invariant : seul ``label`` de l'élément désigné change ; identités, types,
positions, extrémités, ordre des collections et tous les autres éléments sont
repris à l'identique.

Libellé : espaces de tête et de fin retirés, puis règle du modèle (une ligne,
1 à 200 caractères, sans caractère de contrôle). Pour une arête, un libellé vide
(ou fait d'espaces) supprime le libellé : le champ est omis du document, jamais
enregistré vide. Payload mal formé (champ absent, identité trop longue) : 400 ;
élément inconnu ou libellé refusé : 422.
"""

from forge_design.modules import (
    ModuleAction,
    ModuleActionPayload,
    ModuleActionRefused,
    ModuleActionResult,
)

from forge_design_flowchart.contract import FLOWCHART_RESOURCE_TYPE
from forge_design_flowchart.limits import MAX_FLOWCHART_ID_CHARS
from forge_design_flowchart.models import FlowDocument, label_problem

RENAME_NODE_ACTION_ID = "rename-node"
RENAME_EDGE_ACTION_ID = "rename-edge"


def _label(payload: ModuleActionPayload, *, optional: bool) -> str | None:
    label = payload.text("label").strip()
    if not label and optional:
        return None
    problem = label_problem(label)
    if problem is not None:
        raise ModuleActionRefused(problem)
    return label


def rename_node(
    document: FlowDocument, payload: ModuleActionPayload
) -> ModuleActionResult:
    """Nouveau libellé, non vide, du nœud désigné."""
    node_id = payload.text("node", max_chars=MAX_FLOWCHART_ID_CHARS)
    label = _label(payload, optional=False)
    for index, node in enumerate(document.nodes):
        if node.id == node_id:
            break
    else:
        raise ModuleActionRefused(f"Nœud inconnu : {node_id}.")
    if label == node.label:
        return ModuleActionResult(document)
    nodes = (
        *document.nodes[:index],
        node.model_copy(update={"label": label}),
        *document.nodes[index + 1 :],
    )
    return ModuleActionResult(document.model_copy(update={"nodes": nodes}))


def rename_edge(
    document: FlowDocument, payload: ModuleActionPayload
) -> ModuleActionResult:
    """Nouveau libellé de l'arête désignée ; vide : libellé supprimé."""
    edge_id = payload.text("edge", max_chars=MAX_FLOWCHART_ID_CHARS)
    label = _label(payload, optional=True)
    for index, edge in enumerate(document.edges):
        if edge.id == edge_id:
            break
    else:
        raise ModuleActionRefused(f"Arête inconnue : {edge_id}.")
    if label == edge.label:
        return ModuleActionResult(document)
    edges = (
        *document.edges[:index],
        edge.model_copy(update={"label": label}),
        *document.edges[index + 1 :],
    )
    return ModuleActionResult(document.model_copy(update={"edges": edges}))


RENAME_NODE = ModuleAction(
    id=RENAME_NODE_ACTION_ID,
    resource_type=FLOWCHART_RESOURCE_TYPE.id,
    fields=("node", "label"),
    handler=rename_node,
    capability="edit",
)

RENAME_EDGE = ModuleAction(
    id=RENAME_EDGE_ACTION_ID,
    resource_type=FLOWCHART_RESOURCE_TYPE.id,
    fields=("edge", "label"),
    handler=rename_edge,
    capability="edit",
)
