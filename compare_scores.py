"""
Compare two score datasets and generate a publishable diff page.

By default this compares the current scores.json against the version from the
last pre-refactor commit and writes:
    - site/score-diff.json
    - site/score-diff.html

Usage:
    python compare_scores.py
    python compare_scores.py --old-ref 72aa1bb
    python compare_scores.py --old-file /tmp/old-scores.json
"""

import argparse
import csv
import json
import os
import subprocess
from statistics import mean


DEFAULT_OLD_REF = "72aa1bb"
DEFAULT_NEW_FILE = "scores.json"
DEFAULT_OUTPUT_JSON = "site/score-diff.json"
DEFAULT_OUTPUT_HTML = "site/score-diff.html"

CURRENT_COMPONENT_FIELDS = [
    ("agentic_output_potential", "Agentic output"),
    ("cognitive_synthesis_complexity", "Cognitive"),
    ("environmental_unpredictability", "Environment"),
    ("ontological_human_necessity", "Human necessity"),
    ("systemic_accountability", "Accountability"),
]

LEGACY_COMPONENT_FIELDS = [
    ("digitality", "Digital"),
    ("routine_information_processing", "Routine info"),
    ("physical_world_dependency", "Physical"),
    ("human_relationship_dependency", "Relational"),
    ("judgment_accountability_dependency", "Judgment"),
]


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Exposure Score Changes</title>
<style>
* { box-sizing: border-box; }
:root {
  --bg: #f4efe6;
  --panel: rgba(255, 251, 244, 0.9);
  --ink: #171411;
  --muted: #6f665c;
  --line: rgba(23, 20, 17, 0.10);
  --up: #b5442f;
  --down: #1f7a63;
  --accent: #c88b2d;
  --shadow: 0 18px 45px rgba(55, 34, 10, 0.10);
}
body {
  margin: 0;
  font-family: Georgia, "Iowan Old Style", "Palatino Linotype", serif;
  color: var(--ink);
  background:
    radial-gradient(circle at top left, rgba(200, 139, 45, 0.16), transparent 28%),
    radial-gradient(circle at top right, rgba(31, 122, 99, 0.12), transparent 24%),
    linear-gradient(180deg, #f8f3eb 0%, #efe6d8 100%);
}
a { color: inherit; }
.shell {
  width: min(1180px, calc(100vw - 32px));
  margin: 0 auto;
  padding: 32px 0 48px;
}
.hero {
  display: grid;
  grid-template-columns: 1.3fr 0.9fr;
  gap: 18px;
  align-items: stretch;
}
.panel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 24px;
  box-shadow: var(--shadow);
  backdrop-filter: blur(10px);
}
.hero-copy {
  padding: 30px;
}
.eyebrow {
  display: inline-block;
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 14px;
}
h1 {
  margin: 0;
  font-size: clamp(34px, 5vw, 64px);
  line-height: 0.95;
  letter-spacing: -0.04em;
}
.lede {
  margin: 18px 0 0;
  max-width: 58ch;
  color: var(--muted);
  font-size: 18px;
  line-height: 1.55;
}
.hero-meta {
  margin-top: 22px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.pill {
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 8px 12px;
  font-size: 13px;
  background: rgba(255,255,255,0.5);
}
.hero-links {
  margin-top: 18px;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.hero-links a {
  text-decoration: none;
  border-bottom: 1px solid currentColor;
}
.summary {
  padding: 24px;
  display: grid;
  gap: 14px;
}
.summary h2,
.section-title {
  margin: 0;
  font-size: 14px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--muted);
}
.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.metric {
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 16px;
  background: rgba(255,255,255,0.45);
}
.metric .label {
  font-size: 12px;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.metric .value {
  margin-top: 8px;
  font-size: 30px;
  line-height: 1;
}
.metric .sub {
  margin-top: 8px;
  font-size: 12px;
  color: var(--muted);
}
.main-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 18px;
  margin-top: 18px;
}
.controls {
  padding: 18px 20px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}
.controls input,
.controls select {
  border: 1px solid var(--line);
  background: rgba(255,255,255,0.7);
  border-radius: 12px;
  padding: 10px 12px;
  font: inherit;
  min-height: 42px;
}
.controls input {
  flex: 1 1 260px;
}
.table-wrap {
  overflow: auto;
}
table {
  width: 100%;
  border-collapse: collapse;
}
thead th {
  position: sticky;
  top: 0;
  background: rgba(248, 243, 235, 0.98);
  backdrop-filter: blur(6px);
  z-index: 1;
}
th, td {
  text-align: left;
  padding: 14px 16px;
  border-bottom: 1px solid var(--line);
  vertical-align: top;
}
th {
  font-size: 12px;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
td small {
  display: block;
  margin-top: 4px;
  color: var(--muted);
  font-size: 12px;
}
.delta {
  font-weight: 700;
}
.delta.up { color: var(--up); }
.delta.down { color: var(--down); }
.bar {
  width: 108px;
  height: 8px;
  border-radius: 999px;
  background: rgba(23, 20, 17, 0.08);
  overflow: hidden;
  margin-top: 6px;
}
.bar > span {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, #d7b24f 0%, #b5442f 100%);
}
.component-list {
  display: grid;
  gap: 6px;
  font-size: 12px;
  color: var(--muted);
}
.empty {
  padding: 32px 20px;
  text-align: center;
  color: var(--muted);
}
@media (max-width: 900px) {
  .hero {
    grid-template-columns: 1fr;
  }
  .summary-grid {
    grid-template-columns: 1fr 1fr;
  }
}
@media (max-width: 640px) {
  .shell {
    width: min(100vw - 20px, 1180px);
    padding-top: 18px;
  }
  .hero-copy,
  .summary,
  .controls {
    padding: 18px;
  }
  .summary-grid {
    grid-template-columns: 1fr;
  }
  th, td {
    padding: 12px 10px;
  }
}
</style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div class="panel hero-copy">
        <div class="eyebrow">Score Diff</div>
        <h1>What changed when the scoring method changed?</h1>
        <p class="lede">
          This page compares the prior single-prompt exposure scores against the newer
          component-based scoring pipeline. Higher positive deltas mean the occupation
          moved up in AI exposure; negative deltas mean it moved down.
        </p>
        <div class="hero-meta" id="heroMeta"></div>
        <div class="hero-links">
          <a href="./index.html">Back to treemap</a>
          <a id="jsonLink" href="./score-diff.json">Open raw diff data</a>
        </div>
      </div>
      <aside class="panel summary">
        <h2>Summary</h2>
        <div class="summary-grid" id="summaryGrid"></div>
      </aside>
    </section>

    <section class="main-grid">
      <div class="panel">
        <div class="controls">
          <input id="search" type="search" placeholder="Filter by occupation or category">
          <select id="sort">
            <option value="abs_delta">Largest absolute change</option>
            <option value="delta_desc">Biggest increase</option>
            <option value="delta_asc">Biggest decrease</option>
            <option value="jobs_desc">Most jobs affected</option>
            <option value="title_asc">Title A-Z</option>
          </select>
          <select id="direction">
            <option value="all">All changes</option>
            <option value="up">Only increases</option>
            <option value="down">Only decreases</option>
            <option value="same">Only unchanged</option>
          </select>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Occupation</th>
                <th>Change</th>
                <th>Old</th>
                <th>New</th>
                <th>Jobs</th>
                <th>New components</th>
              </tr>
            </thead>
            <tbody id="rows"></tbody>
          </table>
        </div>
        <div class="empty" id="empty" hidden>No occupations match this filter.</div>
      </div>
    </section>
  </div>

<script>
let payload = null;
let visibleRows = [];

function fmtInt(n) {
  return n == null ? "—" : n.toLocaleString();
}

function fmtJobs(n) {
  if (n == null) return "—";
  if (n >= 1000000) return (n / 1000000).toFixed(1) + "M";
  if (n >= 1000) return Math.round(n / 1000) + "K";
  return String(n);
}

function fmtDelta(n) {
  if (n > 0) return `+${n}`;
  return String(n);
}

function escapeHtml(str) {
  return String(str).replace(/[&<>"]/g, ch => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;"
  }[ch]));
}

function renderSummary(summary) {
  const cards = [
    ["Occupations changed", fmtInt(summary.changed_count), `${summary.unchanged_count} unchanged`],
    ["Average score", `${summary.old_average.toFixed(1)} -> ${summary.new_average.toFixed(1)}`, `delta ${summary.average_delta > 0 ? "+" : ""}${summary.average_delta.toFixed(2)}`],
    ["Weighted average", `${summary.old_weighted_average.toFixed(1)} -> ${summary.new_weighted_average.toFixed(1)}`, `delta ${summary.weighted_average_delta > 0 ? "+" : ""}${summary.weighted_average_delta.toFixed(2)}`],
    ["Direction", `${summary.increased_count} up / ${summary.decreased_count} down`, `${fmtInt(summary.jobs_changed)} jobs in changed occupations`],
  ];
  document.getElementById("summaryGrid").innerHTML = cards.map(([label, value, sub]) => `
    <div class="metric">
      <div class="label">${label}</div>
      <div class="value">${value}</div>
      <div class="sub">${sub}</div>
    </div>
  `).join("");

  document.getElementById("heroMeta").innerHTML = [
    `Compared ${summary.total_count} occupations`,
    `Old source: ${payload.old_label}`,
    `New source: ${payload.new_label}`
  ].map(text => `<span class="pill">${escapeHtml(text)}</span>`).join("");
}

function sortRows(rows, mode) {
  const copy = [...rows];
  copy.sort((a, b) => {
    if (mode === "delta_desc") return (b.delta - a.delta) || (b.jobs - a.jobs);
    if (mode === "delta_asc") return (a.delta - b.delta) || (b.jobs - a.jobs);
    if (mode === "jobs_desc") return (b.jobs - a.jobs) || (Math.abs(b.delta) - Math.abs(a.delta));
    if (mode === "title_asc") return a.title.localeCompare(b.title);
    return (Math.abs(b.delta) - Math.abs(a.delta)) || (b.jobs - a.jobs);
  });
  return copy;
}

function filterRows(rows) {
  const term = document.getElementById("search").value.trim().toLowerCase();
  const direction = document.getElementById("direction").value;
  return rows.filter(row => {
    if (direction === "up" && row.delta <= 0) return false;
    if (direction === "down" && row.delta >= 0) return false;
    if (direction === "same" && row.delta !== 0) return false;
    if (!term) return true;
    return row.title.toLowerCase().includes(term) || row.category.toLowerCase().includes(term);
  });
}

function componentMarkup(row) {
  if (!row.new_components) return "—";
  const labels = row.component_labels && row.component_labels.length
    ? row.component_labels
    : [
        ["digitality", "Digital"],
        ["routine_information_processing", "Routine info"],
        ["physical_world_dependency", "Physical"],
        ["human_relationship_dependency", "Relational"],
        ["judgment_accountability_dependency", "Judgment"]
      ];
  return `<div class="component-list">` + labels.map(([key, label]) =>
    `<div>${label}: <strong>${row.new_components[key]}</strong></div>`
  ).join("") + `</div>`;
}

function renderRows() {
  const sortMode = document.getElementById("sort").value;
  visibleRows = sortRows(filterRows(payload.rows), sortMode);
  const tbody = document.getElementById("rows");
  const empty = document.getElementById("empty");

  if (!visibleRows.length) {
    tbody.innerHTML = "";
    empty.hidden = false;
    return;
  }

  empty.hidden = true;
  tbody.innerHTML = visibleRows.map(row => {
    const deltaClass = row.delta > 0 ? "up" : (row.delta < 0 ? "down" : "");
    const barPct = Math.max(0, Math.min(100, row.new_exposure * 10));
    return `
      <tr>
        <td>
          <strong><a href="${escapeHtml(row.url || "#")}">${escapeHtml(row.title)}</a></strong>
          <small>${escapeHtml(row.category_label || row.category)}</small>
        </td>
        <td>
          <div class="delta ${deltaClass}">${fmtDelta(row.delta)}</div>
          <small>rank shift ${row.rank_delta > 0 ? "+" : ""}${row.rank_delta}</small>
        </td>
        <td>${row.old_exposure}</td>
        <td>
          <strong>${row.new_exposure}</strong>
          <div class="bar"><span style="width:${barPct}%"></span></div>
        </td>
        <td>${fmtJobs(row.jobs)}</td>
        <td>${componentMarkup(row)}</td>
      </tr>
    `;
  }).join("");
}

fetch("./score-diff.json")
  .then(res => res.json())
  .then(data => {
    payload = data;
    renderSummary(data.summary);
    renderRows();
    document.getElementById("search").addEventListener("input", renderRows);
    document.getElementById("sort").addEventListener("change", renderRows);
    document.getElementById("direction").addEventListener("change", renderRows);
  });
</script>
</body>
</html>
"""


def load_scores_from_ref(ref):
    raw = subprocess.check_output(["git", "show", f"{ref}:scores.json"], text=True)
    return json.loads(raw)


def load_scores_from_file(path):
    with open(path) as f:
        return json.load(f)


def load_metadata():
    metadata = {}
    with open("occupations.csv") as f:
        reader = csv.DictReader(f)
        for row in reader:
            metadata[row["slug"]] = {
                "category": row["category"],
                "category_label": row["category"].replace("-", " ").title(),
                "jobs": int(row["num_jobs_2024"]) if row["num_jobs_2024"] else 0,
                "url": row.get("url", ""),
            }
    return metadata


def average(values):
    return mean(values) if values else 0.0


def weighted_average(rows, key):
    total_weight = sum(row["jobs"] for row in rows if row["jobs"])
    if not total_weight:
        return 0.0
    weighted = sum(row[key] * row["jobs"] for row in rows if row["jobs"])
    return weighted / total_weight


def extract_components(row):
    components = row.get("components", {})
    current = {
        "agentic_output_potential": components.get("agentic_output_potential", row.get("agentic_output_potential")),
        "cognitive_synthesis_complexity": components.get("cognitive_synthesis_complexity", row.get("cognitive_synthesis_complexity")),
        "environmental_unpredictability": components.get("environmental_unpredictability", row.get("environmental_unpredictability")),
        "ontological_human_necessity": components.get("ontological_human_necessity", row.get("ontological_human_necessity")),
        "systemic_accountability": components.get("systemic_accountability", row.get("systemic_accountability")),
    }
    if any(value is not None for value in current.values()):
        return current, CURRENT_COMPONENT_FIELDS

    legacy = {
        key: row.get(key)
        for key, _label in LEGACY_COMPONENT_FIELDS
    }
    return legacy, LEGACY_COMPONENT_FIELDS


def build_payload(old_scores, new_scores, metadata, old_label, new_label):
    old_map = {row["slug"]: row for row in old_scores}
    new_map = {row["slug"]: row for row in new_scores}

    shared_slugs = [slug for slug in new_map if slug in old_map]
    old_rank = {
        row["slug"]: i + 1
        for i, row in enumerate(sorted(old_scores, key=lambda r: (-r["exposure"], r["title"])))
    }
    new_rank = {
        row["slug"]: i + 1
        for i, row in enumerate(sorted(new_scores, key=lambda r: (-r["exposure"], r["title"])))
    }

    rows = []
    for slug in shared_slugs:
        old_row = old_map[slug]
        new_row = new_map[slug]
        meta = metadata.get(slug, {})
        new_components, component_labels = extract_components(new_row)
        rows.append({
            "slug": slug,
            "title": new_row.get("title") or old_row.get("title") or slug,
            "category": meta.get("category", "unknown"),
            "category_label": meta.get("category_label", "Unknown"),
            "jobs": meta.get("jobs", 0),
            "url": meta.get("url", ""),
            "old_exposure": old_row["exposure"],
            "new_exposure": new_row["exposure"],
            "delta": new_row["exposure"] - old_row["exposure"],
            "abs_delta": abs(new_row["exposure"] - old_row["exposure"]),
            "old_rank": old_rank.get(slug),
            "new_rank": new_rank.get(slug),
            "rank_delta": old_rank.get(slug, 0) - new_rank.get(slug, 0),
            "old_rationale": old_row.get("rationale", ""),
            "new_rationale": new_row.get("rationale", ""),
            "new_components": new_components,
            "component_labels": component_labels,
        })

    rows.sort(key=lambda row: (-row["abs_delta"], -row["jobs"], row["title"]))

    old_vals = [row["old_exposure"] for row in rows]
    new_vals = [row["new_exposure"] for row in rows]
    changed_rows = [row for row in rows if row["delta"] != 0]
    increased_rows = [row for row in rows if row["delta"] > 0]
    decreased_rows = [row for row in rows if row["delta"] < 0]

    summary = {
        "total_count": len(rows),
        "changed_count": len(changed_rows),
        "unchanged_count": len(rows) - len(changed_rows),
        "increased_count": len(increased_rows),
        "decreased_count": len(decreased_rows),
        "old_average": average(old_vals),
        "new_average": average(new_vals),
        "average_delta": average([row["delta"] for row in rows]),
        "old_weighted_average": weighted_average(rows, "old_exposure"),
        "new_weighted_average": weighted_average(rows, "new_exposure"),
        "weighted_average_delta": weighted_average(rows, "new_exposure") - weighted_average(rows, "old_exposure"),
        "jobs_changed": sum(row["jobs"] for row in changed_rows),
    }

    return {
        "old_label": old_label,
        "new_label": new_label,
        "summary": summary,
        "rows": rows,
    }


def write_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f)


def write_html(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(HTML_TEMPLATE)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-ref", default=DEFAULT_OLD_REF,
                        help="Git ref to load old scores.json from")
    parser.add_argument("--old-file", default=None,
                        help="Path to old scores.json (overrides --old-ref)")
    parser.add_argument("--new-file", default=DEFAULT_NEW_FILE)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-html", default=DEFAULT_OUTPUT_HTML)
    args = parser.parse_args()

    old_scores = load_scores_from_file(args.old_file) if args.old_file else load_scores_from_ref(args.old_ref)
    new_scores = load_scores_from_file(args.new_file)
    metadata = load_metadata()

    old_label = args.old_file if args.old_file else f"git:{args.old_ref}"
    payload = build_payload(old_scores, new_scores, metadata, old_label, args.new_file)

    write_json(args.output_json, payload)
    write_html(args.output_html)

    print(f"Wrote diff data to {args.output_json}")
    print(f"Wrote diff page to {args.output_html}")
    print(f"Compared {payload['summary']['total_count']} occupations")
    print(f"Changed: {payload['summary']['changed_count']}")


if __name__ == "__main__":
    main()
