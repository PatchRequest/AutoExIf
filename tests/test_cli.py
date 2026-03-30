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
