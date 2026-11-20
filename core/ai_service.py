"""EVERY call to an AI provider lives in this file.

Providers: Groq (default when GROQ_API_KEY is set) or OpenAI. Both speak the OpenAI
chat-completions format, so one client library is used with a different base URL.
Changing the model or the provider later means changing only this file (or .env).

Safety design:
  * The scope gate runs BEFORE the agent is called (projects/scope.py).
  * The agent quotes rules by ID; numbers come from the Rules table or our tools, never the model.
  * Tools validate everything they write (plans are checked against the rules before saving).
  * Photo checks must return a fixed JSON; Pydantic rejects anything else.
  * Replies are post-filtered so the word "safe" is never used as a verdict.
"""
from __future__ import annotations

import base64
import json
import logging
import re
from typing import Callable, Literal

from django.conf import settings
from pydantic import BaseModel, Field, ValidationError

log = logging.getLogger(__name__)


class AIUnavailable(RuntimeError):
    """No API key configured, or the provider failed.

    kind: "quota" (daily or long limit hit; retry_after seconds), "busy" (short limit), "error" (anything else).
    """

    def __init__(self, message="", kind="error", retry_after=None):
        super().__init__(message)
        self.kind = kind
        self.retry_after = retry_after


def _exhausted_key(m):
    return f"ai-exhausted:{m}"


def mark_exhausted(m, seconds):
    from django.core.cache import cache

    cache.set(_exhausted_key(m), True, timeout=max(30, int(seconds)))
    cache.set(_exhausted_key(m) + ":until", __import__("time").time() + seconds, timeout=max(30, int(seconds)))


def exhausted_for(m):
    """Seconds until this model's quota comes back, or 0."""
    from django.core.cache import cache
    import time

    until = cache.get(_exhausted_key(m) + ":until")
    return max(0, until - time.time()) if until else 0


def chat_models():
    """Main model first, then the backup (its own daily quota)."""
    if provider() == "groq":
        chain = [settings.GROQ_MODEL_CHAT, getattr(settings, "GROQ_MODEL_CHAT_FALLBACK", "")]
    else:
        chain = [settings.OPENAI_MODEL_CHAT]
    return [m for i, m in enumerate(chain) if m and m not in chain[:i]]


# --------------------------------------------------------------------------
# Provider
# --------------------------------------------------------------------------
def provider() -> str | None:
    want = getattr(settings, "AI_PROVIDER", "auto")
    groq, openai = bool(getattr(settings, "GROQ_API_KEY", "")), bool(settings.OPENAI_API_KEY)
    if want == "groq":
        return "groq" if groq else None
    if want == "openai":
        return "openai" if openai else None
    return "groq" if groq else "openai" if openai else None


def ai_available() -> bool:
    return provider() is not None


def voice_available() -> bool:
    return provider() is not None


def model(kind: str) -> str:
    """kind: chat | vision | stt"""
    p = provider()
    if p == "groq":
        return {"chat": settings.GROQ_MODEL_CHAT, "vision": settings.GROQ_MODEL_VISION, "stt": settings.GROQ_MODEL_STT}[kind]
    return {"chat": settings.OPENAI_MODEL_CHAT, "vision": settings.OPENAI_MODEL_VISION, "stt": settings.OPENAI_MODEL_STT}[kind]


def _client():
    p = provider()
    if p is None:
        raise AIUnavailable("No AI key is set (GROQ_API_KEY or OPENAI_API_KEY)")
    from openai import OpenAI

    if p == "groq":
        # max_retries=0: rate limits are handled by _create_with_rate_limit (short waits, then a lighter model)
        return OpenAI(api_key=settings.GROQ_API_KEY, base_url=settings.GROQ_BASE_URL, timeout=60, max_retries=0)
    return OpenAI(api_key=settings.OPENAI_API_KEY, timeout=60, max_retries=2)


# --------------------------------------------------------------------------
# Language helpers
# --------------------------------------------------------------------------
_URDU_CHARS = re.compile(r"[؀-ۿ]")
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_ROMAN_HINTS = re.compile(
    r"\b(kya|kitn[aie]|hai|hain|ka|ki|ke|mein|main|nahi|kaise|kab|kyun|chahiye|karna|karen|karein|bhai|deewar|eent|sariya|"
    r"lanter|bori|ret|bajri|mistri|bunyad|kamra|kamre|ho|ga|gi|tha|aur|ya|se|ko|banana|banwana|ghar|makan)\b",
    re.I,
)


def detect_language(text: str, default: str = "roman") -> str:
    """'ur' for Urdu script, 'roman' for Roman Urdu, 'en' for plain English."""
    text = text or ""
    if _URDU_CHARS.search(text):
        return "ur"
    roman = len(_ROMAN_HINTS.findall(text))
    english = len(re.findall(r"\b(the|is|are|what|how|should|my|do|does|can|when|many|much|need|which|want|build)\b", text, re.I))
    if roman == 0 and english == 0:
        return default
    return "en" if english > roman else "roman"


LANG_INSTRUCTION = {
    "ur": "Reply in Urdu script (اردو).",
    "roman": "Reply in Roman Urdu (Urdu written in English letters), like 'Bunyad kam az kam 3 ft gehri honi chahiye'.",
    "en": "Reply in simple English.",
}

_SAFE_WORDS = re.compile(r"\b(safe|guaranteed|approved|certified)\b|محفوظ|منظور شدہ", re.I)
SAFE_NOTE = {
    "ur": "نوٹ: یہ ایپ کسی عمارت کو 'محفوظ' قرار نہیں دیتی۔ یہ صرف بتاتی ہے کہ کیا چیک کیا اور کیا نظر آیا۔ [SCOPE-08]",
    "roman": "Note: yeh app kisi structure ko 'safe' nahi kehti. Yeh sirf batati hai ke kya check kiya aur kya nazar aaya. [SCOPE-08]",
    "en": "Note: this app never says a structure is 'safe'. It only says what it checked and what it found. [SCOPE-08]",
}


def guard_reply(text: str, language: str) -> str:
    """Plain text for the chat bubble, and never let a reply read like a safety certificate."""
    text = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: m.group(1) or m.group(2), text or "")
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.M)
    if _SAFE_WORDS.search(text or "") and "SCOPE-08" not in text:
        return f"{text.strip()}\n\n{SAFE_NOTE.get(language, SAFE_NOTE['roman'])}"
    return text


def speech_text(text: str) -> str:
    """What the phone should read aloud: no rule IDs, markdown or links."""
    t = re.sub(r"\[[A-Z]{2,6}(?:-[A-Z0-9]+)+(?:,\s*[A-Z]{2,6}(?:-[A-Z0-9]+)+)*\]", "", text or "")
    t = re.sub(r"https?://\S+|[*_#`>|]", "", t)
    return re.sub(r"\s+", " ", t).strip()


# --------------------------------------------------------------------------
# The agent (chat with tools)
# --------------------------------------------------------------------------
def agent_system_prompt(facts: dict, stage_rules: list[str], rule_index: list[str] | None, language: str, voice: bool = False) -> str:
    """Kept short on purpose: Groq's free tier allows about 8,000 tokens a minute, and one turn can be several calls."""
    voice_rule = (" VOICE: the user will HEAR this. Urdu script, max 50 words, plain sentences, no lists or symbols."
                  if voice else "")
    return f"""You are Site Checker: an agent that designs and supervises small SINGLE-STOREY buildings in Pakistan (one room,
washroom, kitchen, or a house up to 8 rooms / 1500 sq ft) with 9 in brick walls and an RCC slab, for an owner with no
engineering knowledge. ACT with tools; after a change say in one line what you did.
LANGUAGE: {LANG_INSTRUCTION.get(language, LANG_INSTRUCTION['roman'])} Whole reply in that language. Max 120 words. Money as "Rs".{voice_rule}
WORDS: lanter/linter/chhat = RCC slab (SLB-*, SST-*); lintel = beam over a door (OPN-*); sariya = steel bars;
eent = brick; bunyad = foundation; tarai = curing; ret = sand; bajri = crush; bori = cement bag; marla/gaz = plot area.
SETUP (facts.setup_complete=false): you need what to build, the city and the rooms. A plot is needed ONLY for a house;
never ask for a plot for one room, washroom or kitchen. Ask only for what is missing. As soon as you know the city and
the rooms, call setup_project ONCE (pass marla/gaz as given, never convert), then summarise in 1-2 lines.
Examples: "Karachi mein 5x7 washroom" -> setup_project(city=Karachi, project_type=washroom, rooms=[{{type:washroom,
length_ft:7, width_ft:5}}]). "Lahore 5 marla, 2 bedroom, kitchen, washroom" -> setup_project(city=Lahore, plot_marla=5,
rooms=[{{type:bedroom,count:2}},{{type:kitchen}},{{type:washroom}}]). "Multan 30x60 plot, 2 bedroom" ->
setup_project(city=Multan, plot_length_ft=30, plot_width_ft=60, rooms=[{{type:bedroom,count:2}}]). Default room sizes are fine; say so.
Plot size is NOT a slab span.
RULES: 1) Any construction number must come from a rule. Use the RULES list below; for anything else call lookup_rule
BEFORE answering, and never say a rule is missing without calling it. Cite like [FND-01].
2) Quantities and cost ONLY from calculate_materials (call it; if there is no plan yet, set up first). Never do arithmetic.
3) Not in the rules after lookup_rule: say so, ask an engineer.
4) Never say safe/approved/guaranteed. 5) Second storey, beams, columns, basement, room span over SCOPE-01, area over
SCOPE-11, commercial, old cracks: "this needs an engineer" + reason. 6) Write diary, rates, stages or plan edits only when
the user asked. 7) If useful end with ONE short "Mistri ko kahein: ..." line ("مستری سے کہیں:" / "Tell the mistri:")
that uses only numbers from the RULES below or a tool result, never other units or your own figures.
FACTS: {json.dumps(facts, ensure_ascii=False, default=str, separators=(',', ':'))}
RULES (id title value): {' | '.join(stage_rules) or '-'}"""


# Kept for older imports.
chat_system_prompt = agent_system_prompt


def chat_reply(
    *,
    system_prompt: str,
    history: list[dict],
    user_text: str,
    tool_handlers: dict[str, Callable[[dict], object]],
    language: str,
    tools: list[dict] | None = None,
    max_rounds: int | None = None,
) -> dict:
    """Run one agent turn: the model may call tools several times before answering.

    Returns {"text", "tools_used", "model", "ui"} where ui is a list of {"label", "url"} buttons the tools suggested.
    """
    client = _client()
    max_rounds = max_rounds or getattr(settings, "AGENT_MAX_STEPS", 8)
    history = [{"role": h["role"], "content": (h.get("content") or "")[:500]} for h in history[-8:]]
    messages = [{"role": "system", "content": system_prompt}, *history, {"role": "user", "content": user_text}]
    tools_used, ui = [], []
    current_model = next((m for m in chat_models() if not exhausted_for(m)), model("chat"))
    done = []  # what tools already changed, so a late failure can still report it
    try:
        for _ in range(max_rounds):
            kwargs = {"model": current_model, "messages": messages, "temperature": 0.2}
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            resp, current_model = _create_with_rate_limit(client, kwargs)
            msg = resp.choices[0].message
            if not msg.tool_calls:
                return {"text": guard_reply(msg.content or "", language), "tools_used": tools_used,
                        "model": current_model, "ui": _dedupe(ui)}
            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in msg.tool_calls
                ],
            })
            for tc in msg.tool_calls:
                handler = tool_handlers.get(tc.function.name)
                try:
                    args = json.loads(tc.function.arguments or "{}") or {}
                    result = handler(args) if handler else {"error": f"unknown tool {tc.function.name}"}
                except Exception as e:  # a tool error goes back to the model, not to the user
                    log.exception("tool %s failed", tc.function.name)
                    result = {"error": str(e)}
                tools_used.append(tc.function.name)
                if isinstance(result, dict) and result.get("ui"):
                    ui.append(result["ui"])
                if isinstance(result, dict) and result.get("ok") and tc.function.name in DONE_LABEL:
                    done.append(tc.function.name)
                if isinstance(result, dict):
                    result = {k: v for k, v in result.items() if k != "ui"}  # the button is for the page, not the model
                messages.append({"role": "tool", "tool_call_id": tc.id,
                                 "content": json.dumps(result, ensure_ascii=False, default=str, separators=(",", ":"))[:3500]})
    except Exception as e:
        if not isinstance(e, AIUnavailable):
            log.exception("chat call failed")
        if done:  # something was already saved: never answer "busy" as if nothing happened
            return {"text": done_summary(done, language), "tools_used": tools_used, "model": current_model,
                    "ui": _dedupe(ui), "partial": True}
        raise e if isinstance(e, AIUnavailable) else AIUnavailable(str(e), kind="error") from e
    if done:
        return {"text": done_summary(done, language), "tools_used": tools_used, "model": current_model,
                "ui": _dedupe(ui), "partial": True}
    raise AIUnavailable("The agent used too many steps.")


DONE_LABEL = {
    # tool: (Roman Urdu, Urdu, English)
    "setup_project": ("project aur naqsha tayyar", "پروجیکٹ اور نقشہ تیار", "project and plan ready"),
    "update_project": ("project ki tafseel save", "پروجیکٹ کی تفصیل محفوظ", "project details saved"),
    "design_layout": ("naqsha bana diya", "نقشہ بنا دیا", "layout designed"),
    "finish_setup": ("setup mukammal", "سیٹ اپ مکمل", "setup finished"),
    "add_room": ("kamra add kar diya", "کمرہ شامل کر دیا", "room added"),
    "edit_room": ("kamra badal diya", "کمرہ بدل دیا", "room changed"),
    "remove_room": ("kamra hata diya", "کمرہ ہٹا دیا", "room removed"),
    "add_opening": ("darwaza/khirki laga di", "دروازہ/کھڑکی لگا دی", "door/window added"),
    "move_opening": ("darwaza/khirki hila di", "دروازہ/کھڑکی منتقل", "door/window moved"),
    "remove_opening": ("darwaza/khirki hata di", "دروازہ/کھڑکی ہٹا دی", "door/window removed"),
    "save_rates": ("rates save", "ریٹ محفوظ", "rates saved"),
    "compare_mistri_demand": ("mistri ki demand save", "مستری کی مانگ محفوظ", "mistri demand saved"),
    "set_stage_status": ("stage update", "مرحلہ اپڈیٹ", "stage updated"),
    "add_diary_entry": ("diary entry likh di", "ڈائری میں لکھ دیا", "diary entry written"),
}


def done_summary(done, language):
    i = {"roman": 0, "ur": 1, "en": 2}.get(language, 0)
    items = ", ".join(dict.fromkeys(DONE_LABEL[d][i] for d in done))
    return {0: f"Ho gaya: {items}. (AI abhi masroof hai, is liye mukhtasar jawab — tafseel neeche button mein.)",
            1: f"ہو گیا: {items}۔ (اے آئی ابھی مصروف ہے، اس لیے مختصر جواب — تفصیل نیچے بٹن میں۔)",
            2: f"Done: {items}. (The AI is busy, so this is a short reply — see the button below for details.)"}[i]


def _dedupe(ui):
    seen, out = set(), []
    for b in ui:
        if b.get("url") not in seen:
            seen.add(b.get("url"))
            out.append(b)
    return out


_WAIT_RE = re.compile(r"try again in (?:(\d+)h)?(?:(\d+)m)?([\d.]+)(ms|s)", re.I)
_DAILY_RE = re.compile(r"per day|\bTPD\b|\bRPD\b", re.I)
_TOOL_FAIL_RE = re.compile(r"tool call validation failed|tool_use_failed|failed to call a function", re.I)


def _wait_seconds(err_text):
    m = _WAIT_RE.search(err_text)
    if not m:
        return 2.0
    h, mins, val, unit = m.groups()
    return int(h or 0) * 3600 + int(mins or 0) * 60 + float(val) / (1000 if unit.lower() == "ms" else 1)


def _create_with_rate_limit(client, kwargs, tries=3):
    """Call the chat model with the provider's limits in mind. Returns (response, model used).

    * short per-minute limit: wait as long as the provider asks (up to AI_MAX_WAIT_SECONDS) and retry;
    * daily quota (or a long wait): remember the model is used up until it resets, move to the backup model;
    * a malformed tool call (the model misspelt a tool): retry once, then try the backup model;
    * weak internet: one more try.
    Raises AIUnavailable(kind="quota", retry_after=...) when every model is used up.
    """
    import time

    from openai import APIConnectionError, BadRequestError, RateLimitError

    max_wait = getattr(settings, "AI_MAX_WAIT_SECONDS", 30)
    models = [m for m in chat_models() if not exhausted_for(m)]
    if kwargs.get("model") in models:  # keep the model this turn started with, if it is still usable
        models.remove(kwargs["model"])
        models.insert(0, kwargs["model"])
    if not models:
        wait = min((exhausted_for(m) for m in chat_models()), default=0)
        raise AIUnavailable("all models used up", kind="quota", retry_after=wait)
    last = None
    for m in models:
        kw = {**kwargs, "model": m}
        for attempt in range(tries):
            try:
                return client.chat.completions.create(**kw), m
            except APIConnectionError as e:
                last = AIUnavailable("connection", kind="error")
                if attempt >= 1:
                    break
                time.sleep(1.5)
            except BadRequestError as e:
                if _TOOL_FAIL_RE.search(str(e)) and attempt == 0:
                    log.info("model %s sent a bad tool call; retrying", m)
                    continue
                last = AIUnavailable(str(e)[:200], kind="error")
                break
            except RateLimitError as e:
                wait = _wait_seconds(str(e))
                daily = bool(_DAILY_RE.search(str(e)))
                if daily or wait > max_wait:
                    log.warning("model %s used up for %.0f s (%s); trying the next model", m, wait, "daily" if daily else "minute")
                    mark_exhausted(m, wait)
                    if not (last and last.kind == "quota"):  # a daily limit anywhere is the message that matters
                        last = AIUnavailable("quota" if daily else "busy", kind="quota" if daily else "busy", retry_after=wait)
                    break
                if attempt == tries - 1:
                    last = AIUnavailable("busy", kind="busy", retry_after=wait)
                    break
                log.info("rate limited, waiting %.1fs (model %s)", wait, m)
                time.sleep(wait + 0.3)
    if last and last.kind in ("quota", "busy"):
        last.retry_after = min((exhausted_for(m) for m in chat_models()), default=last.retry_after) or last.retry_after
    raise last or AIUnavailable("busy", kind="busy")


# --------------------------------------------------------------------------
# Speech to text (voice messages)
# --------------------------------------------------------------------------
STT_PROMPT = ("Ghar ki tameer. eent, sariya, lanter, bunyad, mistri, cement ki bori, ret, bajri, plaster, tarai, "
              "washroom, kitchen, bedroom, marla, gaz, feet. اینٹ، سریا، لینٹر، بنیاد، مستری، سیمنٹ، ریت، بجری۔")


STT_PROMPT_EN = "House construction in Pakistan: bricks, steel bars, RCC slab, foundation, mistri, cement bags, sand, crush, marla."
_ODD_SCRIPT = re.compile(r"[ऀ-ॿ]|[¿¡ñ]")  # Hindi or Spanish-looking output = wrong language guess


def transcribe(audio: bytes, filename: str = "voice.webm", mime: str = "audio/webm", language: str | None = "ur") -> str:
    """Turn a voice message into text with Whisper.

    language: "ur" (Urdu or Roman-Urdu speakers: comes back in Urdu script) or "en". Passing it stops Whisper
    from guessing — on short clips it guessed Spanish and Hindi.
    """
    client = _client()

    def run(lang):
        kw = {"model": model("stt"), "file": (filename, audio, mime), "temperature": 0,
              "prompt": STT_PROMPT_EN if lang == "en" else STT_PROMPT}
        if lang:
            kw["language"] = lang
        return (client.audio.transcriptions.create(**kw).text or "").strip()

    try:
        text = run(language)
        if _ODD_SCRIPT.search(text) and language != "ur":
            text = run("ur")
    except Exception as e:
        from openai import RateLimitError

        if isinstance(e, RateLimitError):
            raise AIUnavailable("voice quota", kind="quota", retry_after=_wait_seconds(str(e))) from e
        log.exception("transcription failed")
        raise AIUnavailable(str(e)) from e
    return text


# --------------------------------------------------------------------------
# Photo check
# --------------------------------------------------------------------------
class PhotoCheckResult(BaseModel):
    status: Literal["green", "yellow", "red"]
    reason: str = Field(min_length=1, max_length=600)
    confidence: float = Field(ge=0.0, le=1.0)
    tell_mistri: str = Field(max_length=400)
    photo_usable: bool


PHOTO_SCHEMA = {
    "name": "photo_check",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["green", "yellow", "red"]},
            "reason": {"type": "string"},
            "confidence": {"type": "number"},
            "tell_mistri": {"type": "string"},
            "photo_usable": {"type": "boolean"},
        },
        "required": ["status", "reason", "confidence", "tell_mistri", "photo_usable"],
        "additionalProperties": False,
    },
}


def photo_prompt(item_title: str, look_for: str, rule_line: str, facts: dict, language: str, measurements: dict | None) -> str:
    return f"""You check ONE construction photo from a small single-storey brick building site in Pakistan.

CHECKLIST ITEM: {item_title}
RULE: {rule_line}
WHAT TO LOOK FOR: {look_for}
PROJECT FACTS: {json.dumps(facts, ensure_ascii=False, default=str)}
USER READINGS (may be empty): {json.dumps(measurements or {}, ensure_ascii=False)}

Return ONLY a JSON object with exactly these keys:
{{"status": "green"|"yellow"|"red", "reason": string, "confidence": number 0-1, "tell_mistri": string, "photo_usable": boolean}}
- status: "green" = no problem seen in this photo for this item; "red" = a problem against the rule is clearly visible;
  "yellow" = cannot tell (blurry, dark, wrong subject, tape unreadable, or partly OK).
- reason: one or two short sentences on what you saw. Never say "safe" or "approved".
- confidence: how sure you are of the status.
- tell_mistri: one short sentence the owner can say to the mistri (empty if green). {LANG_INSTRUCTION.get(language, '')}
  Write "reason" in the same language.
- photo_usable: false if the photo does not show the item.
If you are unsure, choose yellow. A wrong green is the worst mistake."""


def check_photo(
    *, image_bytes: bytes, mime: str, item_title: str, look_for: str, rule_line: str, facts: dict, language: str,
    measurements: dict | None = None,
) -> PhotoCheckResult:
    """Send one photo + its rule to the vision model and validate the fixed JSON reply."""
    client = _client()
    data_url = f"data:{mime or 'image/jpeg'};base64,{base64.b64encode(image_bytes).decode()}"
    prompt = photo_prompt(item_title, look_for, rule_line, facts, language, measurements)
    # Groq vision models support JSON mode; OpenAI supports a strict schema. Pydantic checks both.
    fmt = {"type": "json_object"} if provider() == "groq" else {"type": "json_schema", "json_schema": PHOTO_SCHEMA}
    try:
        resp = client.chat.completions.create(
            model=model("vision"),
            temperature=0,
            response_format=fmt,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }],
        )
        raw = resp.choices[0].message.content or ""
    except Exception as e:
        log.exception("photo check call failed")
        raise AIUnavailable(str(e)) from e
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip()).strip()
    try:
        result = PhotoCheckResult.model_validate_json(raw)
    except ValidationError as e:
        log.warning("photo check reply rejected by schema: %s", raw[:300])
        raise AIUnavailable(f"AI reply did not match the required format: {e.errors()[:1]}") from e
    result.reason = guard_reply(result.reason, language)
    return result
