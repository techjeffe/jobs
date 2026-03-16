"""
Generate prompt.md — a single markdown file containing project data that can be
copy-pasted into an LLM for analysis and discussion.

This version is adapted to the component-based scoring system in this fork.

Usage:
    python make_prompt.py
"""

import csv
import json


def fmt_pay(pay):
    if pay is None:
        return "?"
    return f"${pay:,}"


def fmt_jobs(jobs):
    if jobs is None:
        return "?"
    if jobs >= 1_000_000:
        return f"{jobs / 1e6:.1f}M"
    if jobs >= 1_000:
        return f"{jobs / 1e3:.0f}K"
    return str(jobs)


def avg(values):
    return sum(values) / len(values) if values else 0


def weighted_avg(records, key):
    weighted_sum = sum((r[key] or 0) * (r["jobs"] or 0) for r in records if r[key] is not None and r["jobs"])
    weight = sum(r["jobs"] or 0 for r in records if r[key] is not None and r["jobs"])
    return weighted_sum / weight if weight else 0


def load_diff_summary():
    try:
        with open("site/score-diff.json") as f:
            return json.load(f)["summary"]
    except FileNotFoundError:
        return None


def education_short(label):
    return {
        "High school diploma or equivalent": "HS diploma",
        "Bachelor's degree": "Bachelor's",
        "Master's degree": "Master's",
        "Doctoral or professional degree": "Doctoral/professional",
        "Associate's degree": "Associate's",
        "Postsecondary nondegree award": "Postsecondary",
        "No formal educational credential": "No formal credential",
        "Some college, no degree": "Some college",
        "See How to Become One": "Varies",
    }.get(label, label or "?")


def component_line(record):
    return (
        f"digitality={record.get('digitality', '?')}, "
        f"routine_info={record.get('routine_information_processing', '?')}, "
        f"physical={record.get('physical_world_dependency', '?')}, "
        f"relationships={record.get('human_relationship_dependency', '?')}, "
        f"judgment={record.get('judgment_accountability_dependency', '?')}"
    )


def main():
    with open("occupations.json") as f:
        occupations = json.load(f)

    with open("occupations.csv") as f:
        csv_rows = {row["slug"]: row for row in csv.DictReader(f)}

    with open("scores.json") as f:
        scores = {row["slug"]: row for row in json.load(f)}

    diff_summary = load_diff_summary()

    records = []
    for occ in occupations:
        slug = occ["slug"]
        row = csv_rows.get(slug, {})
        score = scores.get(slug, {})
        pay = int(row["median_pay_annual"]) if row.get("median_pay_annual") else None
        jobs = int(row["num_jobs_2024"]) if row.get("num_jobs_2024") else None
        records.append({
            "title": occ["title"],
            "slug": slug,
            "category": row.get("category", occ.get("category", "")),
            "pay": pay,
            "jobs": jobs,
            "outlook_pct": int(row["outlook_pct"]) if row.get("outlook_pct") else None,
            "outlook_desc": row.get("outlook_desc", ""),
            "education": row.get("entry_education", ""),
            "exposure": score.get("exposure"),
            "rationale": score.get("rationale", ""),
            "digitality": score.get("digitality"),
            "routine_information_processing": score.get("routine_information_processing"),
            "physical_world_dependency": score.get("physical_world_dependency"),
            "human_relationship_dependency": score.get("human_relationship_dependency"),
            "judgment_accountability_dependency": score.get("judgment_accountability_dependency"),
            "url": occ.get("url", ""),
        })

    records.sort(key=lambda r: (-(r["exposure"] or 0), -(r["jobs"] or 0), r["title"]))

    total_jobs = sum(r["jobs"] or 0 for r in records)
    total_wages = sum((r["jobs"] or 0) * (r["pay"] or 0) for r in records)
    exposure_avg = avg([r["exposure"] for r in records if r["exposure"] is not None])
    exposure_wavg = weighted_avg(records, "exposure")

    lines = []
    lines.append("# AI Exposure of the US Job Market")
    lines.append("")
    lines.append(
        "This document packages the dataset in this fork into a single markdown file "
        "for LLM analysis. It includes BLS occupation data, the current component-based "
        "AI exposure scores, and summary statistics from the site."
    )
    lines.append("")
    lines.append("Live visualization: https://jobs-techjeffes-projects.vercel.app/")
    lines.append("GitHub fork: https://github.com/techjeffe/jobs")
    lines.append("Upstream inspiration: https://github.com/karpathy/jobs")
    lines.append("")

    lines.append("## Methodology")
    lines.append("")
    lines.append(
        "In this fork, the model does not assign the final AI Exposure score directly. "
        "Instead, it scores five component dimensions from 0 to 10:"
    )
    lines.append("- digitality")
    lines.append("- routine information processing")
    lines.append("- physical-world dependency")
    lines.append("- human relationship dependency")
    lines.append("- judgment/accountability dependency")
    lines.append("")
    lines.append(
        "The final AI Exposure score is then derived in code from those components. "
        "This was done to reduce prompt anchoring and make the scoring system more inspectable."
    )
    lines.append("")
    lines.append("Interpretation note:")
    lines.append("- higher digitality and routine information processing tend to raise exposure")
    lines.append("- higher physical, relational, and judgment-heavy work tend to lower exposure")
    lines.append("")

    if diff_summary:
        lines.append("## Comparison to the earlier scoring approach")
        lines.append("")
        lines.append(
            f"- Occupations compared: {diff_summary['total_count']}"
        )
        lines.append(
            f"- Occupations changed under the new method: {diff_summary['changed_count']}"
        )
        lines.append(
            f"- Old average exposure: {diff_summary['old_average']:.2f}"
        )
        lines.append(
            f"- New average exposure: {diff_summary['new_average']:.2f}"
        )
        lines.append(
            f"- Old job-weighted average exposure: {diff_summary['old_weighted_average']:.2f}"
        )
        lines.append(
            f"- New job-weighted average exposure: {diff_summary['new_weighted_average']:.2f}"
        )
        lines.append(
            f"- Increased occupations: {diff_summary['increased_count']}"
        )
        lines.append(
            f"- Decreased occupations: {diff_summary['decreased_count']}"
        )
        lines.append("")

    lines.append("## Aggregate statistics")
    lines.append("")
    lines.append(f"- Total occupations: {len(records)}")
    lines.append(f"- Total jobs: {total_jobs:,} ({total_jobs / 1e6:.0f}M)")
    lines.append(f"- Total annual wages: ${total_wages / 1e12:.1f}T")
    lines.append(f"- Average AI exposure: {exposure_avg:.2f}/10")
    lines.append(f"- Job-weighted average AI exposure: {exposure_wavg:.2f}/10")
    lines.append("")

    lines.append("### Average component scores")
    lines.append("")
    for key, label in [
        ("digitality", "Digitality"),
        ("routine_information_processing", "Routine information processing"),
        ("physical_world_dependency", "Physical-world dependency"),
        ("human_relationship_dependency", "Human relationship dependency"),
        ("judgment_accountability_dependency", "Judgment/accountability dependency"),
    ]:
        vals = [r[key] for r in records if r[key] is not None]
        lines.append(f"- {label}: {avg(vals):.2f}")
    lines.append("")

    lines.append("### Average exposure by education level (job-weighted)")
    lines.append("")
    edu_groups = [
        ("No degree / HS diploma", ["No formal educational credential", "High school diploma or equivalent"]),
        ("Postsecondary / Associate's", ["Postsecondary nondegree award", "Some college, no degree", "Associate's degree"]),
        ("Bachelor's", ["Bachelor's degree"]),
        ("Master's", ["Master's degree"]),
        ("Doctoral / Professional", ["Doctoral or professional degree"]),
    ]
    lines.append("| Education | Avg exposure | Jobs |")
    lines.append("|-----------|-------------|------|")
    for name, matches in edu_groups:
        group = [r for r in records if r["education"] in matches and r["exposure"] is not None and r["jobs"]]
        if not group:
            continue
        lines.append(f"| {name} | {weighted_avg(group, 'exposure'):.1f} | {fmt_jobs(sum(r['jobs'] for r in group))} |")
    lines.append("")

    lines.append("### Highest-exposure occupations")
    lines.append("")
    lines.append("| Occupation | Exposure | Jobs | Components |")
    lines.append("|-----------|----------|------|------------|")
    for r in records[:20]:
        lines.append(
            f"| {r['title']} | {r['exposure']}/10 | {fmt_jobs(r['jobs'])} | {component_line(r)} |"
        )
    lines.append("")

    lines.append("### Lowest-exposure occupations")
    lines.append("")
    lines.append("| Occupation | Exposure | Jobs | Components |")
    lines.append("|-----------|----------|------|------------|")
    for r in sorted(records, key=lambda rec: ((rec["exposure"] or 0), -(rec["jobs"] or 0), rec["title"]))[:20]:
        lines.append(
            f"| {r['title']} | {r['exposure']}/10 | {fmt_jobs(r['jobs'])} | {component_line(r)} |"
        )
    lines.append("")

    lines.append("## Full occupation list")
    lines.append("")
    lines.append("Sorted by exposure descending, then by jobs descending.")
    lines.append("")
    for score in range(10, -1, -1):
        group = [r for r in records if r["exposure"] == score]
        if not group:
            continue
        group_jobs = sum(r["jobs"] or 0 for r in group)
        lines.append(f"### Exposure {score}/10 ({len(group)} occupations, {fmt_jobs(group_jobs)} jobs)")
        lines.append("")
        lines.append("| Occupation | Pay | Jobs | Outlook | Education | Components | Rationale |")
        lines.append("|-----------|-----|------|---------|-----------|------------|-----------|")
        for r in group:
            outlook = f"{r['outlook_pct']:+d}%" if r["outlook_pct"] is not None else "?"
            rationale = r["rationale"].replace("|", "/").replace("\n", " ")
            lines.append(
                f"| {r['title']} | {fmt_pay(r['pay'])} | {fmt_jobs(r['jobs'])} | "
                f"{outlook} | {education_short(r['education'])} | {component_line(r)} | {rationale} |"
            )
        lines.append("")

    text = "\n".join(lines)
    with open("prompt.md", "w") as f:
        f.write(text)

    print(f"Wrote prompt.md ({len(text):,} chars, {len(lines):,} lines)")


if __name__ == "__main__":
    main()
