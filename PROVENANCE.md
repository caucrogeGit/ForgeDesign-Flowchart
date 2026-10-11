# Provenance de ForgeDesign-Flowchart

ForgeDesign-Flowchart est une **création originale**. Il a été écrit pour le ticket FD-MODULE-PILOT-001 comme second module pilote du contrat des modules de Forge Design.

| Élément | Valeur |
|---|---|
| Raison d'être | Valider le moteur générique de Forge Design (contrat des modules, Graphic Core, actions bornées) avec un domaine réel distinct de Circuit |
| Date de création | 2026-10-11 |
| Base Forge Design | `8cf8203` (FD-RELEASE-001), version 0.2.0, sans aucune modification |
| Code copié | Aucun. Les conventions (codec strict, descripteur, tests contre l'hôte réel) suivent ForgeDesign-Circuit, sans copie de fichier |
| DrawCiel | Sans rapport : Flowchart n'est pas dérivé de DrawCiel |

Le module témoin `tests/flow_witness/` de Forge Design (FD-ARCH-001) est une preuve d'API interne aux tests du cœur. Flowchart n'en dérive pas : il en reprend seulement l'idée, celle d'un second domaine qui n'utilise que l'API publique.
