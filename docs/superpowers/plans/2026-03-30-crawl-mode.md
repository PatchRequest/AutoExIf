# Crawl Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `--crawl` mode that spiders websites via Scrapy to discover documents/media, then extracts all EXIF metadata into CSV + JSON.

**Architecture:** Three input modes (dork, crawl, urls-file) each produce a URL list. A shared pipeline downloads files, runs exiftool, and writes output. The current monolithic `autoexif.py` is split into a package with focused modules.

**Tech Stack:** Python 3.10+, Scrapy, requests, BeautifulSoup, exiftool (system)

---

## File Structure

```
autoexif/
  __init__.py          # Package init, version
  cli.py               # Argparse CLI, main entry point
  pipeline.py          # Download, exiftool, CSV/JSON output
  dork.py              # DuckDuckGo search (extracted from current code)
  spider.py            # Scrapy spider + CrawlerProcess runner
  filetypes.py         # File extension sets and MIME type mapping
autoexif.py            # Thin wrapper: from autoexif.cli import main; main()
requirements.txt       # Updated with scrapy
tests/
  __init__.py
  conftest.py          # Shared fixtures (tmp dirs, sample metadata dicts)
  test_filetypes.py    # File extension and MIME detection tests
  test_pipeline.py     # Download, exiftool, output tests
  test_dork.py         # DuckDuckGo search extraction tests
  test_spider.py       # Scrapy spider domain filtering + URL collection tests
  test_cli.py          # CLI arg parsing + integration tests
```

---

### Task 1: Project Setup and Dependencies

**Files:**
- Modify: `requirements.txt`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Update requirements.txt**

```
requests
beautifulsoup4
scrapy
pytest
```

- [ ] **Step 2: Install dependencies**

Run: `pip install -r requirements.txt`
Expected: All packages install successfully

- [ ] **Step 3: Create test infrastructure**

Create `tests/__init__.py` (empty file).

Create `tests/conftest.py`:

```python
import json
from pathlib import Path

import pytest


@pytest.fixture
def tmp_download_dir(tmp_path):
    d = tmp_path / "downloads"
    d.mkdir()
    return d


@pytest.fixture
def sample_pdf_metadata():
    return {
        "SourceFile": "test.pdf",
        "FileName": "test.pdf",
        "Author": "John Doe",
        "Creator": "Microsoft Word",
        "Producer": "Adobe PDF Library 17.0",
        "CreateDate": "2024:01:15 10:30:00",
        "ModifyDate": "2024:01:15 10:31:00",
        "Title": "Test Document",
        "PageCount": 5,
    }


@pytest.fixture
def sample_image_metadata():
    return {
        "SourceFile": "photo.jpg",
        "FileName": "photo.jpg",
        "Make": "Canon",
        "Model": "EOS R5",
        "Software": "Adobe Photoshop 25.0",
        "CreateDate": "2024:06:15 14:22:33",
        "GPSLatitude": "48 deg 51' 24.00\" N",
        "GPSLongitude": "2 deg 21' 7.00\" E",
        "ImageWidth": 8192,
        "ImageHeight": 5464,
    }
```

- [ ] **Step 4: Verify pytest runs**

Run: `pytest tests/ -v`
Expected: "no tests ran" (0 collected), exit code 5 (no tests), no import errors

- [ ] **Step 5: Commit**

```bash
git add requirements.txt tests/__init__.py tests/conftest.py
git commit -m "chore: add test infrastructure and scrapy dependency"
```

---

### Task 2: File Type Detection Module

**Files:**
- Create: `autoexif/__init__.py`
- Create: `autoexif/filetypes.py`
- Create: `tests/test_filetypes.py`

- [ ] **Step 1: Write failing tests for file type detection**

Create `autoexif/__init__.py` (empty file).

Create `tests/test_filetypes.py`:

```python
from autoexif.filetypes import (
    DOCUMENT_EXTENSIONS,
    IMAGE_EXTENSIONS,
    AUDIO_EXTENSIONS,
    VIDEO_EXTENSIONS,
    ALL_EXTENSIONS,
    MIME_TO_CATEGORY,
    is_document_url,
    get_file_category,
)


class TestExtensionSets:
    def test_document_extensions_include_pdf(self):
        assert ".pdf" in DOCUMENT_EXTENSIONS

    def test_document_extensions_include_docx(self):
        assert ".docx" in DOCUMENT_EXTENSIONS

    def test_image_extensions_include_jpg(self):
        assert ".jpg" in IMAGE_EXTENSIONS
        assert ".jpeg" in IMAGE_EXTENSIONS

    def test_audio_extensions_include_mp3(self):
        assert ".mp3" in AUDIO_EXTENSIONS

    def test_video_extensions_include_mp4(self):
        assert ".mp4" in VIDEO_EXTENSIONS

    def test_all_extensions_is_union(self):
        assert ALL_EXTENSIONS == (
            DOCUMENT_EXTENSIONS | IMAGE_EXTENSIONS | AUDIO_EXTENSIONS | VIDEO_EXTENSIONS
        )


class TestIsDocumentUrl:
    def test_pdf_url(self):
        assert is_document_url("https://example.com/report.pdf") is True

    def test_docx_url(self):
        assert is_document_url("https://cdn.example.com/file.docx") is True

    def test_jpg_url(self):
        assert is_document_url("https://images.example.com/photo.jpg") is True

    def test_mp4_url(self):
        assert is_document_url("https://media.example.com/video.mp4") is True

    def test_html_url(self):
        assert is_document_url("https://example.com/page.html") is False

    def test_no_extension(self):
        assert is_document_url("https://example.com/page") is False

    def test_url_with_query_params(self):
        assert is_document_url("https://example.com/report.pdf?v=2&token=abc") is True

    def test_url_with_fragment(self):
        assert is_document_url("https://example.com/report.pdf#page=3") is True

    def test_case_insensitive(self):
        assert is_document_url("https://example.com/REPORT.PDF") is True
        assert is_document_url("https://example.com/Photo.JPG") is True


class TestGetFileCategory:
    def test_pdf_is_document(self):
        assert get_file_category("report.pdf") == "document"

    def test_jpg_is_image(self):
        assert get_file_category("photo.jpg") == "image"

    def test_mp3_is_audio(self):
        assert get_file_category("song.mp3") == "audio"

    def test_mp4_is_video(self):
        assert get_file_category("clip.mp4") == "video"

    def test_html_is_none(self):
        assert get_file_category("page.html") is None

    def test_no_extension_is_none(self):
        assert get_file_category("README") is None


class TestMimeMapping:
    def test_pdf_mime(self):
        assert MIME_TO_CATEGORY["application/pdf"] == "document"

    def test_jpeg_mime(self):
        assert MIME_TO_CATEGORY["image/jpeg"] == "image"

    def test_mp3_mime(self):
        assert MIME_TO_CATEGORY["audio/mpeg"] == "audio"

    def test_mp4_mime(self):
        assert MIME_TO_CATEGORY["video/mp4"] == "video"

    def test_docx_mime(self):
        assert MIME_TO_CATEGORY[
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ] == "document"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_filetypes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'autoexif.filetypes'`

- [ ] **Step 3: Implement filetypes module**

Create `autoexif/filetypes.py`:

```python
"""File type extension sets and MIME type mappings for document/media detection."""

from pathlib import PurePosixPath
from urllib.parse import urlparse

DOCUMENT_EXTENSIONS = frozenset({
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".odt", ".ods", ".odp", ".rtf",
})

IMAGE_EXTENSIONS = frozenset({
    ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".gif", ".bmp", ".webp", ".svg",
})

AUDIO_EXTENSIONS = frozenset({
    ".mp3", ".wav", ".flac", ".ogg", ".aac", ".m4a",
})

VIDEO_EXTENSIONS = frozenset({
    ".mp4", ".avi", ".mov", ".mkv", ".wmv", ".webm",
})

ALL_EXTENSIONS = DOCUMENT_EXTENSIONS | IMAGE_EXTENSIONS | AUDIO_EXTENSIONS | VIDEO_EXTENSIONS

_EXT_TO_CATEGORY: dict[str, str] = {}
for _ext in DOCUMENT_EXTENSIONS:
    _EXT_TO_CATEGORY[_ext] = "document"
for _ext in IMAGE_EXTENSIONS:
    _EXT_TO_CATEGORY[_ext] = "image"
for _ext in AUDIO_EXTENSIONS:
    _EXT_TO_CATEGORY[_ext] = "audio"
for _ext in VIDEO_EXTENSIONS:
    _EXT_TO_CATEGORY[_ext] = "video"

MIME_TO_CATEGORY: dict[str, str] = {
    # Documents
    "application/pdf": "document",
    "application/msword": "document",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "document",
    "application/vnd.ms-excel": "document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "document",
    "application/vnd.ms-powerpoint": "document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "document",
    "application/vnd.oasis.opendocument.text": "document",
    "application/vnd.oasis.opendocument.spreadsheet": "document",
    "application/vnd.oasis.opendocument.presentation": "document",
    "application/rtf": "document",
    # Images
    "image/jpeg": "image",
    "image/png": "image",
    "image/tiff": "image",
    "image/gif": "image",
    "image/bmp": "image",
    "image/webp": "image",
    "image/svg+xml": "image",
    # Audio
    "audio/mpeg": "audio",
    "audio/wav": "audio",
    "audio/flac": "audio",
    "audio/ogg": "audio",
    "audio/aac": "audio",
    "audio/mp4": "audio",
    # Video
    "video/mp4": "video",
    "video/x-msvideo": "video",
    "video/quicktime": "video",
    "video/x-matroska": "video",
    "video/x-ms-wmv": "video",
    "video/webm": "video",
}


def is_document_url(url: str) -> bool:
    """Check if a URL points to a known document/media file by extension."""
    try:
        path = urlparse(url).path
    except ValueError:
        return False
    ext = PurePosixPath(path).suffix.lower()
    return ext in ALL_EXTENSIONS


def get_file_category(filename: str) -> str | None:
    """Return the category ('document', 'image', 'audio', 'video') for a filename, or None."""
    ext = PurePosixPath(filename).suffix.lower()
    return _EXT_TO_CATEGORY.get(ext)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_filetypes.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add autoexif/__init__.py autoexif/filetypes.py tests/test_filetypes.py
git commit -m "feat: add file type detection module with extension and MIME mappings"
```

---

### Task 3: Pipeline Module — Exiftool and Output

**Files:**
- Create: `autoexif/pipeline.py`
- Create: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing tests for exiftool and output functions**

Create `tests/test_pipeline.py`:

```python
import csv
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from autoexif.pipeline import (
    run_exiftool,
    extract_all_metadata,
    build_csv_columns,
    write_csv,
    write_json,
    format_summary,
)


class TestRunExiftool:
    @patch("subprocess.run")
    def test_returns_parsed_metadata(self, mock_run):
        meta = {"FileName": "test.pdf", "Author": "Jane"}
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps([meta]), stderr=""
        )
        result = run_exiftool(Path("test.pdf"))
        assert result == meta
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_returns_empty_dict_on_error(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="Error"
        )
        result = run_exiftool(Path("bad.pdf"))
        assert result == {}

    @patch("subprocess.run", side_effect=FileNotFoundError)
    def test_exits_if_exiftool_not_found(self, mock_run):
        import pytest
        with pytest.raises(SystemExit):
            run_exiftool(Path("test.pdf"))


class TestExtractAllMetadata:
    @patch("autoexif.pipeline.run_exiftool")
    def test_extracts_metadata_for_each_file(self, mock_exiftool):
        mock_exiftool.side_effect = [
            {"Author": "Alice", "Creator": "Word"},
            {"Make": "Canon", "Model": "EOS R5"},
        ]
        downloaded = [
            ("https://a.com/doc.pdf", Path("/tmp/doc.pdf")),
            ("https://a.com/photo.jpg", Path("/tmp/photo.jpg")),
        ]
        rows = extract_all_metadata(downloaded)
        assert len(rows) == 2
        assert rows[0]["URL"] == "https://a.com/doc.pdf"
        assert rows[0]["Filename"] == "doc.pdf"
        assert rows[0]["Author"] == "Alice"
        assert rows[1]["Make"] == "Canon"

    @patch("autoexif.pipeline.run_exiftool")
    def test_includes_url_and_filename_even_on_empty_metadata(self, mock_exiftool):
        mock_exiftool.return_value = {}
        downloaded = [("https://a.com/empty.pdf", Path("/tmp/empty.pdf"))]
        rows = extract_all_metadata(downloaded)
        assert rows[0]["URL"] == "https://a.com/empty.pdf"
        assert rows[0]["Filename"] == "empty.pdf"


class TestBuildCsvColumns:
    def test_url_and_filename_come_first(self):
        rows = [
            {"URL": "https://a.com/f.pdf", "Filename": "f.pdf", "Zebra": "z", "Author": "a"},
        ]
        cols = build_csv_columns(rows)
        assert cols[0] == "URL"
        assert cols[1] == "Filename"

    def test_remaining_columns_sorted(self):
        rows = [
            {"URL": "u", "Filename": "f", "Zebra": "z", "Author": "a", "Creator": "c"},
        ]
        cols = build_csv_columns(rows)
        assert cols[2:] == ["Author", "Creator", "Zebra"]

    def test_union_of_all_row_keys(self):
        rows = [
            {"URL": "u", "Filename": "f", "Author": "a"},
            {"URL": "u", "Filename": "f", "Make": "Canon"},
        ]
        cols = build_csv_columns(rows)
        assert "Author" in cols
        assert "Make" in cols


class TestWriteCsv:
    def test_writes_csv_with_all_columns(self, tmp_path):
        rows = [
            {"URL": "u1", "Filename": "f1", "Author": "Alice"},
            {"URL": "u2", "Filename": "f2", "Make": "Canon"},
        ]
        out = tmp_path / "out.csv"
        write_csv(rows, str(out))
        content = out.read_text()
        reader = csv.DictReader(content.splitlines())
        csv_rows = list(reader)
        assert len(csv_rows) == 2
        assert csv_rows[0]["Author"] == "Alice"
        assert csv_rows[0]["Make"] == ""
        assert csv_rows[1]["Make"] == "Canon"


class TestWriteJson:
    def test_writes_json_array(self, tmp_path):
        rows = [{"URL": "u1", "Author": "Alice"}]
        out = tmp_path / "out.json"
        write_json(rows, str(out))
        data = json.loads(out.read_text())
        assert data == rows


class TestFormatSummary:
    def test_counts_by_file_type(self):
        rows = [
            {"Filename": "a.pdf"},
            {"Filename": "b.pdf"},
            {"Filename": "c.jpg"},
        ]
        summary = format_summary(rows)
        assert "2 pdf" in summary.lower()
        assert "1 jpg" in summary.lower()

    def test_unique_authors(self):
        rows = [
            {"Filename": "a.pdf", "Author": "Alice"},
            {"Filename": "b.pdf", "Author": "Bob"},
            {"Filename": "c.pdf", "Author": "Alice"},
        ]
        summary = format_summary(rows)
        assert "Alice" in summary
        assert "Bob" in summary

    def test_unique_tools(self):
        rows = [
            {"Filename": "a.pdf", "Creator": "Word", "Producer": "Adobe PDF Library"},
        ]
        summary = format_summary(rows)
        assert "Word" in summary
        assert "Adobe PDF Library" in summary

    def test_gps_flagged(self):
        rows = [
            {"Filename": "photo.jpg", "GPSLatitude": "48 deg 51' N", "GPSLongitude": "2 deg 21' E"},
        ]
        summary = format_summary(rows)
        assert "photo.jpg" in summary
        assert "GPS" in summary or "gps" in summary.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pipeline.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'autoexif.pipeline'`

- [ ] **Step 3: Implement pipeline module**

Create `autoexif/pipeline.py`:

```python
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
        filename = Path(parsed.path).name
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_pipeline.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add autoexif/pipeline.py tests/test_pipeline.py
git commit -m "feat: add shared pipeline module for download, exiftool, and output"
```

---

### Task 4: Dork Module (Extract from Current Code)

**Files:**
- Create: `autoexif/dork.py`
- Create: `tests/test_dork.py`

- [ ] **Step 1: Write failing tests for dork search helpers**

Create `tests/test_dork.py`:

```python
from autoexif.dork import is_ad_url


class TestIsAdUrl:
    def test_duckduckgo_is_ad(self):
        assert is_ad_url("https://duckduckgo.com/y.js?foo=bar") is True

    def test_bing_is_ad(self):
        assert is_ad_url("https://www.bing.com/aclick?ld=foo") is True

    def test_google_is_ad(self):
        assert is_ad_url("https://www.google.com/search?q=test") is True

    def test_normal_url_is_not_ad(self):
        assert is_ad_url("https://example.com/report.pdf") is False

    def test_invalid_url(self):
        assert is_ad_url("not a url at all :::") is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dork.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'autoexif.dork'`

- [ ] **Step 3: Implement dork module**

Create `autoexif/dork.py`:

```python
"""DuckDuckGo dork search to find document URLs on target domains."""

import random
import re
import time
from urllib.parse import unquote, urlparse

import requests
from bs4 import BeautifulSoup

from autoexif.pipeline import USER_AGENTS

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
    max_pages = (limit // 10) + 3
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

        found_this_page = 0
        for result_div in soup.find_all("div", class_="web-result"):
            a_tag = result_div.find("a", class_="result__a", href=True)
            if not a_tag:
                continue

            href = a_tag["href"]
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_dork.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add autoexif/dork.py tests/test_dork.py
git commit -m "feat: extract dork search into standalone module"
```

---

### Task 5: Scrapy Spider Module

**Files:**
- Create: `autoexif/spider.py`
- Create: `tests/test_spider.py`

- [ ] **Step 1: Write failing tests for spider helpers and domain matching**

Create `tests/test_spider.py`:

```python
from autoexif.spider import extract_allowed_domains, is_same_domain, run_spider
from autoexif.filetypes import is_document_url


class TestExtractAllowedDomains:
    def test_single_url(self):
        domains = extract_allowed_domains(["https://example.com/page"])
        assert domains == ["example.com"]

    def test_multiple_urls(self):
        domains = extract_allowed_domains([
            "https://foo.com/a",
            "https://bar.org/b",
        ])
        assert set(domains) == {"foo.com", "bar.org"}

    def test_strips_www(self):
        domains = extract_allowed_domains(["https://www.example.com/page"])
        assert domains == ["example.com"]

    def test_deduplicates(self):
        domains = extract_allowed_domains([
            "https://example.com/a",
            "https://example.com/b",
        ])
        assert domains == ["example.com"]


class TestIsSameDomain:
    def test_same_domain(self):
        assert is_same_domain("https://example.com/page2", ["example.com"]) is True

    def test_different_domain(self):
        assert is_same_domain("https://other.com/page", ["example.com"]) is False

    def test_subdomain_not_same(self):
        # Link following is same-domain only, subdomains are different
        assert is_same_domain("https://cdn.example.com/file", ["example.com"]) is False

    def test_www_prefix_matches(self):
        assert is_same_domain("https://www.example.com/page", ["example.com"]) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_spider.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'autoexif.spider'`

- [ ] **Step 3: Implement spider module**

Create `autoexif/spider.py`:

```python
"""Scrapy spider that crawls websites to discover document/media URLs."""

import tempfile
from urllib.parse import urlparse

import scrapy
from scrapy.crawler import CrawlerProcess

from autoexif.filetypes import is_document_url


def extract_allowed_domains(start_urls: list[str]) -> list[str]:
    """Extract unique domains from start URLs, stripping www prefix."""
    domains: list[str] = []
    seen: set[str] = set()
    for url in start_urls:
        host = urlparse(url).hostname or ""
        if host.startswith("www."):
            host = host[4:]
        if host and host not in seen:
            seen.add(host)
            domains.append(host)
    return domains


def is_same_domain(url: str, allowed_domains: list[str]) -> bool:
    """Check if a URL's domain matches any allowed domain (exact match, www allowed)."""
    host = urlparse(url).hostname or ""
    if host.startswith("www."):
        host = host[4:]
    return host in allowed_domains


class DocumentSpider(scrapy.Spider):
    name = "document_spider"

    def __init__(self, start_urls, allowed_domains, found_urls, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_urls = start_urls
        self._allowed_domains = allowed_domains
        self.found_urls = found_urls

    def parse(self, response):
        # Extract all links from the page
        for href in response.css("a::attr(href)").getall():
            url = response.urljoin(href)

            if is_document_url(url):
                # Document link — collect it (any origin allowed)
                if url not in self.found_urls:
                    self.found_urls.add(url)
                    yield {"url": url}
            elif is_same_domain(url, self._allowed_domains):
                # Same-domain HTML page — follow it
                yield response.follow(url, callback=self.parse)


def run_spider(
    start_urls: list[str],
    depth: int = 3,
    delay: float = 1.0,
    concurrency: int = 2,
    ignore_robots: bool = False,
) -> list[str]:
    """Run the Scrapy spider and return discovered document URLs."""
    allowed_domains = extract_allowed_domains(start_urls)
    found_urls: set[str] = set()
    collected: list[str] = []

    # Write results to a temp file to decouple from Scrapy's reactor
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
    tmp_path = tmp.name
    tmp.close()

    settings = {
        "DEPTH_LIMIT": depth,
        "DOWNLOAD_DELAY": delay,
        "CONCURRENT_REQUESTS": concurrency,
        "CONCURRENT_REQUESTS_PER_DOMAIN": concurrency,
        "ROBOTSTXT_OBEY": not ignore_robots,
        "LOG_LEVEL": "WARNING",
        "REQUEST_FINGERPRINTER_IMPLEMENTATION": "2.7",
        "FEEDS": {
            tmp_path: {
                "format": "jsonlines",
                "overwrite": True,
            },
        },
        # Avoid Twisted reactor issues on repeated runs
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
    }

    process = CrawlerProcess(settings=settings)
    process.crawl(
        DocumentSpider,
        start_urls=start_urls,
        allowed_domains=allowed_domains,
        found_urls=found_urls,
    )
    process.start()

    # Read collected URLs from the temp file
    import json
    from pathlib import Path

    content = Path(tmp_path).read_text()
    for line in content.strip().splitlines():
        if line.strip():
            data = json.loads(line)
            collected.append(data["url"])

    Path(tmp_path).unlink(missing_ok=True)

    print(f"[+] Spider found {len(collected)} document URLs")
    return collected
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_spider.py -v`
Expected: All tests PASS (only the helper function tests — `run_spider` is tested in integration)

- [ ] **Step 5: Commit**

```bash
git add autoexif/spider.py tests/test_spider.py
git commit -m "feat: add Scrapy spider for website crawling and document discovery"
```

---

### Task 6: CLI Module and Root Wrapper

**Files:**
- Create: `autoexif/cli.py`
- Create: `tests/test_cli.py`
- Modify: `autoexif.py` (replace with thin wrapper)

- [ ] **Step 1: Write failing tests for CLI argument parsing**

Create `tests/test_cli.py`:

```python
import pytest

from autoexif.cli import build_parser


class TestBuildParser:
    def test_dork_mode(self):
        parser = build_parser()
        args = parser.parse_args(["--dork", "site:example.com filetype:pdf"])
        assert args.dork == "site:example.com filetype:pdf"
        assert args.crawl is None
        assert args.urls_file is None

    def test_crawl_mode_single_url(self):
        parser = build_parser()
        args = parser.parse_args(["--crawl", "https://example.com"])
        assert args.crawl == ["https://example.com"]
        assert args.dork is None

    def test_crawl_mode_multiple_urls(self):
        parser = build_parser()
        args = parser.parse_args(["--crawl", "https://a.com", "https://b.com"])
        assert args.crawl == ["https://a.com", "https://b.com"]

    def test_urls_file_mode(self):
        parser = build_parser()
        args = parser.parse_args(["--urls-file", "urls.txt"])
        assert args.urls_file == "urls.txt"

    def test_mutually_exclusive(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--dork", "test", "--crawl", "https://example.com"])

    def test_default_depth(self):
        parser = build_parser()
        args = parser.parse_args(["--crawl", "https://example.com"])
        assert args.depth == 3

    def test_custom_depth(self):
        parser = build_parser()
        args = parser.parse_args(["--crawl", "https://example.com", "--depth", "5"])
        assert args.depth == 5

    def test_default_output(self):
        parser = build_parser()
        args = parser.parse_args(["--dork", "test"])
        assert args.output == "results.csv"

    def test_default_delay(self):
        parser = build_parser()
        args = parser.parse_args(["--crawl", "https://example.com"])
        assert args.delay == 1.0

    def test_default_concurrency(self):
        parser = build_parser()
        args = parser.parse_args(["--crawl", "https://example.com"])
        assert args.concurrency == 2

    def test_ignore_robots_flag(self):
        parser = build_parser()
        args = parser.parse_args(["--crawl", "https://example.com", "--ignore-robots"])
        assert args.ignore_robots is True

    def test_keep_flag(self):
        parser = build_parser()
        args = parser.parse_args(["--dork", "test", "--keep"])
        assert args.keep is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'autoexif.cli'`

- [ ] **Step 3: Implement CLI module**

Create `autoexif/cli.py`:

```python
"""CLI entry point for AutoExIf."""

import shutil
import sys
from pathlib import Path

from autoexif.dork import duckduckgo_search
from autoexif.pipeline import download_files, extract_all_metadata, write_csv, write_json, format_summary
from autoexif.spider import run_spider


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: All tests PASS

- [ ] **Step 5: Replace root autoexif.py with thin wrapper**

Overwrite `autoexif.py` with:

```python
#!/usr/bin/env python3
"""AutoExIf - Website Crawler + Metadata Extractor."""
from autoexif.cli import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Commit**

```bash
git add autoexif/cli.py tests/test_cli.py autoexif.py
git commit -m "feat: add CLI module with --crawl, --dork, --urls-file modes"
```

---

### Task 7: Integration Test

**Files:**
- Create: `tests/test_integration.py`
- Create: `tests/fixtures/` (test PDF and image)

- [ ] **Step 1: Create test fixtures**

Create a minimal test PDF and JPEG for exiftool to process:

```bash
# Create a minimal PDF (valid enough for exiftool)
mkdir -p tests/fixtures
python3 -c "
# Minimal valid PDF
pdf = b'%PDF-1.0\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF'
with open('tests/fixtures/test.pdf', 'wb') as f:
    f.write(pdf)
"
```

- [ ] **Step 2: Write integration test for the full pipeline**

Create `tests/test_integration.py`:

```python
import csv
import json
import http.server
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from autoexif.pipeline import download_files, extract_all_metadata, write_csv, write_json, format_summary


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestFullPipeline:
    """Integration test: serve files via local HTTP, download, extract metadata."""

    @pytest.fixture(autouse=True)
    def setup_server(self, tmp_path):
        """Start a local HTTP server serving test fixtures."""
        handler = http.server.SimpleHTTPRequestHandler
        self.server = http.server.HTTPServer(
            ("127.0.0.1", 0),
            lambda *args, **kwargs: handler(*args, directory=str(FIXTURES_DIR), **kwargs),
        )
        self.port = self.server.server_address[1]
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()
        self.tmp_path = tmp_path
        yield
        self.server.shutdown()

    def test_download_extract_and_output(self):
        urls = [f"{self.base_url}/test.pdf"]
        download_dir = self.tmp_path / "downloads"
        download_dir.mkdir()

        # Download
        downloaded = download_files(urls, download_dir)
        assert len(downloaded) == 1
        assert downloaded[0][1].exists()

        # Extract (requires exiftool installed)
        rows = extract_all_metadata(downloaded)
        assert len(rows) == 1
        assert rows[0]["URL"] == urls[0]
        assert rows[0]["Filename"] == "test.pdf"

        # CSV output
        csv_path = str(self.tmp_path / "results.csv")
        write_csv(rows, csv_path)
        assert Path(csv_path).exists()
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            csv_rows = list(reader)
        assert len(csv_rows) == 1
        assert csv_rows[0]["URL"] == urls[0]

        # JSON output
        json_path = str(self.tmp_path / "results.json")
        write_json(rows, json_path)
        data = json.loads(Path(json_path).read_text())
        assert len(data) == 1

        # Summary
        summary = format_summary(rows)
        assert "1 PDF" in summary
```

- [ ] **Step 3: Run integration test**

Run: `pytest tests/test_integration.py -v`
Expected: PASS (requires `exiftool` installed on system)

- [ ] **Step 4: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/ tests/test_integration.py
git commit -m "test: add integration test with local HTTP server and full pipeline"
```

---

### Task 8: Cleanup and Final Verification

**Files:**
- Modify: `autoexif.py` (already done in Task 6)
- Remove: `results.csv` (sample data from old runs, not needed in repo)

- [ ] **Step 1: Verify all modes work end-to-end**

Run dork mode (quick check with 1 result):
```bash
python autoexif.py --dork "site:example.com filetype:pdf" --limit 1 --keep
```
Expected: Searches, downloads, extracts, writes CSV + JSON

Run urls-file mode:
```bash
echo "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf" > /tmp/test_urls.txt
python autoexif.py --urls-file /tmp/test_urls.txt --keep
```
Expected: Downloads, extracts, writes CSV + JSON

- [ ] **Step 2: Verify crawl mode**

```bash
python autoexif.py --crawl https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/ --depth 1 --keep
```
Expected: Crawls page, finds PDFs, downloads, extracts, writes CSV + JSON

- [ ] **Step 3: Run full test suite one final time**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 4: Remove stale results.csv**

```bash
git rm results.csv
```

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "chore: final cleanup, remove stale results.csv"
```

---

## Spec Coverage Check

| Spec Requirement | Task |
|---|---|
| `--crawl` mode with start URLs | Task 5 (spider), Task 6 (CLI) |
| `--depth N` (default 3) | Task 5, Task 6 |
| Same-domain link following | Task 5 |
| Any-origin document download | Task 5 (spider collects all doc URLs) |
| robots.txt respect + `--ignore-robots` | Task 5 |
| Concurrency + delay config | Task 5, Task 6 |
| File type detection (docs, images, audio, video) | Task 2 |
| MIME type fallback | Task 2 |
| All exiftool fields in CSV (dynamic columns) | Task 3 |
| JSON output | Task 3 |
| Summary: counts, authors, tools, GPS | Task 3 |
| Refactor to shared pipeline | Task 3 |
| Extract dork module | Task 4 |
| Package structure | Tasks 2-6 |
| Error handling (download, exiftool, no results) | Task 3 |
| `--keep` flag | Task 6 |
| Existing modes preserved | Task 6, Task 7 |
| Tests | Tasks 2-7 |
