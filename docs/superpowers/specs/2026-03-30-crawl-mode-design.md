# AutoExIf Crawl Mode Design

## Summary

Add a `--crawl` mode to AutoExIf that takes one or more website URLs, spiders them using Scrapy to discover all linked documents and media, downloads them, extracts all EXIF/metadata via exiftool, and outputs a comprehensive CSV + JSON report.

## Architecture

```
CLI (argparse)
  |-- --dork mode  -> DuckDuckGo search -> URL list
  |-- --crawl mode -> Scrapy spider     -> URL list
  |-- --urls-file  -> read from file    -> URL list
                                             |
                                    Download pipeline
                                             |
                                    Exiftool extraction
                                             |
                                    Output (CSV + JSON)
```

All three input modes produce a list of document URLs. The download, extraction, and output stages are shared.

### Refactor

The existing `main()` function is monolithic. Refactor to extract:

- `download_files(urls, download_dir, session) -> list[tuple[str, Path]]` (already roughly exists)
- `extract_all_metadata(downloaded) -> list[dict]` (new: runs exiftool, returns full metadata dicts)
- `write_outputs(rows, output_path)` (writes both CSV and JSON)
- `print_summary(rows)` (enhanced for multi-type output)

These become the shared pipeline that all input modes feed into.

## Scrapy Spider

### Behavior

- Accepts one or more start URLs via `--crawl`
- Configurable crawl depth via `--depth N` (default: 3)
- **Link following:** same domain only (domain extracted from each start URL)
- **Document downloading:** any origin allowed (CDNs, subdomains, S3 buckets, etc.)
- Respects `robots.txt` by default (Scrapy native), with `--ignore-robots` to override
- Configurable concurrency (default: 2) and delay (default: 1s)

### File Type Detection

Targeted file extensions:

- **Documents:** `.pdf`, `.doc`, `.docx`, `.xls`, `.xlsx`, `.ppt`, `.pptx`, `.odt`, `.ods`, `.odp`, `.rtf`
- **Images:** `.jpg`, `.jpeg`, `.png`, `.tiff`, `.tif`, `.gif`, `.bmp`, `.webp`, `.svg`
- **Audio:** `.mp3`, `.wav`, `.flac`, `.ogg`, `.aac`, `.m4a`
- **Video:** `.mp4`, `.avi`, `.mov`, `.mkv`, `.wmv`, `.webm`

Detection strategy:

1. **Primary:** match file extension in the URL path
2. **Fallback:** for extensionless URLs, send a HEAD request and check `Content-Type` for known document/media MIME types

### Spider Output

The spider writes discovered document URLs to a temporary file (one URL per line). The main script reads this file and feeds it into the shared download pipeline. This keeps Scrapy decoupled from the rest of the tool.

### Module Structure

```
autoexif/
  __init__.py
  cli.py            # argparse, main entry point
  pipeline.py       # download, exiftool, output (shared)
  dork.py           # DuckDuckGo search (extracted from current code)
  spider.py         # Scrapy spider + runner
```

The current single-file `autoexif.py` gets split into a package. A thin `autoexif.py` wrapper at the repo root can remain for backwards compatibility (`from autoexif.cli import main; main()`).

## Output

### CSV

- One row per downloaded file
- One column per unique exiftool field found across all processed files
- Wide and sparse: a PDF row won't have GPS columns, an image row won't have PageCount
- Always includes: `URL`, `Filename` as the first two columns; remaining columns sorted alphabetically
- Default path: `results.csv`

### JSON

- Full exiftool dump, saved alongside the CSV (same basename, `.json` extension)
- Array of objects, one per file, preserving all exiftool fields exactly as returned
- This is the lossless record; CSV is for quick browsing

### Stdout Summary

After processing, print:

- File count by type (e.g. "12 PDFs, 3 DOCX, 5 JPGs")
- Unique authors/creators found
- Unique software/tools found (Creator, Producer fields)
- Files with GPS coordinates flagged (filename + coordinates)

## CLI Interface

```
# Crawl mode (new)
python autoexif.py --crawl https://example.com --depth 3 -o results.csv

# Multiple sites
python autoexif.py --crawl https://a.com https://b.com --depth 2

# Existing modes still work
python autoexif.py --dork "site:example.com filetype:pdf"
python autoexif.py --urls-file urls.txt

# Shared flags
--output / -o        Output CSV path (default: results.csv)
--download-dir       Download directory (default: ./downloads/)
--keep               Keep downloaded files
--limit / -l         Max results to fetch (dork mode only, default: 50)

# Crawl-specific flags
--depth              Crawl depth (default: 3)
--ignore-robots      Ignore robots.txt
--delay              Request delay in seconds (default: 1)
--concurrency        Concurrent requests (default: 2)
```

The `--dork`, `--crawl`, and `--urls-file` flags are mutually exclusive.

## Dependencies

New:

- `scrapy` — crawling framework

Existing (unchanged):

- `requests` — HTTP downloads
- `beautifulsoup4` — DuckDuckGo HTML parsing

External tool (unchanged):

- `exiftool` — must be installed on the system

## Error Handling

- Spider logs crawl errors to stderr (Scrapy native logging)
- Download failures: skip and log, continue with remaining files
- Exiftool failures: skip and log, include empty row in output
- If zero documents found after crawling, exit with a clear message
- If exiftool is not installed, exit with install instructions (existing behavior)

## Testing Strategy

- Unit tests for file extension detection and MIME type matching
- Unit tests for URL domain matching (same-domain check)
- Integration test: crawl a small local HTTP server (pytest + `http.server`) with a few linked PDFs and images, verify CSV/JSON output
- Test that existing `--dork` and `--urls-file` modes still work after refactor
