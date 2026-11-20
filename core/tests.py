import json
from types import SimpleNamespace
from unittest import mock

import pytest
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from pydantic import ValidationError

from accounts.models import User
from core import ai_service


# ---------- ai_service ----------
def test_detect_language():
    assert ai_service.detect_language("بنیاد کتنی گہری ہو؟") == "ur"
    assert ai_service.detect_language("Bunyad kitni gehri honi chahiye?") == "roman"
    assert ai_service.detect_language("How deep should the trench be?") == "en"


def test_guard_adds_note_on_safe_words():
    out = ai_service.guard_reply("Your wall is safe.", "en")
    assert "SCOPE-08" in out
    assert ai_service.guard_reply("Trench 36 in [FND-01]", "en") == "Trench 36 in [FND-01]"


def test_photo_result_schema_rejects_bad_reply():
    with pytest.raises(ValidationError):
        ai_service.PhotoCheckResult.model_validate_json('{"status": "safe", "reason": "x", "confidence": 2}')
    ok = ai_service.PhotoCheckResult.model_validate_json(
        '{"status":"yellow","reason":"blurry","confidence":0.3,"tell_mistri":"","photo_usable":false}')
    assert ok.status == "yellow"


def _msg(content=None, tool_calls=None):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=tool_calls))], model="test-model")


@override_settings(OPENAI_API_KEY="test-key")
def test_chat_reply_runs_tools_then_answers():
    call = SimpleNamespace(id="c1", function=SimpleNamespace(name="lookup_rule", arguments=json.dumps({"query": "FND-01"})))
    fake = mock.MagicMock()
    fake.chat.completions.create.side_effect = [_msg(tool_calls=[call]), _msg(content="Bunyad 36 inch gehri ho [FND-01].")]
    seen = {}
    with mock.patch.object(ai_service, "_client", return_value=fake):
        out = ai_service.chat_reply(system_prompt="sys", history=[], user_text="bunyad?", language="roman",
                                    tool_handlers={"lookup_rule": lambda a: seen.setdefault("q", a["query"]) and [{"rule_id": "FND-01"}]})
    assert out["text"].endswith("[FND-01].")
    assert out["tools_used"] == ["lookup_rule"]
    assert seen["q"] == "FND-01"
    second_call_messages = fake.chat.completions.create.call_args_list[1].kwargs["messages"]
    assert second_call_messages[-1]["role"] == "tool"


@override_settings(OPENAI_API_KEY="test-key")
def test_check_photo_validates_json():
    fake = mock.MagicMock()
    fake.chat.completions.create.return_value = _msg(content='{"status":"red","reason":"No cover blocks","confidence":0.8,"tell_mistri":"Cover block lagayein","photo_usable":true}')
    with mock.patch.object(ai_service, "_client", return_value=fake):
        r = ai_service.check_photo(image_bytes=b"x", mime="image/jpeg", item_title="t", look_for="l", rule_line="SST-03", facts={}, language="roman")
    assert r.status == "red"
    fake.chat.completions.create.return_value = _msg(content="not json")
    with mock.patch.object(ai_service, "_client", return_value=fake), pytest.raises(ai_service.AIUnavailable):
        ai_service.check_photo(image_bytes=b"x", mime="image/jpeg", item_title="t", look_for="l", rule_line="r", facts={}, language="roman")


# ---------- whole site, end to end (no AI key) ----------
@override_settings(OPENAI_API_KEY="")
def test_full_flow_pages(client, db):
    call_command("seed_v1", verbosity=0)
    r = client.post(reverse("signup"), {"phone": "+92 300 1234567", "name": "Ali", "language": "roman", "password": "pakka-pass-9"})
    assert r.status_code == 302
    user = User.objects.get(phone="03001234567")
    r = client.post(reverse("project_new"))
    pid = user.projects.first().pk
    for a in ["Karachi", "1", "12x14", "1", "1", "8 lakh", "aaj"]:
        client.post(reverse("chat_send", args=[pid]), {"text": a})
    for name in ["project_detail", "chat", "plan_editor", "plan_print", "materials", "check_stages", "diary", "diary_report", "rules_list"]:
        assert client.get(reverse(name, args=[pid])).status_code == 200, name
    assert client.get(reverse("check_stage", args=[pid, "foundation"])).status_code == 200
    assert client.get(reverse("check_item", args=[pid, "WAL-C4"])).status_code == 200

    # measure check
    r = client.post(reverse("check_submit", args=[pid, "LAY-C1"]), {"m0": "200", "m1": "200.25"})
    assert r.status_code == 302
    assert user.projects.first().checks.first().status == "green"

    # plan save
    plan = {"length_in": 168, "width_in": 144, "wall_in": 9, "openings": [{"id": "d1", "type": "door", "wall": "S", "offset_in": 60, "width_in": 36, "height_in": 84}]}
    r = client.post(reverse("plan_save", args=[pid]), json.dumps(plan), content_type="application/json")
    assert r.json()["ok"] and r.json()["version"] == 2

    # rates + diary
    client.post(reverse("materials", args=[pid]), {"action": "rates", "rate_brick": "18000", "rate_cement": "1450"})
    client.post(reverse("diary", args=[pid]), {"date": "2026-11-18", "kind": "material", "material": "cement", "quantity": "999"})
    r = client.get(reverse("diary", args=[pid]))
    assert r.context["any_over"]  # 999 bags is far over the estimate

    # another user can not open this project
    client.logout()
    User.objects.create_user("03110000000", "other-pass-1")
    client.login(phone="03110000000", password="other-pass-1")
    assert client.get(reverse("project_detail", args=[pid])).status_code == 404


def test_service_worker_and_manifest(client):
    assert client.get("/sw.js").status_code == 200
    assert client.get("/manifest.webmanifest").json()["display"] == "standalone"
