"""HTML rendering: one standalone file, shareable and printable.

Three choices, all deliberate:

* **the verdict first**, in plain words, including when it says the sample
  cannot settle the question;
* **the change table before the score table** — that is this tool's own
  contribution, not an appendix;
* **no external resource** — a report must open offline and travel as a single
  attachment.

The page carries both languages and a switch. A client who forwards it to a
colleague should not have to explain which build to ask for.
"""

from __future__ import annotations

from collections.abc import Mapping
from html import escape
from typing import Any

from ..i18n import FAQ, LANGS, WHAT, normalise, t
from .build import verdict_sentence

CSS = """
:root { color-scheme: light dark; }
body { font: 15px/1.55 system-ui, -apple-system, Segoe UI, sans-serif;
       max-width: 62rem; margin: 2rem auto; padding: 0 1.2rem; }
h1 { font-size: 1.5rem; margin-bottom: .2rem; }
.sub { opacity: .65; font-size: .9rem; margin-bottom: 1.6rem; }
.verdict { border-left: 5px solid; padding: .9rem 1.1rem; margin: 1rem 0 1.4rem;
           border-radius: 4px; font-size: 1.02rem; }
.verdict.loss         { border-color: #c0392b; background: rgba(192,57,43,.09); }
.verdict.gain         { border-color: #1e8449; background: rgba(30,132,73,.09); }
.verdict.inconclusive { border-color: #b7950b; background: rgba(183,149,11,.10); }
.tag { display: inline-block; font-weight: 700; letter-spacing: .08em;
       font-size: .74rem; padding: .18rem .5rem; border-radius: 3px;
       margin-right: .55rem; vertical-align: .08rem; color: #fff; }
.tag.loss { background: #c0392b; } .tag.gain { background: #1e8449; }
.tag.inconclusive { background: #b7950b; }
.name { font-weight: 600; }
table { border-collapse: collapse; width: 100%; margin: .6rem 0 1.8rem;
        font-variant-numeric: tabular-nums; }
th, td { padding: .5rem .7rem; text-align: right;
         border-bottom: 1px solid rgba(128,128,128,.28); }
th:first-child, td:first-child { text-align: left; }
thead th { font-size: .76rem; text-transform: uppercase; letter-spacing: .04em;
           opacity: .7; }
.destroyed { color: #c0392b; font-weight: 600; }
.improved  { color: #1e8449; font-weight: 600; }
.muted { opacity: .6; }
h2 { font-size: 1.05rem; margin-top: 2.2rem; }
.note { font-size: .87rem; opacity: .72; margin: -.35rem 0 .9rem; }
p { margin: .55rem 0; }
code, pre { font-family: ui-monospace, Consolas, monospace; font-size: .85rem; }
pre { background: rgba(128,128,128,.10); padding: .8rem; border-radius: 4px;
      overflow-x: auto; }
details { border-bottom: 1px solid rgba(128,128,128,.24); padding: .55rem 0; }
summary { cursor: pointer; font-weight: 600; }
details p { margin: .5rem 0 .2rem; opacity: .85; }
.cases td { vertical-align: top; font-size: .88rem; }
.cases td.q { text-align: left; max-width: 26rem; }
.cases .ans { font-family: ui-monospace, Consolas, monospace; }
.pill { font-size: .7rem; font-weight: 700; padding: .12rem .42rem;
        border-radius: 3px; color: #fff; white-space: nowrap; }
.pill.destroyed { background: #c0392b; } .pill.improved { background: #1e8449; }
.pill.neutral_change { background: #b7950b; }
.pill.unchanged { background: rgba(128,128,128,.55); }
.filters { display: flex; gap: .4rem; margin: .3rem 0 .8rem; flex-wrap: wrap; }
.filters button { font: inherit; font-size: .82rem; padding: .25rem .7rem;
                  border: 1px solid rgba(128,128,128,.45); background: none;
                  color: inherit; border-radius: 999px; cursor: pointer; }
.filters button[aria-pressed="true"] { background: rgba(128,128,128,.22);
                                       font-weight: 600; }
tbody.filtered tr { display: none; }
tbody.filtered tr.match { display: table-row; }
footer { margin-top: 2.5rem; font-size: .78rem; opacity: .6; word-break: break-all; }
.switch { float: right; font-size: .82rem; }
.switch a { text-decoration: none; opacity: .7; }
[data-lang] { display: none; } :root[lang="en"] [data-lang="en"],
:root[lang="fr"] [data-lang="fr"] { display: revert; }
"""

SCRIPT = """
(function () {
  var root = document.documentElement;
  var wanted = (navigator.language || 'en').slice(0, 2);
  if (wanted !== 'fr' && wanted !== 'en') { wanted = 'en'; }
  root.setAttribute('lang', wanted);
  document.addEventListener('click', function (event) {
    var trigger = event.target.closest('[data-switch]');
    if (!trigger) { return; }
    event.preventDefault();
    root.setAttribute('lang', root.getAttribute('lang') === 'fr' ? 'en' : 'fr');
  });
  document.addEventListener('click', function (event) {
    var button = event.target.closest('[data-filter]');
    if (!button) { return; }
    var wanted = button.getAttribute('data-filter');
    var body = button.closest('section').querySelector('tbody');
    button.parentNode.querySelectorAll('button').forEach(function (other) {
      other.setAttribute('aria-pressed', other === button ? 'true' : 'false');
    });
    if (wanted === 'all') { body.classList.remove('filtered'); return; }
    body.classList.add('filtered');
    body.querySelectorAll('tr').forEach(function (line) {
      var label = line.getAttribute('data-label') || '';
      var hit = wanted === 'changed' ? label !== 'unchanged' : label === wanted;
      line.classList.toggle('match', hit);
    });
  });
})();
"""


def _pct(value: float) -> str:
    return f"{value:.1%}"


def _cases_section(lang: str, report: Mapping[str, Any]) -> str:
    """Le détail par question, destructions en tête.

    Sans JavaScript, toutes les lignes restent visibles: les filtres sont un
    confort, pas une condition de lecture.
    """
    rows = report.get("cases") or []
    if not rows:
        return ""
    names = list((rows[0].get("variants") or {}).keys())
    if not names:
        return ""
    primary = names[0]

    def clip(value: Any, size: int = 150) -> str:
        text_value = "—" if value in (None, "") else str(value)
        text_value = " ".join(text_value.split())
        return escape(text_value[:size] + ("…" if len(text_value) > size else ""))

    lines = []
    for case in rows:
        row = (case.get("variants") or {}).get(primary) or {}
        label = str(row.get("label", "unchanged"))
        lines.append(
            f'<tr data-label="{escape(label)}">'
            f'<td class="q">{clip(case.get("question"))}</td>'
            f'<td class="ans">{clip(case.get("reference_answer"), 40)}</td>'
            f'<td class="ans">{clip(row.get("answer"), 40)}</td>'
            f'<td class="ans muted">{clip(case.get("target"), 40)}</td>'
            f'<td><span class="pill {escape(label)}">'
            f'{escape(t(lang, "label." + label))}</span></td></tr>'
        )

    truncated = (
        f'<div class="note">{escape(t(lang, "cases.truncated", shown=len(rows), total=report["case_count"]))}</div>'
        if report.get("cases_truncated")
        else ""
    )
    buttons = "".join(
        f'<button type="button" data-filter="{key}" '
        f'aria-pressed="{"true" if key == "all" else "false"}">'
        f'{escape(t(lang, "filter." + key))}</button>'
        for key in ("all", "destroyed", "improved", "changed")
    )
    return f"""
<section>
<h2>{escape(t(lang, "section.cases"))}</h2>
<div class="note">{escape(t(lang, "section.cases.note"))}</div>
{truncated}
<div class="filters">{buttons}</div>
<table class="cases"><thead><tr>
<th>{escape(t(lang, "col.question"))}</th><th>{escape(t(lang, "col.reference"))}</th>
<th>{escape(t(lang, "col.answer"))}</th><th>{escape(t(lang, "col.expected"))}</th>
<th></th></tr></thead><tbody>{"".join(lines)}</tbody></table>
</section>"""


def _section(lang: str, report: Mapping[str, Any]) -> str:
    baseline = report["baseline"]
    variants = report.get("variants") or []
    reference = report.get("reference_for_deviation", "baseline")
    question_set = report.get("question_set", {})

    verdicts = "".join(
        f'<div class="verdict {escape(str(row.get("outcome", "inconclusive")))}">'
        f'<span class="tag {escape(str(row.get("outcome", "inconclusive")))}">'
        f'{escape(t(lang, "outcome." + str(row.get("outcome", "inconclusive"))))}</span>'
        f'<span class="name">{escape(str(row["name"]))}</span> — '
        f'{escape(verdict_sentence(report, row, lang))}</div>'
        for row in variants
    )

    def score_row(row: Mapping[str, Any], label: str) -> str:
        low, high = row["accuracy_ci95"]
        return (
            f"<tr><td>{escape(label)}</td><td>{row['correct']}/{row['cases']}</td>"
            f"<td>{_pct(row['accuracy'])}</td>"
            f"<td class='muted'>[{_pct(low)} – {_pct(high)}]</td>"
            f"<td>{_pct(row['coverage'])}</td><td>{row['refused']}</td></tr>"
        )

    def change_row(row: Mapping[str, Any]) -> str:
        dev = row["deviation_vs_reference"]
        net = dev["net"]
        css = "improved" if net > 0 else ("destroyed" if net < 0 else "muted")
        return (
            f"<tr><td>{escape(str(row['name']))}</td><td>{dev['changed']}</td>"
            f"<td class='improved'>{dev['improved']}</td>"
            f"<td class='destroyed'>{dev['destroyed']}</td>"
            f"<td class='muted'>{dev['neutral_changed']}</td>"
            f"<td class='{css}'>{net:+d}</td></tr>"
        )

    def cost_row(row: Mapping[str, Any]) -> str:
        return (
            f"<tr><td>{escape(str(row['name']))}</td>"
            f"<td>×{row['token_ratio_vs_baseline']:.2f}</td>"
            f"<td>×{row['latency_ratio_vs_baseline']:.2f}</td>"
            f"<td>{row['p95_latency_ms']:.0f} ms</td>"
            f"<td class='muted'>p={row['mcnemar_p']:.3f}</td></tr>"
        )

    what = "".join(f"<p>{block}</p>" for block in WHAT[lang])
    faq = "".join(
        f"<details><summary>{escape(question)}</summary><p>{escape(answer)}</p></details>"
        for question, answer in FAQ[lang]
    )
    reproduction = report.get("reproduction")
    repro = (
        f'<h2>{escape(t(lang, "section.repro"))}</h2>'
        f"<pre>{escape(str(reproduction))}</pre>"
        if reproduction
        else ""
    )

    return f"""
<div class="switch"><a href="#" data-switch>{escape(t(lang, "lang.switch"))}</a></div>
<h1>{escape(t(lang, "title"))}</h1>
<div class="sub">{escape(t(lang, "subtitle", count=report["case_count"],
                           name=str(question_set.get("name", "—"))))}
<span class="muted">({escape(str(question_set.get("sha256", ""))[:16])})</span></div>

{verdicts}

<h2>{escape(t(lang, "section.changed"))}</h2>
<div class="note">{escape(t(lang, "section.changed.note", reference=str(reference)))}</div>
<table><thead><tr>
<th>{escape(t(lang, "col.variant"))}</th><th>{escape(t(lang, "col.changed"))}</th>
<th>{escape(t(lang, "col.improved"))}</th><th>{escape(t(lang, "col.destroyed"))}</th>
<th>{escape(t(lang, "col.neutral"))}</th><th>{escape(t(lang, "col.net"))}</th>
</tr></thead><tbody>{"".join(change_row(row) for row in variants)}</tbody></table>

<h2>{escape(t(lang, "section.accuracy"))}</h2>
<div class="note">{escape(t(lang, "section.accuracy.note"))}</div>
<table><thead><tr>
<th>{escape(t(lang, "col.path"))}</th><th>{escape(t(lang, "col.correct"))}</th>
<th>{escape(t(lang, "col.accuracy"))}</th><th>{escape(t(lang, "col.ci"))}</th>
<th>{escape(t(lang, "col.coverage"))}</th><th>{escape(t(lang, "col.refused"))}</th>
</tr></thead><tbody>{score_row(baseline, t(lang, "row.baseline"))
    + "".join(score_row(row, str(row["name"])) for row in variants)}</tbody></table>

<h2>{escape(t(lang, "section.cost"))}</h2>
<table><thead><tr>
<th>{escape(t(lang, "col.variant"))}</th><th>{escape(t(lang, "col.tokens"))}</th>
<th>{escape(t(lang, "col.latency"))}</th><th>{escape(t(lang, "col.latency_abs"))}</th>
<th>{escape(t(lang, "col.mcnemar"))}</th>
</tr></thead><tbody>{"".join(cost_row(row) for row in variants)}</tbody></table>

{_cases_section(lang, report)}
<h2>{escape(t(lang, "section.what"))}</h2>{what}
<h2>{escape(t(lang, "section.faq"))}</h2>{faq}
{repro}
"""


def render(report: Mapping[str, Any], lang: str | None = None) -> str:
    """Rend le rapport. Sans `lang`, la page embarque les deux langues.

    Le lecteur voit la sienne (détectée par le navigateur, anglais par défaut)
    et peut basculer. Un rapport transmis ne doit pas obliger son destinataire à
    redemander une autre version.
    """
    if lang is not None:
        chosen = normalise(lang)
        body = f'<div data-lang="{chosen}">{_section(chosen, report)}</div>'
        script = f'<script>document.documentElement.setAttribute("lang","{chosen}");</script>'
    else:
        body = "".join(
            f'<div data-lang="{code}">{_section(code, report)}</div>' for code in LANGS
        )
        script = f"<script>{SCRIPT}</script>"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Scaffold report</title><style>{CSS}</style></head><body>
{body}
<footer>{escape(t("en", "signature"))}: {escape(str(report.get("report_sha256", "")))}</footer>
{script}
</body></html>"""
