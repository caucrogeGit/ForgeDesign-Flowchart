"""Actions rename-node et rename-edge : handlers purs, puis hôte réel de Forge Design
(révision, écriture, historique, conflit, refus) et parcours HTTP réel (303, 409,
422, 400, 403)."""

import json
import re
from collections.abc import Generator
from contextlib import contextmanager
from html import unescape
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread
from typing import Any
from urllib.parse import urlencode

import pytest
from flow_support import (
    EXAMPLE,
    PATH,
    document,
    edge,
    flow,
    history,
    make_project,
    node,
    simple,
    to_bytes,
)
from forge_design.modules import (
    ModuleActionPayload,
    ModuleActionPayloadError,
    ModuleActionRefused,
    activate_modules,
)
from forge_design.modules.actions import revision_token
from forge_design.modules.host import ModuleHost
from forge_design.recent_projects import RecentProjects
from forge_design.web.server import ForgeDesignServer, create_server

from forge_design_flowchart import (
    RENAME_EDGE,
    RENAME_NODE,
    FlowCodec,
    FlowDocument,
    rename_edge,
    rename_node,
)

CODEC = FlowCodec()


def node_payload(
    identity: str = "verifier", label: str = "Contrôler"
) -> ModuleActionPayload:
    return ModuleActionPayload({"node": identity, "label": label})


def edge_payload(identity: str = "t3", label: str = "Valide") -> ModuleActionPayload:
    return ModuleActionPayload({"edge": identity, "label": label})


def dumped(value: FlowDocument) -> dict[str, Any]:
    return json.loads(CODEC.encode(value))


# --- Handlers purs ---------------------------------------------------------------


def test_rename_node_changes_only_that_label() -> None:
    before = document()
    result = rename_node(before, node_payload())
    expected = simple()
    expected["nodes"][1]["label"] = "Contrôler"
    assert dumped(result.resource) == expected
    # Document lu intact (fonction pure).
    assert dumped(before) == simple()


def test_rename_node_trims_the_label() -> None:
    result = rename_node(document(), node_payload("fin", "  Terminé  "))
    assert result.resource.nodes[5].label == "Terminé"


@pytest.mark.parametrize("identity", ["inconnu", "t1", "Verifier"])
def test_rename_node_unknown_node_is_refused(identity: str) -> None:
    with pytest.raises(ModuleActionRefused, match=f"Nœud inconnu : {identity}."):
        rename_node(document(), node_payload(identity))


@pytest.mark.parametrize(
    ("label", "reason"),
    [
        ("", "vide"),
        ("   ", "vide"),
        ("x" * 201, "200 caractères"),
        ("a\nb", "retour à la ligne"),
        ("a\tb", "retour à la ligne"),
        ("a\u2028b", "retour à la ligne"),
    ],
)
def test_rename_node_invalid_label_is_refused(label: str, reason: str) -> None:
    with pytest.raises(ModuleActionRefused, match=reason):
        rename_node(document(), node_payload("verifier", label))


def test_rename_node_same_label_is_a_noop() -> None:
    before = document()
    for label in ("Vérifier la valeur", "  Vérifier la valeur "):
        assert rename_node(before, node_payload("verifier", label)).resource is before


def test_rename_edge_changes_only_that_label() -> None:
    before = document()
    result = rename_edge(before, edge_payload())
    expected = simple()
    expected["edges"][2]["label"] = "Valide"
    assert dumped(result.resource) == expected
    assert dumped(before) == simple()


def test_rename_edge_adds_a_first_label() -> None:
    result = rename_edge(document(), edge_payload("t6", " après "))
    assert dumped(result.resource)["edges"][5] == {
        "id": "t6",
        "source": "signaler",
        "target": "fin",
        "label": "après",
    }


@pytest.mark.parametrize("label", ["", " ", "\u00a0 "])
def test_rename_edge_empty_label_removes_it(label: str) -> None:
    result = rename_edge(document(), edge_payload("t3", label))
    assert result.resource.edges[2].label is None
    assert dumped(result.resource)["edges"][2] == {
        "id": "t3",
        "source": "valide",
        "target": "continuer",
    }
    assert b'"label": ""' not in CODEC.encode(result.resource)


def test_rename_edge_noop_cases() -> None:
    before = document()
    assert rename_edge(before, edge_payload("t3", "Oui")).resource is before
    assert rename_edge(before, edge_payload("t3", " Oui ")).resource is before
    assert rename_edge(before, edge_payload("t1", "")).resource is before


@pytest.mark.parametrize("identity", ["inconnu", "debut", "T1"])
def test_rename_edge_unknown_edge_is_refused(identity: str) -> None:
    with pytest.raises(ModuleActionRefused, match=f"Arête inconnue : {identity}."):
        rename_edge(document(), edge_payload(identity))


@pytest.mark.parametrize(
    ("label", "reason"),
    [("x" * 201, "200 caractères"), ("Oui\nNon", "retour à la ligne")],
)
def test_rename_edge_invalid_label_is_refused(label: str, reason: str) -> None:
    with pytest.raises(ModuleActionRefused, match=reason):
        rename_edge(document(), edge_payload("t3", label))


def test_payload_shape_errors_are_400_not_422() -> None:
    with pytest.raises(ModuleActionPayloadError):
        rename_node(document(), ModuleActionPayload({"label": "x"}))
    with pytest.raises(ModuleActionPayloadError):
        rename_node(document(), node_payload("x" * 65))
    with pytest.raises(ModuleActionPayloadError):
        rename_edge(document(), ModuleActionPayload({"edge": "t1"}))
    with pytest.raises(ModuleActionPayloadError):
        rename_edge(document(), edge_payload("x" * 65))


def test_rest_of_the_document_is_identical_for_every_target() -> None:
    before = document()
    for index, item in enumerate(before.nodes):
        after = dumped(rename_node(before, node_payload(item.id, "Nouveau")).resource)
        expected = simple()
        expected["nodes"][index]["label"] = "Nouveau"
        assert after == expected
    for index, item in enumerate(before.edges):
        after = dumped(rename_edge(before, edge_payload(item.id, "Nouveau")).resource)
        expected = simple()
        expected["edges"][index]["label"] = "Nouveau"
        assert after == expected


def test_declared_actions() -> None:
    assert (RENAME_NODE.id, RENAME_NODE.fields, RENAME_NODE.capability) == (
        "rename-node",
        ("node", "label"),
        "edit",
    )
    assert (RENAME_EDGE.id, RENAME_EDGE.fields, RENAME_EDGE.capability) == (
        "rename-edge",
        ("edge", "label"),
        "edit",
    )
    assert RENAME_NODE.handler is rename_node and RENAME_EDGE.handler is rename_edge
    assert RENAME_NODE.resource_type == RENAME_EDGE.resource_type == "flowchart"


# --- Hôte réel -------------------------------------------------------------------


def _host(tmp_path: Path, data: bytes | None = None) -> tuple[ModuleHost, Path]:
    root = make_project(tmp_path / "project")
    (root / PATH).write_bytes(EXAMPLE.read_bytes() if data is None else data)
    return ModuleHost(activate_modules(["forge_design_flowchart"])), root


def _token(host: ModuleHost, root: Path) -> str:
    view = host.read_resource("flowchart", "flowchart", root, PATH)
    assert view.revision_token is not None
    return view.revision_token


def _run(host: ModuleHost, root: Path, token: str, action: str, **fields: str) -> Any:
    return host.execute_action(
        "flowchart", action, root, "flowchart", PATH, token, fields
    )


def test_real_host_saves_one_node_rename(tmp_path: Path) -> None:
    host, root = _host(tmp_path)
    assert [a.id for a in host.actions("flowchart")] == ["rename-node", "rename-edge"]
    outcome = _run(
        host,
        root,
        _token(host, root),
        "rename-node",
        node="valide",
        label="Valeur correcte ?",
    )
    assert outcome.code == "saved"
    expected = simple()
    expected["nodes"][2]["label"] = "Valeur correcte ?"
    assert json.loads((root / PATH).read_text()) == expected
    # Écriture canonique du codec.
    assert (root / PATH).read_bytes() == CODEC.encode(document(expected))
    assert [line["action"] for line in history(root)] == ["write_specialized_resource"]
    assert outcome.revision is not None
    assert _token(host, root) == revision_token(
        "flowchart", "flowchart", PATH, outcome.revision
    )
    view = host.read_resource("flowchart", "flowchart", root, PATH)
    assert view.scene is not None
    assert view.scene["nodes"][2]["lines"] == ["◇ Valeur correcte ?"]


def test_real_host_saves_and_removes_an_edge_label(tmp_path: Path) -> None:
    host, root = _host(tmp_path)
    assert (
        _run(
            host, root, _token(host, root), "rename-edge", edge="t4", label="Invalide"
        ).code
        == "saved"
    )
    assert (
        _run(host, root, _token(host, root), "rename-edge", edge="t5", label="").code
        == "saved"
    )
    data = json.loads((root / PATH).read_text())
    assert data["edges"][3]["label"] == "Invalide" and "label" not in data["edges"][4]
    assert len(history(root)) == 2
    view = host.read_resource("flowchart", "flowchart", root, PATH)
    assert view.scene is not None
    labels = {e["id"]: e.get("label") for e in view.scene["edges"]}
    assert labels["t4"] == "Invalide" and labels["t5"] is None


def test_real_host_noop_conflict_and_refusals(tmp_path: Path) -> None:
    host, root = _host(tmp_path)
    stale = _token(host, root)
    before = (root / PATH).read_bytes()
    assert (
        _run(host, root, stale, "rename-node", node="fin", label="Fin").code
        == "unchanged"
    )
    assert (
        _run(host, root, stale, "rename-edge", edge="t1", label="").code == "unchanged"
    )
    assert history(root) == [] and (root / PATH).read_bytes() == before
    assert (
        _run(host, root, stale, "rename-node", node="fin", label="Terminé").code
        == "saved"
    )
    # Révision consommée : l'écriture déjà faite est préservée.
    conflict = _run(host, root, stale, "rename-node", node="fin", label="Arrêt")
    assert conflict.code == "conflict"
    assert json.loads((root / PATH).read_text())["nodes"][5]["label"] == "Terminé"
    fresh = _token(host, root)
    refused = _run(host, root, fresh, "rename-node", node="t1", label="x")
    assert refused.code == "refused" and refused.message == "Nœud inconnu : t1."
    refused = _run(host, root, fresh, "rename-edge", edge="t1", label="a\nb")
    assert refused.code == "refused"
    assert refused.message == (
        "Le libellé ne peut contenir ni retour à la ligne ni caractère de contrôle."
    )
    assert (
        _run(host, root, fresh, "rename-node", node="x" * 65, label="y").code
        == "payload-invalid"
    )
    assert _run(host, root, fresh, "rename-node", node="fin").code == "payload-invalid"
    assert len(history(root)) == 1


def test_real_host_refuses_actions_on_a_blocked_document(tmp_path: Path) -> None:
    data = simple()
    data["nodes"][1]["kind"] = "start"
    host, root = _host(tmp_path, to_bytes(data))
    view = host.read_resource("flowchart", "flowchart", root, PATH)
    assert view.read is not None and view.read.error == "invalid-resource"
    assert [issue.code for issue in view.read.issues] == ["flowchart.start-duplicate"]
    # Le document reste consultable (scène projetée) malgré le diagnostic bloquant…
    assert view.scene is not None and view.revision_token is not None
    before = (root / PATH).read_bytes()
    # … mais aucune action ne s'y applique tant qu'il n'est pas corrigé.
    outcome = _run(
        host, root, view.revision_token, "rename-node", node="fin", label="Terminé"
    )
    assert outcome.code == "resource-unusable"
    assert [issue.code for issue in outcome.issues] == ["flowchart.start-duplicate"]
    assert (root / PATH).read_bytes() == before and history(root) == []


def test_editor_context_is_exposed_by_the_real_host(tmp_path: Path) -> None:
    host, root = _host(tmp_path)
    view = host.read_resource("flowchart", "flowchart", root, PATH)
    assert view.editor_error is None and view.editor is not None
    assert view.editor["script"] == "/modules/flowchart/assets/flow-editor.js"
    assert view.editor["actions"] == {
        "rename-node": "/modules/flowchart/actions/rename-node",
        "rename-edge": "/modules/flowchart/actions/rename-edge",
    }
    assert view.editor["revision"] == view.revision_token
    # Configuration minimale : ni identités, ni libellés, ni géométrie recopiés.
    assert view.editor["config"] == {
        "renameNodeAction": "rename-node",
        "renameEdgeAction": "rename-edge",
    }
    script, media_type = host.asset("flowchart", "flow-editor.js")
    assert media_type == "text/javascript; charset=utf-8"
    assert script.startswith(b"// ForgeDesign-Flowchart")
    style, media_type = host.asset("flowchart", "flowchart.css")
    assert media_type.startswith("text/css") and style.startswith(
        b"/* ForgeDesign-Flowchart"
    )


# --- HTTP réel -------------------------------------------------------------------

ACTION = "/modules/flowchart/actions/"


@contextmanager
def serving(tmp_path: Path) -> Generator[ForgeDesignServer, None, None]:
    store = RecentProjects(tmp_path / "config/recent.json")
    modules = activate_modules(["forge_design_flowchart"])
    with create_server(port=0, recent_projects=store, modules=modules) as server:
        thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
        thread.start()
        try:
            yield server
        finally:
            server.shutdown()
            thread.join(5)


def request(
    server: ForgeDesignServer,
    method: str,
    url: str,
    fields: list[tuple[str, str]] | None = None,
    *,
    origin: str | None = "local",
) -> tuple[int, str, dict[str, str]]:
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Sec-Fetch-Site": "same-origin",
    }
    if origin is not None:
        headers["Origin"] = (
            f"http://127.0.0.1:{server.server_port}" if origin == "local" else origin
        )
    conn = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    try:
        conn.request(method, url, urlencode(fields or []).encode(), headers)
        response = conn.getresponse()
        return response.status, response.read().decode(), dict(response.getheaders())
    finally:
        conn.close()


def page(path: str = PATH, **extra: str) -> str:
    return "/modules/flowchart/resource?" + urlencode(
        {"type": "flowchart", "path": path, **extra}
    )


def token_of(server: ForgeDesignServer) -> str:
    status, html, _ = request(server, "GET", page())
    assert status == 200
    match = re.search(r'data-revision-token="([0-9a-f]{64})"', html)
    assert match is not None
    return match.group(1)


def embedded(html: str, marker: str) -> Any:
    match = re.search(rf"{marker}>(.*?)</script>", html, re.S)
    assert match is not None
    return json.loads(unescape(match.group(1)))


def envelope(revision: str, **fields: str) -> list[tuple[str, str]]:
    return [
        ("type", "flowchart"),
        ("path", PATH),
        ("revision", revision),
        *fields.items(),
    ]


@pytest.fixture
def web(tmp_path: Path) -> Generator[tuple[ForgeDesignServer, Path], None, None]:
    root = make_project(tmp_path / "project")
    (root / PATH).write_bytes(EXAMPLE.read_bytes())
    with serving(tmp_path) as server:
        assert request(server, "POST", "/inspector", [("path", str(root))])[0] == 200
        yield server, root


def test_http_resource_page_carries_scene_editor_and_style(
    web: tuple[ForgeDesignServer, Path],
) -> None:
    server, _ = web
    status, html, headers = request(server, "GET", page())
    assert status == 200
    policy = headers["Content-Security-Policy"]
    assert "script-src 'self'" in policy and "style-src 'self'" in policy
    assert (
        '<link rel="stylesheet" href="/modules/flowchart/assets/flowchart.css">' in html
    )
    scene = embedded(html, "data-graphic-scene")
    assert len(scene["nodes"]) == 6 and len(scene["edges"]) == 6
    assert [e.get("label") for e in scene["edges"]] == [
        None,
        None,
        "Oui",
        "Non",
        "suite",
        None,
    ]
    editor = embedded(html, "data-module-editor")
    assert editor["type"] == "flowchart" and editor["path"] == PATH
    assert editor["config"] == {
        "renameNodeAction": "rename-node",
        "renameEdgeAction": "rename-edge",
    }
    assert request(server, "GET", "/modules/flowchart/assets/flow-editor.js")[0] == 200


def test_http_post_redirect_get_and_history(
    web: tuple[ForgeDesignServer, Path],
) -> None:
    server, root = web
    revision = token_of(server)
    status, body, headers = request(
        server,
        "POST",
        ACTION + "rename-node",
        envelope(revision, node="verifier", label="Contrôler"),
    )
    assert status == 303 and body == ""
    assert headers["Location"] == page(notice="saved")
    status, html, _ = request(server, "GET", headers["Location"])
    assert status == 200 and "Modification enregistrée." in html
    assert json.loads((root / PATH).read_text())["nodes"][1]["label"] == "Contrôler"
    assert len(history(root)) == 1
    # Même libellé : 303 « unchanged », aucune écriture.
    status, _, headers = request(
        server,
        "POST",
        ACTION + "rename-node",
        envelope(token_of(server), node="verifier", label="Contrôler"),
    )
    assert status == 303 and headers["Location"] == page(notice="unchanged")
    assert len(history(root)) == 1
    status, _, headers = request(
        server,
        "POST",
        ACTION + "rename-edge",
        envelope(token_of(server), edge="t3", label=""),
    )
    assert status == 303 and headers["Location"] == page(notice="saved")
    assert "label" not in json.loads((root / PATH).read_text())["edges"][2]
    assert len(history(root)) == 2


def test_http_conflict_refusal_and_guards(web: tuple[ForgeDesignServer, Path]) -> None:
    server, root = web
    stale = token_of(server)
    assert (
        request(
            server,
            "POST",
            ACTION + "rename-node",
            envelope(stale, node="fin", label="Terminé"),
        )[0]
        == 303
    )
    before = (root / PATH).read_bytes()
    status, html, _ = request(
        server,
        "POST",
        ACTION + "rename-node",
        envelope(stale, node="fin", label="Arrêt"),
    )
    assert status == 409 and "data-action-error" in html
    fresh = token_of(server)
    status, html, _ = request(
        server, "POST", ACTION + "rename-node", envelope(fresh, node="ghost", label="x")
    )
    assert status == 422
    assert re.search(r"data-action-error>Nœud inconnu : ghost.<", html)
    status, html, _ = request(
        server,
        "POST",
        ACTION + "rename-edge",
        envelope(fresh, edge="t2", label="x" * 201),
    )
    assert status == 422 and "200 caractères" in html
    status, _, _ = request(
        server, "POST", ACTION + "rename-edge", envelope(fresh, edge="t2")
    )
    assert status == 400
    status, _, _ = request(
        server,
        "POST",
        ACTION + "rename-edge",
        envelope(fresh, edge="t2", label="x"),
        origin="http://evil.test",
    )
    assert status == 403
    assert (root / PATH).read_bytes() == before and len(history(root)) == 1


def test_http_only_flowchart_actions_exist(web: tuple[ForgeDesignServer, Path]) -> None:
    server, _ = web
    revision = token_of(server)
    for action in ("move-component", "create-connection", "rename-step"):
        assert (
            request(
                server,
                "POST",
                ACTION + action,
                envelope(revision, node="fin", label="x"),
            )[0]
            == 404
        )


def test_parallel_documents_are_independent(tmp_path: Path) -> None:
    host, root = _host(tmp_path)
    other = "mvc/flowchart/autre/second.flow.json"
    (root / other).parent.mkdir(parents=True)
    (root / other).write_bytes(
        CODEC.encode(document(flow([node("a"), node("b")], [edge("e", "a", "b")])))
    )
    ((_, listing),) = host.list_resources("flowchart", root)
    assert listing.paths == (other, PATH)
    first = host.read_resource("flowchart", "flowchart", root, other).revision_token
    assert first is not None
    outcome = host.execute_action(
        "flowchart",
        "rename-edge",
        root,
        "flowchart",
        other,
        first,
        {"edge": "e", "label": "ok"},
    )
    assert outcome.code == "saved"
    assert (root / PATH).read_bytes() == EXAMPLE.read_bytes()
