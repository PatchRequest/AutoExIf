"""CLI entry point for AutoExIf."""

import shutil
import sys
from pathlib import Path


def build_parser():
    import argparse

    parser = argparse.ArgumentParser(
        description="AutoExIf - Website Crawler + Metadata Extractor"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--dork", "-d", help="Search dork query (e.g. 'site:example.com filetype:pdf')"
    )
    group.add_argument(
        "--crawl", "-c", nargs="+", help="URL(s) to crawl for documents"
    )
    group.add_argument(
        "--urls-file", "-u", help="File containing URLs (one per line)"
    )

    parser.add_argument(
        "--limit", "-l", type=int, default=50, help="Max results (dork mode only, default: 50)"
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

    # Crawl-specific
    parser.add_argument(
        "--depth", type=int, default=3, help="Crawl depth (default: 3)"
    )
    parser.add_argument(
        "--ignore-robots", action="store_true", help="Ignore robots.txt"
    )
    parser.add_argument(
        "--delay", type=float, default=1.0, help="Request delay in seconds (default: 1.0)"
    )
    parser.add_argument(
        "--concurrency", type=int, default=2, help="Concurrent requests (default: 2)"
    )

    return parser


def main():
    from autoexif.dork import duckduckgo_search
    from autoexif.pipeline import download_files, extract_all_metadata, write_csv, write_json, format_summary
    from autoexif.spider import run_spider

    parser = build_parser()
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

    elif args.crawl:
        print(f"[*] Crawling {len(args.crawl)} site(s) (depth={args.depth})...")
        urls = run_spider(
            start_urls=args.crawl,
            depth=args.depth,
            delay=args.delay,
            concurrency=args.concurrency,
            ignore_robots=args.ignore_robots,
        )

    else:
        print(f"[*] Dorking: {args.dork}")
        urls = duckduckgo_search(args.dork, args.limit)

    if not urls:
        print("[!] No URLs found.")
        sys.exit(0)

    # Step 2: Download
    print(f"\n[*] Downloading {len(urls)} files...")
    downloaded = download_files(urls, download_dir)

    if not downloaded:
        print("[!] No files downloaded successfully.")
        sys.exit(0)

    # Step 3: Extract metadata
    print(f"\n[*] Running exiftool on {len(downloaded)} files...")
    rows = extract_all_metadata(downloaded)

    # Step 4: Output
    write_csv(rows, args.output)

    json_output = str(Path(args.output).with_suffix(".json"))
    write_json(rows, json_output)

    summary = format_summary(rows)
    print(f"\n{summary}")

    # Cleanup
    if not args.keep:
        shutil.rmtree(download_dir, ignore_errors=True)
        print(f"\n[*] Cleaned up {download_dir}/")
    else:
        print(f"\n[*] Downloaded files kept in {download_dir}/")
