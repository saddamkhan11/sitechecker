"""Answers without the AI: used when no API key is set, the AI fails, or the daily limit is reached.

It only repeats rules from the Rules table and numbers from the calculator,
so it can never invent anything.
"""
from projects.models import Rule

from .tools import MATERIAL_Q, calculate_materials, match_rule_ids

NAMES = {
    "roman": {"brick": "Eent", "cement": "Cement", "sand": "Ret", "crush": "Bajri", "steel": "Sariya"},
    "ur": {"brick": "اینٹ", "cement": "سیمنٹ", "sand": "ریت", "crush": "بجری", "steel": "سریا"},
    "en": {"brick": "Bricks", "cement": "Cement", "sand": "Sand", "crush": "Crush", "steel": "Steel"},
}
UNITS = {
    "roman": {"brick": "adad", "cement": "bori", "sand": "cft", "crush": "cft", "steel": "kg"},
    "ur": {"brick": "عدد", "cement": "بوری", "sand": "مکعب فٹ", "crush": "مکعب فٹ", "steel": "کلو"},
    "en": {"brick": "nos", "cement": "bags", "sand": "cft", "crush": "cft", "steel": "kg"},
}
TEXT = {
    "roman": {
        "rules": "Rules table ke mutabiq:",
        "materials": "Aap ke naqshe ke hisaab se andaaza (wastage samet):",
        "none": "Is sawal ka jawab Rules table mein nahi mila. Baraye meharbani engineer se poochein. Mojooda stage ({stage}) ke rules 'Rules' page par dekhein.",
        "cost": "Kul lagat: Rs {total:,}",
        "no_rates": "Lagat ke liye Materials page par rates likhein.",
    },
    "ur": {
        "rules": "رولز ٹیبل کے مطابق:",
        "materials": "آپ کے نقشے کے حساب سے اندازہ (ضیاع سمیت):",
        "none": "اس سوال کا جواب رولز ٹیبل میں نہیں ملا۔ براہ مہربانی انجینئر سے پوچھیں۔ موجودہ مرحلے ({stage}) کے رولز 'Rules' صفحے پر دیکھیں۔",
        "cost": "کل لاگت: {total:,} روپے",
        "no_rates": "لاگت کے لیے Materials صفحے پر ریٹ لکھیں۔",
    },
    "en": {
        "rules": "From the Rules table:",
        "materials": "Estimate from your plan (wastage included):",
        "none": "The Rules table does not answer this. Please ask an engineer. See the rules for the current stage ({stage}) on the Rules page.",
        "cost": "Total cost: Rs {total:,}",
        "no_rates": "Enter rates on the Materials page to see the cost.",
    },
}


def reply(project, text, language):
    lang = language if language in TEXT else "roman"
    tx = TEXT[lang]
    parts = []
    ids = match_rule_ids(text)

    if is_material_question(text):
        data = calculate_materials(project)
        if "materials" in data:
            lines = [tx["materials"]]
            for k, v in data["materials"].items():
                lines.append(f"- {NAMES[lang][k]}: {v:,} {UNITS[lang][k]}")
            cost = data["cost_pkr"]
            lines.append(tx["no_rates"] if cost["missing"] else tx["cost"].format(total=cost["total"]))
            parts.append("\n".join(lines))
            return "\n\n".join(parts), ["calculate_materials"]

    rules = [r for r in (Rule.objects.filter(rule_id=i).first() for i in ids[:2]) if r]
    if rules:
        body = [tx["rules"]]
        for r in rules:
            body.append(f"[{r.rule_id}] {r.text_for('ur' if lang == 'ur' else 'en')}")
        return "\n".join(body), [r.rule_id for r in rules]
    return tx["none"].format(stage=project.stage_name(language=lang)), []


_RULE_WORDS = ("fasla", "faasla", "spacing", "gap", "mota", "motai", "thick", "gehr", "depth", "din", "days", "ghant", "hour",
               "minute", "mix", "ratio", "nisbat", "farma", "inch", "der ", "der?", "bhig", "soak",
               "فاصل", "موٹ", "گہر", "دن", "نسبت", "دیر", "بھگو")


def is_material_question(text):
    """'kitni eent lagengi?' is a calculator question; 'sariye ka fasla kitna?' is a rule question."""
    t = (text or "").lower()
    if not MATERIAL_Q.search(t) or not _asks_material(t):
        return False
    return not any(w in t for w in _RULE_WORDS)


def _asks_material(t):
    return any(w in t for w in ("eent", "brick", "cement", "seemint", "bori", "ret ", "sand", "bajri", "crush", "sariya", "steel",
                                "اینٹ", "سیمنٹ", "ریت", "بجری", "سریا", "material", "maal", "lagat", "cost", "kharch"))
