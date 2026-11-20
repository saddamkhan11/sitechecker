import datetime as dt
import json
from pathlib import Path

import pytest
from django.core.management import call_command
from django.test import override_settings

from accounts.models import User
from chatbot import onboarding
from chatbot.fallback import is_material_question
from chatbot.service import handle_message
from projects.models import Project
from projects.scope import check_question

QUESTIONS = json.loads((Path(__file__).resolve().parent.parent / "evals" / "chat_questions.json").read_text(encoding="utf-8"))


@pytest.fixture
def seeded(db):
    call_command("seed_v1", verbosity=0)


@pytest.fixture
def project(seeded):
    user = User.objects.create_user("03001234567", "test-pass-123")
    p = Project.objects.create(owner=user)
    for answer in ["Karachi", "1", "12x14", "1", "1", "8 lakh", "2026-12-01"]:
        handle_message(p, user, answer)
    p.refresh_from_db()
    return p


# ---------- onboarding ----------
def test_parsers():
    assert onboarding.parse_size("12x14") == (14, 12)
    assert onboarding.parse_size("12 by 14 ft") == (14, 12)
    assert onboarding.parse_size("۱۲x۱۴") == (14, 12)
    assert onboarding.parse_size("12'6\" x 10") == (12.5, 10)
    assert onboarding.parse_size("hello") is None
    assert onboarding.parse_wall("eent ki") == "brick" and onboarding.parse_wall("2") is None
    assert onboarding.parse_roof("lanter") == "rcc_slab" and onboarding.parse_roof("garder") is None
    assert onboarding.parse_budget("8 lakh") == 800_000
    assert onboarding.parse_budget("7,50,000") == 750_000
    assert onboarding.parse_budget("pata nahi") == "unknown"
    assert onboarding.parse_date("01-12-2026") == dt.date(2026, 12, 1)
    assert onboarding.parse_date("kal", today=dt.date(2026, 1, 1)) == dt.date(2026, 1, 2)


@override_settings(OPENAI_API_KEY="")
def test_six_questions_create_project(project):
    assert project.onboarded
    assert project.city == "Karachi"
    assert float(project.room_length_ft) == 14 and float(project.room_width_ft) == 12
    assert project.wall_type == "brick" and project.roof_type == "rcc_slab"
    assert project.budget_pkr == 800_000
    assert project.project_type == "room"
    assert project.stages.count() == 8  # no plumbing stage for a dry room
    assert project.plans.count() == 1


@override_settings(OPENAI_API_KEY="")
def test_house_from_plot_without_ai(seeded):
    user = User.objects.create_user("03001113333", "test-pass-123")
    p = Project.objects.create(owner=user)
    for a in ["Lahore", "4", "5 marla", "2 bedroom, 1 kitchen aur 1 washroom", "eent", "lanter", "pata nahi", "kal"]:
        msg = handle_message(p, user, a)
    p.refresh_from_db()
    assert p.onboarded and p.project_type == "house"
    assert float(p.plot_length_ft) * float(p.plot_width_ft) == pytest.approx(1125, rel=0.05)
    plan = p.latest_plan().data
    assert sorted(r["type"] for r in plan["rooms"]) == ["bedroom", "bedroom", "kitchen", "washroom"]
    assert p.stages.filter(stage="plumbing").exists()  # wet rooms add the plumbing stage
    assert "Covered area" in msg.text


def test_parse_rooms_and_plot():
    specs = onboarding.parse_rooms("2 bedroom, ek kitchen aur 1 washroom, drawing 14x12")
    assert [s["type"] for s in specs] == ["bedroom", "bedroom", "kitchen", "washroom", "living"]
    assert specs[-1]["length_in"] == 168 and specs[-1]["width_in"] == 144
    assert onboarding.parse_plot("30x60") == {"length_in": 360, "width_in": 720}
    assert onboarding.parse_plot("pata nahi") == "unknown"
    assert onboarding.parse_type("ghar banana hai") == "house"
    assert onboarding.parse_type("2") == "washroom"


@override_settings(OPENAI_API_KEY="")
def test_onboarding_rejects_big_room_and_block_walls(seeded):
    user = User.objects.create_user("03001112222", "test-pass-123")
    p = Project.objects.create(owner=user)
    handle_message(p, user, "Lahore")
    handle_message(p, user, "1")
    msg = handle_message(p, user, "18x24")
    assert "engineer" in msg.text.lower() and "SCOPE-01" in msg.text
    assert p.onboarding_step == 2  # asked again
    handle_message(p, user, "12x12")
    msg = handle_message(p, user, "2")  # block wall
    assert "SCOPE-03" in msg.text and p.onboarding_step == 4


# ---------- scope gate: 10 out-of-scope questions ----------
@pytest.mark.parametrize("case", QUESTIONS["out_of_scope"], ids=lambda c: c["q"][:30])
def test_out_of_scope_needs_engineer(seeded, case):
    res = check_question(case["q"])
    assert not res.ok
    assert res.rule_id == case["expect_rule"]
    assert "engineer" in res.message("roman").lower()


@pytest.mark.parametrize("case", QUESTIONS["in_scope"], ids=lambda c: c["q"][:30])
def test_in_scope_questions_pass_the_gate(case):
    assert check_question(case["q"]).ok, case["q"]


# ---------- 30 in-scope questions answered from the Rules table ----------
@override_settings(OPENAI_API_KEY="")
@pytest.mark.parametrize("case", QUESTIONS["in_scope"], ids=lambda c: c["q"][:30])
def test_rules_answer(project, case):
    msg = handle_message(project, project.owner, case["q"])
    assert msg.source == "rules"
    assert case["expect_rule"] in msg.meta["rule_ids"], msg.text
    assert f"[{case['expect_rule']}]" in msg.text


@override_settings(OPENAI_API_KEY="")
def test_material_question_uses_calculator(project):
    msg = handle_message(project, project.owner, "Kitni eent lagengi?")
    assert msg.meta["rule_ids"] == ["calculate_materials"]
    assert "Eent" in msg.text


def test_material_vs_rule_questions():
    assert is_material_question("kitni eent lagengi")
    assert is_material_question("کتنا سیمنٹ لگے گا")
    assert not is_material_question("sariye ka fasla kitna")
    assert not is_material_question("eent ko kitni der bhigona hai")


@override_settings(OPENAI_API_KEY="")
def test_safe_question_never_gets_safe_verdict(project):
    msg = handle_message(project, project.owner, "Kya mera kamra safe hai?")
    assert msg.source == "scope"
    assert "engineer" in msg.text.lower()
