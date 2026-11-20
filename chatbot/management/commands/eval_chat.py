"""Measure the chatbot on the 40 written questions (plan module 1 'done when').

    python manage.py eval_chat            # uses the real AI if OPENAI_API_KEY is set
    python manage.py eval_chat --rules    # force the rules-only answers

Writes evals/results/chat-<date>.json and prints the score.
"""
import json
from pathlib import Path

from django.conf import settings
from django.core.management import BaseCommand, call_command
from django.db import transaction
from django.test.utils import override_settings
from django.utils import timezone

from accounts.models import User
from chatbot.service import handle_message
from projects.models import Project


class Command(BaseCommand):
    help = "Run the 30 in-scope and 10 out-of-scope test questions through the chatbot."

    def add_arguments(self, parser):
        parser.add_argument("--rules", action="store_true", help="Do not call the AI")

    def handle(self, *args, rules=False, **opts):
        questions = json.loads((settings.BASE_DIR / "evals" / "chat_questions.json").read_text(encoding="utf-8"))
        keys = {"OPENAI_API_KEY": "", "GROQ_API_KEY": ""} if rules else {}
        results = []
        with override_settings(**keys, AI_DAILY_LIMIT_PER_USER=10_000), transaction.atomic():
            call_command("seed_v1", verbosity=0)
            user = User.objects.create_user("03000000099", "eval-pass-123")
            for group in ("in_scope", "out_of_scope"):
                for case in questions[group]:
                    p = Project.objects.create(owner=user)
                    for a in ["Karachi", "1", "12x14", "1", "1", "8 lakh", "aaj"]:
                        handle_message(p, user, a)
                    msg = handle_message(p, user, case["q"])
                    text = msg.text
                    if group == "in_scope":
                        ok = f"[{case['expect_rule']}]" in text or case["expect_rule"] in text
                    else:
                        ok = "engineer" in text.lower() or "انجینئر" in text
                    results.append({"group": group, "q": case["q"], "expect": case["expect_rule"], "ok": ok,
                                    "source": msg.source, "reply": text})
                    self.stdout.write(f"{'PASS' if ok else 'FAIL'} [{msg.source}] {case['q']}")
            transaction.set_rollback(True)  # leave no eval data behind

        ins = [r for r in results if r["group"] == "in_scope"]
        outs = [r for r in results if r["group"] == "out_of_scope"]
        score_in, score_out = sum(r["ok"] for r in ins), sum(r["ok"] for r in outs)
        out_dir = Path(settings.BASE_DIR / "evals" / "results")
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"chat-{timezone.now():%Y%m%d-%H%M}.json"
        path.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(
            f"In scope: {score_in}/{len(ins)} cite the right rule. Out of scope: {score_out}/{len(outs)} say engineer. Saved {path.name}"))
