"""ForgeDesign-Flowchart : module spécialisé Flowchart pour Forge Design.

Second module pilote du contrat des modules (FD-MODULE-PILOT-001), créé pour
vérifier que le moteur générique de Forge Design suffit à un domaine sans bornes,
fils ni routage : organigrammes simples (début, étape, décision, fin), arêtes
orientées et libellées. Ressource V0.1 (``*.flow.json`` sous ``mvc/flowchart``),
validation, projection vers la GraphicScene, renommage d'un nœud ou d'une arête
par les actions bornées rename-node et rename-edge, édition en place depuis le
calque monde du Graphic Core (static/flow-editor.js). Ni création, ni
suppression, ni déplacement, ni mise en page automatique. Activation explicite :
``forge-design --module forge_design_flowchart``.
"""

__version__ = "0.1.0"

from forge_design.modules import (
    MODULE_API_VERSION,
    ModuleAsset,
    ModuleDescriptor,
    ResourceBinding,
)

from forge_design_flowchart.actions import (
    RENAME_EDGE,
    RENAME_NODE,
    rename_edge,
    rename_node,
)
from forge_design_flowchart.codec import FlowCodec
from forge_design_flowchart.contract import FLOWCHART_RESOURCE_TYPE, FLOWCHART_TOOL
from forge_design_flowchart.editor import flow_editor_config
from forge_design_flowchart.models import (
    FlowDocument,
    FlowEdge,
    FlowNode,
    new_flow_document,
)
from forge_design_flowchart.scene import flow_scene
from forge_design_flowchart.validation import validate_flowchart

FLOW_EDITOR_SCRIPT = "flow-editor.js"
FLOW_EDITOR_STYLE = "flowchart.css"
# Versions de Forge Design acceptées (FD-RELEASE-001) : identique au Requires-Dist
# de pyproject.toml, qui reste la première barrière ; l'hôte la revérifie à
# l'activation.
FORGE_DESIGN_REQUIREMENT = ">=0.2.0,<1"

# Descripteur lu par l'hôte Forge Design lors de l'activation explicite.
FORGE_DESIGN_MODULE = ModuleDescriptor(
    definition=FLOWCHART_TOOL,
    version=__version__,
    api_version=MODULE_API_VERSION,
    bindings=(
        ResourceBinding(
            FLOWCHART_RESOURCE_TYPE.id,
            FlowCodec(),
            flow_scene,
            editor_script=FLOW_EDITOR_SCRIPT,
            editor_config=flow_editor_config,
        ),
    ),
    asset_package="forge_design_flowchart",
    assets=(
        ModuleAsset(FLOW_EDITOR_SCRIPT, "static/flow-editor.js"),
        ModuleAsset(FLOW_EDITOR_STYLE, "static/flowchart.css"),
    ),
    actions=(RENAME_NODE, RENAME_EDGE),
    requires_forge_design=FORGE_DESIGN_REQUIREMENT,
)

__all__ = [
    "FORGE_DESIGN_MODULE",
    "FORGE_DESIGN_REQUIREMENT",
    "FLOWCHART_RESOURCE_TYPE",
    "FLOWCHART_TOOL",
    "RENAME_EDGE",
    "RENAME_NODE",
    "FlowCodec",
    "FlowDocument",
    "FlowEdge",
    "FlowNode",
    "flow_editor_config",
    "flow_scene",
    "new_flow_document",
    "rename_edge",
    "rename_node",
    "validate_flowchart",
]
