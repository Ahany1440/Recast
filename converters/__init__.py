"""The one conversion map: input extension -> output id -> (label, programs needed, engine).

Engines are named as "module.function" and imported only when used, so the app starts fast
and each conversion can run in its own process (see app.py).
"""
import importlib
from collections import namedtuple
from pathlib import Path

Conv = namedtuple("Conv", "label needs engine fmt")

ALIASES = {"jpeg": "jpg", "tif": "tiff", "htm": "html", "markdown": "md", "heif": "heic"}

WORD = ["docx", "doc", "odt", "rtf"]
SLIDES = ["pptx", "ppt", "odp"]
SHEETS = ["xlsx", "xls", "ods", "csv"]
IMAGES = ["png", "jpg", "webp", "bmp", "gif", "tiff", "heic", "ico"]
VIDEO = ["mp4", "mov", "avi", "mkv", "webm"]
AUDIO = ["mp3", "wav", "m4a", "ogg", "flac"]

LO = ("soffice",)
MAP = {}


def add(exts, out, label, engine, needs=(), fmt=None):
    for ext in exts:
        if ext != out:  # converting to the same type is pointless
            MAP.setdefault(ext, {})[out] = Conv(label, tuple(needs), engine, fmt or out.split("-")[0])


# PDF
add(["pdf"], "docx", "Word (.docx)", "pdf_tools.to_docx")
add(["pdf"], "txt", "Text (.txt)", "pdf_tools.to_text")
add(["pdf"], "html", "Web page (.html)", "pdf_tools.to_html")
add(["pdf"], "png", "PNG image per page", "pdf_tools.to_images")
add(["pdf"], "jpg", "JPG image per page", "pdf_tools.to_images")
add(["pdf"], "pptx", "PowerPoint (.pptx), page images", "pdf_tools.to_pptx")
add(["pdf"], "pdf-split", "Split into one PDF per page", "pdf_tools.split")
# Word-type documents
for out, label in [("pdf", "PDF"), ("html", "Web page (.html)"), ("odt", "OpenDocument (.odt)"), ("docx", "Word (.docx)")]:
    add(WORD, out, label, "libreoffice.convert", LO)
# Pandoc for text: LibreOffice's .docx -> .txt export hangs. DOC/RTF go through LibreOffice -> .docx first.
for out, label in [("txt", "Text (.txt)"), ("md", "Markdown (.md)")]:
    add(["docx", "odt"], out, label, "pandoc_tools.convert", ["pandoc"])
    add(["doc", "rtf"], out, label, "pandoc_tools.convert", ["pandoc", "soffice"])
# Word-type documents and text -> slides or images, by way of a PDF
for exts in (WORD, ["txt"]):
    add(exts, "pptx", "PowerPoint (.pptx), page images", "libreoffice.to_pdf_then:pdf_tools.to_pptx", LO)
    add(exts, "png", "PNG image per page", "libreoffice.to_pdf_then:pdf_tools.to_images", LO)
    add(exts, "jpg", "JPG image per page", "libreoffice.to_pdf_then:pdf_tools.to_images", LO)
# Presentations
add(SLIDES, "pdf", "PDF", "libreoffice.convert", LO)
add(SLIDES, "png", "PNG image per slide", "libreoffice.to_pdf_then:pdf_tools.to_images", LO)
add(SLIDES, "jpg", "JPG image per slide", "libreoffice.to_pdf_then:pdf_tools.to_images", LO)
# Spreadsheets
add(SHEETS, "pdf", "PDF", "libreoffice.convert", LO)
for out, label in [("csv", "CSV"), ("xlsx", "Excel (.xlsx)"), ("html", "Web page (.html)"), ("json", "JSON")]:
    add(SHEETS, out, label, "sheets.convert")
# Markdown / HTML / text
add(["md", "html"], "pdf", "PDF", "pandoc_tools.convert", ["pandoc", "soffice"])
add(["md", "html"], "docx", "Word (.docx)", "pandoc_tools.convert", ["pandoc"])
add(["md"], "html", "Web page (.html)", "pandoc_tools.convert", ["pandoc"])
add(["html"], "md", "Markdown (.md)", "pandoc_tools.convert", ["pandoc"])
for out, label in [("pdf", "PDF"), ("docx", "Word (.docx)"), ("html", "Web page (.html)")]:
    add(["txt"], out, label, "libreoffice.convert", LO)
# Images
for out in IMAGES:
    add(IMAGES, out, f"{out.upper()} image", "images.convert")
add(IMAGES, "pdf", "PDF", "images.convert")
# Video and audio
for out, label in [("mp4", "MP4 video"), ("webm", "WebM video"), ("gif", "Animated GIF"), ("mp3", "MP3 audio only")]:
    add(VIDEO, out, label, "media.convert", ["ffmpeg"])
for out in AUDIO:
    add(AUDIO, out, f"{out.upper()} audio", "media.convert", ["ffmpeg"])
# OCR
add(["pdf"] + IMAGES, "ocr-pdf", "Searchable PDF (OCR)", "ocr.convert", ["tesseract"], "pdf")
add(["pdf"] + IMAGES, "ocr-txt", "Text from scan (OCR)", "ocr.convert", ["tesseract"], "txt")
# Remove metadata: a clean copy in the same format
add(["pdf", "docx", "xlsx", "pptx"], "clean", "Remove metadata", "clean.convert")
add(IMAGES, "clean", "Remove metadata", "clean.convert", ["exiftool"])
add(VIDEO + AUDIO, "clean", "Remove metadata", "clean.convert", ["ffmpeg"])

# Actions that take several files and make one.
MULTI = {
    "merge-pdf": Conv("Merge into one PDF", (), "pdf_tools.merge", "pdf"),
    "images-pdf": Conv("Combine images into one PDF", (), "images.combine", "pdf"),
}
MULTI_ACCEPTS = {"merge-pdf": {"pdf"}, "images-pdf": set(IMAGES)}


def ext_of(name):
    ext = Path(name).suffix.lower().lstrip(".")
    return ALIASES.get(ext, ext)


def _func(name):
    module, func = name.split(".")
    return getattr(importlib.import_module(f"{__name__}.{module}"), func)


def run(target, srcs, out_dir, opts):
    """Run one conversion. Returns the list of output files."""
    if target in MULTI:
        return _func(MULTI[target].engine)(srcs, out_dir, opts)
    conv = MAP[ext_of(srcs[0])][target]
    first, _, then = conv.engine.partition(":")
    if then:  # two-step chain, e.g. slides -> PDF -> images
        return _func(first)(srcs[0], out_dir, conv.fmt, opts, _func(then))
    return _func(first)(srcs[0], out_dir, conv.fmt, opts)
