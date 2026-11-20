"""Website language (English / Urdu / both / Roman Urdu) and photo sources (camera / gallery)."""
import io
import re

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse
from PIL import Image

from accounts.models import User
from checks.models import Check
from chatbot.agent_tools import Tools
from core.i18n import TR, pick, tr
from projects.models import Project


def test_tr_and_pick():
    assert tr("Diary", "en") == "Diary"
    assert tr("Diary", "ur") == "ڈائری"
    assert tr("Diary", "roman") == "Diary"
    assert tr("Diary", "both") == "Diary · ڈائری"
    assert tr("Something new", "ur") == "Something new"  # unknown strings stay English
    assert pick("Save", "Save karein", "محفوظ کریں", "both") == "Save · محفوظ کریں"
    assert all(len(v) == 2 for v in TR.values())


@pytest.fixture
def setup(db, client):
    call_command("seed_v1", verbosity=0)
    user = User.objects.create_user("03001230000", "lang-pass-1")
    project = Project.objects.create(owner=user)
    Tools(project).setup_project({"city": "Karachi", "rooms": [{"type": "bedroom"}, {"type": "washroom"}]})
    client.force_login(user)
    return user, project


PAGES = ["/p/", "/p/{id}/", "/p/{id}/chat/", "/p/{id}/plan/", "/p/{id}/plan/print/", "/p/{id}/materials/",
         "/p/{id}/checks/", "/p/{id}/checks/stage/foundation/", "/p/{id}/checks/item/FND-C2/", "/p/{id}/checks/item/LAY-C1/",
         "/p/{id}/diary/", "/p/{id}/diary/report/", "/p/{id}/rules/"]


@pytest.mark.parametrize("lang", ["en", "ur", "both", "roman"])
def test_every_page_renders_in_every_language(setup, client, lang):
    user, project = setup
    client.post(reverse("set_ui_language"), {"ui_language": lang, "next": "/p/"})
    user.refresh_from_db()
    assert user.ui_language == lang
    for url in PAGES:
        r = client.get(url.format(id=project.pk))
        assert r.status_code == 200, url
        html = r.content.decode()
        assert f'class="ui-{lang}"' in html
        nav = re.search(r'<nav class="bottom-nav.*?</nav>', html, re.S)
        if nav and lang == "ur":
            assert "ڈائری" in nav.group(0) and "Diary" not in nav.group(0)
        if nav and lang == "en":
            assert "Diary" in nav.group(0) and "ڈائری" not in nav.group(0)
        if nav and lang == "both":
            assert "Diary · ڈائری" in nav.group(0)
    assert 'dir="rtl"' in client.get("/p/").content.decode() if lang == "ur" else True


def test_language_before_login_is_kept_on_signup(client, db):
    client.post(reverse("set_ui_language"), {"ui_language": "ur", "next": "/"})
    assert 'class="ui-ur"' in client.get("/").content.decode()
    client.post(reverse("signup"), {"phone": "03009990000", "name": "A", "language": "ur", "password": "pakka-pass-9"})
    assert User.objects.get(phone="03009990000").ui_language == "ur"


def test_bad_next_url_is_not_followed(client, db):
    r = client.post(reverse("set_ui_language"), {"ui_language": "en", "next": "https://evil.example.com/"})
    assert r.url == "/"


def _jpeg(exif_date=None):
    buf = io.BytesIO()
    img = Image.new("RGB", (40, 30), "gray")
    if exif_date:
        exif = Image.Exif()
        exif[306] = exif_date  # DateTime
        img.save(buf, "JPEG", exif=exif)
    else:
        img.save(buf, "JPEG")
    return SimpleUploadedFile("p.jpg", buf.getvalue(), content_type="image/jpeg")


def test_gallery_photo_is_marked_and_old_date_warned(setup, client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    user, project = setup
    url = reverse("check_submit", args=[project.pk, "FND-C2"])
    client.post(url, {"photo": _jpeg("2025:01:05 10:00:00"), "source": "gallery"})
    c = Check.objects.filter(project=project).first()
    assert c.photo_source == "gallery" and c.photo_taken_at.year == 2025
    assert c.gallery_old_days > 300
    html = client.get(reverse("check_result", args=[project.pk, c.pk])).content.decode()
    assert "From gallery (not verified)" in html and "it may be an old photo" in html


def test_live_camera_photo_source(setup, client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    user, project = setup
    client.post(reverse("check_submit", args=[project.pk, "FND-C2"]), {"photo": _jpeg(), "source": "camera"})
    c = Check.objects.filter(project=project).first()
    assert c.photo_source == "camera" and c.gallery_old_days is None


def test_check_page_offers_camera_and_gallery(setup, client):
    user, project = setup
    html = client.get(reverse("check_item", args=[project.pk, "FND-C2"])).content.decode()
    assert 'id="cam-btn"' in html and 'id="gal-btn"' in html and "camera.js" in html
