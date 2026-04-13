"""Scrapy spider that crawls websites to discover document/media URLs."""

import json
import logging
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import scrapy
from OpenSSL import SSL
from scrapy.core.downloader.contextfactory import ScrapyClientContextFactory
from scrapy.crawler import CrawlerProcess
from twisted.internet._sslverify import ClientTLSOptions

from autoexif.filetypes import MIME_TO_CATEGORY, is_document_url

_NOISY_LOGGERS = (
    "scrapy.core.downloader.tls",
    "scrapy.downloadermiddlewares.retry",
    "scrapy.downloadermiddlewares.robotstxt",
    "scrapy.core.scraper",
    "scrapy.core.engine",
    "scrapy.spidermiddlewares.httperror",
    "py.warnings",
)


def _silence_scrapy_loggers():
    """Mute noisy Scrapy loggers — must be called after CrawlerProcess init."""
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.CRITICAL)


class _NoVerifyTLSOptions(ClientTLSOptions):
    """ClientTLSOptions that skips hostname verification entirely."""

    def _identityVerifyingInfoCallback(self, connection, where, ret):
        # Only set SNI, skip all verification
        if where & SSL.SSL_CB_HANDSHAKE_START:
            connection.set_tlsext_host_name(self._hostnameBytes)


class NoVerifyContextFactory(ScrapyClientContextFactory):
    """TLS context factory that skips all certificate and hostname verification."""

    def creatorForNetloc(self, hostname, port):
        return _NoVerifyTLSOptions(
            hostname.decode("ascii"),
            self.getContext(),
        )


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

    def __init__(self, start_urls, allowed_domains, found_urls, failed_hosts, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_urls = start_urls
        self._allowed_domains = allowed_domains
        self.found_urls = found_urls
        self.failed_hosts = failed_hosts

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse, errback=self.on_error)

    def on_error(self, failure):
        url = failure.request.url
        host = urlparse(url).hostname or url
        if host not in self.failed_hosts:
            self.failed_hosts.add(host)
            print(f"    [!] Skipping {host} (unreachable)")

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
                yield response.follow(url, callback=self.parse, errback=self.on_error)


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
    failed_hosts: set[str] = set()
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
        "DOWNLOADER_CLIENTCONTEXTFACTORY": "autoexif.spider.NoVerifyContextFactory",
        "LOG_LEVEL": "ERROR",
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
    _silence_scrapy_loggers()
    process.crawl(
        DocumentSpider,
        start_urls=start_urls,
        allowed_domains=allowed_domains,
        found_urls=found_urls,
        failed_hosts=failed_hosts,
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
