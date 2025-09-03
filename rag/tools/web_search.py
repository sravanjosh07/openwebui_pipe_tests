#!/usr/bin/env python3
# web_search.py
# Minimal web search CLI using ddgs (DuckDuckGo/Metasearch)

import argparse, json, sys
from typing import List, Dict
from ddgs import DDGS
from ddgs.exceptions import DDGSException, RatelimitException, TimeoutException

def search_web(query: str, max_results: int = 5, region: str = "us-en",
               timelimit: str | None = None, backend: str = "auto") -> List[Dict]:
    """
    Run a web search and return a list of results:
    [{title, href, body}, ...]
    - region: e.g. "us-en", "uk-en"
    - timelimit: 'd' (day), 'w' (week), 'm' (month), 'y' (year) or None
    - backend: "auto" (default) or a comma list like "google, brave, duckduckgo"
    """
    with DDGS() as ddgs:
        return ddgs.text(
            query=query,
            region=region,
            timelimit=timelimit,
            backend=backend,
            max_results=max_results
        )

def main():
    p = argparse.ArgumentParser(description="Minimal web search tool (ddgs).")
    p.add_argument("query", help="Your search query (supports site:, filetype:, etc.)")
    p.add_argument("-m", "--max-results", type=int, default=5, help="Number of results")
    p.add_argument("-r", "--region", default="us-en", help="Region, e.g. us-en, uk-en")
    p.add_argument("-t", "--timelimit", default=None, help="d, w, m, y or omit")
    p.add_argument("-b", "--backend", default="auto",
                   help='Search backend(s): "auto" or "google, brave, duckduckgo, yahoo, ..."')
    p.add_argument("--json", action="store_true", help="Output JSON instead of pretty text")
    args = p.parse_args()

    try:
        results = search_web(args.query, args.max_results, args.region, args.timelimit, args.backend)
        if args.json:
            json.dump(results, sys.stdout, ensure_ascii=False, indent=2)
            print()
        else:
            for i, r in enumerate(results, 1):
                title = r.get("title", "").strip()
                url = r.get("href", "").strip()
                snippet = r.get("body", "").strip()
                print(f"\n[{i}] {title}\n{url}\n{snippet}")
    except (RatelimitException, TimeoutException, DDGSException) as e:
        print(f"Search error: {e}", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()