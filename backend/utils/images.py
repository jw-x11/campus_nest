from io import BytesIO

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError

THUMBNAIL_LONG_EDGE = 400

_FORMAT_BY_TYPE = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
    "image/gif": "GIF",
}


def resize_long_edge(
    body: bytes, content_type: str, long_edge: int = THUMBNAIL_LONG_EDGE
) -> tuple[bytes, str]:
    """Shrink an image so its longer side is at most long_edge pixels. Smaller images stay as they are."""
    try:
        with Image.open(BytesIO(body)) as opened:
            opened.load()
            transposed = ImageOps.exif_transpose(opened) or opened
            image = transposed.copy()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(status_code=400, detail="INVALID_IMAGE")

    if content_type == "image/jpeg" or image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGB")

    image.thumbnail((long_edge, long_edge), Image.Resampling.LANCZOS)

    output = BytesIO()
    image_format = _FORMAT_BY_TYPE.get(content_type, "JPEG")
    if image_format == "JPEG":
        image.save(output, format=image_format, quality=85, optimize=True)
    elif image_format == "WEBP":
        image.save(output, format=image_format, quality=80, method=4)
    elif image_format == "PNG":
        image.save(output, format=image_format, optimize=True)
    else:
        image.convert("P", palette=Image.Palette.ADAPTIVE).save(output, format="GIF")
    return output.getvalue(), content_type
