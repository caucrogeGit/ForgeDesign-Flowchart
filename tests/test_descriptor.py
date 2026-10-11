"""Descripteur FORGE_DESIGN_MODULE, activation réelle par l'hôte du cœur, frontières
(API publique seulement, aucune dépendance Circuit, jamais un Tool) et coexistence
avec Circuit."""

import ast
from importlib.util import find_spec
from pathlib import Path
from typing import Any

import pytest
from flow_support import EXAMPLE, PATH, make_project
from forge_design.modules import (
    DESCRIPTOR_ATTRIBUTE,
    MODULE_API_VERSION,
    ModuleAsset,
    activate_modules,
)
from forge_design.modules.host import ModuleHost
from forge_design.specialized import UiEntry

import forge_design_flowchart
from forge_design_flowchart import (
    FLOWCHART_RESOURCE_TYPE,
    FLOWCHART_TOOL,
    FORGE_DESIGN_MODULE,
    RENAME_EDGE,
    RENAME_NODE,
    FlowCodec,
    flow_editor_config,
    flow_scene,
)

PACKAGE = Path(forge_design_flowchart.__file__).parent


def test_descriptor_declares_flowchart() -> None:
    assert DESCRIPTOR_ATTRIBUTE == "FORGE_DESIGN_MODULE"
    module = FORGE_DESIGN_MODULE
    assert module.id == "flowchart" and module.definition is FLOWCHART_TOOL
    assert module.version == forge_design_flowchart.__version__ == "0.1.0"
    assert module.api_version == MODULE_API_VERSION == 1
    assert module.requires_forge_design == ">=0.2.0,<1"
    assert FLOWCHART_TOOL.name == "Flowchart"
    assert FLOWCHART_TOOL.ui_entry == UiEntry("Flowchart")
    (binding,) = module.bindings
    assert binding.resource_type == FLOWCHART_RESOURCE_TYPE.id == "flowchart"
    assert isinstance(binding.codec, FlowCodec)
    assert binding.scene is flow_scene
    assert binding.editor_script == "flow-editor.js"
    assert binding.editor_config is flow_editor_config
    assert module.asset_package == "forge_design_flowchart"
    assert module.assets == (
        ModuleAsset("flow-editor.js", "static/flow-editor.js"),
        ModuleAsset("flowchart.css", "static/flowchart.css"),
    )
    assert module.actions == (RENAME_NODE, RENAME_EDGE)


def test_resource_type() -> None:
    resource_type = FLOWCHART_RESOURCE_TYPE
    assert resource_type.format_id == "flowchart-json"
    assert resource_type.suffix == ".flow.json"
    assert resource_type.source_prefix == "mvc/flowchart"
    assert (
        resource_type.read_versions == {"0.1"} and resource_type.write_version == "0.1"
    )
    assert resource_type.editable
    assert resource_type.validation_levels == ("structure", "graph")
    assert resource_type.persistent_state == ("nodes", "edges")


def test_capabilities_are_exactly_the_implemented_ones() -> None:
    expected = ["open", "validate", "save", "edit"]
    assert [c.id for c in FLOWCHART_RESOURCE_TYPE.capabilities] == expected
    assert [c.id for c in FLOWCHART_TOOL.capabilities] == expected
    for absent in ("create", "export", "interactive-runtime"):
        assert absent not in {c.id for c in FLOWCHART_TOOL.capabilities}


def test_real_activation_by_package_name() -> None:
    activation = activate_modules(["forge_design_flowchart"])
    assert activation.diagnostics == ()
    (active,) = activation.modules
    assert active.package == "forge_design_flowchart"
    assert active.descriptor is FORGE_DESIGN_MODULE
    assert active.available_capabilities == frozenset(
        {"open", "validate", "save", "edit"}
    )


def test_activation_refuses_an_incompatible_core() -> None:
    activation = activate_modules(["forge_design_flowchart"], core_version="0.1.9")
    assert activation.modules == ()
    (diagnostic,) = activation.diagnostics
    assert diagnostic.code == "core-version-incompatible"
    assert (
        activate_modules(["forge_design_flowchart"], core_version="1.0.0").modules == ()
    )
    assert (
        len(activate_modules(["forge_design_flowchart"], core_version="0.9.3").modules)
        == 1
    )


def test_host_lists_reads_and_projects(tmp_path: Path) -> None:
    root = make_project(tmp_path / "project")
    (root / PATH).write_bytes(EXAMPLE.read_bytes())
    (root / "mvc/flowchart/notes.json").write_text("{}")
    host = ModuleHost(activate_modules(["forge_design_flowchart"]))
    (entry,) = host.navigation()
    assert (entry.module_id, entry.label, entry.url) == (
        "flowchart",
        "Flowchart",
        "/modules/flowchart/",
    )
    ((resource_type, listing),) = host.list_resources("flowchart", root)
    assert resource_type is FLOWCHART_RESOURCE_TYPE
    assert listing.paths == (PATH,)
    view = host.read_resource("flowchart", "flowchart", root, PATH)
    assert view.runtime_error is None and view.scene_error is None
    assert view.read is not None and view.read.error is None
    assert view.scene is not None and len(view.scene["nodes"]) == 6


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for item in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(item, ast.Import):
            names.update(alias.name for alias in item.names)
        elif isinstance(item, ast.ImportFrom) and item.module:
            names.add(item.module)
    return names


def test_module_uses_only_the_public_core_api_and_never_circuit() -> None:
    public = {"forge_design.modules", "forge_design.specialized"}
    allowed_third_party = {"pydantic", "pydantic_core", "pydantic.json_schema"}
    for path in sorted(PACKAGE.glob("*.py")):
        for name in _imports(path):
            top = name.split(".")[0]
            if top == "forge_design":
                assert name in public, f"{path.name} importe {name}"
            elif top != "forge_design_flowchart" and name not in allowed_third_party:
                # Bibliothèque standard seulement.
                assert find_spec(top) is not None and top in _stdlib(), (
                    f"{path.name} importe {name}"
                )
    shipped = [*PACKAGE.rglob("*.py"), *PACKAGE.rglob("*.js"), *PACKAGE.rglob("*.css")]
    for path in shipped:
        text = path.read_text(encoding="utf-8").lower()
        assert "circuit" not in text, path.name


def _stdlib() -> frozenset[str]:
    import sys

    return frozenset(sys.stdlib_module_names)


def test_flowchart_is_never_a_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    """Comportemental : le registre composé par le serveur, Flowchart activé, ne
    contient que les outils du cœur ; Flowchart n'apparaît que dans les modules."""
    import forge_design.web.server as server
    from forge_design.app import create_tool_registry as original

    built: list[Any] = []

    def capture() -> Any:
        registry = original()
        built.append(registry)
        return registry

    monkeypatch.setattr(server, "create_tool_registry", capture)
    server.create_application(modules=activate_modules(["forge_design_flowchart"]))
    (registry,) = built
    tools = [tool.id for tool in registry.list()]
    assert tools == [tool.id for tool in original().list()]
    assert not any("flow" in tool for tool in tools)


def test_coexistence_with_circuit(tmp_path: Path) -> None:
    """Les deux modules externes réels, activés ensemble, dans les deux ordres :
    navigation, types, actions et assets restent séparés."""
    if find_spec("forge_design_circuit") is None:
        pytest.skip(
            "ForgeDesign-Circuit non installé (dépendance de test facultative)."
        )
    for order in (
        ["forge_design_circuit", "forge_design_flowchart"],
        ["forge_design_flowchart", "forge_design_circuit"],
    ):
        activation = activate_modules(order)
        assert activation.diagnostics == ()
        host = ModuleHost(activation)
        ids = [entry.module_id for entry in host.navigation()]
        assert sorted(ids) == ["circuit", "flowchart"]
        assert [a.id for a in host.actions("flowchart")] == [
            "rename-node",
            "rename-edge",
        ]
        assert "rename-node" not in {a.id for a in host.actions("circuit")}
        with pytest.raises(KeyError):
            host.action("flowchart", "move-component")
        with pytest.raises(KeyError):
            host.action("circuit", "rename-node")
        with pytest.raises(KeyError):
            host.asset("flowchart", "circuit-editor.js")
        with pytest.raises(KeyError):
            host.asset("circuit", "flow-editor.js")
    root = make_project(tmp_path / "project")
    (root / PATH).write_bytes(EXAMPLE.read_bytes())
    (root / "mvc/circuit").mkdir()
    (root / "mvc/circuit/demo.circuit.json").write_text("{}")
    host = ModuleHost(
        activate_modules(["forge_design_circuit", "forge_design_flowchart"])
    )
    ((_, flows),) = host.list_resources("flowchart", root)
    assert flows.paths == (PATH,)
    # Flowchart ne lit pas une ressource Circuit, même nommée explicitement.
    refused = host.read_resource(
        "flowchart", "flowchart", root, "mvc/circuit/demo.circuit.json"
    )
    assert refused.scene is None
