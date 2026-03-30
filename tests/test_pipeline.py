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
