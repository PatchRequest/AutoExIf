# AutoExIf

Automated OSINT metadata extraction tool. Crawl websites, search via dorks, or provide URL lists — AutoExIf downloads all documents, images, and media, then extracts every piece of metadata using [exiftool](https://exiftool.org/).

Discover authors, software tools, original filenames, GPS coordinates, and more — all exported to CSV and JSON.

## Features

- **Website Crawling** — Scrapy-powered spider follows links to discover documents across a site
- **Dork Search** — DuckDuckGo dorking to find files on target domains
- **URL List** — Process a pre-built list of URLs
- **Full Metadata Extraction** — Every field exiftool returns, not just a curated subset
- **Dual Output** — Wide CSV for browsing + full JSON dump for programmatic use
- **Smart Summary** — File counts by type, unique authors, software/tools used, GPS-tagged files flagged
- **Broad File Support** — PDFs, Office docs, images, audio, video — anything with metadata
- **CDN-Aware** — Follows links on the target domain, but downloads documents from any origin (CDNs, subdomains, S3)
- **Polite by Default** — Respects `robots.txt`, configurable rate limiting and concurrency

## Installation

```bash
git clone https://github.com/PatchRequest/AutoExIf.git
cd AutoExIf
pip install -r requirements.txt
```

**Requires [exiftool](https://exiftool.org/) on your system:**

```bash
# macOS
brew install exiftool

# Debian/Ubuntu
sudo apt install libimage-exiftool-perl

# Arch
sudo pacman -S perl-image-exiftool
```

## Usage

### Crawl a Website

```bash
python autoexif.py --crawl https://example.com --depth 3
```

Spider the site up to 3 levels deep, find all documents and media, extract metadata.

### Crawl Multiple Sites

```bash
python autoexif.py --crawl https://a.com https://b.com --depth 2
```

### Dork Search

```bash
python autoexif.py --dork "site:example.com filetype:pdf" --limit 50
```

### URL List

```bash
python autoexif.py --urls-file urls.txt
```

### Options

| Flag | Description | Default |
|------|-------------|---------|
| `--crawl URL [URL ...]` | Website(s) to crawl | — |
| `--dork QUERY` | DuckDuckGo dork query | — |
| `--urls-file FILE` | File with URLs (one per line) | — |
| `--depth N` | Crawl depth | 3 |
| `--output FILE` | Output CSV path | `results.csv` |
| `--keep` | Keep downloaded files after extraction | off |
| `--limit N` | Max dork results | 50 |
| `--delay SECS` | Request delay | 1.0 |
| `--concurrency N` | Concurrent requests | 2 |
| `--ignore-robots` | Ignore robots.txt | off |
| `--download-dir DIR` | Download directory | `./downloads/` |

## Output

### CSV (`results.csv`)

One row per file. Columns are dynamic — every unique exiftool field across all files gets its own column. `URL` and `Filename` are always first, the rest sorted alphabetically.

### JSON (`results.json`)

Full exiftool dump. Array of objects, one per file, with every field preserved exactly as returned.

### Terminal Summary

```
[+] Files processed: 12 PDF, 5 JPG, 3 DOCX
[+] Authors: Alice Smith, Bob Jones
[+] Tools/Software: Adobe PDF Library 17.0, Microsoft Word, Photoshop 25.0
[+] Files with GPS coordinates:
  photo_001.jpg: 48 deg 51' 24.00" N, 2 deg 21' 7.00" E
```

## What It Finds

| Field | Source |
|-------|--------|
| **Author / Creator** | Who created or last edited the document |
| **Producer / Software** | Tool used to create/export (Word, Photoshop, PDF libraries) |
| **Original Filename** | Sometimes embedded in metadata, differs from the URL filename |
| **Create / Modify Dates** | Document timeline |
| **GPS Coordinates** | Geotagged images |
| **Camera Model** | Make, model, lens info from photos |
| **Page Count / Dimensions** | Document and image properties |
| **Title / Subject** | Document metadata fields |
| ...and everything else | exiftool extracts 20,000+ tag types |

## File Types

**Documents:** PDF, DOC, DOCX, XLS, XLSX, PPT, PPTX, ODT, ODS, ODP, RTF

**Images:** JPG, PNG, TIFF, GIF, BMP, WebP, SVG

**Audio:** MP3, WAV, FLAC, OGG, AAC, M4A

**Video:** MP4, AVI, MOV, MKV, WMV, WebM

## License

MIT
