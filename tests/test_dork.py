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
