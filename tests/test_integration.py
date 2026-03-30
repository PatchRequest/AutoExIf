import csv
import json
import http.server
import threading
from pathlib import Path

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
