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
