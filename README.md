# AI Exposure of the US Job Market

A research tool for exploring Bureau of Labor Statistics [Occupational Outlook Handbook](https://www.bls.gov/ooh/) (OOH) data and one fork-specific attempt to score how exposed different occupations may be to AI.

This fork builds on Josh Kale's restoration of the original project after Andrej Karpathy briefly shared it and took it down. Josh preserved the pipeline, data, and visualization so the work did not disappear.

![AI Exposure Treemap](jobs.png)

## What's here

The BLS OOH covers **342 occupations** spanning every sector of the US economy, with detailed data on job duties, work environment, education requirements, pay, and employment projections. We scraped all of it, scored each occupation's AI exposure using an LLM, and built an interactive treemap visualization.

This repository is best understood as an exploration tool, not a paper or a rigorous labor-economics model. The scores are useful for inspection and debate, but they are still heuristic judgments produced by an LLM-guided pipeline.

## Data pipeline

1. **Scrape** (`scrape.py`) — Playwright (non-headless, BLS blocks bots) downloads raw HTML for all 342 occupation pages into `html/`.
2. **Parse** (`parse_detail.py`, `process.py`) — BeautifulSoup converts raw HTML into clean Markdown files in `pages/`.
3. **Tabulate** (`make_csv.py`) — Extracts structured fields (pay, education, job count, growth outlook, SOC code) into `occupations.csv`.
4. **Score** (`score.py`) — Sends each occupation's Markdown description to an LLM (Gemini Flash via OpenRouter), asks for component scores (digitality, routine information processing, physical-world dependence, human-relationship dependence, judgment/accountability), and derives a final AI Exposure score from 0-10 in code. Results saved to `scores.json`.
5. **Build site data** (`build_site_data.py`) — Merges CSV stats and AI exposure scores into a compact `site/data.json` for the frontend.
6. **Prompt export** (`make_prompt.py`) — Packages the dataset, current methodology, and summary statistics into `prompt.md`, a single markdown file designed for LLM analysis.
7. **Website** (`site/index.html`) — Interactive treemap visualization where area = employment and color = AI exposure (green to red).

## Key files

| File | Description |
|------|-------------|
| `occupations.json` | Master list of 342 occupations with title, URL, category, slug |
| `occupations.csv` | Summary stats: pay, education, job count, growth projections |
| `scores.json` | AI exposure scores, component subscores, and rationales for all 342 occupations |
| `prompt.md` | Single-file export of the dataset and methodology for use with an LLM |
| `html/` | Raw HTML pages from BLS (source of truth, ~40MB) |
| `pages/` | Clean Markdown versions of each occupation page |
| `site/` | Static website (treemap visualization) |

## AI exposure scoring

Each occupation is scored on a single **AI Exposure** axis from 0 to 10, measuring how much AI will reshape that occupation. The score considers both direct automation (AI doing the work) and indirect effects (AI making workers so productive that fewer are needed).

Instead of asking the model for one final score directly, the pipeline now asks for component judgments about:
- digitality of the work
- routine information processing
- dependence on the physical world
- dependence on human relationships
- dependence on judgment and accountability

The final exposure score is then derived in code from those components. This reduces how much the final number depends on a single highly prescriptive prompt and makes the scoring logic easier to inspect and compare across occupations.

**What this score is not:**
- It is not a prediction that a job disappears.
- It does not capture demand elasticity, regulation, union power, labor shortages, or cultural preferences for human work.
- It does not tell you whether employment in a field will rise or fall overall.
- High exposure can mean a job is transformed, compressed, or reorganized rather than eliminated.

**Calibration examples from the dataset:**

| Score | Meaning | Examples |
|-------|---------|---------|
| 0-1 | Minimal | Roofers, janitors, construction laborers |
| 2-3 | Low | Electricians, plumbers, nurses aides, firefighters |
| 4-5 | Moderate | Registered nurses, retail workers, physicians |
| 6-7 | High | Teachers, managers, accountants, engineers |
| 8-9 | Very high | Software developers, paralegals, data analysts, editors |
| 10 | Maximum | Medical transcriptionists |

Average exposure across all 342 occupations under the current method: **4.5/10**.

## Visualization

The main visualization is an interactive **treemap** where:
- **Area** of each rectangle is proportional to employment (number of jobs)
- **Color** indicates AI exposure on a green (safe) to red (exposed) scale
- **Layout** groups occupations by BLS category
- **Hover** shows detailed tooltip with pay, jobs, outlook, education, exposure score, and LLM rationale

## Prompt export

[`prompt.md`](prompt.md) packages this fork's dataset, component-based scoring method, aggregate statistics, and full occupation list into a single markdown file intended for copy-pasting into an LLM. It also includes a summary of how the current scoring differs from the earlier approach.

## Setup

```
uv sync
uv run playwright install chromium
```

Requires an OpenRouter API key in `.env`:
```
OPENROUTER_API_KEY=your_key_here
```

## Usage

```bash
# Scrape BLS pages (only needed once, results are cached in html/)
uv run python scrape.py

# Generate Markdown from HTML
uv run python process.py

# Generate CSV summary
uv run python make_csv.py

# Score AI exposure (uses OpenRouter API)
uv run python score.py

# Build website data
uv run python build_site_data.py

# Compare the current scores against the pre-refactor baseline
python compare_scores.py

# Export the full dataset and methodology into prompt.md for LLM analysis
python make_prompt.py

# Serve the site locally
cd site && python -m http.server 8000
```
