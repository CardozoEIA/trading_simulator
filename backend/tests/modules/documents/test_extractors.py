# tests/modules/documents/test_extractors.py
import pytest

from app.modules.documents.ingestion.extractors import (
    MAX_FILE_BYTES,
    EmptyDocumentError,
    UnsupportedFileError,
    extract,
    safe_filename,
    validate_upload,
)


def test_accepts_allowed_extensions_case_insensitive():
    assert validate_upload("Notes.PDF", 100) == "pdf"
    assert validate_upload("glossary.md", 100) == "md"


@pytest.mark.parametrize("name", ["virus.exe", "noextension", "archive.zip", ""])
def test_rejects_other_types(name):
    with pytest.raises(UnsupportedFileError):
        validate_upload(name, 100)


def test_rejects_empty_and_oversized_files():
    with pytest.raises(UnsupportedFileError):
        validate_upload("a.txt", 0)

    with pytest.raises(UnsupportedFileError):
        validate_upload("a.txt", MAX_FILE_BYTES + 1)


def test_safe_filename_drops_directories():
    assert safe_filename("../../etc/passwd.txt") == "passwd.txt"
    assert safe_filename("C:\\Users\\me\\a.pdf") == "a.pdf"


def test_txt_utf8_and_latin1():
    assert extract("txt", "Rentabilidad ñ".encode("utf-8"))[0].text == "Rentabilidad ñ"
    assert extract("txt", "Rentabilidad ñ".encode("latin-1"))[0].text == "Rentabilidad ñ"


def test_blank_text_is_rejected():
    with pytest.raises(EmptyDocumentError):
        extract("txt", b"   \n  ")


# TODO(Lucas): write the tests for your three extractors (same style as above):
#   - test_csv_rows_keep_their_column_names   -> 'date: 2024-01-02; close: 4750' is in the text
#   - test_docx_paragraphs_are_extracted      -> build a tiny .docx in memory with python-docx
#   - test_pdf_sections_carry_page_numbers    -> build a 2-page PDF with pypdf PdfWriter, or skip with a reason
