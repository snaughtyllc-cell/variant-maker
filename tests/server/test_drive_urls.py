import pytest
from variant_maker.server.drive_urls import DriveUrlError, parse_folder_id


def test_parse_standard_folder_link():
    assert parse_folder_id(
        "https://drive.google.com/drive/folders/1AbCdefghijk0123456789"
    ) == "1AbCdefghijk0123456789"


def test_parse_u0_folder_link_with_query():
    assert parse_folder_id(
        "https://drive.google.com/drive/u/0/folders/1AbCdefghijk0123456789?usp=sharing"
    ) == "1AbCdefghijk0123456789"


def test_parse_bare_folder_id():
    assert parse_folder_id("1AbCdefghijk0123456789") == "1AbCdefghijk0123456789"


def test_reject_file_link():
    with pytest.raises(DriveUrlError, match="folder"):
        parse_folder_id("https://drive.google.com/file/d/1AbCdefghijk0123456789/view")


def test_reject_garbage():
    with pytest.raises(DriveUrlError):
        parse_folder_id("not a link")
