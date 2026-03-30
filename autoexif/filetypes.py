"""File type extension sets and MIME type mappings for document/media detection."""

from pathlib import PurePosixPath
from urllib.parse import urlparse

DOCUMENT_EXTENSIONS = frozenset({
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".odt", ".ods", ".odp", ".rtf",
})

IMAGE_EXTENSIONS = frozenset({
    ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".gif", ".bmp", ".webp", ".svg",
})

AUDIO_EXTENSIONS = frozenset({
    ".mp3", ".wav", ".flac", ".ogg", ".aac", ".m4a",
})

VIDEO_EXTENSIONS = frozenset({
    ".mp4", ".avi", ".mov", ".mkv", ".wmv", ".webm",
})

ALL_EXTENSIONS = DOCUMENT_EXTENSIONS | IMAGE_EXTENSIONS | AUDIO_EXTENSIONS | VIDEO_EXTENSIONS

_EXT_TO_CATEGORY: dict[str, str] = {}
for _ext in DOCUMENT_EXTENSIONS:
    _EXT_TO_CATEGORY[_ext] = "document"
for _ext in IMAGE_EXTENSIONS:
    _EXT_TO_CATEGORY[_ext] = "image"
for _ext in AUDIO_EXTENSIONS:
    _EXT_TO_CATEGORY[_ext] = "audio"
for _ext in VIDEO_EXTENSIONS:
    _EXT_TO_CATEGORY[_ext] = "video"

MIME_TO_CATEGORY: dict[str, str] = {
    # Documents
    "application/pdf": "document",
    "application/msword": "document",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "document",
    "application/vnd.ms-excel": "document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "document",
    "application/vnd.ms-powerpoint": "document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "document",
    "application/vnd.oasis.opendocument.text": "document",
    "application/vnd.oasis.opendocument.spreadsheet": "document",
    "application/vnd.oasis.opendocument.presentation": "document",
    "application/rtf": "document",
    # Images
    "image/jpeg": "image",
    "image/png": "image",
    "image/tiff": "image",
    "image/gif": "image",
    "image/bmp": "image",
    "image/webp": "image",
    "image/svg+xml": "image",
    # Audio
    "audio/mpeg": "audio",
    "audio/wav": "audio",
    "audio/flac": "audio",
    "audio/ogg": "audio",
    "audio/aac": "audio",
    "audio/mp4": "audio",
    # Video
    "video/mp4": "video",
    "video/x-msvideo": "video",
    "video/quicktime": "video",
    "video/x-matroska": "video",
    "video/x-ms-wmv": "video",
    "video/webm": "video",
}


def is_document_url(url: str) -> bool:
    """Check if a URL points to a known document/media file by extension."""
    try:
        path = urlparse(url).path
    except ValueError:
        return False
    ext = PurePosixPath(path).suffix.lower()
    return ext in ALL_EXTENSIONS


def get_file_category(filename: str) -> str | None:
    """Return the category ('document', 'image', 'audio', 'video') for a filename, or None."""
    ext = PurePosixPath(filename).suffix.lower()
    return _EXT_TO_CATEGORY.get(ext)
