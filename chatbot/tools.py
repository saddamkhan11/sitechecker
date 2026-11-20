"""The two tools the AI may call. Both run our own Python code."""
import re

from django.db.models import Q

from projects.models import Rule

# Roman Urdu / Urdu / English words -> rule IDs. Used by lookup_rule and by the offline fallback.
KEYWORDS = [
    (r"gehr|gehra|gehrai|depth|deep|گہر", ["FND-01"]),
    (r"khudai|khodai|trench|کھدائی", ["FND-01", "FND-02"]),
    (r"chaura|chaurai|chorai|width|wide|چوڑ", ["FND-02"]),
    (r"\bpcc\b|concrete bed|پی سی سی", ["FND-03"]),
    (r"foundation (brick|chunai)|bunyad (ki )?(chunai|chinai|deewar)", ["FND-04"]),
    (r"plinth|kursi|کرسی|پلنتھ", ["PLN-01"]),
    (r"\bdpc\b|nami|seelan|damp|ڈی پی سی|سیلن", ["PLN-02"]),
    (r"bhigo|bhigon|bhego|soak|bheeg|بھگو|بھیگ", ["WALL-02"]),
    (r"\bjoint|\bjor\b|\bjorr\b|jod|جوڑ", ["WALL-03", "WALL-05"]),
    (r"seedh|plumb|sahul|tilt|jhukav|vertical|ساہل|جھکاؤ", ["WALL-04"]),
    (r"ek din|aik din|per day|one day|roz(ana)? kitn|ایک دن", ["WALL-06"]),
    (r"masal|mortar|مسال", ["WALL-07"]),
    (r"deewar.{0,20}(motai|mota|thick)|wall thick|دیوار.{0,10}موٹ", ["WALL-01"]),
    (r"lintel|lintal|لنٹل", ["OPN-01", "OPN-02", "OPN-03"]),
    (r"sariy|sariye|sarya|steel|\bbars?\b|سری", ["SST-01", "SST-02"]),
    (r"cover|کور", ["SST-03"]),
    (r"ball[iy]|bali|props?|بلی|بلیاں", ["SST-04", "SLB-05"]),
    (r"shutter|شٹرنگ", ["SST-06"]),
    (r"lanter.{0,20}(mota|motai|thick)|slab thick|لینٹر.{0,10}موٹ", ["SLB-01"]),
    (r"mix|mixture|farma|ratio|nisbat|مکسچر|فرما|نسبت", ["SLB-02"]),
    (r"ek (hi )?baar|one go|continuous|beech mein|رات", ["SLB-03"]),
    (r"vibrat|compact|honeycomb|dabana|وائبریٹر", ["SLB-04"]),
    (r"tarai|taraai|curing|cure|pani (dena|lagana|dalna)|ترائی|کیورنگ", ["CUR-01", "CUR-02"]),
    (r"plaster|palastar|پلستر", ["PLS-01", "PLS-03"]),
    (r"gaz|straight edge|level|hamwar|ہموار", ["PLS-02"]),
    (r"diagonal|wattar|watar|kon[ae]|corner|square|وتر|کون", ["LAY-01"]),
    (r"chuna|choona|doori|dori|string|nishan|peg|khunt|چونا|ڈوری|نشان", ["LAY-03"]),
    (r"darwaz|door|دروازہ", ["PLAN-06", "PLAN-02"]),
    (r"khirk|window|کھڑکی", ["PLAN-03", "PLAN-02"]),
    (r"green|hara|ہرا|result", ["GEN-01"]),
    (r"nali|naali|drain|pipe|paip|dhalan|dhalwan|slope|ڈھلوان|نالی|پائپ", ["PLB-01", "PLB-02"]),
    (r"waterproof|water proof|واٹر ?پروف", ["PLB-03"]),
    (r"commode|kamod|seat|w\.?c\b|کموڈ", ["PLB-04"]),
    (r"water test|pani bhar|leak|risao|rasao|رساؤ", ["PLB-05"]),
    (r"trap|gully|gutter|badbu|smell|ٹریپ|گٹر|بدبو", ["PLB-06"]),
    (r"roshandan|ventilat|exhaust|روشن ?دان", ["PLAN-08"]),
    (r"marla|مرلہ", ["PLOT-MARLA"]),
]

MATERIAL_Q = re.compile(
    r"kitn[aie]|kitne|how (many|much)|quantity|material|maal\b|bori|bag|kharch|cost|lagat|کتن|بوری|خرچ|لاگت",
    re.I,
)
RULE_ID_RE = re.compile(r"\b([A-Z]{2,5}(?:-[A-Z0-9]+)+)\b")


def match_rule_ids(text: str) -> list[str]:
    """Rule IDs whose keywords appear in the text, best match first."""
    t = (text or "").lower()
    scores = {}
    for pattern, ids in KEYWORDS:
        if re.search(pattern, t):
            for i, rid in enumerate(ids):
                scores[rid] = scores.get(rid, 0) + (2 if i == 0 else 1)
    return [rid for rid, _ in sorted(scores.items(), key=lambda kv: -kv[1])]


def rule_payload(rule: Rule) -> dict:
    return {
        "rule_id": rule.rule_id, "stage": rule.category, "title": rule.title,
        "value": float(rule.value) if rule.value is not None else None, "unit": rule.unit,
        "text_en": rule.text_en, "text_ur": rule.text_ur, "engineer_reviewed": rule.engineer_reviewed,
    }


def lookup_rule(query: str, limit: int = 5) -> list[dict]:
    query = (query or "").strip()
    ids = [m.upper() for m in RULE_ID_RE.findall(query.upper())]
    found = list(Rule.objects.filter(rule_id__in=ids)) if ids else []
    if not found:
        for rid in match_rule_ids(query):
            r = Rule.objects.filter(rule_id=rid).first()
            if r:
                found.append(r)
    if not found:
        words = [w for w in re.findall(r"[a-zA-Z]{4,}", query)]
        q = Q()
        for w in words:
            q |= Q(title__icontains=w) | Q(text_en__icontains=w)
        if words:
            found = list(Rule.objects.filter(q)[:limit])
    return [rule_payload(r) for r in found[:limit]]


def calculate_materials(project) -> dict:
    from calculator.service import build_estimate

    est = build_estimate(project)
    if est is None:
        return {"error": "The project has no room size yet."}
    return {
        "plan_version": est.plan_version,
        "materials": est.materials,
        "units": est.quantities.get("units"),
        "by_section": est.quantities.get("sections"),
        "cost_pkr": est.cost,
        "rates_used": est.rates_used,
        "notes": est.quantities.get("notes"),
    }


def handlers_for(project):
    return {
        "lookup_rule": lambda args: lookup_rule(args.get("query", "")),
        "calculate_materials": lambda args: calculate_materials(project),
    }
