"""Statistiques appariées, sans dépendance externe.

Deux outils seulement, mais ce sont les deux qui manquent partout: un intervalle
de confiance sur une proportion, et un test apparié qui dit si une différence
observée peut être du bruit.
"""

from __future__ import annotations

from math import comb, sqrt

# Valeur critique de la loi normale pour un intervalle bilatéral à 95 %.
Z95 = 1.959963984540054


def wilson_interval(successes: int, total: int, z: float = Z95) -> tuple[float, float]:
    """Intervalle de Wilson pour une proportion.

    Préféré à l'intervalle normal parce qu'il reste valide aux petits effectifs
    et aux proportions extrêmes — exactement le régime où l'on travaille quand
    un jeu de tâches compte cinq questions. Sur 5/5, il renvoie environ
    [0,48 ; 1,00], ce qui rend visible l'impossibilité de conclure.
    """
    if total <= 0:
        return (0.0, 0.0)
    if successes < 0 or successes > total:
        raise ValueError("successes doit être compris entre 0 et total")
    proportion = successes / total
    denominator = 1.0 + z * z / total
    centre = (proportion + z * z / (2 * total)) / denominator
    spread = (
        z
        / denominator
        * sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total))
    )
    return (max(0.0, centre - spread), min(1.0, centre + spread))


def mcnemar_exact(only_left: int, only_right: int) -> float:
    """Test exact de McNemar bilatéral sur les paires discordantes.

    `only_left` = cas où la référence a raison et la variante a tort.
    `only_right` = l'inverse. Les cas où les deux s'accordent n'apportent
    aucune information et sont ignorés — c'est tout l'intérêt de l'appariement.

    Renvoie une p-valeur. Aucune paire discordante = aucune preuve de
    différence = 1.0.
    """
    if only_left < 0 or only_right < 0:
        raise ValueError("les comptes discordants doivent être positifs")
    discordant = only_left + only_right
    if discordant == 0:
        return 1.0
    smaller = min(only_left, only_right)
    tail = sum(comb(discordant, index) for index in range(smaller + 1))
    return min(1.0, 2.0 * tail / (2**discordant))
