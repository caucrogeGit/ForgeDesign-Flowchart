"""Distribution forge-design-flowchart : version, double contrainte sur le cœur
(FD-RELEASE-001), fichiers livrés, sources sans caractère invisible."""

import re
import tomllib
from importlib.metadata import metadata, requires, version
from pathlib import Path

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version

import forge_design_flowchart
from forge_design_flowchart import FORGE_DESIGN_MODULE, FORGE_DESIGN_REQUIREMENT

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "forge_design_flowchart"
CONFIG = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def _core(items: list[str]) -> list[Requirement]:
    return [
        Requirement(item) for item in items if Requirement(item).name == "forge-design"
    ]


def test_version_has_a_single_source() -> None:
    project = CONFIG["project"]
    assert project["name"] == "forge-design-flowchart"
    assert "version" not in project and "version" in project["dynamic"]
    assert CONFIG["tool"]["setuptools"]["dynamic"]["version"] == {
        "attr": "forge_design_flowchart.__version__"
    }
    assert forge_design_flowchart.__version__ == "0.1.0"
    assert str(Version(forge_design_flowchart.__version__)) == "0.1.0"
    assert version("forge-design-flowchart") == "0.1.0"
    assert metadata("forge-design-flowchart")["Name"] == "forge-design-flowchart"


def test_core_requirement_matches_the_distribution_dependency() -> None:
    """Requires-Dist (première barrière, pip) et requires_forge_design (seconde
    barrière, activation) ne divergent jamais."""
    (declared,) = _core(CONFIG["project"]["dependencies"])
    assert declared.specifier == SpecifierSet(FORGE_DESIGN_REQUIREMENT)
    assert FORGE_DESIGN_MODULE.requires_forge_design == FORGE_DESIGN_REQUIREMENT
    assert FORGE_DESIGN_REQUIREMENT == ">=0.2.0,<1"
    (installed,) = _core(requires("forge-design-flowchart") or [])
    assert installed.specifier == SpecifierSet(FORGE_DESIGN_REQUIREMENT)
    # Le cœur installé satisfait la contrainte ; aucune dépendance Circuit.
    assert version("forge-design") in SpecifierSet(FORGE_DESIGN_REQUIREMENT)
    names = {
        Requirement(item).name for item in requires("forge-design-flowchart") or []
    }
    assert "forge-design-circuit" not in names
    assert {Requirement(item).name for item in CONFIG["project"]["dependencies"]} == {
        "forge-design",
        "pydantic",
    }


def test_shipped_files() -> None:
    assert CONFIG["tool"]["setuptools"]["packages"] == ["forge_design_flowchart"]
    data = CONFIG["tool"]["setuptools"]["package-data"]["forge_design_flowchart"]
    assert data == ["py.typed", "static/*.js", "static/*.css"]
    # Paquet typé : marqueur PEP 561 présent.
    assert (PACKAGE / "py.typed").is_file()
    # Chaque asset déclaré existe et relève des motifs livrés.
    for asset in FORGE_DESIGN_MODULE.assets:
        assert (PACKAGE / asset.source).is_file(), asset.source
        assert any(Path(asset.source).match(pattern) for pattern in data)
    assert sorted(p.name for p in (PACKAGE / "static").iterdir()) == [
        "flow-editor.js",
        "flowchart.css",
    ]


def test_sources_contain_no_invisible_line_breaks() -> None:
    """Un séparateur de ligne Unicode littéral casse une expression rationnelle
    JavaScript ; les sources les écrivent toujours en échappement."""
    invisible = re.compile(r"[\u2028\u2029\u0085\u00a0]")
    paths = [
        *PACKAGE.rglob("*.py"),
        *PACKAGE.rglob("*.js"),
        *PACKAGE.rglob("*.css"),
        *(ROOT / "tests").rglob("*.py"),
        *(ROOT / "tests").rglob("*.mjs"),
    ]
    assert paths
    for path in paths:
        assert not invisible.search(path.read_text(encoding="utf-8")), path.name


def test_readme_states_the_contract() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "module externe" in readme.lower()
    assert "forge-design>=0.2.0,<1" in readme
    assert "MODULE_API_VERSION = 1" in readme
    assert "forge-design --module forge_design_flowchart" in readme
