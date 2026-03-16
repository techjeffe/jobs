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
SCORE_VERSION = 3

SYSTEM_PROMPT = """\
You are an expert analyst evaluating how exposed different occupations are to \
AI and autonomous agents. You will be given a detailed description of an occupation from the Bureau \
of Labor Statistics.

Your goal is to assess the occupation across five evolved dimensions from 0 to \
10. Do not rely on job titles or prestige; analyze the specific tasks and \
environmental constraints described.

Scoring dimensions:

- **agentic_output_potential**: How much of the final value of this job is a \
digital artifact or a command that can be executed via software. 0 = output is \
strictly a physical change in the world; 10 = output is entirely digital and \
can be delivered or executed by an AI agent.
- **cognitive_synthesis_complexity**: The degree to which the job requires \
high-dimensional reasoning, non-routine problem solving, or creative synthesis. \
0 = simple, repetitive data retrieval; 10 = complex, multi-variable strategy \
and novel solution architecture.
- **environmental_unpredictability**: How much the work occurs in unstructured \
physical environments. 0 = controlled settings; 10 = wild or volatile \
environments with high-stakes physical variables.
- **ontological_human_necessity**: The extent to which the core value depends \
on a human being a human, including empathy, moral authority, shared physical \
experience, or trust based on human liability. 0 = interaction is purely \
functional or informational; 10 = the human-to-human bond is the primary product.
- **systemic_accountability**: The degree of non-delegatable professional, \
legal, or ethical liability. 0 = low-consequence errors; 10 = the buck stops \
here for life-altering or system-critical decisions that a machine cannot \
legally or ethically own.

Important:
- Ignore the routine trap: assume AI can now handle complex, non-routine \
cognitive tasks. Focus instead on whether the AI can execute the final step \
(agentic output potential).
- Structured vs. unstructured: a robot can flip a burger in a lab, but \
struggling to fix a leak in a 100-year-old crawlspace is a very different kind \
of problem.
- Use the full scale aggressively based on the evidence in the text.

Respond with ONLY a JSON object in this exact format, no other text:
{
  "agentic_output_potential": <0-10 integer>,
  "cognitive_synthesis_complexity": <0-10 integer>,
  "environmental_unpredictability": <0-10 integer>,
  "ontological_human_necessity": <0-10 integer>,
  "systemic_accountability": <0-10 integer>,
  "rationale": "<2-3 sentences explaining how agentic potential and environmental constraints defined the score.>"
}\
"""


def clamp(value, low=0, high=10):
    return max(low, min(high, value))


def derive_exposure_score(components):
    """
    Convert component dimensions into the final exposure score.

    Agentic output potential is weighted most heavily. Cognitive complexity
    still contributes because agentic systems increasingly handle non-routine
    work, while environmental unpredictability, human necessity, and systemic
    accountability act as barriers.
    """
    raw_score = (
        0.45 * components["agentic_output_potential"]
        + 0.20 * components["cognitive_synthesis_complexity"]
        + 0.15 * (10 - components["environmental_unpredictability"])
        + 0.10 * (10 - components["ontological_human_necessity"])
        + 0.10 * (10 - components["systemic_accountability"])
    )
    return int(round(clamp(raw_score)))


def normalize_component_scores(result):
    fields = [
        "agentic_output_potential",
        "cognitive_synthesis_complexity",
        "environmental_unpredictability",
        "ontological_human_necessity",
        "systemic_accountability",
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
