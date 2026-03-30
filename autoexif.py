#!/usr/bin/env python3
"""AutoExIf - Dork + ExifTool Metadata Extractor.

Automates OSINT metadata extraction: search dork to find files on a target
domain, download them, run exiftool, and output a CSV summary.
Uses DuckDuckGo HTML search to avoid Google's anti-scraping measures.
"""

import argparse
import csv
import json
import random
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests
from bs4 import BeautifulSoup

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

CSV_COLUMNS = [
    "URL",
    "Filename",
    "Author",
    "Creator",
    "Producer",
    "CreateDate",
    "ModifyDate",
    "Title",
    "Subject",
    "PageCount",
]

# Domains to skip when extracting search results (ads, trackers, etc.)
SKIP_DOMAINS = {"duckduckgo.com", "bing.com", "google.com", "google.de"}


def is_ad_url(url: str) -> bool:
    """Check if a URL is an ad/tracker redirect rather than an organic result."""
    try:
        host = urlparse(url).hostname or ""
    except ValueError:
        return True
    return any(d in host for d in SKIP_DOMAINS)


def duckduckgo_search(dork: str, limit: int) -> list[str]:
    """Scrape DuckDuckGo HTML search results for the given dork query."""
    urls: list[str] = []
    session = requests.Session()
    session.headers.update({"User-Agent": random.choice(USER_AGENTS)})

    page = 0
    max_pages = (limit // 10) + 3  # safety cap
    next_form_data = None
    retries = 0

    while len(urls) < limit and page < max_pages:
        if page == 0:
            print("[*] Querying DuckDuckGo...")
        else:
            print(f"[*] Querying DuckDuckGo (page {page + 1})...")

        try:
            if page == 0:
                resp = session.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": dork},
                    timeout=15,
                )
            else:
                resp = session.post(
                    "https://html.duckduckgo.com/html/",
                    data=next_form_data,
                    timeout=15,
                )
        except requests.RequestException as e:
            print(f"[!] Search request failed: {e}")
            break

        # DDG returns 202 when rate-limiting
        if resp.status_code == 202:
            retries += 1
            if retries > 2:
                print("[!] Rate limited too many times. Giving up.")
                break
            wait = 10 * retries
            print(f"[!] Rate limited by DuckDuckGo. Waiting {wait}s (attempt {retries}/2)...")
            time.sleep(wait)
            continue

        if resp.status_code != 200:
            print(f"[!] Unexpected status {resp.status_code}")
            break

        soup = BeautifulSoup(resp.text, "html.parser")

        # Extract result URLs from organic results (skip ads)
        found_this_page = 0
        for result_div in soup.find_all("div", class_="web-result"):
            a_tag = result_div.find("a", class_="result__a", href=True)
            if not a_tag:
                continue

            href = a_tag["href"]
            # DDG wraps URLs in //duckduckgo.com/l/?uddg=<encoded_url>&...
            match = re.search(r"[?&]uddg=([^&]+)", href)
            if match:
                url = unquote(match.group(1))
            elif href.startswith("http"):
                url = href
            else:
                continue

            if is_ad_url(url):
                continue

            if url.startswith("http") and url not in urls:
                urls.append(url)
                found_this_page += 1
                if len(urls) >= limit:
                    break

        if found_this_page == 0:
            print("[*] No more results found.")
            break

        print(f"[*] Found {found_this_page} URLs (total: {len(urls)}).")

        # Find the "Next" form for pagination
        next_form = soup.find("form", class_="nav-link")
        if not next_form:
            break
        next_form_data = {}
        for inp in next_form.find_all("input", attrs={"name": True}):
            next_form_data[inp["name"]] = inp.get("value", "")

        page += 1
        delay = random.uniform(2, 5)
        print(f"[*] Sleeping {delay:.1f}s...")
        time.sleep(delay)

    print(f"[+] Total URLs collected: {len(urls)}")
    return urls[:limit]


def download_file(url: str, download_dir: Path, session: requests.Session) -> Path | None:
    """Download a file from the given URL. Returns path or None on failure."""
    try:
        parsed = urlparse(url)
        filename = Path(parsed.path).name
        if not filename:
            filename = "unknown_file"

        # Deduplicate filenames
        dest = download_dir / filename
        counter = 1
        while dest.exists():
            stem = Path(filename).stem
            suffix = Path(filename).suffix
            dest = download_dir / f"{stem}_{counter}{suffix}"
            counter += 1

        resp = session.get(url, timeout=30, stream=True)
        resp.raise_for_status()

        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        size_kb = dest.stat().st_size / 1024
        print(f"    Downloaded: {dest.name} ({size_kb:.1f} KB)")
        return dest

    except requests.RequestException as e:
        print(f"    [!] Failed to download {url}: {e}")
        return None


def run_exiftool(filepath: Path) -> dict:
    """Run exiftool on a file and return parsed metadata dict."""
    try:
        result = subprocess.run(
            ["exiftool", "-json", str(filepath)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            print(f"    [!] exiftool error for {filepath.name}: {result.stderr.strip()}")
            return {}

        data = json.loads(result.stdout)
        return data[0] if data else {}

    except FileNotFoundError:
        print("[!] exiftool not found. Please install it: https://exiftool.org/")
        sys.exit(1)
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        print(f"    [!] exiftool failed for {filepath.name}: {e}")
        return {}


def extract_metadata(meta: dict, url: str, filename: str) -> dict:
    """Extract relevant fields from exiftool metadata into a flat dict."""
    return {
        "URL": url,
        "Filename": filename,
        "Author": meta.get("Author", ""),
        "Creator": meta.get("Creator", ""),
        "Producer": meta.get("Producer", ""),
        "CreateDate": meta.get("CreateDate", ""),
        "ModifyDate": meta.get("ModifyDate", ""),
        "Title": meta.get("Title", ""),
        "Subject": meta.get("Subject", ""),
        "PageCount": meta.get("PageCount", ""),
    }


def write_csv(rows: list[dict], output_path: str) -> None:
    """Write metadata rows to a CSV file."""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n[+] CSV written to {output_path}")


def print_summary(rows: list[dict]) -> None:
    """Print a formatted summary table to stdout."""
    if not rows:
        print("\n[*] No metadata extracted.")
        return

    # Compute column widths
    widths = {}
    display_cols = ["Filename", "Author", "Creator", "CreateDate"]
    for col in display_cols:
        values = [str(r.get(col, "")) for r in rows]
        widths[col] = max(len(col), max((len(v) for v in values), default=0))
        widths[col] = min(widths[col], 40)  # cap width

    # Header
    header = " | ".join(col.ljust(widths[col]) for col in display_cols)
    sep = "-+-".join("-" * widths[col] for col in display_cols)
    print(f"\n{header}")
    print(sep)

    # Rows
    for row in rows:
        line = " | ".join(
            str(row.get(col, ""))[:widths[col]].ljust(widths[col])
            for col in display_cols
        )
        print(line)

    print(f"\n[+] {len(rows)} files processed.")

    # Unique authors
    authors = {r["Author"] for r in rows if r.get("Author")}
    if authors:
        print(f"[+] Unique authors found: {', '.join(sorted(authors))}")


def main():
    parser = argparse.ArgumentParser(
        description="AutoExIf - Dork + ExifTool Metadata Extractor"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--dork", "-d", help="Search dork query (e.g. 'site:example.com filetype:pdf')"
    )
    group.add_argument(
        "--urls-file", "-u", help="File containing URLs (one per line) to process directly"
    )
    parser.add_argument(
        "--limit", "-l", type=int, default=50, help="Max results to fetch (default: 50)"
    )
    parser.add_argument(
        "--output", "-o", default="results.csv", help="Output CSV path (default: results.csv)"
    )
    parser.add_argument(
        "--download-dir", default="./downloads", help="Download directory (default: ./downloads/)"
    )
    parser.add_argument(
        "--keep", action="store_true", help="Keep downloaded files after extraction"
    )
    args = parser.parse_args()

    download_dir = Path(args.download_dir)
    download_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Get URLs
    if args.urls_file:
        urls_path = Path(args.urls_file)
        if not urls_path.exists():
            print(f"[!] URLs file not found: {args.urls_file}")
            sys.exit(1)
        urls = [
            line.strip()
            for line in urls_path.read_text().splitlines()
            if line.strip() and line.strip().startswith("http")
        ]
        print(f"[+] Loaded {len(urls)} URLs from {args.urls_file}")
    else:
        print(f"[*] Dorking: {args.dork}")
        urls = duckduckgo_search(args.dork, args.limit)

    if not urls:
        print("[!] No URLs found. Try a different dork or check your connection.")
        sys.exit(0)

    # Step 2: Download files
    print(f"\n[*] Downloading {len(urls)} files...")
    session = requests.Session()
    session.headers.update({"User-Agent": random.choice(USER_AGENTS)})

    downloaded: list[tuple[str, Path]] = []
    for i, url in enumerate(urls, 1):
        print(f"  [{i}/{len(urls)}] {url}")
        path = download_file(url, download_dir, session)
        if path:
            downloaded.append((url, path))

    if not downloaded:
        print("[!] No files downloaded successfully.")
        sys.exit(0)

    # Step 3: Extract metadata
    print(f"\n[*] Running exiftool on {len(downloaded)} files...")
    rows: list[dict] = []
    for url, path in downloaded:
        meta = run_exiftool(path)
        row = extract_metadata(meta, url, path.name)
        rows.append(row)

    # Step 4: Output
    write_csv(rows, args.output)
    print_summary(rows)

    # Cleanup
    if not args.keep:
        shutil.rmtree(download_dir, ignore_errors=True)
        print(f"[*] Cleaned up {download_dir}/")
    else:
        print(f"[*] Downloaded files kept in {download_dir}/")


if __name__ == "__main__":
    main()
