"""Déclaration du type de ressource et de l'outil spécialisé Flowchart.

Capacités exactes : ouvrir, valider, modifier et enregistrer. Pas de création
de ressource, pas d'export, pas d'exécution interactive : rien n'est déclaré
qui ne soit implémenté.
"""

from forge_design.specialized import (
    SpecializedCapability,
    SpecializedResourceType,
    SpecializedToolDefinition,
    UiEntry,
)

from forge_design_flowchart.limits import MAX_FLOWCHART_RESOURCE_BYTES
from forge_design_flowchart.models import FORMAT_VERSION
from forge_design_flowchart.validation import FLOWCHART_VALIDATION_LEVELS

FLOWCHART_SOURCE_PREFIX = "mvc/flowchart"
FLOWCHART_SUFFIX = ".flow.json"

_CAPABILITIES = tuple(
    SpecializedCapability.platform(name)
    for name in ("open", "validate", "save", "edit")
)

FLOWCHART_RESOURCE_TYPE = SpecializedResourceType(
    id="flowchart",
    format_id="flowchart-json",
    suffix=FLOWCHART_SUFFIX,
    source_prefix=FLOWCHART_SOURCE_PREFIX,
    read_versions=frozenset({FORMAT_VERSION}),
    write_version=FORMAT_VERSION,
    editable=True,
    max_size=MAX_FLOWCHART_RESOURCE_BYTES,
    capabilities=_CAPABILITIES,
    validation_levels=FLOWCHART_VALIDATION_LEVELS,
    blocking_validation_levels=frozenset(FLOWCHART_VALIDATION_LEVELS),
    persistent_state=("nodes", "edges"),
    runtime_only_state=("selection", "viewport", "history", "text-editing"),
)

FLOWCHART_TOOL = SpecializedToolDefinition(
    id="flowchart",
    name="Flowchart",
    description="Organigrammes simples, versionnés dans les sources du projet.",
    resource_types=(FLOWCHART_RESOURCE_TYPE,),
    capabilities=_CAPABILITIES,
    optional_dependencies=(),
    # Entrée « Modules → Flowchart » de l'hôte ; aucune icône en V1.
    ui_entry=UiEntry("Flowchart"),
)
