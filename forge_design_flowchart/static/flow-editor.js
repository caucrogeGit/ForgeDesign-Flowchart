// ForgeDesign-Flowchart — éditeur de ressource : renommer un nœud ou une arête
// (FD-MODULE-PILOT-001).
// Module ES déclaré par le descripteur (editor_script), importé par le client générique
// de Forge Design depuis l'URL calculée par l'hôte. Il ne crée pas de moteur et ne lit
// que l'API publique : la scène validée (engine.scene(), engine.node()), un calque monde
// (addOverlay), l'échelle (viewport(), onViewChange) et le contexte de l'hôte (URL
// d'action, révision, annonce).
// - nœuds : une poignée focalisable par nœud dans le calque, au coin supérieur droit ;
// - arêtes : le Graphic Core ne sélectionne pas d'arête ; le calque porte, pour chaque
//   arête, une zone de détection transparente le long du segment et une poignée au point
//   d'ancrage du libellé (labelAt), dans un seul élément focalisable ;
// - édition en place : Entrée (ou clic) sur une poignée ouvre un champ HTML dans un
//   foreignObject du calque, contre-mis à l'échelle (taille écran stable quel que soit le
//   zoom) ; Entrée enregistre, Échap annule, un appui hors du champ annule. Aucun
//   enregistrement implicite, aucune dépendance aux événements focus ou blur ;
// - envoi : une action rename-node ou rename-edge (formulaire encodé, révision du
//   contexte), au plus une à la fois. Succès : rechargement de la page ressource, focus
//   rendu à la poignée de l'élément renommé. Échec : message annoncé, champ conservé.
// Aucun état global : tout appartient à l'instance créée par createResourceEditor.

const SVG_NS = "http://www.w3.org/2000/svg";
const XHTML_NS = "http://www.w3.org/1999/xhtml";
// Fragment de retour après rechargement : poignée à refocaliser.
const RETURN_PREFIX = Object.freeze({ node: "#flow-node=", edge: "#flow-edge=" });
const MAX_LABEL_CHARS = 200;
const MAX_MESSAGE_CHARS = 300;
// Tailles écran stables, converties en unités monde par l'échelle.
const HANDLE_PX = 6;
const HIT_PX = 12;
const EDGE_HIT_PX = 6;
const FIELD_WIDTH = 300;
const FIELD_HEIGHT = 40;
// Mêmes règles que le modèle Python (label_problem) : une ligne, sans contrôle.
const FORBIDDEN = /[\u0000-\u001f\u007f-\u009f\u2028\u2029]/;
const KIND_NAMES = Object.freeze({ start: "début", step: "étape", decision: "décision", end: "fin" });
const HELP =
  "Libellés : Tab jusqu'à la poignée d'un nœud ou à une transition, Entrée (ou clic) pour modifier, " +
  "Entrée pour enregistrer, Échap pour annuler.";
const FALLBACK = Object.freeze({
  400: "Libellé refusé : requête invalide.",
  403: "Libellé refusé : origine non autorisée.",
  404: "Renommage indisponible pour cette ressource.",
  409: "La ressource a changé depuis son affichage : rechargez la page.",
  413: "Libellé refusé par le serveur.",
  415: "Libellé refusé par le serveur.",
  422: "Libellé refusé par la validation de l'organigramme.",
  500: "Erreur du serveur pendant l'enregistrement : rechargez la page avant de réessayer.",
});

// Configuration produite par flow_editor_config (Python) ; toute autre forme est refusée.
export function readConfig(raw) {
  const invalid = () => new Error("configuration Flowchart invalide");
  if (raw === null || typeof raw !== "object" || Array.isArray(raw)) throw invalid();
  if (Object.keys(raw).some((key) => key !== "renameNodeAction" && key !== "renameEdgeAction")) throw invalid();
  const action = (value) => {
    if (value === undefined) return null;
    if (typeof value !== "string" || !/^[a-z][a-z0-9-]{0,47}$/.test(value)) throw invalid();
    return value;
  };
  const config = { renameNodeAction: action(raw.renameNodeAction), renameEdgeAction: action(raw.renameEdgeAction) };
  if (config.renameNodeAction === null && config.renameEdgeAction === null) throw invalid();
  return Object.freeze(config);
}

// Raison du refus d'un libellé déjà débarrassé de ses espaces de tête et de fin, ou null.
export function labelProblem(value) {
  if (!value) return "Le libellé ne peut pas être vide.";
  if (value.length > MAX_LABEL_CHARS) return `Le libellé dépasse ${MAX_LABEL_CHARS} caractères.`;
  if (FORBIDDEN.test(value)) return "Le libellé ne peut contenir ni retour à la ligne ni caractère de contrôle.";
  return null;
}

// Nom accessible d'une transition : « Transition Vérifier → Continuer — Oui ».
export function edgeName(sourceLabel, targetLabel, label) {
  const base = `Transition ${sourceLabel} → ${targetLabel}`;
  return label === null ? `${base}, sans libellé` : `${base} — ${label}`;
}

export function nodeName(label, kind) {
  const name = Object.hasOwn(KIND_NAMES, kind) ? KIND_NAMES[kind] : null;
  return name ? `Renommer le nœud « ${label} » (${name})` : `Renommer le nœud « ${label} »`;
}

// Adresse de rechargement : page ressource renvoyée par l'hôte, fragment de retour.
export function returnUrl(url, kind, id) {
  const target = new URL(url);
  target.hash = `${RETURN_PREFIX[kind].slice(1)}${encodeURIComponent(id)}`;
  return target.href;
}

function bounded(text) {
  const clean = String(text).replace(/\s+/g, " ").trim();
  return clean.length > MAX_MESSAGE_CHARS ? `${clean.slice(0, MAX_MESSAGE_CHARS - 1)}…` : clean;
}

function formatPoints(points) {
  return points.map((point) => `${point.x},${point.y}`).join(" ");
}

function middle(points) {
  const first = points[0];
  const last = points[points.length - 1];
  return { x: (first.x + last.x) / 2, y: (first.y + last.y) / 2 };
}

// Environnement navigateur ; les tests en fournissent un autre.
export function browserEnvironment() {
  const location = globalThis.location;
  return {
    fetch: (url, init) => globalThis.fetch(url, init),
    hash: () => location.hash,
    // Analyse inerte (DOMParser n'exécute rien) du message de la page d'erreur du cœur.
    errorMessage(text) {
      const parsed = new globalThis.DOMParser().parseFromString(text, "text/html");
      const node = parsed.querySelector("[data-action-error]");
      return node ? node.textContent : "";
    },
    // Même adresse (même notice) : un simple changement de fragment ne rechargerait
    // pas la page ; on remplace l'entrée d'historique puis on recharge.
    navigate(url) {
      const target = new URL(url, location.href);
      const here = new URL(location.href);
      if (target.origin === here.origin && target.pathname === here.pathname && target.search === here.search) {
        globalThis.history.replaceState(null, "", target.href);
        location.reload();
      } else {
        location.assign(target.href);
      }
    },
  };
}

export function createResourceEditor(context, environment = browserEnvironment()) {
  const config = readConfig(context.config);
  const urls = {
    node: config.renameNodeAction ? context.actions[config.renameNodeAction] : undefined,
    edge: config.renameEdgeAction ? context.actions[config.renameEdgeAction] : undefined,
  };
  const canRename = { node: typeof urls.node === "string", edge: typeof urls.edge === "string" };
  // Aucune action exposée par l'hôte (capacité indisponible) : consultation seule.
  if (!canRename.node && !canRename.edge) return null;
  let engine = null;
  let overlay = null;
  let scale = 1;
  let pending = false;
  // Édition en cours : élément visé, champ, groupe contre-mis à l'échelle.
  let editing = null;
  // Éléments éditables ("node:<id>", "edge:<id>") et leurs formes à taille écran stable.
  const targets = new Map();

  function create(namespace, name, attributes = {}) {
    const element = overlay.root.ownerDocument.createElementNS(namespace, name);
    for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
    return element;
  }

  // Contre-échelle purement géométrique : ancrage monde, puis 1 / échelle.
  function placement(anchor) {
    return `translate(${anchor.x} ${anchor.y}) scale(${1 / scale})`;
  }

  function applyScale() {
    for (const target of targets.values()) {
      target.handle.setAttribute("r", String(HANDLE_PX / scale));
      target.hit.setAttribute("r", String(HIT_PX / scale));
      if (target.line) target.line.setAttribute("stroke-width", String((2 * EDGE_HIT_PX) / scale));
    }
    if (editing) editing.group.setAttribute("transform", placement(editing.target.anchor));
  }

  // Envoi d'une action bornée : formulaire encodé, URL et révision du contexte.
  async function post(url, fields) {
    const body = new URLSearchParams([
      ["type", context.resourceType],
      ["path", context.path],
      ["revision", context.revision],
      ...fields,
    ]);
    return environment.fetch(url, { method: "POST", body, credentials: "same-origin", redirect: "follow" });
  }

  async function failureMessage(response) {
    let message = "";
    try {
      message = environment.errorMessage(await response.text());
    } catch {
      message = "";
    }
    return bounded(message || FALLBACK[response.status] || `Libellé non enregistré (erreur ${response.status}).`);
  }

  function close(restoreFocus) {
    if (!editing) return;
    const { group, target, outside } = editing;
    editing = null;
    overlay.root.ownerDocument.removeEventListener("pointerdown", outside, true);
    group.remove();
    if (restoreFocus) target.item.focus({ preventScroll: true });
  }

  function cancel(restoreFocus) {
    if (!editing || pending) return;
    close(restoreFocus);
    context.announce("Modification du libellé annulée.");
  }

  async function submit() {
    if (!editing || pending) return;
    const { target, input } = editing;
    const value = input.value.trim();
    const label = target.kind === "edge" && value === "" ? null : value;
    const problem = label === null ? null : labelProblem(label);
    if (problem) {
      input.setAttribute("aria-invalid", "true");
      context.announce(problem);
      return;
    }
    if (label === target.label) {
      close(true);
      context.announce("Libellé inchangé : aucune modification.");
      return;
    }
    pending = true;
    input.readOnly = true;
    input.setAttribute("aria-busy", "true");
    context.announce(`Enregistrement du libellé de ${target.title}…`);
    let response = null;
    try {
      response = await post(urls[target.kind], [
        [target.kind, target.id],
        ["label", value],
      ]);
    } catch {
      response = null;
    }
    if (response && response.ok && response.redirected) {
      // pending reste vrai : aucune seconde action avant la nouvelle révision.
      context.announce(`Libellé de ${target.title} enregistré : rechargement…`);
      environment.navigate(returnUrl(response.url, target.kind, target.id));
      return;
    }
    const message = response ? await failureMessage(response) : "Serveur injoignable : libellé non enregistré.";
    pending = false;
    input.readOnly = false;
    input.removeAttribute("aria-busy");
    if (response && response.status === 422) input.setAttribute("aria-invalid", "true");
    context.announce(message);
  }

  function open(target) {
    if (pending || overlay === null) return;
    if (editing) {
      if (editing.target === target) return;
      close(false);
    }
    const group = create(SVG_NS, "g", { class: "flow-editor", transform: placement(target.anchor) });
    const frame = create(SVG_NS, "foreignObject", {
      x: -FIELD_WIDTH / 2,
      y: -FIELD_HEIGHT / 2,
      width: FIELD_WIDTH,
      height: FIELD_HEIGHT,
    });
    const box = create(XHTML_NS, "div", { class: "flow-editor-box" });
    const input = create(XHTML_NS, "input", {
      class: "flow-editor-input",
      type: "text",
      maxlength: MAX_LABEL_CHARS,
      "aria-label": target.field,
    });
    input.value = target.label ?? "";
    const save = create(XHTML_NS, "button", {
      class: "flow-editor-save",
      type: "button",
      "aria-label": "Enregistrer le libellé",
    });
    save.textContent = "✓";
    const dismiss = create(XHTML_NS, "button", { class: "flow-editor-cancel", type: "button", "aria-label": "Annuler" });
    dismiss.textContent = "✕";
    box.append(input, save, dismiss);
    frame.append(box);
    group.append(frame);
    // Les touches du champ restent au champ : ni Échap de désélection ni Maj + flèches
    // de pan du moteur.
    box.addEventListener("keydown", (event) => {
      event.stopPropagation();
      if (event.isComposing) return;
      if (event.key === "Escape") {
        event.preventDefault();
        cancel(true);
      } else if (event.key === "Enter" && event.target === input) {
        event.preventDefault();
        submit();
      }
    });
    input.addEventListener("input", () => input.removeAttribute("aria-invalid"));
    save.addEventListener("click", () => submit());
    dismiss.addEventListener("click", () => cancel(true));
    // Appui hors du champ : annulation, jamais enregistrement implicite.
    const outside = (event) => {
      if (editing && !editing.group.contains(event.target)) cancel(false);
    };
    editing = { target, group, input, outside };
    overlay.root.ownerDocument.addEventListener("pointerdown", outside, true);
    overlay.root.append(group);
    input.focus({ preventScroll: true });
    input.select();
    context.announce(`Modification du libellé de ${target.title} : Entrée pour enregistrer, Échap pour annuler.`);
  }

  function item(label) {
    const element = create(SVG_NS, "g", {
      class: "gx-overlay-item",
      tabindex: 0,
      role: "button",
      "aria-label": label,
      "aria-keyshortcuts": "Enter",
    });
    const title = create(SVG_NS, "title");
    title.textContent = label;
    element.append(title);
    return element;
  }

  function bind(target) {
    target.item.addEventListener("click", () => open(target));
    target.item.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== "F2") return;
      event.preventDefault();
      open(target);
    });
    overlay.root.append(target.item);
    targets.set(`${target.kind}:${target.id}`, target);
  }

  function buildNodes(scene) {
    for (const node of scene.nodes) {
      const { x, y, width, height } = node.rect;
      const element = item(nodeName(node.label, node.data.kind));
      const corner = { cx: x + width, cy: y };
      const hit = create(SVG_NS, "circle", { class: "gx-overlay-hit", ...corner, r: HIT_PX });
      const handle = create(SVG_NS, "circle", { class: "gx-overlay-handle", ...corner, r: HANDLE_PX });
      element.append(hit, handle);
      bind({
        kind: "node",
        id: node.id,
        label: node.label,
        title: `« ${node.label} »`,
        field: `Nouveau libellé du nœud « ${node.label} »`,
        anchor: { x: x + width / 2, y: y + height / 2 },
        item: element,
        handle,
        hit,
        line: null,
      });
    }
  }

  function buildEdges(scene) {
    for (const edge of scene.edges) {
      const source = engine.node(edge.source);
      const target = engine.node(edge.target);
      if (!source || !target) continue;
      const anchor = edge.labelAt ?? middle(edge.points);
      const element = item(edgeName(source.label, target.label, edge.label));
      const points = formatPoints(edge.points);
      // Zone de détection : trait transparent (attributs de présentation, pas de style).
      const line = create(SVG_NS, "polyline", {
        points,
        fill: "none",
        stroke: "transparent",
        "stroke-width": 2 * EDGE_HIT_PX,
        "pointer-events": "stroke",
      });
      const trace = create(SVG_NS, "polyline", { class: "gx-overlay-path flow-edge-trace", points });
      const hit = create(SVG_NS, "circle", { class: "gx-overlay-hit", cx: anchor.x, cy: anchor.y, r: HIT_PX });
      const handle = create(SVG_NS, "circle", { class: "gx-overlay-handle", cx: anchor.x, cy: anchor.y, r: HANDLE_PX });
      element.append(line, trace, hit, handle);
      bind({
        kind: "edge",
        id: edge.id,
        label: edge.label,
        title: `la transition ${source.label} → ${target.label}`,
        field: `Libellé de la transition ${source.label} → ${target.label} (vide : sans libellé)`,
        anchor,
        item: element,
        handle,
        hit,
        line,
      });
    }
  }

  // Après un enregistrement : focus rendu à la poignée de l'élément renommé.
  function restore() {
    const hash = environment.hash();
    for (const [kind, prefix] of Object.entries(RETURN_PREFIX)) {
      if (!hash.startsWith(prefix)) continue;
      let id;
      try {
        id = decodeURIComponent(hash.slice(prefix.length));
      } catch {
        return;
      }
      const target = targets.get(`${kind}:${id}`);
      if (target) target.item.focus({ preventScroll: true });
      return;
    }
  }

  return Object.freeze({
    onViewChange(state) {
      const next = state.scale > 0 ? state.scale : 1;
      if (next === scale) return;
      scale = next;
      applyScale();
    },
    attach(instance) {
      engine = instance;
      const scene = engine.scene();
      overlay = engine.addOverlay({ label: "Libellés de l'organigramme" });
      if (canRename.node) buildNodes(scene);
      if (canRename.edge) buildEdges(scene);
      const current = engine.viewport().scale;
      scale = current > 0 ? current : 1;
      applyScale();
      context.announce(HELP);
      restore();
    },
    pending: () => pending,
    editing: () =>
      editing ? Object.freeze({ kind: editing.target.kind, id: editing.target.id, value: editing.input.value }) : null,
  });
}
