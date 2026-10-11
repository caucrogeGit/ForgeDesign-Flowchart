"""Script d'édition Flowchart : paquet, syntaxe et suite Node."""

import shutil
import subprocess
from importlib.resources import files
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "forge_design_flowchart/static/flow-editor.js"
SUITES = sorted((ROOT / "tests/js").glob("*.test.mjs"))


def _node() -> str:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node indisponible ; contrats statiques conservés.")
    return node


def test_script_and_style_are_packaged_as_module_resources() -> None:
    for name in ("flow-editor.js", "flowchart.css"):
        packaged = files("forge_design_flowchart").joinpath(f"static/{name}")
        assert packaged.is_file()
        assert packaged.read_bytes() == (SCRIPT.parent / name).read_bytes()


@pytest.mark.parametrize("path", [SCRIPT, *SUITES], ids=lambda path: path.name)
def test_node_check(path: Path) -> None:
    subprocess.run([_node(), "--check", str(path)], check=True, timeout=30)


def test_node_suites() -> None:
    assert [path.name for path in SUITES] == ["flow-editor.test.mjs"]
    result = subprocess.run(
        [_node(), "--test", *map(str, SUITES)],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ℹ fail 0" in result.stdout
