"""Scrapy spider that crawls websites to discover document/media URLs."""

import json
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import scrapy
from scrapy.crawler import CrawlerProcess

from autoexif.filetypes import MIME_TO_CATEGORY, is_document_url


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
        content_type = response.headers.get("Content-Type", b"").decode("utf-8", errors="ignore")
        mime = content_type.split(";")[0].strip().lower()

        # Non-text response — treat as a discovered document
        if not mime.startswith("text/") and mime != "application/xhtml+xml":
            url = response.url
            if url not in self.found_urls:
                self.found_urls.add(url)
                yield {"url": url}
            return

        # Text/HTML response — extract links
        for href in response.css("a::attr(href)").getall():
            url = response.urljoin(href)

            if is_document_url(url):
                # Document link — collect it (any origin allowed)
                if url not in self.found_urls:
                    self.found_urls.add(url)
                    yield {"url": url}
            elif is_same_domain(url, self._allowed_domains):
                # Same-domain HTML page — follow it
                # Scrapy's DUPEFILTER handles already-visited URLs
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
    content = Path(tmp_path).read_text()
    for line in content.strip().splitlines():
        if line.strip():
            data = json.loads(line)
            collected.append(data["url"])

    Path(tmp_path).unlink(missing_ok=True)

    print(f"[+] Spider found {len(collected)} document URLs")
    return collected
