"""Remove metadata: makes a clean copy, '<name> (clean).<ext>', with the same content.

PDF: PyMuPDF. Word/Excel/PowerPoint: rewrite the document properties inside the zip.
Images: ExifTool. Audio/video: FFmpeg (streams copied as they are, so no quality loss).
"""
import re
import shutil
import zipfile
from pathlib import Path

from .tools import ConversionError, require, run

OFFICE = {"docx", "xlsx", "pptx"}
EMPTY_CORE = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
              '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
              'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
              'xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"/>')
# Comment and tracked-change authors ("w:author", "w:initials", "author") inside the document parts.
AUTHOR_ATTR = re.compile(rb'\b((?:w:|w15:)?(?:author|initials|userId)|providerId)="[^"]*"')
APP_TAGS = re.compile(rb"<(Company|Manager|Template|HyperlinkBase)>[^<]*</\1>")


def _out(src, out_dir):
    src = Path(src)
    return Path(out_dir) / f"{src.stem} (clean){src.suffix.lower()}"


def _pdf(src, out):
    import pymupdf as fitz
    from .pdf_tools import _open
    doc = _open(src)
    # Only metadata: the hidden text layer of OCR'd scans is real content, so hidden_text stays off.
    doc.scrub(metadata=True, xml_metadata=True, thumbnails=True, javascript=True, attached_files=False,
              embedded_files=False, clean_pages=False, hidden_text=False, redactions=False,
              remove_links=False, reset_fields=False, reset_responses=False)
    doc.set_metadata({})
    doc.save(out, garbage=4, deflate=True)
    if any(fitz.open(out).metadata.get(k) for k in ("author", "creator", "producer", "title", "subject", "keywords")):
        raise ConversionError("Some PDF metadata could not be removed.")


def _office(src, out):
    try:
        zin = zipfile.ZipFile(src)
    except zipfile.BadZipFile:
        raise ConversionError("This file could not be opened (it may be damaged or password-protected).")
    with zin, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        # custom properties, the list of people who edited it, the preview picture
        dropped = [n for n in zin.namelist()
                   if n == "docProps/custom.xml" or n.endswith("/people.xml") or n.startswith("docProps/thumbnail")]
        for item in zin.infolist():
            name, data = item.filename, zin.read(item)
            if name in dropped:
                continue
            if name == "docProps/core.xml":
                data = EMPTY_CORE.encode()
            elif name == "docProps/app.xml":
                data = APP_TAGS.sub(b"", data)
            elif name.endswith(".rels") or name == "[Content_Types].xml":
                # drop references to the removed parts, or Office reports the file as damaged
                data = re.sub(rb"<(?:Relationship|Override)\b[^>]*/>",
                              lambda m: b"" if any(Path(d).name.encode() in m.group(0) for d in dropped) else m.group(0),
                              data)
            elif name.endswith(".xml"):
                data = AUTHOR_ATTR.sub(lambda m: m.group(1) + b'=""', data)
            new = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))  # zip entry times are metadata too
            new.compress_type = zipfile.ZIP_DEFLATED
            zout.writestr(new, data)


def _image(src, out, opts):
    ext = Path(src).suffix.lower().lstrip(".")
    if ext in ("bmp", "ico"):
        shutil.copyfile(src, out)  # these formats have no place to store metadata
        return
    # Keep the rotation and colour profile, or photos would show sideways or with shifted colours.
    run([require("exiftool"), "-q", "-q", "-all=", "-tagsfromfile", "@", "-Orientation", "-ICC_Profile",
         "-o", out, src], opts["_timeout"])


def _media(src, out, opts):
    run([require("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-i", src, "-map", "0",
         "-map_metadata", "-1", "-map_chapters", "-1", "-c", "copy", "-fflags", "+bitexact",
         "-flags:v", "+bitexact", "-flags:a", "+bitexact", out], opts["_timeout"])


def convert(src, out_dir, fmt, opts):
    from . import AUDIO, IMAGES, VIDEO
    out = _out(src, out_dir)
    ext = Path(src).suffix.lower().lstrip(".")
    ext = {"jpeg": "jpg", "tif": "tiff", "heif": "heic"}.get(ext, ext)
    if ext == "pdf":
        _pdf(src, out)
    elif ext in OFFICE:
        _office(src, out)
    elif ext in IMAGES:
        _image(src, out, opts)
    elif ext in VIDEO + AUDIO:
        _media(src, out, opts)
    else:
        raise ConversionError(f".{ext} files aren't supported for removing metadata.")
    return [out]
