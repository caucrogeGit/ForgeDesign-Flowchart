# ForgeDesign-Flowchart

Module externe Flowchart pour [Forge Design](https://github.com/caucrogeGit/ForgeDesign) : organigrammes simples (début, étape, décision, fin), arêtes orientées et libellées, libellés éditables en place.

C'est le **second module pilote** du contrat des modules de Forge Design (FD-MODULE-PILOT-001). Il a été créé pour vérifier que le moteur générique suffit à un domaine sans bornes, fils ni routage. Ce n'est pas encore un éditeur d'organigrammes complet : il ne permet ni de créer, ni de supprimer, ni de déplacer.

| Élément | Valeur |
|---|---|
| Distribution | `forge-design-flowchart` 0.1.0 |
| Paquet | `forge_design_flowchart` |
| Cœur requis | `forge-design>=0.2.0,<1` (Requires-Dist et `requires_forge_design`, identiques) |
| Contrat | `MODULE_API_VERSION = 1` |
| Module | `flowchart`, entrée « Modules → Flowchart » |
| Ressources | `mvc/flowchart/**/*.flow.json`, type `flowchart`, format `flowchart-json` 0.1 |
| Capacités | `open`, `validate`, `save`, `edit` |
| Actions | `rename-node` (`node`, `label`), `rename-edge` (`edge`, `label`) |
| Assets | `flow-editor.js` (script d'édition), `flowchart.css` (champ d'édition) |

Le module dépend de Forge Design, jamais l'inverse. Il n'importe que les API publiques `forge_design.modules` et `forge_design.specialized`, et ne dépend pas de ForgeDesign-Circuit. Les deux modules peuvent être activés ensemble.

## Installation et activation

```bash
python -m venv .venv
.venv/bin/pip install forge-design-flowchart        # ou : pip install -e .
.venv/bin/forge-design --module forge_design_flowchart
```

Avec Circuit :

```bash
forge-design --module forge_design_circuit --module forge_design_flowchart --no-browser
```

L'activation est explicite : le module n'est jamais découvert automatiquement. Si le cœur installé est hors de `>=0.2.0,<1`, Forge Design démarre quand même, sans activer le module, et affiche le diagnostic `core-version-incompatible`.

## Exemple

[`examples/simple-flow.flow.json`](examples/simple-flow.flow.json) : Début → Vérifier la valeur → Valeur valide ? → (Oui) Continuer / (Non) Signaler l'erreur → Fin. Pour l'ouvrir, copiez-le sous `mvc/flowchart/` d'un projet Forge.

## Documentation

- [Domaine et format V0.1](docs/flowchart-domain.md)
- [Édition des libellés](docs/flowchart-editing.md)
- [Provenance](PROVENANCE.md)
- [Rapport FD-MODULE-PILOT-001](docs/rapports/FD-MODULE-PILOT-001.md)

## Développement

```bash
python -m venv .venv
.venv/bin/pip install --config-settings editable_mode=compat -e ../ForgeDesign
.venv/bin/pip install --config-settings editable_mode=compat -e . pytest ruff pyright
# Facultatif, pour le test de coexistence :
.venv/bin/pip install --no-deps --config-settings editable_mode=compat -e ../ForgeDesign-Circuit
.venv/bin/python -m pytest
.venv/bin/ruff check forge_design_flowchart tests && .venv/bin/ruff format --check .
.venv/bin/pyright
node --test tests/js/flow-editor.test.mjs
```

Le mode éditable `compat` permet à Pyright de suivre les paquets installés.
