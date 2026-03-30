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
