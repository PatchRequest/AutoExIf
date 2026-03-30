"""Shared pipeline: download files, run exiftool, write CSV/JSON output."""

import csv
import json
import random
import subprocess
import sys
from collections import Counter
from pathlib import Path, PurePosixPath

import requests

from autoexif.filetypes import get_file_category

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]


def download_file(url: str, download_dir: Path, session: requests.Session) -> Path | None:
    """Download a file from the given URL. Returns path or None on failure."""
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        filename = PurePosixPath(parsed.path).name
        if not filename:
            filename = "unknown_file"

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


def download_files(
    urls: list[str], download_dir: Path, session: requests.Session | None = None
) -> list[tuple[str, Path]]:
    """Download all URLs. Returns list of (url, local_path) for successes."""
    if session is None:
        session = requests.Session()
        session.headers.update({"User-Agent": random.choice(USER_AGENTS)})

    downloaded: list[tuple[str, Path]] = []
    for i, url in enumerate(urls, 1):
        print(f"  [{i}/{len(urls)}] {url}")
        path = download_file(url, download_dir, session)
        if path:
            downloaded.append((url, path))
    return downloaded


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


def extract_all_metadata(downloaded: list[tuple[str, Path]]) -> list[dict]:
    """Run exiftool on all downloaded files, return list of metadata dicts."""
    rows: list[dict] = []
    for url, path in downloaded:
        meta = run_exiftool(path)
        meta["URL"] = url
        meta["Filename"] = path.name
        rows.append(meta)
    return rows


def build_csv_columns(rows: list[dict]) -> list[str]:
    """Build CSV column list: URL, Filename first, then remaining sorted."""
    all_keys: set[str] = set()
    for row in rows:
        all_keys.update(row.keys())

    all_keys.discard("URL")
    all_keys.discard("Filename")
    return ["URL", "Filename"] + sorted(all_keys)


def write_csv(rows: list[dict], output_path: str) -> None:
    """Write metadata rows to a CSV with dynamic columns."""
    columns = build_csv_columns(rows)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, restval="", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n[+] CSV written to {output_path}")


def write_json(rows: list[dict], output_path: str) -> None:
    """Write full metadata to a JSON file."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, default=str)
    print(f"[+] JSON written to {output_path}")


def format_summary(rows: list[dict]) -> str:
    """Build a human-readable summary string."""
    if not rows:
        return "[*] No metadata extracted."

    lines: list[str] = []

    # Count by file type
    ext_counts: Counter[str] = Counter()
    for row in rows:
        filename = row.get("Filename", "")
        ext = PurePosixPath(filename).suffix.lower().lstrip(".")
        if ext:
            ext_counts[ext] += 1
        else:
            ext_counts["unknown"] += 1

    type_parts = [f"{count} {ext.upper()}" for ext, count in ext_counts.most_common()]
    lines.append(f"[+] Files processed: {', '.join(type_parts)}")

    # Unique authors
    authors = {r["Author"] for r in rows if r.get("Author")}
    if authors:
        lines.append(f"[+] Authors: {', '.join(sorted(authors))}")

    # Unique tools (Creator + Producer)
    tools: set[str] = set()
    for r in rows:
        if r.get("Creator"):
            tools.add(str(r["Creator"]))
        if r.get("Producer"):
            tools.add(str(r["Producer"]))
    if tools:
        lines.append(f"[+] Tools/Software: {', '.join(sorted(tools))}")

    # GPS coordinates
    gps_files: list[str] = []
    for r in rows:
        if r.get("GPSLatitude") and r.get("GPSLongitude"):
            gps_files.append(
                f"  {r['Filename']}: {r['GPSLatitude']}, {r['GPSLongitude']}"
            )
    if gps_files:
        lines.append("[+] Files with GPS coordinates:")
        lines.extend(gps_files)

    return "\n".join(lines)
