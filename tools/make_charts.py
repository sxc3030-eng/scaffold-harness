"""Génère les graphiques des résultats en SVG statique, clair et sombre.

Pourquoi du SVG écrit à la main plutôt qu'une bibliothèque : le paquet n'a
aucune dépendance d'exécution, l'outillage n'en aura pas non plus. Et un SVG
statique reste lisible sur GitHub, dans un PDF et dans dix ans — ce qu'aucun
graphique généré par script côté client ne garantit.

Deux variantes par figure. GitHub choisit la bonne via `<picture>` et
`prefers-color-scheme`; un rapport imprimé prend la variante claire.

Palette validée avec `scripts/validate_palette.js` du guide de visualisation :
bleu accent contre gris de mise en retrait, aucune paire rouge/vert — elle
échouait à 4,1 ΔE en deutéranopie, et « zéro amélioration » n'est de toute
façon pas une bonne nouvelle à peindre en vert.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "docs" / "img"

FONT = (
    "ui-sans-serif,system-ui,-apple-system,'Segoe UI',Roboto,'Helvetica Neue',sans-serif"
)


@dataclass(frozen=True)
class Theme:
    name: str
    surface: str
    ink: str
    secondary: str
    muted: str
    grid: str
    accent: str
    plain: str


LIGHT = Theme("light", "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9",
              "#2a78d6", "#888780")
DARK = Theme("dark", "#1a1a19", "#ffffff", "#c3c2b7", "#898781", "#2c2c2a",
             "#3987e5", "#888780")


def bar_chart(
    theme: Theme,
    rows: list[tuple[str, float, bool]],
    value_of,
    axis_max: float,
    ticks: list[float],
    tick_label,
    title: str,
    subtitle: str,
    label_width: int = 210,
) -> str:
    """Barres horizontales, une teinte plus un gris de mise en retrait.

    La longueur encode déjà la grandeur : la couleur ne la redouble pas, elle
    sert uniquement à désigner la ligne qui porte le propos.
    """
    pad_left, pad_right, pad_top, pad_bottom = label_width, 108, 58, 34
    row_height, bar_height = 34, 20
    plot_width = 470
    height = pad_top + row_height * len(rows) + pad_bottom
    width = pad_left + plot_width + pad_right

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" '
        f'aria-labelledby="t d">',
        f"<title id='t'>{escape(title)}</title>",
        f"<desc id='d'>{escape(subtitle)}</desc>",
        f'<rect width="{width}" height="{height}" fill="{theme.surface}"/>',
        f'<text x="{pad_left}" y="24" font-family="{FONT}" font-size="15" '
        f'font-weight="500" fill="{theme.ink}">{escape(title)}</text>',
        f'<text x="{pad_left}" y="42" font-family="{FONT}" font-size="12" '
        f'fill="{theme.secondary}">{escape(subtitle)}</text>',
    ]

    for tick in ticks:
        x = pad_left + plot_width * tick / axis_max
        parts.append(
            f'<line x1="{x:.1f}" y1="{pad_top}" x2="{x:.1f}" '
            f'y2="{pad_top + row_height * len(rows)}" stroke="{theme.grid}" '
            f'stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{x:.1f}" y="{height - 12}" font-family="{FONT}" '
            f'font-size="11" fill="{theme.muted}" text-anchor="middle">'
            f"{escape(tick_label(tick))}</text>"
        )

    for index, (label, value, emphasised) in enumerate(rows):
        centre = pad_top + row_height * index + row_height / 2
        top = centre - bar_height / 2
        length = max(2.0, plot_width * value / axis_max)
        colour = theme.accent if emphasised else theme.plain
        radius = min(4.0, length / 2)
        parts.append(
            f'<path d="M{pad_left} {top} H{pad_left + length - radius:.1f} '
            f"a{radius:.1f} {radius:.1f} 0 0 1 {radius:.1f} {radius:.1f} "
            f"V{top + bar_height - radius:.1f} "
            f"a{radius:.1f} {radius:.1f} 0 0 1 -{radius:.1f} {radius:.1f} "
            f'H{pad_left} Z" fill="{colour}"/>'
        )
        parts.append(
            f'<text x="{pad_left - 10}" y="{centre + 4:.1f}" font-family="{FONT}" '
            f'font-size="12" fill="{theme.muted}" text-anchor="end">'
            f"{escape(label)}</text>"
        )
        parts.append(
            f'<text x="{pad_left + length + 8:.1f}" y="{centre + 4:.1f}" '
            f'font-family="{FONT}" font-size="12.5" font-weight="500" '
            f'fill="{theme.ink}">{escape(value_of(value))}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


ARMS = [
    ("deterministic executor", 100.0, True),
    ("llm_nexus_adaptive", 87.25, False),
    ("llm_experts", 81.00, False),
    ("llm_memory", 7.88, False),
    ("llm_direct", 6.38, False),
]

MODES = [
    ("copied from the prompt", 498, True),
    ("unjustified sentinel", 76, False),
    ("wrong recomputation", 43, False),
    ("off-contract format", 24, False),
    ("verification, not result", 21, False),
    ("precision lost", 11, False),
    ("no answer", 7, False),
    ("rounding", 3, False),
]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    written = []
    for theme in (LIGHT, DARK):
        figures = {
            f"accuracy-{theme.name}.svg": bar_chart(
                theme,
                ARMS,
                lambda v: f"{v:.2f} %".replace(".", "."),
                100.0,
                [0, 25, 50, 75, 100],
                lambda v: f"{v:.0f}%",
                "The deterministic path solves everything the LLM arms do not",
                "800 sealed questions · exact accuracy per path",
            ),
            f"failure-modes-{theme.name}.svg": bar_chart(
                theme,
                MODES,
                lambda v: f"{int(v)}  ({round(v / 6.8)} %)",
                520.0,
                [0, 100, 200, 300, 400, 500],
                lambda v: f"{v:.0f}",
                "Three destructions in four are a copy, not a miscalculation",
                "680 answers the layer destroyed · rounding explains 3 of them",
                label_width=200,
            ),
        }
        for name, svg in figures.items():
            (OUT / name).write_text(svg + "\n", encoding="utf-8")
            written.append(name)
    print(f"{len(written)} figures -> {OUT}")
    for name in sorted(written):
        print("   ", name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
