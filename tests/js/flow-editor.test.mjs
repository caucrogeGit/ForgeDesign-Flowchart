// Éditeur Flowchart (FD-MODULE-PILOT-001) : configuration, poignées des nœuds et des
// transitions, édition en place (Entrée, Échap, appui extérieur), POST exact, révision,
// réponses 303/409/422/500, double envoi, deux instances, actions absentes, échelle,
// gardes statiques. Moteur, DOM et navigateur simulés : le Graphic Core réel est éprouvé
// dans Forge Design et dans les navigateurs.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

import {
  createResourceEditor,
  edgeName,
  labelProblem,
  nodeName,
  readConfig,
  returnUrl,
} from "../../forge_design_flowchart/static/flow-editor.js";

const SVG = "http://www.w3.org/2000/svg";
const XHTML = "http://www.w3.org/1999/xhtml";
const NODE_ACTION = "/modules/flowchart/actions/rename-node";
const EDGE_ACTION = "/modules/flowchart/actions/rename-edge";
const PAGE = "http://127.0.0.1:8765/modules/flowchart/resource?type=flowchart&path=mvc%2Fflowchart%2Fsimple.flow.json";
const REVISION = "a".repeat(64);
const ACTIONS = Object.freeze({ "rename-node": NODE_ACTION, "rename-edge": EDGE_ACTION });
const CONFIG = Object.freeze({ renameNodeAction: "rename-node", renameEdgeAction: "rename-edge" });

class FakeElement {
  constructor(document, namespace, name) {
    this.ownerDocument = document;
    this.namespaceURI = namespace;
    this.localName = name;
    this.attributes = new Map();
    this.children = [];
    this.parent = null;
    this.listeners = [];
    this.value = "";
    this.readOnly = false;
    this.selected = false;
    this._text = "";
  }
  setAttribute(name, value) {
    if (name === "style" || name.startsWith("on")) throw new Error(`attribut interdit : ${name}`);
    this.attributes.set(name, String(value));
  }
  getAttribute(name) {
    return this.attributes.has(name) ? this.attributes.get(name) : null;
  }
  removeAttribute(name) {
    this.attributes.delete(name);
  }
  set textContent(value) {
    this._text = String(value);
  }
  get textContent() {
    return this._text;
  }
  append(...nodes) {
    for (const node of nodes) {
      node.parent = this;
      this.children.push(node);
    }
  }
  remove() {
    if (!this.parent) return;
    this.parent.children = this.parent.children.filter((child) => child !== this);
    this.parent = null;
  }
  contains(node) {
    for (let current = node; current; current = current.parent) if (current === this) return true;
    return false;
  }
  addEventListener(type, handler) {
    this.listeners.push({ type, handler });
  }
  focus(options) {
    this.focusOptions = options;
    this.ownerDocument.activeElement = this;
  }
  select() {
    this.selected = true;
  }
  // Propagation simulée : la cible, puis ses ancêtres, jusqu'à stopPropagation.
  dispatch(type, init = {}) {
    let stopped = false;
    const event = {
      type,
      key: "",
      isComposing: false,
      target: this,
      ...init,
      defaultPrevented: false,
      preventDefault() {
        this.defaultPrevented = true;
      },
      stopPropagation() {
        stopped = true;
      },
    };
    for (let current = this; current && !stopped; current = current.parent) {
      for (const { type: kind, handler } of [...current.listeners]) if (kind === type) handler(event);
    }
    return event;
  }
  find(predicate) {
    if (predicate(this)) return this;
    for (const child of this.children) {
      const found = child.find(predicate);
      if (found) return found;
    }
    return null;
  }
}

class FakeDocument {
  constructor() {
    this.activeElement = null;
    this.listeners = [];
  }
  createElementNS(namespace, name) {
    assert.ok(namespace === SVG || namespace === XHTML, namespace);
    return new FakeElement(this, namespace, name);
  }
  addEventListener(type, handler, capture) {
    this.listeners.push({ type, handler, capture });
  }
  removeEventListener(type, handler, capture) {
    this.listeners = this.listeners.filter((l) => !(l.type === type && l.handler === handler && l.capture === capture));
  }
  // Appui pointeur : écouteurs du document en capture, puis la cible.
  press(target) {
    for (const { type, handler } of [...this.listeners]) if (type === "pointerdown") handler({ type, target });
    target.dispatch("pointerdown");
  }
}

// Scène projetée par flow_scene pour trois nœuds et deux transitions.
const SCENE = Object.freeze({
  width: 608,
  height: 400,
  nodes: [
    { id: "debut", label: "Début", rect: { x: 40, y: 40, width: 208, height: 48 }, data: { kind: "start" } },
    { id: "verifier", label: "Vérifier", rect: { x: 40, y: 140, width: 208, height: 48 }, data: { kind: "step" } },
    { id: "continuer", label: "Continuer", rect: { x: 40, y: 240, width: 208, height: 48 }, data: { kind: "step" } },
  ],
  edges: [
    {
      id: "t1",
      source: "debut",
      target: "verifier",
      points: [
        { x: 144, y: 88 },
        { x: 144, y: 140 },
      ],
      label: null,
      labelAt: { x: 144, y: 114 },
    },
    {
      id: "t2",
      source: "verifier",
      target: "continuer",
      points: [
        { x: 144, y: 188 },
        { x: 144, y: 240 },
      ],
      label: "Oui",
      labelAt: { x: 167, y: 217 },
    },
  ],
});

const redirect = (url = `${PAGE}&notice=saved`) => ({ ok: true, redirected: true, status: 200, url, text: async () => "" });
const failure = (status, text = "") => ({ ok: false, redirected: false, status, url: NODE_ACTION, text: async () => text });
const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

function harness({ responses = [], actions = ACTIONS, config = CONFIG, scale = 1, hash = "", document = new FakeDocument() } = {}) {
  const calls = [];
  const navigations = [];
  const announced = [];
  const overlays = [];
  const queue = [...responses];
  const environment = {
    fetch(url, init) {
      calls.push({ url, init });
      const next = queue.shift();
      if (next === "hang") return new Promise(() => {});
      if (next instanceof Error) return Promise.reject(next);
      return Promise.resolve(next);
    },
    hash: () => hash,
    errorMessage: (text) => (text.startsWith("ALERT:") ? text.slice(6) : ""),
    navigate: (url) => navigations.push(url),
  };
  const context = Object.freeze({
    resourceType: "flowchart",
    path: "mvc/flowchart/simple.flow.json",
    revision: REVISION,
    actions: Object.freeze(actions),
    config,
    announce: (message) => announced.push(message),
  });
  const editor = createResourceEditor(context, environment);
  const nodes = new Map(SCENE.nodes.map((node) => [node.id, node]));
  const engine = {
    scene: () => SCENE,
    node: (id) => nodes.get(id) ?? null,
    viewport: () => ({ scale }),
    addOverlay(options) {
      const root = document.createElementNS(SVG, "g");
      overlays.push({ root, options });
      return { root, remove() {} };
    },
  };
  if (editor) editor.attach(engine);
  const root = overlays[0]?.root ?? null;
  const items = () => (root ? root.children.filter((child) => child.getAttribute("role") === "button") : []);
  const item = (label) => items().find((element) => element.getAttribute("aria-label") === label);
  const field = () => (root ? root.find((element) => element.localName === "input") : null);
  const group = () => (root ? root.children.find((child) => child.getAttribute("class") === "flow-editor") ?? null : null);
  const press = (element, key, extra = {}) => element.dispatch("keydown", { key, ...extra });
  const sent = (index = 0) => [...calls[index].init.body.entries()];
  return { editor, engine, document, calls, navigations, announced, overlays, root, items, item, field, group, press, sent };
}

const DEBUT = "Renommer le nœud « Début » (début)";
const VERIFIER = "Renommer le nœud « Vérifier » (étape)";
const T1 = "Transition Début → Vérifier, sans libellé";
const T2 = "Transition Vérifier → Continuer — Oui";

test("configuration : forme exacte exigée", () => {
  assert.deepEqual(readConfig(CONFIG), CONFIG);
  assert.ok(Object.isFrozen(readConfig(CONFIG)));
  assert.deepEqual(readConfig({ renameNodeAction: "rename-node" }), { renameNodeAction: "rename-node", renameEdgeAction: null });
  for (const bad of [
    null,
    "x",
    [],
    {},
    { renameNodeAction: "" },
    { renameNodeAction: "Rename" },
    { renameNodeAction: 3 },
    { ...CONFIG, nodes: [] },
    { ...CONFIG, revision: REVISION },
  ]) {
    assert.throws(() => readConfig(bad), /configuration Flowchart invalide/);
  }
});

test("règle des libellés identique au modèle Python", () => {
  assert.equal(labelProblem("Oui"), null);
  assert.equal(labelProblem("x".repeat(200)), null);
  assert.match(labelProblem(""), /vide/);
  assert.match(labelProblem("x".repeat(201)), /200 caractères/);
  for (const value of ["a\nb", "a\tb", "a\u0085b", "a\u2028b", "a\u007fb"]) assert.match(labelProblem(value), /retour à la ligne/);
});

test("noms accessibles et adresse de retour", () => {
  assert.equal(edgeName("Vérifier", "Continuer", "Oui"), T2);
  assert.equal(edgeName("Début", "Vérifier", null), T1);
  assert.equal(nodeName("Valeur ?", "decision"), "Renommer le nœud « Valeur ? » (décision)");
  assert.equal(nodeName("X", "inconnu"), "Renommer le nœud « X »");
  assert.equal(nodeName("X", "constructor"), "Renommer le nœud « X »");
  assert.equal(returnUrl(`${PAGE}&notice=saved`, "node", "a b"), `${PAGE}&notice=saved#flow-node=a%20b`);
  assert.equal(returnUrl(`${PAGE}#old`, "edge", "t2"), `${PAGE}#flow-edge=t2`);
});

test("initialisation : un calque, une poignée focalisable par nœud et par transition", () => {
  const h = harness();
  assert.equal(h.overlays.length, 1);
  assert.equal(h.overlays[0].options.label, "Libellés de l'organigramme");
  assert.deepEqual(
    h.items().map((element) => element.getAttribute("aria-label")),
    [DEBUT, VERIFIER, "Renommer le nœud « Continuer » (étape)", T1, T2],
  );
  for (const element of h.items()) {
    assert.equal(element.getAttribute("tabindex"), "0");
    assert.equal(element.getAttribute("class"), "gx-overlay-item");
    assert.equal(element.children[0].localName, "title");
  }
  // Poignée de nœud au coin supérieur droit ; poignée de transition à labelAt.
  const handle = h.item(DEBUT).children.find((c) => c.getAttribute("class") === "gx-overlay-handle");
  assert.deepEqual([handle.getAttribute("cx"), handle.getAttribute("cy"), handle.getAttribute("r")], ["248", "40", "6"]);
  const edge = h.item(T2);
  const line = edge.children.find((c) => c.localName === "polyline" && c.getAttribute("pointer-events") === "stroke");
  assert.equal(line.getAttribute("points"), "144,188 144,240");
  assert.equal(line.getAttribute("stroke"), "transparent");
  const edgeHandle = edge.children.find((c) => c.getAttribute("class") === "gx-overlay-handle");
  assert.deepEqual([edgeHandle.getAttribute("cx"), edgeHandle.getAttribute("cy")], ["167", "217"]);
  assert.match(h.announced[0], /Entrée pour enregistrer, Échap pour annuler/);
  assert.equal(h.editor.editing(), null);
  assert.equal(h.calls.length, 0);
});

test("édition d'un nœud au clavier : Entrée ouvre, Entrée enregistre, POST exact", async () => {
  const h = harness({ responses: [redirect()] });
  const opened = h.press(h.item(VERIFIER), "Enter");
  assert.ok(opened.defaultPrevented);
  const input = h.field();
  assert.equal(input.namespaceURI, XHTML);
  assert.equal(input.value, "Vérifier");
  assert.equal(input.getAttribute("aria-label"), "Nouveau libellé du nœud « Vérifier »");
  assert.equal(input.getAttribute("maxlength"), "200");
  assert.ok(input.selected);
  assert.equal(h.document.activeElement, input);
  assert.deepEqual(input.focusOptions, { preventScroll: true });
  assert.deepEqual(h.editor.editing(), { kind: "node", id: "verifier", value: "Vérifier" });
  // Champ centré sur le nœud, contre-mis à l'échelle.
  assert.equal(h.group().getAttribute("transform"), "translate(144 164) scale(1)");
  const frame = h.group().children[0];
  assert.equal(frame.localName, "foreignObject");
  assert.deepEqual(
    ["x", "y", "width", "height"].map((name) => frame.getAttribute(name)),
    ["-150", "-20", "300", "40"],
  );
  input.value = "  Vérifier la valeur  ";
  const saved = h.press(input, "Enter");
  assert.ok(saved.defaultPrevented);
  await settle();
  assert.equal(h.calls.length, 1);
  assert.equal(h.calls[0].url, NODE_ACTION);
  assert.deepEqual(
    { ...h.calls[0].init, body: undefined },
    { method: "POST", body: undefined, credentials: "same-origin", redirect: "follow" },
  );
  assert.deepEqual(h.sent(), [
    ["type", "flowchart"],
    ["path", "mvc/flowchart/simple.flow.json"],
    ["revision", REVISION],
    ["node", "verifier"],
    ["label", "Vérifier la valeur"],
  ]);
  assert.deepEqual(h.navigations, [`${PAGE}&notice=saved#flow-node=verifier`]);
  assert.match(h.announced.at(-1), /enregistré : rechargement/);
  // Aucun second envoi avant la nouvelle révision.
  assert.equal(h.editor.pending(), true);
  h.press(input, "Enter");
  h.press(h.item(DEBUT), "Enter");
  await settle();
  assert.equal(h.calls.length, 1);
});

test("édition d'une transition : libellé vide envoyé pour le supprimer", async () => {
  const h = harness({ responses: [redirect(), redirect()] });
  h.press(h.item(T2), "Enter");
  const input = h.field();
  assert.equal(input.value, "Oui");
  assert.equal(input.getAttribute("aria-label"), "Libellé de la transition Vérifier → Continuer (vide : sans libellé)");
  assert.equal(h.group().getAttribute("transform"), "translate(167 217) scale(1)");
  input.value = "   ";
  h.press(input, "Enter");
  await settle();
  assert.equal(h.calls[0].url, EDGE_ACTION);
  assert.deepEqual(h.sent().slice(3), [
    ["edge", "t2"],
    ["label", ""],
  ]);
  assert.deepEqual(h.navigations, [`${PAGE}&notice=saved#flow-edge=t2`]);
});

test("transition sans libellé : un premier libellé, ouverture au clic", async () => {
  const h = harness({ responses: [redirect()] });
  h.item(T1).dispatch("click");
  const input = h.field();
  assert.equal(input.value, "");
  input.value = "suite";
  h.press(input, "Enter");
  await settle();
  assert.deepEqual(h.sent().slice(3), [
    ["edge", "t1"],
    ["label", "suite"],
  ]);
});

test("Échap annule sans envoi et rend le focus à la poignée", async () => {
  const h = harness();
  h.press(h.item(VERIFIER), "Enter");
  const input = h.field();
  input.value = "Autre";
  const escape = h.press(input, "Escape");
  assert.ok(escape.defaultPrevented);
  await settle();
  assert.equal(h.field(), null);
  assert.equal(h.editor.editing(), null);
  assert.equal(h.calls.length, 0);
  assert.equal(h.document.activeElement, h.item(VERIFIER));
  assert.deepEqual(h.item(VERIFIER).focusOptions, { preventScroll: true });
  assert.equal(h.announced.at(-1), "Modification du libellé annulée.");
});

test("les touches du champ ne remontent ni au moteur ni aux poignées", () => {
  const h = harness();
  const seen = [];
  h.root.addEventListener("keydown", (event) => seen.push(event.key));
  h.press(h.item(VERIFIER), "Enter");
  const input = h.field();
  for (const key of ["a", "ArrowLeft", "Enter", "Escape"]) {
    h.press(input, key, key === "ArrowLeft" ? { shiftKey: true } : {});
  }
  // Seule la touche Entrée de la poignée (avant l'ouverture) atteint le calque.
  assert.deepEqual(seen, ["Enter"]);
});

test("composition en cours : Entrée ne soumet pas", async () => {
  const h = harness({ responses: [redirect()] });
  h.press(h.item(VERIFIER), "Enter");
  h.field().value = "Vérifié";
  h.press(h.field(), "Enter", { isComposing: true });
  await settle();
  assert.equal(h.calls.length, 0);
  assert.ok(h.editor.editing());
});

test("bouton ✓ et bouton ✕", async () => {
  const h = harness({ responses: [redirect()] });
  h.press(h.item(DEBUT), "Enter");
  const cancel = h.root.find((e) => e.getAttribute("class") === "flow-editor-cancel");
  assert.equal(cancel.getAttribute("aria-label"), "Annuler");
  cancel.dispatch("click");
  assert.equal(h.field(), null);
  h.press(h.item(DEBUT), "Enter");
  h.field().value = "Départ";
  const save = h.root.find((e) => e.getAttribute("class") === "flow-editor-save");
  assert.equal(save.getAttribute("type"), "button");
  save.dispatch("click");
  await settle();
  assert.deepEqual(h.sent().slice(3), [
    ["node", "debut"],
    ["label", "Départ"],
  ]);
});

test("appui hors du champ : annulation, jamais d'enregistrement implicite", async () => {
  const h = harness();
  h.press(h.item(VERIFIER), "Enter");
  h.field().value = "Modifié";
  // Appui dans le champ : rien ne change.
  h.document.press(h.field());
  assert.ok(h.editor.editing());
  // Appui ailleurs (une autre poignée) : annulation, puis le clic ouvre l'autre.
  h.document.press(h.item(DEBUT));
  assert.equal(h.editor.editing(), null);
  assert.equal(h.document.listeners.length, 0);
  h.item(DEBUT).dispatch("click");
  assert.deepEqual(h.editor.editing(), { kind: "node", id: "debut", value: "Début" });
  await settle();
  assert.equal(h.calls.length, 0);
});

test("un seul champ à la fois ; rouvrir le même élément le conserve", () => {
  const h = harness();
  h.press(h.item(VERIFIER), "Enter");
  h.field().value = "Brouillon";
  h.press(h.item(VERIFIER), "Enter");
  assert.equal(h.field().value, "Brouillon");
  h.press(h.item(T2), "Enter");
  assert.equal(h.root.children.filter((c) => c.getAttribute("class") === "flow-editor").length, 1);
  assert.equal(h.field().value, "Oui");
  assert.equal(h.document.listeners.length, 1);
});

test("libellé inchangé ou invalide : aucun envoi", async () => {
  const h = harness();
  h.press(h.item(VERIFIER), "Enter");
  h.field().value = " Vérifier ";
  h.press(h.field(), "Enter");
  await settle();
  assert.equal(h.calls.length, 0);
  assert.equal(h.field(), null);
  assert.equal(h.announced.at(-1), "Libellé inchangé : aucune modification.");
  // Nœud : vide refusé, champ conservé, marqué invalide.
  h.press(h.item(VERIFIER), "Enter");
  h.field().value = "   ";
  h.press(h.field(), "Enter");
  await settle();
  assert.equal(h.calls.length, 0);
  assert.equal(h.field().getAttribute("aria-invalid"), "true");
  assert.match(h.announced.at(-1), /vide/);
  h.field().dispatch("input");
  assert.equal(h.field().getAttribute("aria-invalid"), null);
  h.field().value = "x".repeat(201);
  h.press(h.field(), "Enter");
  await settle();
  assert.equal(h.calls.length, 0);
  assert.match(h.announced.at(-1), /200 caractères/);
  // Transition déjà sans libellé, laissée vide : inchangée.
  h.press(h.item(T1), "Enter");
  h.press(h.field(), "Enter");
  await settle();
  assert.equal(h.calls.length, 0);
  assert.equal(h.announced.at(-1), "Libellé inchangé : aucune modification.");
});

test("409 : conflit annoncé, champ conservé, nouvel essai possible", async () => {
  const h = harness({ responses: [failure(409, "ALERT:La ressource a changé depuis son affichage."), redirect()] });
  h.press(h.item(VERIFIER), "Enter");
  h.field().value = "Contrôler";
  h.press(h.field(), "Enter");
  assert.equal(h.editor.pending(), true);
  assert.equal(h.field().readOnly, true);
  assert.equal(h.field().getAttribute("aria-busy"), "true");
  await settle();
  assert.equal(h.announced.at(-1), "La ressource a changé depuis son affichage.");
  assert.equal(h.editor.pending(), false);
  assert.equal(h.field().readOnly, false);
  assert.equal(h.field().getAttribute("aria-busy"), null);
  assert.equal(h.field().getAttribute("aria-invalid"), null);
  assert.equal(h.field().value, "Contrôler");
  assert.equal(h.navigations.length, 0);
  h.press(h.field(), "Enter");
  await settle();
  assert.equal(h.calls.length, 2);
  // La révision envoyée reste celle du contexte : seule la page rechargée en apporte une autre.
  assert.deepEqual(h.sent(1)[2], ["revision", REVISION]);
});

test("422 : message de l'hôte, champ marqué invalide", async () => {
  const h = harness({ responses: [failure(422, "ALERT:Nœud inconnu : verifier.")] });
  h.press(h.item(VERIFIER), "Enter");
  h.field().value = "Contrôler";
  h.press(h.field(), "Enter");
  await settle();
  assert.equal(h.announced.at(-1), "Nœud inconnu : verifier.");
  assert.equal(h.field().getAttribute("aria-invalid"), "true");
  assert.ok(h.editor.editing());
});

test("500, statut inattendu, page illisible et serveur injoignable", async () => {
  const h = harness({
    responses: [failure(500), failure(418), { ...failure(400), text: async () => Promise.reject(new Error("x")) }, new Error("réseau")],
  });
  h.press(h.item(VERIFIER), "Enter");
  h.field().value = "Contrôler";
  const expected = [
    "Erreur du serveur pendant l'enregistrement : rechargez la page avant de réessayer.",
    "Libellé non enregistré (erreur 418).",
    "Libellé refusé : requête invalide.",
    "Serveur injoignable : libellé non enregistré.",
  ];
  for (const message of expected) {
    h.press(h.field(), "Enter");
    await settle();
    assert.equal(h.announced.at(-1), message);
    assert.equal(h.editor.pending(), false);
  }
  assert.equal(h.calls.length, 4);
  assert.equal(h.navigations.length, 0);
});

test("réponse 200 sans redirection : jamais prise pour un enregistrement", async () => {
  const h = harness({ responses: [{ ok: true, redirected: false, status: 200, url: NODE_ACTION, text: async () => "" }] });
  h.press(h.item(VERIFIER), "Enter");
  h.field().value = "Contrôler";
  h.press(h.field(), "Enter");
  await settle();
  assert.equal(h.navigations.length, 0);
  assert.equal(h.announced.at(-1), "Libellé non enregistré (erreur 200).");
  assert.equal(h.editor.pending(), false);
  assert.ok(h.editor.editing());
});

test("double envoi : une seule requête pendant l'attente, Échap sans effet", async () => {
  const h = harness({ responses: ["hang"] });
  h.press(h.item(VERIFIER), "Enter");
  h.field().value = "Contrôler";
  h.press(h.field(), "Enter");
  h.press(h.field(), "Enter");
  h.root.find((e) => e.getAttribute("class") === "flow-editor-save").dispatch("click");
  h.press(h.field(), "Escape");
  h.document.press(h.item(DEBUT));
  h.press(h.item(DEBUT), "Enter");
  await settle();
  assert.equal(h.calls.length, 1);
  assert.deepEqual(h.editor.editing(), { kind: "node", id: "verifier", value: "Contrôler" });
});

test("deux instances : états, calques et envois indépendants", async () => {
  const document = new FakeDocument();
  const a = harness({ document, responses: ["hang"] });
  const b = harness({ document, responses: [redirect()] });
  assert.notEqual(a.root, b.root);
  a.press(a.item(VERIFIER), "Enter");
  a.field().value = "A";
  a.press(a.field(), "Enter");
  assert.equal(a.editor.pending(), true);
  assert.equal(b.editor.pending(), false);
  assert.equal(b.editor.editing(), null);
  b.press(b.item(T2), "Enter");
  b.field().value = "B";
  b.press(b.field(), "Enter");
  await settle();
  assert.equal(a.calls.length, 1);
  assert.equal(b.calls.length, 1);
  assert.deepEqual(b.sent().slice(3), [
    ["edge", "t2"],
    ["label", "B"],
  ]);
  assert.equal(a.navigations.length, 0);
  assert.equal(b.navigations.length, 1);
  assert.deepEqual(a.editor.editing(), { kind: "node", id: "verifier", value: "A" });
});

test("actions absentes : consultation seule, ou seulement le type exposé", () => {
  assert.equal(harness({ actions: {} }).editor, null);
  assert.equal(harness({ actions: { other: "/modules/flowchart/actions/other" } }).editor, null);
  const nodesOnly = harness({ actions: { "rename-node": NODE_ACTION } });
  assert.deepEqual(
    nodesOnly.items().map((e) => e.getAttribute("aria-label")),
    [DEBUT, VERIFIER, "Renommer le nœud « Continuer » (étape)"],
  );
  const edgesOnly = harness({ actions: { "rename-edge": EDGE_ACTION } });
  assert.deepEqual(
    edgesOnly.items().map((e) => e.getAttribute("aria-label")),
    [T1, T2],
  );
  assert.throws(() => harness({ config: { renameNodeAction: 1 } }), /configuration Flowchart invalide/);
});

test("échelle : poignées, zones et champ gardent leur taille écran", () => {
  const h = harness({ scale: 2 });
  const circle = (label, name) => h.item(label).children.find((c) => c.getAttribute("class") === name);
  assert.equal(circle(DEBUT, "gx-overlay-handle").getAttribute("r"), "3");
  assert.equal(circle(DEBUT, "gx-overlay-hit").getAttribute("r"), "6");
  const line = h.item(T2).children.find((c) => c.getAttribute("pointer-events") === "stroke");
  assert.equal(line.getAttribute("stroke-width"), "6");
  h.press(h.item(VERIFIER), "Enter");
  assert.equal(h.group().getAttribute("transform"), "translate(144 164) scale(0.5)");
  h.editor.onViewChange({ scale: 0.5, x: 0, y: 0, width: 800, height: 480, detailLevel: "normal" });
  assert.equal(circle(DEBUT, "gx-overlay-handle").getAttribute("r"), "12");
  assert.equal(line.getAttribute("stroke-width"), "24");
  assert.equal(h.group().getAttribute("transform"), "translate(144 164) scale(2)");
  // Échelle invalide : repli sur 1, jamais de division par zéro.
  h.editor.onViewChange({ scale: 0, detailLevel: "normal" });
  assert.equal(circle(DEBUT, "gx-overlay-handle").getAttribute("r"), "6");
});

test("onViewChange avant attach : sans effet", () => {
  const document = new FakeDocument();
  const editor = createResourceEditor(
    Object.freeze({ resourceType: "flowchart", path: "p", revision: REVISION, actions: ACTIONS, config: CONFIG, announce() {} }),
    { fetch() {}, hash: () => "", errorMessage: () => "", navigate() {} },
  );
  editor.onViewChange({ scale: 3, detailLevel: "normal" });
  assert.equal(document.listeners.length, 0);
});

test("retour après enregistrement : focus rendu à la poignée de l'élément renommé", () => {
  const node = harness({ hash: "#flow-node=verifier" });
  assert.equal(node.document.activeElement, node.item(VERIFIER));
  assert.deepEqual(node.item(VERIFIER).focusOptions, { preventScroll: true });
  const edge = harness({ hash: "#flow-edge=t2" });
  assert.equal(edge.document.activeElement, edge.item(T2));
  for (const hash of ["#flow-node=inconnu", "#flow-node=%E0%A4%A", "#autre", ""]) {
    assert.equal(harness({ hash }).document.activeElement, null);
  }
});

test("gardes statiques : API publique seulement, aucun DOM privé, ni CDN, ni Circuit", async () => {
  const source = await readFile(new URL("../../forge_design_flowchart/static/flow-editor.js", import.meta.url), "utf8");
  for (const forbidden of [
    "prompt(",
    "alert(",
    "confirm(",
    "innerHTML",
    "outerHTML",
    "insertAdjacent",
    "eval(",
    "Function(",
    "import(",
    "import ",
    "https://",
    "cdn",
    "document.cookie",
    "localStorage",
    "sessionStorage",
    "/modules/",
    "/graphics/",
    "viewBox",
    "createElement(",
    ".style",
    "querySelector(",
    "getElementsBy",
    // Aucune remontée dans le DOM privé du moteur : seul le calque fourni est utilisé.
    "parentNode",
    "parentElement",
    "closest(",
    "ownerSVGElement",
    "gx-node",
    "gx-edge",
    "gx-scene",
    "circuit",
    "Circuit",
    "react",
    "jquery",
    "focusin",
    "focusout",
    '"focus"',
    '"blur"',
    "globalThis.document",
    "window.",
  ]) {
    const allowed = forbidden === "querySelector(" ? source.split("querySelector(").length - 1 === 1 : false;
    assert.ok(!source.includes(forbidden) || allowed, forbidden);
  }
  // Seul querySelector : page d'erreur analysée par DOMParser, jamais le document.
  assert.match(source, /parsed\.querySelector\("\[data-action-error\]"\)/);
  // Éléments créés seulement dans le document du calque fourni par le moteur.
  assert.equal(source.split("createElementNS(").length - 1, 1);
  assert.match(source, /overlay\.root\.ownerDocument\.createElementNS\(namespace, name\)/);
  // Un seul envoi, vers une URL d'action du contexte.
  assert.equal(source.split("fetch(").length - 1, 2);
  assert.match(source, /return environment\.fetch\(url, /);
  assert.match(source, /context\.actions\[config\.renameNodeAction\]/);
  assert.match(source, /context\.actions\[config\.renameEdgeAction\]/);
  // Géométrie et libellés lus dans la scène validée ; aucune sélection d'arête demandée.
  assert.match(source, /engine\.scene\(\)/);
  for (const forbidden of ["engine.select", "selectEdge", "engine.focus", "nodeMove", "worldAt"]) {
    assert.ok(!source.includes(forbidden), forbidden);
  }
  // Seul écouteur global : l'appui hors du champ, en capture, retiré à la fermeture.
  assert.equal(source.split("ownerDocument.addEventListener(").length - 1, 1);
  assert.equal(source.split("ownerDocument.removeEventListener(").length - 1, 1);
  // Aucun état de module : rien de mutable hors de createResourceEditor.
  const top = source.slice(0, source.indexOf("export function createResourceEditor"));
  assert.ok(!/^(let|var) /m.test(top));
});

test("feuille du module : classes propres seulement, aucune ressource externe", async () => {
  const css = await readFile(new URL("../../forge_design_flowchart/static/flowchart.css", import.meta.url), "utf8");
  const selectors = css
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .split("}")
    .map((block) => block.split("{")[0].trim())
    .filter(Boolean);
  for (const group of selectors) {
    for (const selector of group.split(",")) {
      const classes = selector.match(/\.[a-z-]+/g) ?? [];
      assert.ok(classes.length > 0, selector);
      // La classe visée est toujours une classe flow-* ; gx-overlay-item (classe générique
      // publique du calque) n'apparaît qu'en ancêtre.
      assert.match(classes.at(-1), /^\.flow-/, selector);
      for (const name of classes) assert.ok(/^\.(flow-|gx-overlay-item$)/.test(name), selector);
    }
  }
  for (const forbidden of ["@import", "url(", "http", "expression("]) assert.ok(!css.includes(forbidden), forbidden);
});
