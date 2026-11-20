"""Server-side photo cleanup: the phone already shrinks photos, this is a safety net."""
import io
import uuid

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_SIDE = 1600


class BadPhoto(ValueError):
    pass


def taken_at(upload):
    """The date stored inside a photo (EXIF DateTimeOriginal), as an aware datetime, or None."""
    import datetime as dt

    from django.utils import timezone

    try:
        upload.seek(0)
        exif = Image.open(upload).getexif()
        raw = exif.get_ifd(0x8769).get(36867) or exif.get(306)  # DateTimeOriginal, else DateTime
        upload.seek(0)
        if not raw:
            return None
        return timezone.make_aware(dt.datetime.strptime(str(raw).strip()[:19], "%Y:%m:%d %H:%M:%S"))
    except Exception:
        try:
            upload.seek(0)
        except Exception:
            pass
        return None


def normalise(upload) -> ContentFile:
    """Return a JPEG no larger than MAX_SIDE px, with EXIF rotation applied and metadata stripped."""
    try:
        img = Image.open(upload)
        img = ImageOps.exif_transpose(img)
    except (UnidentifiedImageError, OSError) as e:
        raise BadPhoto("That file is not a photo.") from e
    img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=82, optimize=True)
    return ContentFile(buf.getvalue(), name=f"{uuid.uuid4().hex}.jpg")
