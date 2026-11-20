from django import template

from core.i18n import DEFAULT_UI, pick
from core.i18n import tr as _tr

register = template.Library()


def _lang(context, fallback=None):
    return context.get("ui_lang") or fallback or DEFAULT_UI


@register.filter
def get(d, key):
    try:
        return d.get(key)
    except AttributeError:
        return None


@register.filter
def pick_lang(d, language):
    """Pick the text for a language from a dict with en/roman/ur keys (no 'both')."""
    if not isinstance(d, dict):
        return d
    return d.get(language) or d.get("roman") or d.get("en")


@register.filter
def ft_in(inches):
    """144 -> 12'-0\""""
    try:
        total = round(float(inches))
    except (TypeError, ValueError):
        return ""
    return f"{total // 12}'-{total % 12}\""


@register.filter
def rs(value):
    try:
        return f"Rs {int(round(float(value))):,}"
    except (TypeError, ValueError):
        return "-"


@register.filter
def rs_short(value):
    """Rs 1,175,000 -> Rs 11.8 lakh (short enough for a small card)."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "-"
    if v >= 10_000_000:
        return f"Rs {v / 10_000_000:.2f} crore"
    if v >= 100_000:
        return f"Rs {v / 100_000:.1f} lakh"
    return f"Rs {int(round(v)):,}"


@register.simple_tag(takes_context=True)
def t(context, language, en, roman, ur=""):
    """{% t lang "English" "Roman Urdu" "اردو" %} - follows the website language (English, Urdu, both, Roman)."""
    return pick(en, roman, ur, _lang(context, language))


@register.simple_tag(takes_context=True)
def tr(context, text):
    """{% tr "English text" %} - translated from core/i18n.py."""
    return _tr(text, _lang(context))


@register.simple_tag(takes_context=True)
def tdict(context, d):
    """A dict with en/roman/ur keys (plan findings, scope messages)."""
    if not isinstance(d, dict):
        return d
    return pick(d.get("en", ""), d.get("roman", ""), d.get("ur", ""), _lang(context))


@register.simple_tag(takes_context=True)
def tfield(context, obj, base):
    """{% tfield item "title" %} -> item.title_en / item.title_ur by website language."""
    en = getattr(obj, f"{base}_en", "") or ""
    ur = getattr(obj, f"{base}_ur", "") or ""
    lang = _lang(context)
    if lang in ("ur",):
        return ur or en
    if lang == "both":
        return f"{en} · {ur}" if ur else en
    return en  # English and Roman Urdu readers get the English text (no Roman version stored)


@register.simple_tag(takes_context=True)
def stage(context, project, code=None):
    lang = _lang(context)
    if lang == "both":
        return f"{project.stage_name(code, 'en')} · {project.stage_name(code, 'ur')}"
    return project.stage_name(code, lang)


@register.simple_tag(takes_context=True)
def lang_class(context):
    """'urdu' when the page is in Urdu only, for RTL and the Nastaliq font."""
    return "urdu" if _lang(context) == "ur" else ""
