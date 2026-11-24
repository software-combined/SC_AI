"""Build the codebase AI readiness report as one self-contained HTML file.

Usage:  python3 -I build_report.py results.json report.html

Reads results.json (written by the agent) and the skill's framework.json.
The page holds its own style, needs no network, and works in light and dark
mode, on a phone and in print. Standard library only. It never changes
results.json; an invalid file stops the build with a clear error.
"""
import datetime
import html
import json
import pathlib
import sys

# This script sits in <plugin-root>/scripts; the skill folder holds the framework and the style.
SKILL = pathlib.Path(__file__).resolve().parent.parent / "skills" / "codebase-ai-readiness"
COLOUR = {1: "red", 2: "red", 3: "amber", 4: "green", 5: "green"}
WORD = {"red": "Red", "amber": "Amber", "green": "Green", "na": "Not applicable", "nc": "Not checked"}
e = html.escape


def fail(message):
    print("build_report: " + message, file=sys.stderr)
    sys.exit(1)


def load(results_path):
    framework = json.loads((SKILL / "references" / "framework.json").read_text(encoding="utf-8"))
    results = json.loads(pathlib.Path(results_path).read_text(encoding="utf-8"))
    listed = [a.get("itemCode") for a in results.get("answers", [])]
    repeated = sorted({c for c in listed if listed.count(c) > 1}, key=str)
    if repeated:
        fail(f"each question needs one answer. Repeated: {repeated}.")
    answers = {a.get("itemCode"): a for a in results.get("answers", [])}
    items = {i["code"]: i for d in framework["dimensions"] for i in d["items"]}
    codes = list(items)
    missing = [c for c in codes if c not in answers]
    extra = [c for c in answers if c not in codes]
    if missing or extra:
        fail(f"answers must match the framework. Missing: {missing or 'none'}. Unknown: {extra or 'none'}.")
    for code, answer in answers.items():
        state = answer.get("answer", {})
        if state.get("kind") == "scored" and state.get("level") not in COLOUR:
            fail(f"question {code} needs a level from 1 to 5.")
        if state.get("kind") not in ("scored", "not-applicable", "unanswered"):
            fail(f"question {code} must be scored, not-applicable or unanswered.")
        if state.get("kind") == "not-applicable" and not items[code].get("naAllowed"):
            fail(f"question {code} does not allow not-applicable.")
    for field in ("repository", "commit", "assessedAt", "summary"):
        if not results.get(field):
            fail(f"results.json needs '{field}'.")
    return framework, results, answers


def when(stamp):
    """Show an ISO timestamp as '23 November 2026, 11:08 (UTC+11:00)'."""
    try:
        moment = datetime.datetime.fromisoformat(stamp)
    except ValueError:
        return stamp
    offset = moment.strftime("%z")
    zone = f" (UTC{offset[:3]}:{offset[3:]})" if offset else ""
    return f"{moment.day} {moment:%B %Y, %H:%M}{zone}"


def card(item, answer):
    state = answer["answer"]
    level = state.get("level")
    colour = COLOUR[level] if state["kind"] == "scored" else "nc" if state["kind"] == "unanswered" else "na"
    descriptor = next((d["text"] for d in item["descriptors"] if d["level"] == level), "")
    dots = "".join(f'<span class="dot{" on" if level and n <= level else ""}"></span>' for n in range(1, 6))
    score = (f'<div class="score"><span class="dots" aria-hidden="true">{dots}</span>'
             f'<span>Level {level} of 5</span><span class="tag tag-{colour}">{WORD[colour]}</span></div>'
             if level else f'<div class="score"><span class="tag tag-na">{WORD[colour]}</span></div>')
    return (f'<article class="card card-{colour}"><h3><span class="code">{e(item["code"])}</span>{e(item["subCapability"])}</h3>'
            f'{score}<p>{e(answer.get("reason", ""))}</p>'
            + (f'<p class="level-text muted">{e(descriptor)}</p>' if descriptor else "")
            + f'<details><summary>Evidence</summary><p>{e(answer.get("evidence", ""))}</p></details></article>')


def checked(verification):
    """The score check from results.json: who checked, what held, and each change or rejected suggestion."""
    if not isinstance(verification, dict):
        return '<div class="panel"><h3>Score check</h3><p>No score check was recorded.</p></div>'
    who = "A second agent" if verification.get("checkedBy") == "subagent" else "The scoring agent itself"
    changed, rejected = verification.get("changed") or [], verification.get("rejected") or []
    rows = [f'<li>{e(str(c.get("itemCode", "")))}: level {e(str(c.get("from", "")))} to {e(str(c.get("to", "")))}. '
            f'{e(str(c.get("why", "")))}</li>' for c in changed]
    rows += [f'<li>{e(str(r.get("itemCode", "")))}: suggestion not accepted. '
             f'{e(str(r.get("why", "")))}</li>' for r in rejected]
    return (f'<div class="panel"><h3>Score check</h3><p>{who} checked the scores against the evidence: '
            f'{e(str(verification.get("held", "?")))} held, {len(changed)} changed, '
            f'{len(rejected)} suggestions not accepted.</p>'
            + (f'<ul class="notes">{"".join(rows)}</ul>' if rows else "") + f'<p>{second(verification)}</p></div>')


def second(verification):
    check = verification.get("secondCheck")
    if not isinstance(check, dict):
        return "No second check was recorded."
    if check.get("skipped"):
        return "The second check did not run: " + e(str(check["skipped"]))
    asked = check.get("questions") or []
    return (f"A second check looked again at {len(asked)} questions ({e(', '.join(map(str, asked)))}): "
            f"{e(str(check.get('held', '?')))} held.")


def render(framework, results, answers):
    levels = [a["answer"]["level"] for a in answers.values() if a["answer"]["kind"] == "scored"]
    counts = {c: sum(1 for lv in levels if COLOUR[lv] == c) for c in ("green", "amber", "red")}
    average = f"{sum(levels) / len(levels):.1f}" if levels else "n/a"
    unchecked = sum(1 for a in answers.values() if a["answer"]["kind"] == "unanswered")
    tiles = (f'<div class="tile tile-overall"><span class="tile-number">{average}</span><span class="tile-label">Average out of 5'
             + (f', {unchecked} not checked' if unchecked else '') + '</span></div>'
             + "".join(f'<div class="tile tile-{c}"><span class="tile-number">{counts[c]}</span><span class="tile-label">{WORD[c]}</span></div>'
                       for c in ("green", "amber", "red")))
    actions = "".join(f'<li><strong>{e(a.get("title", ""))}</strong> <span class="muted">({e(", ".join(a.get("itemCodes", [])))})</span>'
                      f'<p>{e(a.get("firstStep", ""))}</p></li>' for a in results.get("actions", []))
    dimensions = "".join(
        f'<section><div class="dim-head"><h2>{e(d["name"])}</h2></div><p class="dim-summary">{e(d.get("summary", ""))}</p>'
        f'<div class="cards">{"".join(card(i, answers[i["code"]]) for i in d["items"])}</div></section>'
        for d in framework["dimensions"])
    notes = "".join(f"<li>{e(n)}</li>" for n in results.get("notChecked", []))
    check = checked(results.get("verification"))
    style = (SKILL / "assets" / "report.css").read_text(encoding="utf-8")
    return f"""<!doctype html>
<html lang="en-AU"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI readiness: {e(results["repository"])}</title><style>{style}</style>
<script>document.documentElement.dataset.theme=matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'</script></head>
<body><a class="skip" href="#results">Skip to results</a><div class="shell">
<header><div class="mast"><span>Software Combined</span><button type="button" onclick="var r=document.documentElement;r.dataset.theme=r.dataset.theme==='dark'?'light':'dark'">Light or dark</button></div>
<h1>AI readiness: {e(results["repository"])}</h1><p class="lead">{e(results["summary"])}</p>
<p class="context"><span>Unit: {e(results.get("unit", "repository"))}</span><span>Commit {e(results["commit"])}</span><span>Assessed {e(when(results["assessedAt"]))}</span><span>{e(framework["name"])}, {len(answers)} questions</span></p></header>
<main id="results"><div class="tiles">{tiles}</div>
{f'<div class="panel actions-panel"><h3>Top actions</h3><ol class="actions">{actions}</ol></div>' if actions else ''}
{dimensions}
{f'<div class="panel"><h3>Not checked</h3><ul class="notes">{notes}</ul></div>' if notes else ''}
{check}
</main><footer>Levels: 1 or 2 red, 3 amber, 4 or 5 green. Each score is based on the evidence shown under it.</footer></div></body></html>
"""


def main():
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    framework, results, answers = load(sys.argv[1])
    pathlib.Path(sys.argv[2]).write_text(render(framework, results, answers), encoding="utf-8")
    print("Wrote " + sys.argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main())
