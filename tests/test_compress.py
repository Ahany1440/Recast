"""Smaller file: the copy must be smaller, in the same format, and still open."""
import io
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import converters  # noqa: E402
from converters.tools import ConversionError, find, status  # noqa: E402

TOOLS = status()


def photo(w=3000, h=2000):
    """A noisy picture: compresses like a real photo, unlike a flat colour."""
    from PIL import Image
    return Image.effect_noise((w, h), 60).convert("RGB")


def compress(path, tmp_path, strength="Light"):
    out_dir = tmp_path / f"out-{path.stem}-{strength}"
    out_dir.mkdir()
    out = converters.run("compress", [path], out_dir, {"_timeout": 300, "strength": strength})[0]
    assert out.name == f"{path.stem} (compressed){path.suffix}"
    assert out.stat().st_size < path.stat().st_size
    return out


def test_jpg_light_and_strong(tmp_path):
    from PIL import Image
    src = tmp_path / "a.jpg"
    photo().save(src, quality=98)
    light, strong = compress(src, tmp_path), compress(src, tmp_path, "Strong")
    assert strong.stat().st_size < light.stat().st_size
    assert max(Image.open(strong).size) == 1600


def test_pdf_with_big_picture(tmp_path):
    import pymupdf as fitz
    buf = io.BytesIO()
    photo().save(buf, "PNG")
    src = tmp_path / "a.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "keep this text")
    page.insert_image(fitz.Rect(72, 100, 500, 400), stream=buf.getvalue())
    doc.save(src)
    out = compress(src, tmp_path)
    assert "keep this text" in fitz.open(out)[0].get_text()


def test_docx_with_big_picture(tmp_path):
    import docx
    pic = tmp_path / "pic.jpg"
    photo().save(pic, quality=98)
    src = tmp_path / "a.docx"
    d = docx.Document()
    d.add_paragraph("keep this text")
    d.add_picture(str(pic))
    d.save(src)
    out = compress(src, tmp_path)
    assert docx.Document(out).paragraphs[0].text == "keep this text"


def test_already_small_makes_no_copy(tmp_path):
    from PIL import Image
    src = tmp_path / "tiny.png"
    Image.new("RGB", (10, 10), "red").save(src, optimize=True)
    with pytest.raises(ConversionError, match="already"):
        converters.run("compress", [src], tmp_path, {"_timeout": 60})
    assert not list(tmp_path.glob("*(compressed)*"))


@pytest.mark.skipif(not TOOLS["ffmpeg"]["found"], reason="needs FFmpeg")
def test_mp3(tmp_path):
    src = tmp_path / "a.mp3"
    subprocess.run([find("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", "anoisesrc=d=5", "-b:a", "320k", str(src)],
                   check=True)
    compress(src, tmp_path)
