# Domaine Flowchart et format V0.1

Organigramme pédagogique simple : des nœuds typés reliés par des transitions orientées, éventuellement libellées. Pas de sous-graphe, de couloir (swimlane), de BPMN ni de diagramme d'activité UML.

## Ressource

| Élément | Valeur |
|---|---|
| Emplacement | `mvc/flowchart/**/*.flow.json` dans un projet Forge |
| Type de ressource | `flowchart` |
| Format | `flowchart-json`, version `0.1` (lecture et écriture) |
| Taille maximale | 4 Mio |
| État persistant | `nodes`, `edges` |
| État runtime seulement | sélection, viewport, historique, édition de texte en cours |
| Niveaux de validation | `structure`, `graph` (tous deux bloquants) |

## Format

```json
{
  "format_version": "0.1",
  "nodes": [
    { "id": "debut", "kind": "start", "label": "Début", "x": 0, "y": 0 },
    { "id": "valide", "kind": "decision", "label": "Valeur valide ?", "x": 0, "y": 200 }
  ],
  "edges": [
    { "id": "t1", "source": "debut", "target": "valide" },
    { "id": "t3", "source": "valide", "target": "continuer", "label": "Oui" }
  ]
}
```

Exemple complet : [`examples/simple-flow.flow.json`](../examples/simple-flow.flow.json).

### FlowNode

| Champ | Règle |
|---|---|
| `id` | Lettre puis lettres, chiffres, `_` ou `-` ; 64 caractères au plus |
| `kind` | `start`, `step`, `decision` ou `end` |
| `label` | 1 à 200 caractères, une ligne : ni caractère de contrôle (C0, C1, DEL), ni séparateur de ligne Unicode, ni espace en tête ou en fin |
| `x`, `y` | Entiers dans ±100 000 : coin supérieur gauche du nœud, en unités de scène |

### FlowEdge

| Champ | Règle |
|---|---|
| `id` | Même règle que les nœuds |
| `source`, `target` | Identités de nœuds existants, distinctes (pas de boucle sur un même nœud) |
| `label` | Facultatif, même règle que les nœuds ; **omis** quand il est absent, jamais `null` ni vide |

Le document ne persiste pas les points des arêtes : la projection les calcule.

### Identités

Les identités sont uniques dans un seul espace de noms, nœuds et arêtes confondus. L'ordre des collections est conservé (ordre de rendu et de tabulation), mais il ne sert jamais d'identité.

## Validation

**Structure** : le décodage échoue, le document n'est pas chargé. Les causes et leurs codes de diagnostic :

| Code | Cause |
|---|---|
| `flowchart.json-invalid` | Octets non UTF-8, JSON invalide, clé dupliquée, `NaN`/`Infinity` |
| `flowchart.validation-error` | Champ inconnu ou manquant, type de nœud inconnu, mauvais type de valeur, version de format inconnue |
| `flowchart.identity-invalid` | Identité mal formée |
| `flowchart.identity-duplicate` | Identité déjà utilisée (nœud ou arête) |
| `flowchart.endpoint-unknown` | Arête vers ou depuis un nœud absent |
| `flowchart.self-loop` | Arête d'un nœud vers lui-même |
| `flowchart.label-invalid` | Libellé vide, trop long, sur plusieurs lignes ou avec un caractère de contrôle |
| `flowchart.limit-exceeded` | Coordonnée hors bornes, identité trop longue, plus de 500 nœuds ou de 2 000 arêtes |

**Graph** : le document est lu et affiché avec ses diagnostics, mais il ne peut pas être écrit.

| Code | Règle |
|---|---|
| `flowchart.start-duplicate` | Au plus un nœud `start` |

Un document en cours de construction reste valide. Aucun `start` ni aucun `end` n'est exigé, et plusieurs `end` sont permis. Plusieurs arêtes entre les mêmes nœuds sont permises, dans un sens comme dans l'autre. Aucune analyse de chemins n'est faite (accessibilité, cycles, dominance).

## Projection vers la GraphicScene

`flow_scene(document)` est pure et déterministe : le même document produit la même scène, octet pour octet. La scène n'est jamais persistée.

| Document | Scène |
|---|---|
| `FlowNode` | Nœud de 208 unités de large ; hauteur selon le nombre de lignes (48, 66 ou 92) |
| `label` d'un nœud | `label` exact (nom accessible, info-bulle) ; `lines` = libellé replié sur 25 caractères, 3 lignes au plus, « … » au-delà |
| `kind` | `data.kind` ; variante de couleur générique : `start` → `category-3`, `decision` → `category-4`, `end` → `category-5`, `step` → `default` ; marque en tête du texte : `▶` début, `◇` décision, `■` fin |
| `FlowEdge` | Arête orientée (`arrow: end`), segment droit entre les bords des deux rectangles, sur la droite des centres |
| `label` d'une arête | `label` + `labelAt` (le moteur n'affiche un libellé qu'avec les deux) ; au milieu du segment, au-dessus s'il est plutôt horizontal, à droite s'il est plutôt vertical |
| Arêtes d'une même paire | Décalées de 16 unités par rang, dans l'ordre du document, à ±20 au plus, dans le sens canonique de la paire (identité la plus petite vers la plus grande) |
| Coordonnées | Translatées pour que le nœud le plus à gauche et le plus haut commence à 40 unités du bord |

**Limite.** Le Graphic Core ne dessine que des rectangles. Le début, la décision et la fin se distinguent par leur couleur et leur marque, pas par une forme (losange, pastille). Une primitive générique `presentation.shape` serait la candidate, mais elle n'existe pas et n'a pas été créée (voir le rapport).
