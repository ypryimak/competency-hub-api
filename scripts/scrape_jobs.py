"""
scrape_jobs.py

Збирає вакансії для Data Analyst, Software Engineer, DevOps Engineer
з публічних API (без API-ключів) і зберігає результат у JSON-файл
для подальшого завантаження в БД через API.

Джерела:
  1. The Muse API   — https://www.themuse.com/api/public/jobs
  2. Arbeitnow API  — https://www.arbeitnow.com/api/job-board-api
  3. RemoteOK API   — https://remoteok.io/api

Результат: scraped_jobs.json
  [
    {"position_name": "Data Analyst", "title": "...", "description": "..."},
    ...
  ]

Використання:
  python scrape_jobs.py [--target 200] [--output scraped_jobs.json]
"""

import argparse
import json
import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path

import requests

# Fix Windows console encoding
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ─── Config ─────────────────────────────────────────────────────────────────

DEFAULT_TARGET = 200   # jobs per position
REQUEST_DELAY = 0.8    # seconds between outbound HTTP requests

POSITIONS = [
    {
        "name": "Data Analyst",
        "muse_categories": ["Data and Analytics"],
        "muse_title_keywords": ["data analyst", "analytics", "business analyst", "bi analyst", "reporting analyst"],
        "arbeitnow_query": "data analyst",
        "remoteok_tags": ["data-analyst", "data", "analytics"],
    },
    {
        "name": "Software Engineer",
        "muse_categories": ["Software Engineering"],
        "muse_title_keywords": [],  # accept all from this category
        "arbeitnow_query": "software engineer",
        "remoteok_tags": ["software-engineer", "backend", "fullstack"],
    },
    {
        "name": "DevOps Engineer",
        "muse_categories": ["Software Engineering", "Computer and IT"],
        "muse_title_keywords": ["devops", "infrastructure", "sre", "platform engineer", "cloud engineer", "site reliability"],
        "arbeitnow_query": "devops engineer",
        "remoteok_tags": ["devops", "infrastructure", "sre", "kubernetes"],
    },
    {
        "name": "Product Manager",
        "muse_categories": ["Product Management"],
        "muse_title_keywords": [],  # accept all from this category
        "arbeitnow_query": "product manager",
        "remoteok_tags": ["product-manager", "product"],
    },
    {
        "name": "Data Scientist",
        "muse_categories": ["Data and Analytics", "Science and Engineering"],
        "muse_title_keywords": ["data scientist", "machine learning", "ai scientist", "research scientist", "quantitative"],
        "arbeitnow_query": "data scientist",
        "remoteok_tags": ["data-science", "machine-learning", "python"],
    },
    {
        "name": "Machine Learning Engineer",
        "muse_categories": ["Software Engineering", "Science and Engineering"],
        "muse_title_keywords": ["machine learning", "ml engineer", "ai engineer", "deep learning", "nlp engineer", "computer vision", "llm"],
        "arbeitnow_query": "machine learning engineer",
        "remoteok_tags": ["machine-learning", "ai", "deep-learning"],
    },
    {
        "name": "Front End Developer",
        "muse_categories": ["Software Engineering"],
        "muse_title_keywords": ["frontend", "front-end", "front end", "react", "vue", "angular", "ui developer", "web developer", "javascript developer"],
        "arbeitnow_query": "frontend developer",
        "remoteok_tags": ["frontend", "react", "javascript", "vue"],
    },
    {
        "name": "Quality Assurance Engineer",
        "muse_categories": ["Computer and IT", "Software Engineering"],
        "muse_title_keywords": ["qa", "quality assurance", "test engineer", "sdet", "automation engineer", "quality engineer", "tester"],
        "arbeitnow_query": "qa engineer",
        "remoteok_tags": ["qa", "testing"],
    },
    {
        "name": "Cybersecurity Analyst",
        "muse_categories": ["Computer and IT", "Science and Engineering"],
        "muse_title_keywords": ["security", "cybersecurity", "cyber", "information security", "soc analyst", "penetration", "threat"],
        "arbeitnow_query": "cybersecurity analyst",
        "remoteok_tags": ["security", "cybersecurity"],
    },
    {
        "name": "Cloud Architect",
        "muse_categories": ["Software Engineering", "Computer and IT"],
        "muse_title_keywords": ["cloud architect", "solutions architect", "aws architect", "azure architect", "gcp architect", "cloud solution", "enterprise architect"],
        "arbeitnow_query": "cloud architect",
        "remoteok_tags": ["cloud", "aws", "azure"],
    },
]


# ─── HTML → plain text ───────────────────────────────────────────────────────

class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str):
        self.parts.append(data)

    def handle_starttag(self, tag, attrs):
        if tag in ("p", "br", "li", "div", "h1", "h2", "h3", "h4", "ul", "ol"):
            self.parts.append("\n")

    def get_text(self) -> str:
        text = "".join(self.parts)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def strip_html(html: str) -> str:
    if not html:
        return ""
    parser = _HTMLStripper()
    parser.feed(html)
    return parser.get_text()


# ─── Source: The Muse ────────────────────────────────────────────────────────

MUSE_API = "https://www.themuse.com/api/public/jobs"


def scrape_muse(categories: list[str], target: int, title_keywords: list[str] | None = None) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()

    for category in categories:
        if len(jobs) >= target:
            break
        page = 1
        while len(jobs) < target:
            try:
                resp = requests.get(
                    MUSE_API,
                    params={"category": category, "page": page, "descending": "true"},
                    timeout=15,
                )
                time.sleep(REQUEST_DELAY)
                if resp.status_code != 200:
                    print(f"    [muse] HTTP {resp.status_code} cat={category} p={page}")
                    break
                data = resp.json()
                results = data.get("results", [])
                if not results:
                    break

                for item in results:
                    title = item.get("name", "").strip()
                    description = strip_html(item.get("contents", ""))
                    company = (item.get("company") or {}).get("name", "")
                    if not title or not description or len(description) < 150:
                        continue
                    if title_keywords and not any(kw in title.lower() for kw in title_keywords):
                        continue
                    key = f"{title}|{company}".lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    full_title = f"{title} — {company}" if company else title
                    jobs.append({"title": full_title[:255], "description": description})
                    if len(jobs) >= target:
                        break

                page_count = data.get("page_count", 1)
                if page >= page_count:
                    break
                page += 1

            except Exception as exc:
                print(f"    [muse] error cat={category} p={page}: {exc}")
                break

    return jobs


# ─── Source: Arbeitnow ──────────────────────────────────────────────────────

ARBEITNOW_API = "https://www.arbeitnow.com/api/job-board-api"


def scrape_arbeitnow(query: str, target: int) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()
    page = 1

    while len(jobs) < target:
        try:
            resp = requests.get(
                ARBEITNOW_API,
                params={"search": query, "page": page},
                timeout=15,
            )
            time.sleep(REQUEST_DELAY)
            if resp.status_code != 200:
                print(f"    [arbeitnow] HTTP {resp.status_code} p={page}")
                break
            data = resp.json()
            items = data.get("data", [])
            if not items:
                break

            for item in items:
                title = item.get("title", "").strip()
                description = strip_html(item.get("description", ""))
                company = item.get("company_name", "")
                if not title or not description or len(description) < 150:
                    continue
                key = f"{title}|{company}".lower()
                if key in seen:
                    continue
                seen.add(key)
                full_title = f"{title} — {company}" if company else title
                jobs.append({"title": full_title[:255], "description": description})
                if len(jobs) >= target:
                    break

            meta = data.get("meta", {})
            last_page = meta.get("last_page", 1)
            if page >= last_page:
                break
            page += 1

        except Exception as exc:
            print(f"    [arbeitnow] error p={page}: {exc}")
            break

    return jobs


# ─── Source: RemoteOK ───────────────────────────────────────────────────────

REMOTEOK_API = "https://remoteok.io/api"
REMOTEOK_HEADERS = {
    "User-Agent": "Mozilla/5.0 (job data collection; educational research)"
}


def scrape_remoteok(tags: list[str], target: int) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()

    for tag in tags:
        if len(jobs) >= target:
            break
        try:
            resp = requests.get(
                REMOTEOK_API,
                params={"tag": tag},
                headers=REMOTEOK_HEADERS,
                timeout=15,
            )
            time.sleep(REQUEST_DELAY * 2)
            if resp.status_code != 200:
                print(f"    [remoteok] HTTP {resp.status_code} tag={tag}")
                continue
            items = resp.json()
            if not isinstance(items, list):
                continue

            for item in items:
                if not isinstance(item, dict):
                    continue
                title = item.get("position", "").strip()
                description = strip_html(item.get("description", ""))
                company = item.get("company", "")
                if not title or not description or len(description) < 150:
                    continue
                key = f"{title}|{company}".lower()
                if key in seen:
                    continue
                seen.add(key)
                full_title = f"{title} — {company}" if company else title
                jobs.append({"title": full_title[:255], "description": description})
                if len(jobs) >= target:
                    break

        except Exception as exc:
            print(f"    [remoteok] error tag={tag}: {exc}")

    return jobs


# ─── Per-position orchestration ──────────────────────────────────────────────

def scrape_for_position(pos_cfg: dict, target: int) -> list[dict]:
    name = pos_cfg["name"]
    all_jobs: list[dict] = []
    seen_titles: set[str] = set()

    def _merge(batch: list[dict]) -> int:
        added = 0
        for j in batch:
            key = j["title"].lower()
            if key not in seen_titles and len(all_jobs) < target:
                seen_titles.add(key)
                all_jobs.append({"position_name": name, **j})
                added += 1
        return added

    # Source 1: The Muse
    print(f"  [muse] fetching …")
    title_kws = pos_cfg.get("muse_title_keywords") or None
    added = _merge(scrape_muse(pos_cfg["muse_categories"], target, title_keywords=title_kws))
    print(f"    -> {added} added  (total {len(all_jobs)}/{target})")

    # Source 2: Arbeitnow
    if len(all_jobs) < target:
        print(f"  [arbeitnow] fetching …")
        added = _merge(scrape_arbeitnow(pos_cfg["arbeitnow_query"], target - len(all_jobs)))
        print(f"    -> {added} added  (total {len(all_jobs)}/{target})")

    # Source 3: RemoteOK
    if len(all_jobs) < target:
        print(f"  [remoteok] fetching …")
        added = _merge(scrape_remoteok(pos_cfg["remoteok_tags"], target - len(all_jobs)))
        print(f"    -> {added} added  (total {len(all_jobs)}/{target})")

    return all_jobs


# ─── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Scrape job postings → JSON")
    parser.add_argument(
        "--target", type=int, default=DEFAULT_TARGET,
        help=f"Jobs per position (default {DEFAULT_TARGET})",
    )
    parser.add_argument(
        "--output", default="scraped_jobs.json",
        help="Output JSON file (default scraped_jobs.json)",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    all_results: list[dict] = []

    for pos_cfg in POSITIONS:
        name = pos_cfg["name"]
        print(f"\n=== {name} (target={args.target}) ===")
        jobs = scrape_for_position(pos_cfg, args.target)
        print(f"  Collected {len(jobs)} jobs for '{name}'")
        all_results.extend(jobs)

    output_path.write_text(
        json.dumps(all_results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    by_pos: dict[str, int] = {}
    for j in all_results:
        by_pos[j["position_name"]] = by_pos.get(j["position_name"], 0) + 1

    print(f"\n=== DONE — {len(all_results)} jobs saved to '{output_path}' ===")
    for pos_name, count in by_pos.items():
        print(f"  {pos_name}: {count}")
    print()


if __name__ == "__main__":
    main()
