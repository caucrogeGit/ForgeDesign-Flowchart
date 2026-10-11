# Rapport — FD-MODULE-PILOT-001

Second module pilote : ForgeDesign-Flowchart. Date : 2026-10-11.

**Réponse à la question du ticket.** Oui : le moteur générique construit jusqu'ici suffit pour un second domaine sans bornes, fils ni routage spécialisé. Un vrai module externe Flowchart :

- charge, valide et projette un organigramme ;
- affiche les textes des nœuds et les libellés des arêtes ;
- modifie un libellé de nœud ou d'arête, l'enregistre, et gère le conflit et l'historique ;
- fonctionne en même temps que Circuit.

Tout cela sans aucune modification de Forge Design : 0 ligne de diff, preuve ci-dessous. **Nouvelle API du cœur nécessaire : 0.** Deux limites génériques sont documentées comme candidates, sans être créées : une forme de nœud, et un repli textuel sans JavaScript.

## Objectif

Créer un module externe réel, indépendant et minimal, consacré aux organigrammes, pour vérifier la frontière fixée par FD-ARCH-001 et FD-RELEASE-001 sur un domaine très différent de Circuit. Le besoin nouveau éprouvé est l'**édition de texte**, y compris le texte porté par une arête, et non la géométrie.

| Critère architectural | Résultat |
|---|---|
| Flowchart fonctionne seul | Oui : roue installée seule, activation sans diagnostic |
| Flowchart + Circuit fonctionnent ensemble | Oui : trois roues dans un venv neuf, vraie commande, Chromium et Firefox |
| Forge Design | 0 modification (instantané avant/après identique) |
| Dépendance Circuit dans Flowchart | Aucune (métadonnée, imports, texte livré : tests) |
| Édition nœud/arête | Uniquement par l'API publique (scène validée, calque, actions de l'hôte) |
| DOM privé du moteur | Jamais touché (gardes statiques, 70 mutations) |
| Nouvelle API du cœur | 0 |

## Dépôts et baselines

| Dépôt | Avant | Après |
|---|---|---|
| Forge Design | `8cf8203` (FD-RELEASE-001), `origin/main` = `691e83e`, 0.2.0 ; seul `docs/rapports/FD-CONTRACT-001.md` modifié | Identique : même HEAD, même instantané (contenu des fichiers suivis, diff de travail, non suivis). `FD-CONTRACT-001.md` préservé, ni restauré ni commité |
| ForgeDesign-Circuit | `967b5b3`, `origin/main` = `536adfc`, arbre propre | Identique (instantané). Installé en mode éditable dans le venv Flowchart pour le test de coexistence, sans fichier suivi modifié |
| ForgeDesign-Flowchart | Inexistant | Créé : `/home/roger/Projets/ForgeDesign-Flowchart`, `git init` sur `main`, sans remote, un commit |

La baseline du cœur contient FD-GRAPHICS-EDIT-002 (`44ded4b`), FD-ARCH-001 (`3fcb51d`) et FD-RELEASE-001 (`8cf8203`).

## Architecture

```text
Forge MVC ← Forge Design 0.2.0 ← forge-design-flowchart 0.1.0
                              ↖ forge-design-circuit 0.1.0   (indépendants l'un de l'autre)
```

| Fichier | Rôle |
|---|---|
| `forge_design_flowchart/__init__.py` | `FORGE_DESIGN_MODULE`, version, contrainte sur le cœur |
| `models.py` | `FlowDocument`, `FlowNode`, `FlowEdge` (Pydantic strict, gelés) |
| `validation.py` | Règle de domaine : au plus un début |
| `codec.py` | `FlowCodec` : octets ↔ document, diagnostics localisés |
| `contract.py` | Type de ressource `flowchart`, outil `Flowchart`, `UiEntry` |
| `scene.py` | `flow_scene` : projection pure vers la GraphicScene |
| `actions.py` | `rename-node`, `rename-edge` |
| `editor.py` | Configuration minimale du script |
| `static/flow-editor.js` | Script d'édition (calque, champ en place) |
| `static/flowchart.css` | Feuille du module (champ d'édition, trace focalisée) |

Flowchart n'est pas un Tool (décision B) et ne fait pas partie du cœur (décision C). Il apparaît sous « Modules → Flowchart » à `/modules/flowchart/`.

## Contrat Forge Design utilisé

Seulement `forge_design.modules` et `forge_design.specialized` (test d'imports) :

| API | Usage |
|---|---|
| `ModuleDescriptor`, `ResourceBinding`, `ModuleAsset`, `MODULE_API_VERSION` = 1 | Descripteur (décision D) |
| `requires_forge_design` | `">=0.2.0,<1"` (décision E) |
| `ModuleAction`, `ModuleActionPayload`, `ModuleActionRefused`, `ModuleActionResult` | Deux actions pures |
| `SpecializedResourceType`, `SpecializedToolDefinition`, `SpecializedCapability`, `UiEntry` | Déclaration |
| `SpecializedIssue`, `SpecializedValidationResult`, `SpecializedFormatError`, `loads_strict_json`, `MAX_SPECIALIZED_*` | Codec et validation |
| Graphic Core : `scene()`, `node()`, `viewport()`, `addOverlay()`, `onViewChange` | Script d'édition |
| Contexte d'édition de l'hôte : `actions`, `revision`, `resourceType`, `path`, `config`, `announce` | Script d'édition |
| GraphicScene : `label`, `lines`, `presentation.variant`, `data`, arêtes `label` + `labelAt`, `presentation.arrow` | Projection |

Non utilisés : `nodeMove` (pas de déplacement persistant, §72), `worldAt`, `select`, `focus`.

## Dépendances

| Distribution | Requires-Dist |
|---|---|
| `forge-design-flowchart` 0.1.0 | `forge-design<1,>=0.2.0`, `pydantic<3,>=2` ; extra `dev` : pytest, ruff, pyright |

Il n'y a aucune dépendance frontend (pas de CDN, de framework ni de bundler) et aucune dépendance Circuit. Le test `test_core_requirement_matches_the_distribution_dependency` vérifie que `pyproject.toml`, la métadonnée installée et `requires_forge_design` portent le même spécificateur. `test_activation_refuses_an_incompatible_core` vérifie le diagnostic `core-version-incompatible` (cœur 0.1.9 ou 1.0.0 refusé, 0.9.3 accepté).

## Format Flowchart V0.1

Fichiers `mvc/flowchart/**/*.flow.json`, format `flowchart-json` 0.1, 4 Mio au plus. Enveloppe `{format_version, nodes, edges}`. Je l'ai alignée sur la convention réelle des ressources spécialisées : `detect_version` lit `format_version`, comme Circuit et le témoin du cœur. C'est un ajustement de l'enveloppe `{format, version, …}` évoquée dans le repérage. Détail : [domaine et format](../flowchart-domain.md). Exemple : `examples/simple-flow.flow.json`.

## Modèle

| Élément | Règle |
|---|---|
| Identité | `^[A-Za-z][A-Za-z0-9_-]*$`, 64 caractères au plus, unique entre nœuds et arêtes |
| `kind` | `start`, `step`, `decision`, `end` |
| Libellé | 1 à 200 caractères, une ligne : ni C0/C1/DEL, ni U+2028/U+2029, ni espace de bord |
| `x`, `y` | **Entiers** dans ±100 000 (le ticket proposait `int \| float` : l'entier suffit, sans arrondi ni `NaN`) |
| Arête | `source` ≠ `target`, toutes deux existantes ; `label` facultatif, omis, jamais `null` |
| Collections | 500 nœuds, 2 000 arêtes |

Le modèle est Pydantic en mode JSON strict (`extra="forbid"`, `strict=True`, `frozen=True`). Les 85 tests de `test_models.py` couvrent : document minimal, types de nœuds, identités, libellés, coordonnées, arêtes valides (parallèles et inverses), extrémité inconnue, boucle, champs inconnus et manquants, version, limites, gel.

## Validation

| Niveau | Bloquant | Contenu |
|---|---|---|
| `structure` | Oui (échec du décodage) | Tout le §46 : type inconnu, identité invalide ou dupliquée, extrémité inconnue, boucle, coordonnée invalide, libellé hors limite, champ inconnu |
| `graph` | Oui (lecture affichée, écriture refusée) | `flowchart.start-duplicate` : au plus un `start` |

Zéro ou un `start`, autant de `end` que voulu (§50) : un document en construction reste enregistrable. Aucune analyse de chemins (§51). Un document à deux débuts reste affiché avec son diagnostic, mais toute action est refusée (`resource-unusable`, test sur l'hôte réel).

## Codec

`FlowCodec` utilise `loads_strict_json` du cœur (UTF-8, clés uniques, ni `NaN` ni `Infinity`), puis la validation Pydantic en JSON. L'encodage est canonique : ordre du modèle, indentation 2, UTF-8 sans échappement, fin de ligne, libellé absent omis. L'exemple fait un aller-retour octet pour octet. Les diagnostics sont localisés (par exemple `("edges", 4, "target")`) et bornés : un diagnostic de plus que `MAX_SPECIALIZED_ISSUES` signale la troncature. `validate` revalide d'abord le format d'un document non vérifié (`model_construct`). La taille est bornée par le type : 4 Mio + 1 octet refusé par l'hôte, 4 Mio exactement accepté (21 tests).

## Projection GraphicScene

`flow_scene(document)` est pure (aucun fichier ouvert : test avec `open` interdit), ne modifie pas le document et rend un résultat neuf à chaque appel. Elle est déterministe : même document, même JSON. Les scènes sont validées par le **vrai** `model.js` du Graphic Core : scène vide, exemple, libellés hostiles `</script><svg onload=…>`, et document au plafond (500 nœuds, 2 000 arêtes libellées de 200 caractères). Chaque libellé d'arête est affichable : `label` et `labelAt` sont présents ensemble (15 tests).

## Nœuds textuels

`label` porte le libellé exact du document : c'est le nom accessible, l'info-bulle et la valeur de départ de l'édition. `lines` en est l'affichage replié sur 25 caractères (12 px monospace du moteur), 3 lignes au plus, « … » au-delà, ce qui fait varier la hauteur (48, 66 ou 92). Les types se distinguent par une variante de couleur **générique** (`category-3`, `category-4`, `category-5`) et par une marque (`▶`, `◇`, `■`) :

```text
▶ Début → Vérifier la valeur → ◇ Valeur valide ? → Continuer / Signaler l'erreur → ■ Fin
```

**Limite.** Le moteur ne dessine que des rectangles. Le losange et la pastille ne sont pas disponibles, et le cœur n'a pas été modifié (§27). La feuille du module ne cible pas les classes du renderer (`.gx-node-box`) pour imiter une forme : ce serait dépendre de la structure privée du rendu.

## Arêtes orientées

Chaque arête est un segment droit, flèche à l'arrivée, entre les bords des deux rectangles, sur la droite des centres. Le calcul est un découpage paramétrique de type Liang-Barsky. Les arêtes d'une même paire, dans un sens ou dans l'autre, sont décalées de 16 unités par rang, bornées à ±20 pour rester dans les nœuds, dans le sens canonique de la paire : une transition retour passe de l'autre côté. Cas dégénérés : pour des nœuds superposés, la droite des centres entière ; pour des nœuds confondus, deux points égaux, et le moteur ne dessine pas de flèche. Aucun routage, aucune mise en page automatique.

## Labels d'arêtes

La capacité existait déjà : `GraphicEdge.label` + `labelAt`. Le renderer n'affiche un libellé que si les deux sont présents (constaté dans `svg-renderer.js`). La projection pose donc toujours `labelAt` : au milieu du segment, 6 unités au-dessus d'un segment plutôt horizontal, à droite d'un segment plutôt vertical (demi-largeur estimée). Elle le pose aussi pour une arête **sans** libellé, comme ancre d'édition. Aucune primitive n'a été ajoutée (§34). Dans le navigateur, les 6 arêtes ont leurs 6 flèches et les 3 libellés `Oui`, `Non` et `suite` sont rendus (Chromium et Firefox).

## Choix UI d'édition

La comparaison obligatoire (§82) a été faite avec un prototype de panneau **non livré** (`flow-editor.js` modifié dans le venv de test, roue restaurée et vérifiée octet pour octet ensuite). Mesures sur la page réelle, édition par Entrée sur la poignée du début puis sur celle de « Continuer → Fin » :

| Mesure | Inline (livré) | Panneau (prototype) |
|---|---|---|
| Distance poignée ↔ champ, nœud | 115 px (Chromium, Firefox) | 412 px (Chromium), 380 px (Firefox) |
| Distance poignée ↔ champ, arête | 32 px | 288 px (Chromium), 149 px (Firefox) |
| Champ visible sans défilement | Oui | Oui (position fixe en bas) |
| Recouvre le dessin | Seulement l'élément édité | Une bande du bas de la zone graphique |
| Focus, Échap, retour du focus, enregistrement | OK | OK |
| Surface DOM utilisée | Le calque fourni (`overlay.root`) | `document.body` : hors du calque, faute de surface HTML hôte |
| Plusieurs graphes sur une page | Chacun son calque | Retrouver son conteneur exigerait la structure privée de la page |
| Zoom | Contre-échelle nécessaire (faite) | Indifférent |
| Erreurs ou violations CSP | 0 | 0 |

**Décision : inline dans le calque.** Le panneau ne serait propre qu'avec une API hôte (surface HTML de module, `formHost`), ce que le ticket interdit d'anticiper (§99). Sans elle, il sort du calque. L'inline tient entièrement dans le contrat actuel. La préférence du ticket (« panneau simple… si possible sans toucher au core », §83) n'est donc pas réalisable proprement. Ce constat est le résultat, pas un manque à combler maintenant.

## Script éditeur

`static/flow-editor.js`, 433 lignes, module ES natif, aucune dépendance. `createResourceEditor(context, environment)` lit la configuration exacte (`renameNodeAction`, `renameEdgeAction`), dérive les URL du contexte de l'hôte et rend `null` si aucune action n'est exposée (consultation seule). Il fournit `onViewChange` et `attach`, plus `pending()` et `editing()` pour l'inspection. La configuration ne recopie rien de la scène (§94-97) : `{"renameNodeAction": "rename-node", "renameEdgeAction": "rename-edge"}`.

Le champ est un `<input>` XHTML dans un `foreignObject`, lui-même dans un groupe du calque : `translate(ancre) scale(1 / échelle)`. Il garde 300 × 40 px écran à tout zoom, mesuré dans les deux navigateurs, y compris après un zoom ×1,56. Le calcul est purement géométrique : seule l'échelle est lue, le viewport n'est jamais recopié. Les poignées et les zones de détection gardent aussi leur taille écran : rayon 6 px avant et après zoom dans Chromium, 6,76 et 6,78 dans Firefox, dont la boîte inclut le trait.

## Interaction nœuds

Une poignée focalisable par nœud (`role="button"`, `tabindex="0"`, `aria-keyshortcuts="Enter"`, `<title>`) est placée au coin supérieur droit, avec le nom « Renommer le nœud « Valeur valide ? » (décision) ». Elle est placée dans le calque : elle ne couvre pas le nœud, dont la sélection reste au moteur. Un clic ou Entrée (F2 aussi) ouvre le champ centré sur le nœud, contenu présélectionné.

## Interaction arêtes

Le Graphic Core ne sélectionne pas d'arête (§85). Le module pose donc, dans son calque et pour chaque arête lue dans `engine.scene()` :

- une zone de détection transparente le long du segment (`stroke="transparent"`, `pointer-events="stroke"`, 12 px écran : des attributs de présentation, pas de style en ligne) ;
- une poignée au point du libellé ;
- une trace visible au focus clavier ou au survol (CSS du module) ;

le tout dans **un seul** élément focalisable, nommé « Transition Valeur valide ? → Continuer — Oui » ou « Transition Début → Vérifier la valeur, sans libellé » (§92). Dans le navigateur, un appui sur le segment lui-même ouvre le champ : le test vérifie par `elementFromPoint` que le point visé est la zone de tracé. Conclusion du §88 : une arête non sélectionnable par le cœur n'empêche pas une interaction métier locale.

## Clavier

Le scénario en clavier seul : Tab (27 appuis depuis le haut de la page), Entrée, saisie, Entrée renomme « Fin » en « Terminé ». Après le rechargement, le focus est rendu à cette poignée. Ensuite Tab (5 appuis), Entrée, Retour arrière, Entrée supprime le libellé « suite ». Échap annule et rend le focus à la poignée.

Dans le champ, les touches **ne remontent pas** au moteur (`stopPropagation` sur le conteneur) : Échap ne désélectionne pas, Maj + flèches sélectionne du texte sans faire défiler le graphe, et Entrée pendant une composition IME ne soumet pas.

Aucune dépendance aux événements `focus` ou `blur` (§93) : l'ouverture, l'enregistrement et l'annulation passent par `keydown`, `click` et `pointerdown`. Le focus est donné avec `preventScroll: true`, et la page ne défile pas au clic (mesuré). Quitter le champ par Tab le laisse ouvert : c'est un choix délibéré, aucun enregistrement implicite.

## Actions rename-node / rename-edge

Les handlers sont purs : `(document, payload) → ModuleActionResult`. Seul le libellé visé change ; le test le vérifie pour **chaque** nœud et **chaque** arête de l'exemple. Les espaces de bord sont retirés, puis la règle du modèle est appliquée par la même fonction `label_problem` (le script en a la copie `labelProblem`, testée sur les mêmes cas).

| Cas | Résultat |
|---|---|
| Libellé identique (aux espaces près) | Même objet rendu : no-op de l'hôte, aucune écriture ni historique (§63) |
| `rename-edge` vide ou fait d'espaces | `label = None`, champ **omis** du JSON, jamais `""` (§67-68) |
| Élément inconnu, libellé refusé | `ModuleActionRefused` → 422 |
| Champ absent, identité de plus de 64 caractères | `ModuleActionPayloadError` → 400 |

36 tests au total, dont l'hôte réel `ModuleHost` et le serveur HTTP réel (`create_server`).

## Révision

Le script envoie la révision du contexte (`type`, `path`, `revision`, puis `node`/`edge`, `label`, en `x-www-form-urlencoded`). Après un succès, le jeton relu correspond à `revision_token(...)` de la nouvelle révision (test). Un 409 laisse la révision du contexte inchangée : seule une page rechargée en apporte une autre (test JS).

## Historique

Chaque enregistrement ajoute une ligne `write_specialized_resource` à `.forge-design/history.jsonl` ; un no-op n'ajoute rien. Vérifié sur l'hôte réel, en HTTP et dans les navigateurs, avec une ligne par édition.

## Conflit

Le scénario navigateur ouvre le champ sur « Début » et saisit « Départ ». Le fichier est ensuite modifié sur disque, hors de Forge Design (« Commencer »), puis Entrée est pressée. Résultat :

- 409 et un seul POST ;
- aucun rechargement ;
- message annoncé (« La ressource a changé depuis son affichage : rechargez-la. », lu dans la page d'erreur du cœur) ;
- le champ reste ouvert avec « Départ », de nouveau modifiable ;
- l'écriture externe est préservée et aucune ligne d'historique n'est ajoutée.

Après rechargement, « ▶ Commencer » est affiché. C'est identique dans les deux navigateurs.

## CSP

La CSP du cœur est inchangée (`script-src 'self'`, `style-src 'self'`, testé en HTTP) :

- aucun style en ligne : le champ et les boutons sont stylés par `flowchart.css`, chargée par l'hôte sur les seules pages Flowchart ;
- aucun attribut `on*`, aucun `innerHTML` ni `eval` ;
- 0 violation, exception ou boîte de dialogue dans Chromium et Firefox.

## Isolation

| Garde | Preuve |
|---|---|
| Pas de DOM privé du moteur | Tests statiques : aucun `parentNode`, `parentElement`, `closest(`, `ownerSVGElement`, `querySelector` sur la page, classe `gx-node`/`gx-edge`/`gx-scene`, `engine.select`/`engine.focus`/`nodeMove`. Un seul `createElementNS`, sur le document du calque. Un seul écouteur global (appui hors du champ, retiré à la fermeture) |
| CSS du module | Ne vise que des classes `flow-*` (`gx-overlay-item`, classe publique du calque, seulement en ancêtre) ; ni `@import` ni `url(` |
| Pas de vocabulaire Circuit | Texte livré (Python, JS, CSS) sans « circuit » ; aucun import `forge_design_circuit` |
| Assets séparés | Page Flowchart : aucune requête `/modules/circuit/…` ; page Circuit : aucune requête `/modules/flowchart/…`, aucun élément `flow-*` (navigateurs) |
| Actions séparées | `move-component` et `create-connection` sur `/modules/flowchart/actions/` → 404 ; hôte : `KeyError` dans les deux sens, dans les deux ordres d'activation |
| Ressources séparées | Flowchart ne liste ni ne lit une ressource Circuit, même nommée explicitement |
| Jamais un Tool | Registre réellement composé par le serveur avec Flowchart activé : outils du cœur seulement |

## Multi-instance

Tout l'état (calque, champ, envoi en cours, échelle) appartient à la fermeture de `createResourceEditor`, et le test statique vérifie qu'il n'y a ni `let` ni `var` au niveau du module. Le test JS « deux instances » fait tourner deux éditeurs sur le même document : calques distincts, un envoi en attente sur l'un, un enregistrement sur l'autre, sans interférence. Côté hôte, deux ressources Flowchart sont modifiées indépendamment (test).

## Packaging

| Vérification | Résultat |
|---|---|
| Version | Source unique `forge_design_flowchart.__version__ = "0.1.0"`, `version = {attr = …}` |
| Roue `forge_design_flowchart-0.1.0-py3-none-any.whl` | 10 modules, `py.typed`, `static/flow-editor.js`, `static/flowchart.css` |
| Métadonnée | `Name: forge-design-flowchart`, `Version: 0.1.0`, `Requires-Python: >=3.12`, `Requires-Dist: forge-design<1,>=0.2.0`, `pydantic<3,>=2` |
| Venv neuf, trois roues (cœur 0.2.0, Circuit 0.1.0, Flowchart 0.1.0) | `pip check` : aucune dépendance cassée ; activation `['circuit', 'flowchart']` sans diagnostic |
| Venv neuf, cœur + Flowchart seuls, `forge-design --module forge_design_flowchart` | `pip check` OK ; ressource 200 ; zone Modules = `/modules/flowchart/` seul ; `/modules/circuit/` 404. Ce 404 journalise « Rendu de errors/404.html impossible » : le cœur seul fait de même (projet sans page d'erreur), ce n'est pas lié au module |
| Paquet typé | `py.typed` livré, Pyright strict sur le paquet et les tests |

## Tests Python

**175 tests**, tous verts :

| Fichier | Tests |
|---|---|
| `test_models.py` | 85 |
| `test_actions.py` | 36, dont hôte réel et HTTP réel (303, 409, 422, 400, 403, 404) |
| `test_codec.py` | 21 |
| `test_scene.py` | 15, dont la validation par `model.js` |
| `test_descriptor.py` | 9, dont l'activation réelle, la version de cœur incompatible, le registre des Tools et la coexistence avec Circuit dans les deux ordres |
| `test_packaging.py` | 5 |
| `test_editor_script.py` | 4 (paquet, `node --check`, suite Node) |

`test_sources_contain_no_invisible_line_breaks` est né d'un piège réel. Un U+2028 littéral, introduit à l'écriture d'une expression rationnelle, rendait `flow-editor.js` invalide : « Invalid regular expression ». Les sources écrivent désormais ces caractères en échappement, et le test le garantit.

**Mutations : 70/70 tuées**, sources restaurées à l'identique (empreinte vérifiée). Elles couvrent le modèle (16), le codec (9), la validation (2), le contrat (2), les actions (8), la projection (12), la configuration (1) et le script (20). Une seule a d'abord survécu : « succès sans redirection », où une réponse 200 non redirigée était prise pour un enregistrement. Elle est tuée par un test ajouté.

## Tests JavaScript

`tests/js/flow-editor.test.mjs` : **26 tests**, DOM et moteur simulés. Ils couvrent chaque point du §122 :

- initialisation et éléments focalisables ;
- édition d'un nœud, d'une arête, et d'une arête sans libellé ;
- Entrée, Échap, composition IME, boutons ✓ et ✕, appui extérieur ;
- POST exact et révision ;
- réponses 409, 422, 500, statut inattendu, page illisible, réseau, 200 sans redirection ;
- double envoi, deux instances, action absente (consultation seule ou un seul type exposé) ;
- échelle, et `onViewChange` avant `attach` ;
- retour du focus après rechargement ;
- gardes statiques du script et de la feuille (§123).

## Chromium

La vraie commande est lancée depuis les roues, avec un HOME isolé :

```bash
forge-design --module forge_design_circuit --module forge_design_flowchart --no-browser
```

Résultat : **12/12**. Le scénario reprend le §124 en entier :

1. navigation ;
2. 6 nœuds, 6 arêtes, 6 flèches, libellés `Oui`, `Non` et `suite` ;
3. édition d'un nœud au pointeur, avec un seul POST, un JSON modifié sur ce seul libellé et une ligne d'historique ;
4. édition d'une transition par le bouton ✓, avec mise à jour du libellé graphique ;
5. ouverture par le segment ;
6. clavier seul ;
7. Échap ;
8. appui extérieur ;
9. contre-échelle ;
10. conflit 409 ;
11. Circuit ;
12. aucune erreur.

## Firefox

Même scénario par WebDriver BiDi : **12/12**. La fenêtre headless n'émet pas d'événement `focus`, et le script n'en dépend pas. Pendant la mise au point, deux défauts du *scénario*, pas du module, ont été corrigés :

- les poignées sous la ligne de flottaison doivent défiler dans la vue avant le pointeur ;
- le point visé sur un segment doit être calculé en coordonnées monde puis converties en écran, car la boîte englobante de Firefox inclut le trait.

## Sans JavaScript

Chromium (scripts désactivés) et Firefox (`javascript.enabled = false`) donnent le même résultat. La page est servie : chemin, révision, « Validation : valide », message « La visualisation graphique nécessite JavaScript. ». Il n'y a ni moteur, ni calque, ni champ, ni formulaire, et le statut d'édition est masqué. Le bloc JSON du contexte est présent et inerte. Il n'y a donc pas d'édition, mais **les libellés du dessin ne sont pas lisibles** : voir « Dette découverte ».

## Validation Circuit + Flowchart

Les trois roues sont installées ensemble dans un venv neuf, avec la vraie commande et les deux modules :

| Vérification | Chromium | Firefox |
|---|---|---|
| Navigation : outils du cœur inchangés, « Modules » = `/modules/circuit/`, `/modules/flowchart/` | OK | OK |
| Ressource Circuit ouverte, calque Circuit présent, aucun asset ni élément Flowchart | OK | OK |
| Déplacement d'un composant (Ctrl + Maj + →) : un POST, une ligne d'historique, `c_battery001` décalé d'une case, fichier Flowchart inchangé | OK | OK |

Non-régression du cœur, inchangé et lancé contre lui-même (§150) :

- suite Python complète : **4 631 tests** verts ;
- Graphic Core Node : **134** ;
- parcours navigateur génériques (Route, Entity, Debug, témoin, cœur sans module, sans JavaScript) : **14/14**, Chromium et Firefox.

Pas de commit Forge Design (§151).

## Matrice des besoins génériques

Les besoins se rangent en trois catégories :

- **le cœur suffit directement** : l'API couvre le besoin tel quel ;
- **le cœur suffit, avec une adaptation du module** : le module compose l'API existante, ce qui est attendu d'une plateforme extensible ;
- **le cœur est réellement insuffisant** : un besoin générique ne peut pas être couvert proprement sans une nouvelle API.

| Besoin Flowchart | Core existant suffit ? | Contournement module ? | Nouvelle API core nécessaire ? | Catégorie |
|---|---|---|---|---|
| Labels de nœuds | Oui : `label`, `lines` | Repli des lignes et marque calculés par la projection | Non | Suffit + adaptation |
| Labels d'arêtes | Oui : `label` + `labelAt` | Ancre `labelAt` calculée (obligatoire pour l'affichage) | Non | Suffit directement |
| Arêtes orientées | Oui : `presentation.arrow` | Points calculés (bords, décalage des parallèles) | Non | Suffit + adaptation |
| Formes début, décision, fin | En partie : variantes de couleur génériques | Variante + marque `▶ ◇ ■` ; pas de losange | Non pour le pilote. Candidate documentée : `presentation.shape` | Suffit + adaptation (limite visuelle) |
| Édition texte | Oui : calque + `foreignObject`, CSS du module sous CSP | Champ en place, contre-échelle par `onViewChange` | Non : ni `onTextEdit`, ni `formHost` | Suffit + adaptation |
| Interaction edge | Oui : `engine.scene()` + calque | Zone de détection et poignée par arête | Non : pas d'`edgeSelection` | Suffit + adaptation |
| Overlay | Oui : `addOverlay`, `onViewChange` | — | Non | Suffit directement |
| Clavier | Oui : éléments focalisables du calque, `preventDefault` respecté par le moteur | `stopPropagation` dans le champ | Non | Suffit + adaptation |
| Action | Oui : `ModuleAction`, payload borné, 303/409/422/400 | — | Non | Suffit directement |
| Révision, conflit, historique | Oui | — | Non | Suffit directement |
| Validation métier bloquante | Oui : niveaux déclarés bloquants | — | Non | Suffit directement |
| Multi-instance, isolation, coexistence | Oui | État dans la fermeture | Non | Suffit directement |
| Versions et packaging | Oui (FD-RELEASE-001) | — | Non | Suffit directement |
| Consultation sans JavaScript | En partie : résumé et validation | Aucun possible : un module n'a pas de surface HTML serveur | Pas pour le pilote. Candidate : repli textuel générique de la GraphicScene | **Réellement insuffisant** (limite partagée avec Circuit) |

## API core manquantes

**Nécessaires au pilote : 0.** Les deux candidates ci-dessous n'ont **pas** été créées (§5, §6, §136). Elles sont décrites selon la procédure du §5, pour un éventuel ticket du cœur séparé.

| Procédure §5 | `presentation.shape` (forme de nœud) | Repli textuel sans JavaScript |
|---|---|---|
| 1. Besoin exact | Dessiner un losange ou une pastille plutôt qu'un rectangle | Lire, sans JavaScript, les libellés de nœuds et de liens d'une ressource de module |
| 2. Générique ? | Oui : formes de diagramme (organigramme, réseau, UML), sans vocabulaire métier | Oui : un rendu de `GraphicScene` (nœuds, `source → target : label`) par l'hôte vaut pour tout module |
| 3. Existe déjà ? | Non : `NODE_VARIANTS` et `NODE_TONES` ne règlent que couleur et trait, `rx` fixe | Non : sans JavaScript, la page ressource n'a que le résumé et un message de repli |
| 4. Pourquoi pas dans le module | Une CSS de module sur `.gx-node-box` dépendrait de la structure privée du renderer ; un losange posé dans le calque n'existerait pas sans JavaScript et doublerait le rendu | Un module ne fournit aucun HTML serveur : il n'y a pas de point d'extension, et en créer un serait le ticket du cœur |
| 5. Proposition | Ticket du cœur MINEUR quand un module en a besoin pour sa fonction, pas pour l'esthétique d'un pilote | Ticket du cœur MINEUR à arbitrer, utile aussi à Circuit et à l'accessibilité |

## Dette découverte

1. **Lecture sans JavaScript** limitée au résumé (ci-dessus), commune à tous les modules.
2. **Formes** : rectangles seulement ; distinction par la couleur et la marque.
3. **Éditeur exposé sur un document bloqué** (deux `start`) : le cœur publie le contexte d'édition d'une ressource lue en `invalid-resource`, et chaque action est ensuite refusée (`resource-unusable`, message clair). Observation sur le comportement du cœur, sans gravité, non modifiée.
4. **Tab hors du champ** le laisse ouvert : c'est la conséquence voulue de « ni `blur`, ni enregistrement implicite ». Une fermeture par `focusout` serait possible, mais non fiable dans Firefox headless et risquée (fenêtre qui perd le focus).
5. **Largeurs de texte estimées** : 7,2 px par caractère monospace pour le repli, 6,5 px pour l'ancre d'arête. Les caractères larges (CJK) peuvent déborder.
6. **`foreignObject`** éprouvé dans Chromium et Firefox seulement ; WebKit n'a pas été testé.
7. **Tests sur l'hôte réel** : ils utilisent `forge_design.modules.host.ModuleHost` et `forge_design.web.server.create_server`. Ce sont des API d'hôte, pas du contrat des modules ; le code livré ne les importe pas (test).

## Recommandation pour la suite

1. Considérer la frontière **validée par deux domaines réels distincts**. Circuit est géométrique et topologique ; Flowchart est textuel. Aucun des deux n'a exigé de modification du cœur depuis FD-ARCH-001.
2. N'ouvrir un ticket du cœur que pour le **repli textuel sans JavaScript**, si l'accessibilité sans script devient un objectif. Il est générique et bénéficierait à Circuit.
3. Garder `presentation.shape` en réserve jusqu'à ce qu'un module en ait besoin pour sa fonction.
4. Faire évoluer Flowchart (création, suppression, déplacement par `nodeMove`) dans des tickets du module seulement, si l'outil doit devenir un éditeur.

## Fichiers créés

```text
ForgeDesign-Flowchart/
├── .gitignore
├── PROVENANCE.md
├── README.md
├── pyproject.toml
├── docs/
│   ├── flowchart-domain.md
│   ├── flowchart-editing.md
│   └── rapports/FD-MODULE-PILOT-001.md
├── examples/simple-flow.flow.json
├── forge_design_flowchart/
│   ├── __init__.py  actions.py  codec.py  contract.py  editor.py
│   ├── limits.py  models.py  scene.py  validation.py  py.typed
│   └── static/flow-editor.js  static/flowchart.css
└── tests/
    ├── flow_support.py
    ├── test_actions.py  test_codec.py  test_descriptor.py  test_editor_script.py
    ├── test_models.py  test_packaging.py  test_scene.py
    └── js/flow-editor.test.mjs
```

Aucun fichier créé ni modifié dans Forge Design ou ForgeDesign-Circuit.

## Validation finale

| Commande | Résultat |
|---|---|
| `python -m compileall -q forge_design_flowchart` | OK |
| `ruff check forge_design_flowchart tests` | All checks passed |
| `ruff format --check .` | Tout formaté |
| `pyright` (strict) | 0 erreur, 0 avertissement |
| `git diff --cached --check` | Propre |
| `pytest` | 175 passed |
| `node --test tests/js/flow-editor.test.mjs` | 26/26 |
| `python -m pip check` | Aucune dépendance cassée |
| Mutations | 70/70 |
| Roue + venv neuf (cœur, Circuit, Flowchart) | Métadonnée conforme, `pip check` OK |
| Chromium, Firefox (vraie commande, deux modules) | 12/12 chacun |
| Sans JavaScript (Chromium, Firefox) | OK |
| Cœur inchangé : pytest, Graphic Core Node, parcours génériques | 4 631 ; 134 ; 14/14 |

## État Git final

| Dépôt | État |
|---|---|
| ForgeDesign-Flowchart | `main`, un commit `feat: créer le module pilote Flowchart (FD-MODULE-PILOT-001)`, aucun remote, aucun push |
| Forge Design | HEAD `8cf8203` inchangé ; seul `docs/rapports/FD-CONTRACT-001.md` modifié, préservé, hors commit ; aucun commit |
| ForgeDesign-Circuit | HEAD `967b5b3` inchangé, arbre propre ; aucun commit |
