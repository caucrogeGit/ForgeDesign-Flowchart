"""Limites de la ressource Flowchart V0.1, plus strictes que le plafond spécialisé.

Le plafond en octets borne effectivement la ressource ; les plafonds de
collections bornent la validation et la projection (O(n)) indépendamment du
contenu des chaînes.
"""

# 4 Mio : un organigramme au plafond des collections, libellés pleins, tient
# sous 3 Mio ; le plafond technique des ressources spécialisées (64 Mio) n'est
# pas un objectif Flowchart.
MAX_FLOWCHART_RESOURCE_BYTES = 4 * 1024 * 1024

MAX_FLOWCHART_NODES = 500
MAX_FLOWCHART_EDGES = 2000

# Identité : lettre initiale, puis lettres, chiffres, « _ » ou « - ».
MAX_FLOWCHART_ID_CHARS = 64
# Libellé d'un nœud ou d'une arête : une ligne, sans caractère de contrôle.
MAX_FLOWCHART_LABEL_CHARS = 200

# Coordonnées entières du coin supérieur gauche d'un nœud, en unités de scène.
MAX_FLOWCHART_COORDINATE = 100_000
