"""Configuration de l'éditeur Flowchart, transmise inerte au script.

Seulement ce que la scène ne porte pas : les identifiants des deux actions.
Identités, libellés exacts, types (``data.kind``) et géométrie sont lus par le
script dans la scène validée du moteur (``engine.scene()``) ; URL d'action et
révision viennent du contexte générique de l'hôte. Rien n'est recopié ici.
"""

from typing import Any

from forge_design_flowchart.actions import RENAME_EDGE_ACTION_ID, RENAME_NODE_ACTION_ID
from forge_design_flowchart.models import FlowDocument


def flow_editor_config(document: FlowDocument) -> dict[str, Any]:
    """JSON du script d'édition ; indépendant du document, sans donnée de l'hôte."""
    del document
    return {
        "renameNodeAction": RENAME_NODE_ACTION_ID,
        "renameEdgeAction": RENAME_EDGE_ACTION_ID,
    }
