from autoexif.filetypes import (
    DOCUMENT_EXTENSIONS,
    IMAGE_EXTENSIONS,
    AUDIO_EXTENSIONS,
    VIDEO_EXTENSIONS,
    ALL_EXTENSIONS,
    MIME_TO_CATEGORY,
    is_document_url,
    get_file_category,
)


class TestExtensionSets:
    def test_document_extensions_include_pdf(self):
        assert ".pdf" in DOCUMENT_EXTENSIONS

    def test_document_extensions_include_docx(self):
        assert ".docx" in DOCUMENT_EXTENSIONS

    def test_image_extensions_include_jpg(self):
        assert ".jpg" in IMAGE_EXTENSIONS
        assert ".jpeg" in IMAGE_EXTENSIONS

    def test_audio_extensions_include_mp3(self):
        assert ".mp3" in AUDIO_EXTENSIONS

    def test_video_extensions_include_mp4(self):
        assert ".mp4" in VIDEO_EXTENSIONS

    def test_all_extensions_is_union(self):
        assert ALL_EXTENSIONS == (
            DOCUMENT_EXTENSIONS | IMAGE_EXTENSIONS | AUDIO_EXTENSIONS | VIDEO_EXTENSIONS
        )


class TestIsDocumentUrl:
    def test_pdf_url(self):
        assert is_document_url("https://example.com/report.pdf") is True

    def test_docx_url(self):
        assert is_document_url("https://cdn.example.com/file.docx") is True

    def test_jpg_url(self):
        assert is_document_url("https://images.example.com/photo.jpg") is True

    def test_mp4_url(self):
        assert is_document_url("https://media.example.com/video.mp4") is True

    def test_html_url(self):
        assert is_document_url("https://example.com/page.html") is False

    def test_no_extension(self):
        assert is_document_url("https://example.com/page") is False

    def test_url_with_query_params(self):
        assert is_document_url("https://example.com/report.pdf?v=2&token=abc") is True

    def test_url_with_fragment(self):
        assert is_document_url("https://example.com/report.pdf#page=3") is True

    def test_case_insensitive(self):
        assert is_document_url("https://example.com/REPORT.PDF") is True
        assert is_document_url("https://example.com/Photo.JPG") is True


class TestGetFileCategory:
    def test_pdf_is_document(self):
        assert get_file_category("report.pdf") == "document"

    def test_jpg_is_image(self):
        assert get_file_category("photo.jpg") == "image"

    def test_mp3_is_audio(self):
        assert get_file_category("song.mp3") == "audio"

    def test_mp4_is_video(self):
        assert get_file_category("clip.mp4") == "video"

    def test_html_is_none(self):
        assert get_file_category("page.html") is None

    def test_no_extension_is_none(self):
        assert get_file_category("README") is None


class TestMimeMapping:
    def test_pdf_mime(self):
        assert MIME_TO_CATEGORY["application/pdf"] == "document"

    def test_jpeg_mime(self):
        assert MIME_TO_CATEGORY["image/jpeg"] == "image"

    def test_mp3_mime(self):
        assert MIME_TO_CATEGORY["audio/mpeg"] == "audio"

    def test_mp4_mime(self):
        assert MIME_TO_CATEGORY["video/mp4"] == "video"

    def test_docx_mime(self):
        assert MIME_TO_CATEGORY[
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ] == "document"
