"""Smaller file: saves '<name> (compressed).<ext>', same format, smaller size.

opts["strength"]: "Light" (default, hard to tell apart) or "Strong" (smaller, visibly lower quality).
PDF: PyMuPDF shrinks the images inside. Images: Pillow. Word/Excel/PowerPoint: shrink the pictures
inside the zip. Audio/video: FFmpeg re-encodes. If the result isn't smaller, no copy is kept.
"""
import io
import zipfile
from pathlib import Path

from .tools import ConversionError, require, run

OFFICE = {"docx", "xlsx", "pptx"}
IMAGES = ["png", "jpg", "webp", "tiff", "heic"]  # BMP/GIF/ICO have nothing worth squeezing
AUDIO = ["mp3", "m4a", "ogg", "flac"]  # WAV is raw by definition: make it an MP3 instead
# (light, strong) settings
JPEG_QUALITY = (80, 60)
MAX_SIDE = (2560, 1600)  # longest side of a photo, in pixels
PDF_DPI = (150, 96)  # target resolution of the pictures in a PDF
VIDEO_CRF = (28, 32)  # H.264: higher = smaller; 23 is FFmpeg's default
VIDEO_HEIGHT = (None, 720)
AUDIO_ARGS = {
    "mp3": (["-c:a", "libmp3lame", "-q:a", "5"], ["-c:a", "libmp3lame", "-q:a", "7"]),
    "m4a": (["-c:a", "aac", "-b:a", "128k"], ["-c:a", "aac", "-b:a", "80k"]),
    "ogg": (["-c:a", "libvorbis", "-q:a", "3"], ["-c:a", "libvorbis", "-q:a", "1"]),
    "flac": (["-c:a", "flac", "-compression_level", "12"], ["-c:a", "flac", "-compression_level", "12"]),
}


def _pdf(src, out, strong):
    from .pdf_tools import _open
    doc = _open(src)
    dpi = PDF_DPI[strong]
    doc.rewrite_images(dpi_threshold=dpi + 10, dpi_target=dpi, quality=JPEG_QUALITY[strong], lossy=True,
                       lossless=True, bitonal=True, color=True, gray=True)
    doc.save(out, garbage=4, deflate=True, deflate_images=True, deflate_fonts=True, use_objstms=1)


def _shrink_image(im, fmt, strong):
    """Pillow image -> bytes in the same format, smaller."""
    from PIL import Image
    im.thumbnail((MAX_SIDE[strong],) * 2, Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    if fmt in ("jpg", "webp", "heic"):
        if fmt == "jpg" and im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        im.save(buf, {"jpg": "JPEG", "webp": "WEBP", "heic": "HEIF"}[fmt], quality=JPEG_QUALITY[strong],
                **({"optimize": True, "progressive": True} if fmt == "jpg" else {}))
    elif fmt == "png":
        if strong and im.mode in ("RGB", "RGBA"):
            im = im.quantize(256, method=Image.Quantize.FASTOCTREE)  # 256 colours: fine for screenshots, rough on photos
        im.save(buf, "PNG", optimize=True)
    else:  # tiff
        im.save(buf, "TIFF", compression="tiff_adobe_deflate")
    return buf.getvalue()


def _image(src, out, fmt, strong):
    from PIL import Image, ImageOps, UnidentifiedImageError
    from . import images  # noqa: F401  registers the HEIC opener
    try:
        im = ImageOps.exif_transpose(Image.open(src))  # bake in the rotation: EXIF isn't carried over
    except (UnidentifiedImageError, OSError):
        raise ConversionError("This image could not be opened (it may be damaged or not really an image).")
    Path(out).write_bytes(_shrink_image(im, fmt, strong))


def _office(src, out, strong):
    from PIL import Image, UnidentifiedImageError
    try:
        zin = zipfile.ZipFile(src)
    except zipfile.BadZipFile:
        raise ConversionError("This file could not be opened (it may be damaged or password-protected).")
    with zin, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zout:
        for item in zin.infolist():
            data = zin.read(item)
            fmt = Path(item.filename).suffix.lower().lstrip(".").replace("jpeg", "jpg")
            if "/media/" in item.filename and fmt in ("jpg", "png") and len(data) > 100_000:
                try:
                    smaller = _shrink_image(Image.open(io.BytesIO(data)), fmt, strong)
                    data = smaller if len(smaller) < len(data) else data
                except (UnidentifiedImageError, OSError):
                    pass  # keep a picture Pillow can't read as it is
            zout.writestr(item, data, zipfile.ZIP_DEFLATED, 9)


def _media(src, out, ext, strong, opts):
    from . import VIDEO
    args = [require("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-i", src, "-map", "0:v:0?", "-map", "0:a?"]
    if ext in VIDEO:
        if ext == "webm":
            args += ["-c:v", "libvpx-vp9", "-crf", str(VIDEO_CRF[strong] + 8), "-b:v", "0",
                     "-deadline", "good", "-cpu-used", "4", "-c:a", "libopus", "-b:a", "96k"]
        else:
            args += ["-c:v", "libx264", "-preset", "medium", "-crf", str(VIDEO_CRF[strong]), "-pix_fmt", "yuv420p",
                     "-c:a", "aac", "-b:a", "128k" if not strong else "96k"]
            if ext in ("mp4", "mov"):
                args += ["-movflags", "+faststart"]
        if VIDEO_HEIGHT[strong]:
            args += ["-vf", f"scale=-2:'min({VIDEO_HEIGHT[strong]},ih)'"]
    else:
        args += ["-vn", *AUDIO_ARGS[ext][strong]]
    run(args + [out], opts["_timeout"])


def convert(src, out_dir, fmt, opts):
    from . import VIDEO
    src = Path(src)
    out = Path(out_dir) / f"{src.stem} (compressed){src.suffix.lower()}"
    ext = src.suffix.lower().lstrip(".")
    ext = {"jpeg": "jpg", "tif": "tiff", "heif": "heic"}.get(ext, ext)
    strong = opts.get("strength") == "Strong"
    if ext == "pdf":
        _pdf(src, out, strong)
    elif ext in OFFICE:
        _office(src, out, strong)
    elif ext in IMAGES:
        _image(src, out, ext, strong)
    elif ext in VIDEO + AUDIO:
        _media(src, out, ext, strong, opts)
    else:
        raise ConversionError(f".{ext} files can't be made smaller.")
    if out.stat().st_size >= src.stat().st_size * 0.97:
        out.unlink()
        raise ConversionError("This file is already about as small as it gets, so no copy was made."
                              + ("" if strong else " Try Strong."))
    return [out]
