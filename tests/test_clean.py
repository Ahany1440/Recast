"""Remove metadata: the clean copy must not contain the name, and must keep the content."""
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import converters  # noqa: E402
from converters.tools import find, status  # noqa: E402

SECRET = "Secret Person"
TOOLS = status()


def clean(path, tmp_path):
    out_dir = tmp_path / f"out-{path.stem}"
    out_dir.mkdir()
    out = converters.run("clean", [path], out_dir, {"_timeout": 120})[0]
    assert out.name.endswith(f" (clean){path.suffix}")
    assert SECRET.encode() not in out.read_bytes()
    return out


def test_pdf(tmp_path):
    import pymupdf as fitz
    src = tmp_path / "a.pdf"
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "keep this text")
    doc.set_metadata({"author": SECRET, "creator": SECRET, "title": "t"})
    doc.save(src)
    out = clean(src, tmp_path)
    cleaned = fitz.open(out)
    assert not cleaned.metadata["author"] and "keep this text" in cleaned[0].get_text()


def test_docx(tmp_path):
    import docx
    src = tmp_path / "a.docx"
    d = docx.Document()
    d.add_paragraph("keep this text")
    d.core_properties.author = SECRET
    d.core_properties.last_modified_by = SECRET
    d.core_properties.comments = SECRET
    d.save(src)
    out = clean(src, tmp_path)
    cleaned = docx.Document(out)  # still opens
    assert cleaned.paragraphs[0].text == "keep this text"
    assert not cleaned.core_properties.author and not cleaned.core_properties.last_modified_by
    assert all(i.date_time == (1980, 1, 1, 0, 0, 0) for i in zipfile.ZipFile(out).infolist())


def test_xlsx_and_pptx(tmp_path):
    import openpyxl
    from pptx import Presentation
    x = tmp_path / "a.xlsx"
    wb = openpyxl.Workbook()
    wb.active["A1"] = "keep"
    wb.properties.creator = SECRET
    wb.save(x)
    assert openpyxl.load_workbook(clean(x, tmp_path)).active["A1"].value == "keep"
    p = tmp_path / "b.pptx"
    prs = Presentation()
    prs.slides.add_slide(prs.slide_layouts[5]).shapes.title.text = "keep"
    prs.core_properties.author = SECRET
    prs.save(p)
    assert len(Presentation(clean(p, tmp_path)).slides) == 1


@pytest.mark.skipif(not TOOLS["exiftool"]["found"], reason="needs ExifTool")
def test_jpg_keeps_rotation(tmp_path):
    from PIL import Image
    src = tmp_path / "a.jpg"
    exif = Image.Exif()
    exif[0x013B] = SECRET  # Artist
    exif[0x0110] = "Secret Phone"  # camera model
    exif[0x0112] = 6  # rotated 90 degrees: must survive, or the photo shows sideways
    Image.new("RGB", (40, 20), "red").save(src, exif=exif)
    out = clean(src, tmp_path)
    tags = json.loads(subprocess.run([find("exiftool"), "-j", "-n", str(out)], capture_output=True, text=True).stdout)[0]
    assert "Artist" not in tags and "Model" not in tags and tags.get("Orientation") == 6


@pytest.mark.skipif(not TOOLS["ffmpeg"]["found"], reason="needs FFmpeg")
def test_mp3(tmp_path):
    src = tmp_path / "a.mp3"
    subprocess.run([find("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", "sine=duration=1", "-metadata",
                    f"artist={SECRET}", "-metadata", "comment=gps here", str(src)], check=True)
    out = clean(src, tmp_path)
    assert b"gps here" not in out.read_bytes()
