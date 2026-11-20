from django.conf import settings
from django.http import FileResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .i18n import UI_LANGS
from django.templatetags.static import static


def home(request):
    if request.user.is_authenticated:
        return redirect("project_list")
    return render(request, "home.html")


def offline(request):
    return render(request, "offline.html")


def service_worker(request):
    """Served from the site root so its scope covers every page."""
    resp = FileResponse(open(settings.BASE_DIR / "static" / "js" / "sw.js", "rb"), content_type="application/javascript")
    resp["Service-Worker-Allowed"] = "/"
    resp["Cache-Control"] = "no-cache"
    return resp


def manifest(request):
    return JsonResponse({
        "name": "Construction Checker AI",
        "short_name": "Site Checker",
        "start_url": "/p/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#b45309",
        "lang": "ur",
        "icons": [
            {"src": static("icons/icon.svg"), "sizes": "any", "type": "image/svg+xml", "purpose": "any maskable"},
        ],
    }, content_type="application/manifest+json")


@require_POST
def set_ui_language(request):
    """Website language from the header menu: saved on the user, or in the session before login."""
    lang = request.POST.get("ui_language")
    if lang in UI_LANGS:
        if request.user.is_authenticated:
            request.user.ui_language = lang
            request.user.save(update_fields=["ui_language"])
        else:
            request.session["ui_language"] = lang
    nxt = request.POST.get("next") or "/"
    if not url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        nxt = "/"
    return redirect(nxt)
