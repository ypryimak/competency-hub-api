"""
scrape_jobs.py

Collect vacancies for selected IT positions from public job APIs and save them
to JSON for later loading into the database.

Sources:
  1. Arbeitnow API - https://www.arbeitnow.com/api/job-board-api
  2. RemoteOK API  - https://remoteok.io/api

Result: scraped_jobs.json

Usage:
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


if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


DEFAULT_TARGET = 200
REQUEST_DELAY = 0.8

POSITIONS = [
    {
        "name": "Data Analyst",
        "arbeitnow_query": "data analyst",
        "remoteok_tags": ["data-analyst", "data", "analytics"],
    },
    {
        "name": "Software Engineer",
        "arbeitnow_query": "software engineer",
        "remoteok_tags": ["software-engineer", "backend", "fullstack"],
    },
    {
        "name": "DevOps Engineer",
        "arbeitnow_query": "devops engineer",
        "remoteok_tags": ["devops", "infrastructure", "sre", "kubernetes"],
    },
    {
        "name": "Product Manager",
        "arbeitnow_query": "product manager",
        "remoteok_tags": ["product-manager", "product"],
    },
    {
        "name": "Data Scientist",
        "arbeitnow_query": "data scientist",
        "remoteok_tags": ["data-science", "machine-learning", "python"],
    },
    {
        "name": "Machine Learning Engineer",
        "arbeitnow_query": "machine learning engineer",
        "remoteok_tags": ["machine-learning", "ai", "deep-learning"],
    },
    {
        "name": "Front End Developer",
        "arbeitnow_query": "frontend developer",
        "remoteok_tags": ["frontend", "react", "javascript", "vue"],
    },
    {
        "name": "Quality Assurance Engineer",
        "arbeitnow_query": "qa engineer",
        "remoteok_tags": ["qa", "testing"],
    },
    {
        "name": "Cybersecurity Analyst",
        "arbeitnow_query": "cybersecurity analyst",
        "remoteok_tags": ["security", "cybersecurity"],
    },
    {
        "name": "Cloud Architect",
        "arbeitnow_query": "cloud architect",
        "remoteok_tags": ["cloud", "aws", "azure"],
    },
]


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
                full_title = f"{title} - {company}" if company else title
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
                full_title = f"{title} - {company}" if company else title
                jobs.append({"title": full_title[:255], "description": description})
                if len(jobs) >= target:
                    break

        except Exception as exc:
            print(f"    [remoteok] error tag={tag}: {exc}")

    return jobs


def scrape_for_position(pos_cfg: dict, target: int) -> list[dict]:
    name = pos_cfg["name"]
    all_jobs: list[dict] = []
    seen_titles: set[str] = set()

    def _merge(batch: list[dict]) -> int:
        added = 0
        for job in batch:
            key = job["title"].lower()
            if key not in seen_titles and len(all_jobs) < target:
                seen_titles.add(key)
                all_jobs.append({"position_name": name, **job})
                added += 1
        return added

    print("  [arbeitnow] fetching ...")
    added = _merge(scrape_arbeitnow(pos_cfg["arbeitnow_query"], target - len(all_jobs)))
    print(f"    -> {added} added  (total {len(all_jobs)}/{target})")

    if len(all_jobs) < target:
        print("  [remoteok] fetching ...")
        added = _merge(scrape_remoteok(pos_cfg["remoteok_tags"], target - len(all_jobs)))
        print(f"    -> {added} added  (total {len(all_jobs)}/{target})")

    return all_jobs


def main():
    parser = argparse.ArgumentParser(description="Scrape job postings to JSON")
    parser.add_argument(
        "--target",
        type=int,
        default=DEFAULT_TARGET,
        help=f"Jobs per position (default {DEFAULT_TARGET})",
    )
    parser.add_argument(
        "--output",
        default="scraped_jobs.json",
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
    for job in all_results:
        by_pos[job["position_name"]] = by_pos.get(job["position_name"], 0) + 1

    print(f"\n=== DONE - {len(all_results)} jobs saved to '{output_path}' ===")
    for pos_name, count in by_pos.items():
        print(f"  {pos_name}: {count}")
    print()


if __name__ == "__main__":
    main()
