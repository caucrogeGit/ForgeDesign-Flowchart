# Édition des libellés

Le module ne permet de changer que le texte : le libellé d'un nœud ou celui d'une transition. Il ne permet ni de créer, ni de supprimer, ni de déplacer.

## Actions

Ce sont deux actions bornées du contrat des modules (FD-EDIT-001), en fonctions pures `handler(document, payload)`. Forge Design se charge de lire la ressource, de vérifier la révision, de valider, d'écrire de façon atomique et de journaliser l'historique.

| Action | Champs | Effet |
|---|---|---|
| `rename-node` | `node`, `label` | Remplace `label` du nœud désigné |
| `rename-edge` | `edge`, `label` | Remplace `label` de l'arête désignée ; vide ou fait d'espaces : libellé **supprimé** (champ omis) |

Seul le libellé visé change. Les identités, les types, les positions, les extrémités, l'ordre et tous les autres éléments sont repris à l'identique. Les espaces de tête et de fin sont retirés.

| Situation | Résultat HTTP |
|---|---|
| Libellé changé | 303 vers la page ressource, notice « Modification enregistrée. », une ligne d'historique |
| Même libellé | 303, notice « Aucune modification. », aucune écriture ni historique |
| Révision périmée | 409, écriture concurrente préservée |
| Nœud ou arête inconnu, libellé refusé | 422, message du module |
| Champ absent, identité de plus de 64 caractères | 400 |
| Origine étrangère | 403 |
| Document bloqué par la validation (deux `start`) | Refus, aucune écriture |

## Édition en place

Le script `flow-editor.js` est chargé par le client générique de Forge Design. Il n'utilise que l'API publique : la scène validée (`engine.scene()`, `engine.node()`), un calque monde (`addOverlay`), l'échelle (`viewport()`, `onViewChange`) et le contexte de l'hôte (URL d'action, révision, annonce).

| Élément | Interaction |
|---|---|
| Nœud | Poignée focalisable au coin supérieur droit, nom accessible « Renommer le nœud « Début » (début) » |
| Transition | Le Graphic Core ne sélectionne pas d'arête. Le calque porte, par transition, une zone de détection transparente le long du segment et une poignée au point du libellé, dans un seul élément focalisable : « Transition Vérifier → Continuer — Oui » ou « …, sans libellé » |
| Ouverture | Entrée (ou F2) sur la poignée, ou clic sur la poignée ou le segment |
| Champ | Champ HTML dans un `foreignObject` du calque, centré sur l'élément, contenu présélectionné ; boutons ✓ et ✕ |
| Enregistrer | Entrée dans le champ, ou ✓ ; une seule requête à la fois |
| Annuler | Échap (le focus revient à la poignée), ✕, ou appui hors du champ |
| Après enregistrement | Page rechargée, focus rendu à la poignée de l'élément renommé |
| Échec | Message annoncé ; le champ reste ouvert avec la saisie ; marqué invalide sur un 422 |

**Aucun enregistrement implicite.** Quitter le champ n'enregistre jamais rien, et aucun comportement ne dépend des événements `focus` ou `blur` (Firefox headless ne les émet pas de façon fiable).

**Touches réservées au champ.** Dans le champ, les touches ne remontent pas au moteur : Échap ne désélectionne pas, et Maj + flèches sélectionne du texte sans faire défiler le graphe.

**Taille écran stable.** Le champ est contre-mis à l'échelle (`translate(ancre) scale(1 / échelle)`) depuis `onViewChange`. Il garde 300 × 40 px quel que soit le zoom. Les poignées et les zones de détection gardent leur taille écran de la même façon. Ce calcul est purement géométrique : seule l'échelle est lue, le viewport n'est pas recopié.

**Configuration minimale.** `{ "renameNodeAction", "renameEdgeAction" }` : les identités, libellés et types sont lus dans la scène, l'URL et la révision dans le contexte de l'hôte.

**Sans JavaScript.** La page ressource reste consultable (chemin, révision, validation, diagnostics), sans dessin ni édition.

## Choix : inline plutôt que panneau

Les deux options ont été comparées par un prototype de panneau, non livré et mesuré dans Chromium et Firefox (détails dans le rapport). Le panneau fonctionne, mais :

- aucune surface HTML hôte n'est fournie au script. Le panneau doit donc écrire hors du calque (`document.body`) ou chercher le conteneur de la page dans une structure privée de l'hôte ;
- il s'affiche loin de l'élément édité (150 à 410 px mesurés, contre 32 à 115 px en place) et recouvre une partie du dessin.

L'édition en place reste entièrement dans le calque fourni par le moteur.

## Gardes

Des tests statiques vérifient l'absence des éléments suivants dans le code livré : `prompt()`, `innerHTML`, `eval`, `import`, CDN, `querySelector` sur la page, `parentNode`, `closest`, `ownerSVGElement`, classes du renderer (`gx-node`, `gx-edge`, `gx-scene`), état de module global, vocabulaire Circuit.

Les seuls éléments créés le sont dans le document du calque. Le seul écouteur global est l'appui hors du champ, retiré à la fermeture. La feuille `flowchart.css` ne vise que les classes `flow-*` posées par le script.
