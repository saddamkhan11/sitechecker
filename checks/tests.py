import io
from unittest import mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import override_settings
from PIL import Image

from accounts.models import User
from checks import measure
from checks.models import Check
from checks.tasks import run_photo_check
from core import ai_service
from projects.models import ChecklistItem, Project


def test_diff_compare():
    assert measure.compare("diff", [200, 200.25], 0.5)["status"] == "green"
    assert measure.compare("diff", [200, 200.75], 0.5)["status"] == "yellow"
    assert measure.compare("diff", [200, 202], 0.5)["status"] == "red"


def test_min_max_plan_compare():
    assert measure.compare("min", [36, 38], 36)["status"] == "green"
    assert measure.compare("min", [35], 36)["status"] == "yellow"
    assert measure.compare("min", [30], 36)["status"] == "red"
    assert measure.compare("max", [6], 6)["status"] == "green"
    assert measure.compare("max", [8], 6)["status"] == "red"
    assert measure.compare("plan", [168.5, 144], 1, plan_values=[168, 144])["status"] == "green"
    with pytest.raises(ValueError):
        measure.compare("diff", [1], 0.5)


def test_tilt():
    assert measure.tilt([0.2, -0.4], 0.5)["status"] == "green"
    assert measure.tilt([0.8], 0.5)["status"] == "yellow"
    assert measure.tilt([2], 0.5)["status"] == "red"


def jpeg():
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), "gray").save(buf, "JPEG")
    return SimpleUploadedFile("p.jpg", buf.getvalue(), content_type="image/jpeg")


@pytest.fixture
def setup(db, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    call_command("seed_v1", verbosity=0)
    user = User.objects.create_user("03009998888", "test-pass-123")
    project = Project.objects.create(owner=user, city="Karachi", room_length_ft=14, room_width_ft=12, onboarding_step=8)
    project.ensure_stages()
    item = ChecklistItem.objects.get(code="SST-C1")
    check = Check.objects.create(project=project, item=item, photo=jpeg())
    return check


def fake_result(**kw):
    base = dict(status="green", reason="Bars look evenly spaced at about 6 in.", confidence=0.9, tell_mistri="", photo_usable=True)
    base.update(kw)
    return ai_service.PhotoCheckResult(**base)


@override_settings(OPENAI_API_KEY="test-key")
def test_photo_check_green(setup):
    with mock.patch.object(ai_service, "check_photo", return_value=fake_result()) as m:
        run_photo_check(setup.pk)
    setup.refresh_from_db()
    assert setup.status == "green" and not setup.retake
    assert "SST-01" in m.call_args.kwargs["rule_line"]


@override_settings(OPENAI_API_KEY="test-key", PHOTO_MIN_CONFIDENCE=0.6)
def test_low_confidence_becomes_yellow_and_asks_new_photo(setup):
    with mock.patch.object(ai_service, "check_photo", return_value=fake_result(status="green", confidence=0.4)):
        run_photo_check(setup.pk)
    setup.refresh_from_db()
    assert setup.status == "yellow" and setup.retake


@override_settings(OPENAI_API_KEY="test-key")
def test_unusable_photo_never_red_or_green(setup):
    with mock.patch.object(ai_service, "check_photo", return_value=fake_result(status="red", photo_usable=False)):
        run_photo_check(setup.pk)
    setup.refresh_from_db()
    assert setup.status == "yellow"


@override_settings(OPENAI_API_KEY="test-key")
def test_ai_failure_is_reported_not_green(setup):
    with mock.patch.object(ai_service, "check_photo", side_effect=ai_service.AIUnavailable("down")):
        run_photo_check(setup.pk)
    setup.refresh_from_db()
    assert setup.status == "error"


@override_settings(OPENAI_API_KEY="")
def test_no_api_key_marks_yellow(setup):
    run_photo_check(setup.pk)
    setup.refresh_from_db()
    assert setup.status == "yellow"
