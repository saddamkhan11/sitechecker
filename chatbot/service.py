"""One chat (or voice) turn.

With an AI key:    scope gate -> agent (tools design, calculate, write) -> rules-only fallback if the AI fails.
Without an AI key: starting questions (fixed code) -> scope gate -> answers from the Rules table.
"""
from core import ai_service
from core.models import AIUsage
from projects.models import Rule
from projects.scope import check_question

from . import fallback, onboarding
from .agent_tools import handlers_for, tools_for
from .models import ChatMessage
from .tools import RULE_ID_RE

LIMIT_TEXT = {
    "roman": "Aaj ki AI had poori ho gayi. Yeh jawab Rules table se hai:\n\n",
    "ur": "آج کی اے آئی حد پوری ہو گئی۔ یہ جواب رولز ٹیبل سے ہے:\n\n",
    "en": "Today's AI limit is used up. This answer is from the Rules table:\n\n",
}
AGENT_HELLO = {
    "roman": "Assalam o alaikum! Main aap ka tameer ka assistant hoon. Ek kamra, washroom, kitchen ya khali plot par poora ek-manzila ghar — "
             "batayein kya banana hai aur kis sheher mein? Aap likh kar ya 🎤 bol kar baat kar sakte hain.",
    "ur": "السلام علیکم! میں آپ کا تعمیر کا اسسٹنٹ ہوں۔ ایک کمرہ، واش روم، کچن یا خالی پلاٹ پر پورا ایک منزلہ گھر — "
          "بتائیں کیا بنانا ہے اور کس شہر میں؟ آپ لکھ کر یا 🎤 بول کر بات کر سکتے ہیں۔",
    "en": "Hello! I am your building assistant. One room, a washroom, a kitchen or a whole single-storey house on an empty plot — "
          "tell me what you want to build and in which city. You can type or press 🎤 and speak.",
}


def start(project):
    """First message when a chat is opened for a new project."""
    if not project.messages.exists():
        text = (AGENT_HELLO if ai_service.ai_available() else {k: onboarding.first_question(k) for k in AGENT_HELLO})
        ChatMessage.objects.create(project=project, role=ChatMessage.ASSISTANT, source="onboarding",
                                   language=project.language, text=text.get(project.language, text["roman"]))


BUSY = {
    "roman": "AI abhi masroof hai (bohat sawal ek saath). Ek minute baad dobara likhein ya bolein.",
    "ur": "اے آئی ابھی مصروف ہے۔ ایک منٹ بعد دوبارہ لکھیں یا بولیں۔",
    "en": "The AI is busy right now. Please try again in a minute.",
}


def _short_rule(r):
    val = f" {r.value.normalize():f} {r.unit}".rstrip() if r.value is not None else ""
    return f"{r.rule_id} {r.title}{val}"


def build_system_prompt(project, language, voice=False):
    """Compact on purpose (rate limits): stage rules as one-liners, other rules via lookup_rule."""
    if project.onboarded:
        rules = Rule.objects.filter(category=project.current_stage)
    else:
        rules = Rule.objects.filter(rule_id__in=["SCOPE-01", "SCOPE-02", "SCOPE-11", "SCOPE-12", "PLAN-MIN-BEDROOM", "PLAN-MIN-WASHROOM"])
    facts = project.facts()
    if facts.get("plan"):
        facts["plan"] = {k: v for k, v in facts["plan"].items() if k != "openings"}  # get_project has them
    facts = {k: v for k, v in facts.items() if v not in (None, "", [])}
    # The numbers people ask about most, so the agent never has to guess them (it once said "slab 150 mm").
    key = Rule.objects.filter(rule_id__in=KEY_RULES).exclude(rule_id__in=[r.rule_id for r in rules])
    lines = [_short_rule(r) for r in rules] + [_short_rule(r) for r in key]
    return ai_service.agent_system_prompt(facts, lines, None, language, voice=voice)


KEY_RULES = ["WALL-01", "FND-01", "FND-02", "PLN-01", "SLB-01", "SST-01", "SST-02", "SST-03", "OPN-01", "CUR-01",
             "PLAN-02", "SCOPE-01", "SCOPE-11"]


def _history(project):
    msgs = project.messages.order_by("-created_at")[1:13]
    return [{"role": m.role, "content": m.text} for m in msgs][::-1]


def reply_language(project, voice=False):
    """The language the user picked: spoken replies follow the speaking language (the phone reads them aloud)."""
    if voice:
        return "en" if project.voice_language == "en" else "ur"
    return project.language if project.language in ("roman", "ur", "en") else "roman"


def no_ai_note(err, language):
    """Say plainly why the AI is not answering and when it will be back."""
    mins = None
    if err is not None and getattr(err, "retry_after", None):
        mins = max(1, round(err.retry_after / 60))
    kind = getattr(err, "kind", "busy") if err is not None else "busy"
    if kind == "quota":
        return {
            "roman": f"Aaj ka muft AI quota khatam ho gaya (Groq ki had).{f' Taqreeban {mins} minute baad' if mins else ' Thori dair baad'} AI wapas aayega. Tab tak Rules table se madad karta hoon.",
            "ur": f"آج کا مفت اے آئی کوٹہ ختم ہو گیا (گروک کی حد)۔{f' تقریباً {mins} منٹ بعد' if mins else ' تھوڑی دیر بعد'} اے آئی واپس آئے گا۔ تب تک رولز ٹیبل سے مدد کرتا ہوں۔",
            "en": f"Today's free AI quota is used up (Groq limit).{f' The AI is back in about {mins} min.' if mins else ' The AI will be back later.'} Until then I answer from the Rules table.",
        }[language]
    secs = round(err.retry_after) if err is not None and getattr(err, "retry_after", None) else None
    if secs:
        when = {"roman": f"{secs} second" if secs < 90 else f"{mins} minute",
                "ur": f"{secs} سیکنڈ" if secs < 90 else f"{mins} منٹ",
                "en": f"{secs} seconds" if secs < 90 else f"{mins} minutes"}[language]
        return {"roman": f"AI abhi masroof hai (bohat sawal ek saath). {when} baad dobara poochein. Tab tak Rules table se madad karta hoon.",
                "ur": f"اے آئی ابھی مصروف ہے۔ {when} بعد دوبارہ پوچھیں۔ تب تک رولز ٹیبل سے مدد کرتا ہوں۔",
                "en": f"The AI is busy (too many questions at once). Ask again in {when}. Until then I answer from the Rules table."}[language]
    return BUSY.get(language, BUSY["roman"])


def handle_message(project, user, text, voice=False) -> ChatMessage:
    text = (text or "").strip()[:1000]
    language = reply_language(project, voice)
    ChatMessage.objects.create(project=project, role=ChatMessage.USER, text=text,
                               language=ai_service.detect_language(text, project.language),
                               meta={"voice": True} if voice else {})

    def answer(reply, source, **meta):
        if voice:
            meta["speak"] = ai_service.speech_text(reply)
        return ChatMessage.objects.create(project=project, role=ChatMessage.ASSISTANT, text=reply,
                                          source=source, language=language, meta=meta)

    use_ai = ai_service.ai_available()

    # 1. The fixed starting questions: without AI, or while the AI is out and they were already asked.
    last = project.messages.filter(role=ChatMessage.ASSISTANT).order_by("-id").first()
    if not project.onboarded and (not use_ai or (last and last.meta.get("fixed_setup"))):
        if use_ai and last.meta.get("fixed_setup") and not ai_service.exhausted_for(ai_service.chat_models()[0]):
            pass  # the AI is back: let it take over again below
        else:
            return answer(onboarding.handle(project, text, language), "onboarding", fixed_setup=use_ai)

    # 2. Scope gate always runs before the agent.
    scope = check_question(text)
    if not scope.ok:
        return answer(scope.message(language), "scope", rule_ids=[scope.rule_id])

    # 3. The agent: plans, designs, calculates and writes through tools.
    err = None
    if use_ai:
        if AIUsage.take(user):
            try:
                out = ai_service.chat_reply(
                    system_prompt=build_system_prompt(project, language, voice), history=_history(project),
                    user_text=text, tools=tools_for(project), tool_handlers=handlers_for(project), language=language,
                )
                project.refresh_from_db()
                return answer(out["text"], "ai", tools=out["tools_used"], model=out["model"], ui=out["ui"],
                              rule_ids=sorted(set(RULE_ID_RE.findall(out["text"]))))
            except ai_service.AIUnavailable as e:
                err = e
        else:
            reply, used = fallback.reply(project, text, language)
            return answer(LIMIT_TEXT.get(language, LIMIT_TEXT["roman"]) + ai_service.guard_reply(reply, language), "limit", rule_ids=used)

        note = no_ai_note(err, language)
        if not project.onboarded:
            # Carry on with the simple questions from where things stand (answers the AI saved are kept).
            return answer(note + "\n\n" + onboarding.resume_question(project, language), "onboarding", fixed_setup=True)
        if fallback.match_rule_ids(text) or fallback.is_material_question(text):
            reply, used = fallback.reply(project, text, language)
            return answer(note + "\n\n" + ai_service.guard_reply(reply, language), "rules", rule_ids=used)
        return answer(note, "rules")

    # 4. Rules-only answer.
    reply, used = fallback.reply(project, text, language)
    return answer(ai_service.guard_reply(reply, language), "rules", rule_ids=used)
