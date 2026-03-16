"""
Score each occupation's AI exposure using an LLM via OpenRouter.

Reads Markdown descriptions from pages/, sends each to an LLM with a scoring
rubric, and collects structured scores. Results are cached incrementally to
scores.json so the script can be resumed if interrupted.

Usage:
    uv run python score.py
    uv run python score.py --model google/gemini-3.1-flash-lite-preview
    uv run python score.py --start 0 --end 10   # test on first 10
"""

import argparse
import json
import os
import time
import httpx
from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "google/gemini-3.1-flash-lite-preview"
OUTPUT_FILE = "scores.json"
API_URL = "https://openrouter.ai/api/v1/chat/completions"
SCORE_VERSION = 2

SYSTEM_PROMPT = """\
You are an expert analyst evaluating how exposed different occupations are to \
AI. You will be given a detailed description of an occupation from the Bureau \
of Labor Statistics.

Your job is NOT to directly assign the final exposure score. Instead, assess \
the occupation on five component dimensions from 0 to 10, using the occupation \
description itself rather than stereotypes about the title.

Scoring dimensions:

- **digitality**: How much of the core work product is created, handled, or \
delivered in digital form. 0 = almost entirely non-digital; 10 = almost \
entirely digital.
- **routine_information_processing**: How much of the core work consists of \
structured or repeatable information processing, analysis, drafting, lookup, \
documentation, or decision support. 0 = very little; 10 = most of the job.
- **physical_world_dependency**: How much the core work depends on physical \
presence, manual manipulation, site-specific activity, or operating in the \
real world. 0 = almost none; 10 = essential to most of the job.
- **human_relationship_dependency**: How much the core work depends on trust, \
persuasion, empathy, negotiation, live coordination, or sustained interpersonal \
relationships. 0 = almost none; 10 = essential to most of the job.
- **judgment_accountability_dependency**: How much the core work depends on \
high-stakes judgment, professional accountability, or domain responsibility \
that is difficult to delegate. 0 = very little; 10 = central to the role.

Important:
- Do not assume all computer-based jobs are highly exposed.
- Do not assume all physical jobs are protected.
- Use the middle of the scale when evidence is mixed or ambiguous.
- Base the scores on the occupation description, not on generic beliefs about \
the profession.

Respond with ONLY a JSON object in this exact format, no other text:
{
  "digitality": <0-10 integer>,
  "routine_information_processing": <0-10 integer>,
  "physical_world_dependency": <0-10 integer>,
  "human_relationship_dependency": <0-10 integer>,
  "judgment_accountability_dependency": <0-10 integer>,
  "rationale": "<2-3 sentences explaining the key factors>"
}\
"""


def clamp(value, low=0, high=10):
    return max(low, min(high, value))


def derive_exposure_score(components):
    """
    Convert component dimensions into the final exposure score.

    Higher digital/routine work increases exposure; higher physical, human,
    and judgment/accountability requirements act as barriers.
    """
    raw_score = (
        0.30 * components["digitality"]
        + 0.30 * components["routine_information_processing"]
        + 0.15 * (10 - components["physical_world_dependency"])
        + 0.15 * (10 - components["human_relationship_dependency"])
        + 0.10 * (10 - components["judgment_accountability_dependency"])
    )
    return int(round(clamp(raw_score)))


def normalize_component_scores(result):
    fields = [
        "digitality",
        "routine_information_processing",
        "physical_world_dependency",
        "human_relationship_dependency",
        "judgment_accountability_dependency",
    ]
    components = {}
    for field in fields:
        components[field] = int(clamp(round(float(result[field]))))
    return components


def score_occupation(client, text, model):
    """Send one occupation to the LLM and return component scores."""
    response = client.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            "temperature": 0.2,
        },
        timeout=60,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]

    # Strip markdown code fences if present
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1]  # remove first line
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

    result = json.loads(content)
    components = normalize_component_scores(result)
    return {
        "components": components,
        "rationale": result["rationale"],
        "exposure": derive_exposure_score(components),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--force", action="store_true",
                        help="Re-score even if already cached")
    args = parser.parse_args()

    with open("occupations.json") as f:
        occupations = json.load(f)

    subset = occupations[args.start:args.end]

    # Load existing scores
    all_scores = {}
    scores = {}
    if os.path.exists(OUTPUT_FILE) and not args.force:
        with open(OUTPUT_FILE) as f:
            for entry in json.load(f):
                all_scores[entry["slug"]] = entry
                if entry.get("score_version") == SCORE_VERSION:
                    scores[entry["slug"]] = entry

    print(f"Scoring {len(subset)} occupations with {args.model}")
    print(f"Already cached: {len(scores)}")

    errors = []
    client = httpx.Client()

    for i, occ in enumerate(subset):
        slug = occ["slug"]

        if slug in scores:
            continue

        md_path = f"pages/{slug}.md"
        if not os.path.exists(md_path):
            print(f"  [{i+1}] SKIP {slug} (no markdown)")
            continue

        with open(md_path) as f:
            text = f.read()

        print(f"  [{i+1}/{len(subset)}] {occ['title']}...", end=" ", flush=True)

        try:
            result = score_occupation(client, text, args.model)
            entry = {
                "slug": slug,
                "title": occ["title"],
                "score_version": SCORE_VERSION,
                **result["components"],
                **result,
            }
            scores[slug] = entry
            all_scores[slug] = entry
            print(f"exposure={result['exposure']}")
        except Exception as e:
            print(f"ERROR: {e}")
            errors.append(slug)

        # Save after each one (incremental checkpoint)
        with open(OUTPUT_FILE, "w") as f:
            json.dump(list(all_scores.values()), f, indent=2)

        if i < len(subset) - 1:
            time.sleep(args.delay)

    client.close()

    print(f"\nDone. Scored {len(all_scores)} occupations, {len(errors)} errors.")
    if errors:
        print(f"Errors: {errors}")

    # Summary stats
    vals = [s for s in all_scores.values() if "exposure" in s]
    if vals:
        avg = sum(s["exposure"] for s in vals) / len(vals)
        by_score = {}
        for s in vals:
            bucket = s["exposure"]
            by_score[bucket] = by_score.get(bucket, 0) + 1
        print(f"\nAverage exposure across {len(vals)} occupations: {avg:.1f}")
        print("Distribution:")
        for k in sorted(by_score):
            print(f"  {k}: {'█' * by_score[k]} ({by_score[k]})")


if __name__ == "__main__":
    main()
