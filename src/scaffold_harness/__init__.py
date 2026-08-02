"""Harnais de mesure d'échafaudage.

Ne mesure pas « quel score fait mon modèle » — les benchmarks existants le font.
Mesure « est-ce que la couche que j'ai construite par-dessus aide ou nuit ».
"""

from .core import (
    Case,
    ComparisonReport,
    Deviation,
    Response,
    VariantResult,
    compare,
)
from .stats import mcnemar_exact, wilson_interval

__all__ = [
    "Case",
    "ComparisonReport",
    "Deviation",
    "Response",
    "VariantResult",
    "compare",
    "mcnemar_exact",
    "wilson_interval",
]
