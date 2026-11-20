"""The agent: Groq provider, tools that design and write, and the voice endpoint. No real AI is called."""
import io
import json
from types import SimpleNamespace
from unittest import mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse

from accounts.models import User
from chatbot.agent_tools import TOOLS, Tools, handlers_for
from chatbot.service import handle_message
from core import ai_service
from diary.models import DiaryEntry
from projects.models import Project, Rate

GROQ = dict(GROQ_API_KEY="gsk_test", OPENAI_API_KEY="", AI_PROVIDER="auto")


@pytest.fixture
def project(db):
    call_command("seed_v1", verbosity=0)
    user = User.objects.create_user("03004445555", "test-pass-123")
    return Project.objects.create(owner=user)


# ---------- provider ----------
@override_settings(**GROQ)
def test_groq_is_chosen_and_uses_groq_url():
    assert ai_service.provider() == "groq"
    assert ai_service.model("chat") == "openai/gpt-oss-120b"
    c = ai_service._client()
    assert "api.groq.com" in str(c.base_url)


@override_settings(GROQ_API_KEY="", OPENAI_API_KEY="sk-x")
def test_openai_fallback_provider():
    assert ai_service.provider() == "openai"


def test_tool_schemas_are_valid():
    names = [t["function"]["name"] for t in TOOLS]
    assert len(names) == len(set(names))
    for t in TOOLS:
        assert t["type"] == "function" and t["function"]["parameters"]["type"] == "object"
        json.dumps(t)


# ---------- tools do the real work ----------
def test_tools_design_a_house_from_a_plot_and_finish_setup(project):
    t = Tools(project)
    out = t.update_project({"city": "lahore", "project_type": "house", "plot_marla": 5, "budget_pkr": 3000000})
    assert out["ok"] and project.city == "Lahore"
    out = t.design_layout({"rooms": [{"type": "bedroom", "count": 2}, {"type": "kitchen"}, {"type": "washroom"}]})
    assert out["ok"], out
    assert len(out["plan"]["rooms"]) == 4 and out["ui"]["url"].endswith("/plan/")
    out = t.finish_setup({})
    assert out["ok"] and "plumbing" in out["stages"]
    project.refresh_from_db()
    assert project.onboarded and project.project_type == "house"
    mats = t.calculate_materials({})
    assert mats["materials"]["brick"] > 10000


def test_tools_refuse_out_of_scope(project):
    t = Tools(project)
    out = t.design_layout({"rooms": [{"type": "living", "length_ft": 20, "width_ft": 16}]})
    assert not out["ok"] and out["needs_engineer"] and "SCOPE-01" in out["error"]
    assert t.update_project({"wall_type": "block"})["needs_engineer"]
    assert project.plans.count() == 0


def test_tools_edit_add_remove_rooms_and_openings(project):
    t = Tools(project)
    t.update_project({"city": "Karachi"})
    t.design_layout({"rooms": [{"type": "room", "length_ft": 12, "width_ft": 12}]})
    out = t.add_room({"type": "washroom"})
    assert out["ok"] and len(out["plan"]["rooms"]) == 2
    rid = next(r["id"] for r in out["plan"]["rooms"] if r["type"] == "washroom")
    out = t.edit_room({"room_id": rid, "length_ft": 8, "width_ft": 5})
    assert out["ok"] and any(r["size_ft"] in ("8 x 5", "5 x 8") for r in out["plan"]["rooms"])  # layout may turn it
    out = t.add_opening({"room_id": "r1", "type": "window"})
    assert out["ok"], out
    wid = out["done"].split()[2]
    assert t.remove_opening({"opening_id": wid})["ok"]
    assert t.remove_room({"room_id": rid})["ok"]
    assert project.plans.count() >= 5  # every change is a new version


def test_tools_money_and_diary(project):
    t = Tools(project)
    t.update_project({"city": "Karachi"})
    t.design_layout({"rooms": [{"type": "room"}]})
    t.finish_setup({})
    assert t.save_rates({"cement_per_bag": 1450, "brick_per_1000": 18000})["saved"] == {"cement": 1450.0, "brick": 18000.0}
    assert Rate.objects.filter(city="Karachi").count() == 2
    cmp = t.compare_mistri_demand({"cement": 999})
    assert cmp["comparison"]["cement"]["flag"] is True
    out = t.add_diary_entry({"kind": "payment", "payment_type": "labour", "amount": 25000, "paid_to": "Mistri Aslam"})
    assert out["ok"] and DiaryEntry.objects.filter(project=project, amount=25000).exists()
    assert not t.add_diary_entry({"kind": "material"})["ok"]  # missing quantity is refused
    assert t.set_stage_status({"stage": "layout", "status": "done"})["current_stage"] == "foundation"
    assert t.get_stage_checklist({})["stage"] == "foundation"


# ---------- the agent loop calls our tools ----------
def _msg(content=None, tool_calls=None):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=tool_calls))], model="openai/gpt-oss-120b")


def _call(i, name, args):
    return SimpleNamespace(id=f"c{i}", function=SimpleNamespace(name=name, arguments=json.dumps(args)))


@override_settings(**GROQ)
def test_agent_sets_up_a_house_through_tools(project):
    fake = mock.MagicMock()
    fake.chat.completions.create.side_effect = [
        _msg(tool_calls=[_call(1, "update_project", {"city": "Multan", "project_type": "house", "plot_length_ft": 30, "plot_width_ft": 60})]),
        _msg(tool_calls=[_call(2, "design_layout", {"rooms": [{"type": "bedroom", "count": 2}, {"type": "washroom"}]})]),
        _msg(tool_calls=[_call(3, "finish_setup", {})]),
        _msg(content="Naqsha ban gaya: 2 bedroom aur 1 washroom, 30x60 plot par."),
    ]
    with mock.patch.object(ai_service, "_client", return_value=fake):
        msg = handle_message(project, project.owner, "Multan mein 30x60 plot par 2 bedroom aur washroom wala ghar")
    project.refresh_from_db()
    assert msg.source == "ai"
    assert msg.meta["tools"] == ["update_project", "design_layout", "finish_setup"]
    assert any(b["url"].endswith("/plan/") for b in msg.meta["ui"])
    assert project.onboarded and project.city == "Multan" and project.plans.count() == 1
    # the system prompt carried the facts and the tools were offered
    first = fake.chat.completions.create.call_args_list[0].kwargs
    assert first["tools"] and "setup_complete" in first["messages"][0]["content"]


@override_settings(**GROQ)
def test_scope_gate_runs_before_agent(project):
    fake = mock.MagicMock()
    with mock.patch.object(ai_service, "_client", return_value=fake):
        msg = handle_message(project, project.owner, "upar dusri manzil banani hai")
    assert msg.source == "scope" and not fake.chat.completions.create.called


@override_settings(**GROQ)
def test_ai_failure_during_setup_falls_back_to_questions(project):
    fake = mock.MagicMock()
    fake.chat.completions.create.side_effect = RuntimeError("groq down")
    with mock.patch.object(ai_service, "_client", return_value=fake):
        msg = handle_message(project, project.owner, "Karachi")
    assert msg.source == "onboarding"


# ---------- voice ----------
@override_settings(**GROQ)
def test_transcribe_retries_in_urdu_when_whisper_writes_hindi():
    fake = mock.MagicMock()
    fake.audio.transcriptions.create.side_effect = [SimpleNamespace(text="नींव कितनी गहरी"), SimpleNamespace(text="بنیاد کتنی گہری")]
    with mock.patch.object(ai_service, "_client", return_value=fake):
        assert ai_service.transcribe(b"x" * 3000, language=None) == "بنیاد کتنی گہری"
    assert fake.audio.transcriptions.create.call_args_list[1].kwargs["language"] == "ur"


def test_speech_text_drops_rule_ids():
    assert ai_service.speech_text("Bunyad 36 inch [FND-01]. **Mistri** ko kahein.") == "Bunyad 36 inch . Mistri ko kahein."


@override_settings(**GROQ)
def test_voice_endpoint(client, project):
    client.force_login(project.owner)
    audio = SimpleUploadedFile("voice.webm", b"\x1a\x45\xdf\xa3" + b"0" * 4000, content_type="audio/webm")
    with mock.patch.object(ai_service, "transcribe", return_value="upar doosri manzil ban sakti hai?"):
        r = client.post(reverse("chat_voice", args=[project.pk]), {"audio": audio})
    j = r.json()
    assert r.status_code == 200 and j["ok"]
    assert j["transcript"].startswith("upar") and "انجینئر" in j["text"]  # spoken reply in the speaking language
    assert "[SCOPE" not in j["speak"]
    assert project.messages.filter(role="user", meta__voice=True).exists()


def test_voice_without_key_says_so(client, project):
    client.force_login(project.owner)
    audio = SimpleUploadedFile("voice.webm", b"0" * 4000, content_type="audio/webm")
    r = client.post(reverse("chat_voice", args=[project.pk]), {"audio": audio})
    assert r.status_code == 503 and "GROQ_API_KEY" in r.json()["error"]


def test_setup_project_does_everything_in_one_call(project):
    out = Tools(project).setup_project({"city": "Multan", "plot_marla": 5,
                                        "rooms": [{"type": "bedroom", "count": 2}, {"type": "washroom"}]})
    project.refresh_from_db()
    assert out["ok"] and project.onboarded and project.project_type == "house" and project.plot_length_ft


@override_settings(**GROQ)
def test_saved_work_is_reported_when_ai_goes_busy(project):
    from openai import RateLimitError

    Tools(project).setup_project({"city": "Karachi", "rooms": [{"type": "room"}]})
    err = RateLimitError("Rate limit reached ... Please try again in 59.5s.", response=mock.MagicMock(status_code=429), body=None)
    fake = mock.MagicMock()
    fake.chat.completions.create.side_effect = [
        _msg(tool_calls=[_call(1, "add_diary_entry", {"kind": "payment", "payment_type": "labour", "amount": 20000})]), err]
    with mock.patch.object(ai_service, "_client", return_value=fake):
        msg = handle_message(project, project.owner, "mistri ko 20 hazar diye")
    assert msg.source == "ai" and msg.text.startswith("Ho gaya: diary entry likh di")
    assert DiaryEntry.objects.filter(project=project, amount=20000).count() == 1


def test_setup_offers_fewer_tools(project):
    from chatbot.agent_tools import tools_for

    assert len(tools_for(project)) == 7
    Tools(project).setup_project({"city": "Karachi", "rooms": [{"type": "room"}]})
    project.refresh_from_db()
    assert len(tools_for(project)) == len(TOOLS) - 1


def test_chat_page_shows_mic_only_with_a_key(client, project):
    client.force_login(project.owner)
    assert 'id="mic"' not in client.get(reverse("chat", args=[project.pk])).content.decode()
    with override_settings(**GROQ):
        html = client.get(reverse("chat", args=[project.pk])).content.decode()
    assert 'id="mic"' in html and "voice.js" in html


def test_handlers_cover_every_tool(project):
    h = handlers_for(project)
    assert set(h) == {t["function"]["name"] for t in TOOLS}


# ---------- quotas, backup model, languages ----------
def _rate_err(text):
    from openai import RateLimitError

    return RateLimitError(text, response=mock.MagicMock(status_code=429), body=None)


@override_settings(**GROQ, GROQ_MODEL_CHAT_FALLBACK="qwen/qwen3.8-27b")
def test_daily_quota_switches_to_backup_model(project):
    from django.core.cache import cache

    cache.clear()
    fake = mock.MagicMock()
    fake.chat.completions.create.side_effect = [
        _rate_err("Rate limit reached for model openai/gpt-oss-120b on tokens per day (TPD): Please try again in 17m48.336s."),
        _msg(content="Jee, bataiye kya banana hai?"),
    ]
    with mock.patch.object(ai_service, "_client", return_value=fake):
        msg = handle_message(project, project.owner, "salam")
    assert msg.source == "ai" and msg.meta["model"] == "qwen/qwen3.8-27b"
    assert fake.chat.completions.create.call_args_list[1].kwargs["model"] == "qwen/qwen3.8-27b"
    assert 1000 < ai_service.exhausted_for("openai/gpt-oss-120b") <= 1069
    cache.clear()


@override_settings(**GROQ, GROQ_MODEL_CHAT_FALLBACK="qwen/qwen3.8-27b")
def test_all_quota_used_continues_setup_with_simple_questions(project):
    from django.core.cache import cache

    cache.clear()
    Tools(project).update_project({"city": "Karachi"})  # the AI already saved the city
    err = _rate_err("Rate limit reached on tokens per day (TPD): Please try again in 9m10s.")
    fake = mock.MagicMock()
    fake.chat.completions.create.side_effect = [err, err]
    with mock.patch.object(ai_service, "_client", return_value=fake):
        msg = handle_message(project, project.owner, "ghar banana hai")
        assert "quota" in msg.text and "9 minute" in msg.text
        assert "Kya banana hai?" in msg.text  # city is known, so it asks the next thing
        assert msg.meta["fixed_setup"] is True
        msg2 = handle_message(project, project.owner, "2")  # washroom; answered by the simple flow
    project.refresh_from_db()
    assert project.project_type == "washroom" and msg2.source == "onboarding"
    assert fake.chat.completions.create.call_count == 2  # the AI is not asked again while it is used up
    cache.clear()


@override_settings(**GROQ)
def test_no_ai_note_after_setup_still_answers_rules(project):
    from django.core.cache import cache

    Tools(project).setup_project({"city": "Karachi", "rooms": [{"type": "room"}]})
    for m in ai_service.chat_models():
        ai_service.mark_exhausted(m, 600)
    msg = handle_message(project, project.owner, "Bunyad kitni gehri ho?")
    assert "quota" in msg.text and "[FND-01]" in msg.text
    cache.clear()


def test_language_picker_and_reply_language(client, project):
    client.force_login(project.owner)
    r = client.post(reverse("chat_language", args=[project.pk]), {"language": "en", "voice_language": "en"})
    assert r.json() == {"ok": True, "language": "en", "voice_language": "en"}
    project.refresh_from_db()
    project.owner.refresh_from_db()
    assert project.language == "en" and project.owner.language == "en"
    Tools(project).setup_project({"city": "Karachi", "rooms": [{"type": "room"}]})
    project.refresh_from_db()
    msg = handle_message(project, project.owner, "Kya upar dusri manzil ban sakti hai?")  # Roman text, English picked
    assert msg.text.startswith("This needs an engineer")
    client.post(reverse("chat_language", args=[project.pk]), {"language": "xx"})  # junk is ignored
    project.refresh_from_db()
    assert project.language == "en"


@override_settings(**GROQ)
def test_voice_uses_the_picked_speaking_language(client, project):
    client.force_login(project.owner)
    project.voice_language = "en"
    project.save()
    audio = SimpleUploadedFile("voice.webm", b"0" * 4000, content_type="audio/webm")
    with mock.patch.object(ai_service, "transcribe", return_value="is a second floor possible?") as t:
        j = client.post(reverse("chat_voice", args=[project.pk]), {"audio": audio}).json()
    assert t.call_args.kwargs["language"] == "en"
    assert j["lang"] == "en" and "engineer" in j["text"].lower()


@override_settings(**GROQ)
def test_whisper_is_told_the_language():
    fake = mock.MagicMock()
    fake.audio.transcriptions.create.return_value = SimpleNamespace(text="اسلام علیکم")
    with mock.patch.object(ai_service, "_client", return_value=fake):
        ai_service.transcribe(b"x" * 3000, language="ur")
    assert fake.audio.transcriptions.create.call_args.kwargs["language"] == "ur"
