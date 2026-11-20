from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from core import ai_service
from core.models import AIUsage
from projects.views import get_project

from .service import handle_message, start

MAX_AUDIO_BYTES = 6 * 1024 * 1024
AUDIO_TYPES = {"audio/webm", "audio/ogg", "audio/mp4", "audio/mpeg", "audio/wav", "audio/x-wav", "audio/aac", "audio/m4a",
               "video/webm", "application/octet-stream"}
NO_VOICE = {
    "roman": "Awaz ke liye server par GROQ_API_KEY chahiye. Abhi likh kar poochein.",
    "ur": "آواز کے لیے سرور پر GROQ_API_KEY چاہیے۔ ابھی لکھ کر پوچھیں۔",
    "en": "Voice needs GROQ_API_KEY on the server. Please type for now.",
}
NOT_HEARD = {
    "roman": "Awaz samajh nahi aayi. Dobara thora qareeb se bolein.",
    "ur": "آواز سمجھ نہیں آئی۔ دوبارہ تھوڑا قریب سے بولیں۔",
    "en": "I could not hear that. Please speak again, a little closer.",
}


def _payload(msg, project, was_onboarded):
    return {
        "ok": True, "text": msg.text, "source": msg.get_source_display(), "lang": msg.language,
        "speak": msg.meta.get("speak") or ai_service.speech_text(msg.text), "ui": msg.meta.get("ui", []),
        "onboarded_now": project.onboarded and not was_onboarded,
    }


@login_required
def chat(request, project_id):
    project = get_project(request, project_id)
    start(project)
    return render(request, "chatbot/chat.html", {
        "project": project, "chat_messages": project.messages.all(), "ai_on": ai_service.ai_available(),
        "voice_on": ai_service.voice_available(), "provider": ai_service.provider(),
        "max_seconds": settings.VOICE_MAX_SECONDS,
        "languages": project.LANGUAGE_CHOICES, "voice_languages": project.VOICE_LANGUAGE_CHOICES,
    })


@login_required
@require_POST
def set_language(request, project_id):
    """Save the typing language and the speaking language (also the user's default for new projects)."""
    project = get_project(request, project_id)
    typing, speaking = request.POST.get("language"), request.POST.get("voice_language")
    if typing in dict(project.LANGUAGE_CHOICES):
        project.language = typing
        request.user.language = typing
        request.user.save(update_fields=["language"])
    if speaking in dict(project.VOICE_LANGUAGE_CHOICES):
        project.voice_language = speaking
    project.save(update_fields=["language", "voice_language"])
    return JsonResponse({"ok": True, "language": project.language, "voice_language": project.voice_language})


@login_required
@require_POST
def send(request, project_id):
    project = get_project(request, project_id)
    text = request.POST.get("text", "").strip()
    if not text:
        return JsonResponse({"ok": False, "error": "empty"}, status=400)
    was = project.onboarded
    msg = handle_message(project, request.user, text)
    project.refresh_from_db()
    if request.headers.get("Accept", "").startswith("application/json"):
        return JsonResponse(_payload(msg, project, was))
    return redirect("chat", project_id=project.pk)


@login_required
@require_POST
def voice(request, project_id):
    """A recorded voice message: Whisper turns it into text, then it is handled like a typed message."""
    project = get_project(request, project_id)
    lang = project.language
    if not ai_service.voice_available():
        return JsonResponse({"ok": False, "error": NO_VOICE.get(lang, NO_VOICE["en"])}, status=503)
    audio = request.FILES.get("audio")
    if not audio or audio.size == 0:
        return JsonResponse({"ok": False, "error": NOT_HEARD.get(lang, NOT_HEARD["en"])}, status=400)
    if audio.size > MAX_AUDIO_BYTES:
        return JsonResponse({"ok": False, "error": "Recording too long."}, status=400)
    mime = (audio.content_type or "audio/webm").split(";")[0]
    if mime not in AUDIO_TYPES:
        return JsonResponse({"ok": False, "error": f"Unsupported audio type {mime}"}, status=400)
    if not AIUsage.take(request.user):
        return JsonResponse({"ok": False, "error": "Today's AI limit is used up."}, status=429)
    ext = {"audio/ogg": "ogg", "audio/mp4": "m4a", "audio/m4a": "m4a", "audio/mpeg": "mp3", "audio/wav": "wav",
           "audio/x-wav": "wav", "audio/aac": "aac"}.get(mime, "webm")
    try:
        text = ai_service.transcribe(audio.read(), f"voice.{ext}", mime, language=project.voice_language)
    except ai_service.AIUnavailable as e:
        from .service import no_ai_note

        msg = no_ai_note(e, lang) if e.kind == "quota" else NOT_HEARD.get(lang, NOT_HEARD["en"])
        return JsonResponse({"ok": False, "error": msg}, status=502)
    if len(text.strip()) < 2:
        return JsonResponse({"ok": False, "error": NOT_HEARD.get(lang, NOT_HEARD["en"])}, status=400)
    was = project.onboarded
    msg = handle_message(project, request.user, text, voice=True)
    project.refresh_from_db()
    return JsonResponse({**_payload(msg, project, was), "transcript": text})
