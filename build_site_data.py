"""
Build a compact JSON for the website by merging CSV stats with AI exposure scores.

Reads occupations.csv (for stats) and scores.json (for AI exposure).
Writes site/data.json.

Usage:
    uv run python build_site_data.py
"""

import csv
import json


def extract_components(score):
    components = score.get("components", {})
    return {
        "agentic_output_potential": components.get("agentic_output_potential", score.get("agentic_output_potential", score.get("digitality"))),
        "cognitive_synthesis_complexity": components.get("cognitive_synthesis_complexity", score.get("cognitive_synthesis_complexity", score.get("routine_information_processing"))),
        "environmental_unpredictability": components.get("environmental_unpredictability", score.get("environmental_unpredictability", score.get("physical_world_dependency"))),
        "ontological_human_necessity": components.get("ontological_human_necessity", score.get("ontological_human_necessity", score.get("human_relationship_dependency"))),
        "systemic_accountability": components.get("systemic_accountability", score.get("systemic_accountability", score.get("judgment_accountability_dependency"))),
    }


def main():
    # Load AI exposure scores
    with open("scores.json") as f:
        scores_list = json.load(f)
    scores = {s["slug"]: s for s in scores_list}

    # Load CSV stats
    with open("occupations.csv") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Merge
    data = []
    for row in rows:
        slug = row["slug"]
        score = scores.get(slug, {})
        components = extract_components(score)
        data.append({
            "title": row["title"],
            "slug": slug,
            "category": row["category"],
            "pay": int(row["median_pay_annual"]) if row["median_pay_annual"] else None,
            "jobs": int(row["num_jobs_2024"]) if row["num_jobs_2024"] else None,
            "outlook": int(row["outlook_pct"]) if row["outlook_pct"] else None,
            "outlook_desc": row["outlook_desc"],
            "education": row["entry_education"],
            "exposure": score.get("exposure"),
            "exposure_rationale": score.get("rationale"),
            "components": components,
            "agentic_output_potential": components["agentic_output_potential"],
            "cognitive_synthesis_complexity": components["cognitive_synthesis_complexity"],
            "environmental_unpredictability": components["environmental_unpredictability"],
            "ontological_human_necessity": components["ontological_human_necessity"],
            "systemic_accountability": components["systemic_accountability"],
            # Legacy aliases kept for compatibility with older exports and UI code.
            "digitality": components["agentic_output_potential"],
            "routine_information_processing": components["cognitive_synthesis_complexity"],
            "physical_world_dependency": components["environmental_unpredictability"],
            "human_relationship_dependency": components["ontological_human_necessity"],
            "judgment_accountability_dependency": components["systemic_accountability"],
            "url": row.get("url", ""),
        })

    import os
    os.makedirs("site", exist_ok=True)
    with open("site/data.json", "w") as f:
        json.dump(data, f)

    print(f"Wrote {len(data)} occupations to site/data.json")
    total_jobs = sum(d["jobs"] for d in data if d["jobs"])
    print(f"Total jobs represented: {total_jobs:,}")


if __name__ == "__main__":
    main()
