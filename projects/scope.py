"""The scope gate. It runs before any AI call.

Version 1 covers ONE single-storey room with brick walls and an RCC slab.
Anything else gets "this needs an engineer" with the reason.
"""
import re
from dataclasses import dataclass

from .models import rule_value

ENGINEER_EN = "This needs an engineer."
ENGINEER_ROMAN = "Is ke liye engineer zaroori hai."
ENGINEER_UR = "اس کے لیے انجینئر ضروری ہے۔"


@dataclass
class ScopeResult:
    ok: bool
    reason_en: str = ""
    reason_roman: str = ""
    reason_ur: str = ""
    rule_id: str = ""

    def message(self, language):
        if self.ok:
            return ""
        if language == "ur":
            return f"{ENGINEER_UR} وجہ: {self.reason_ur} ({self.rule_id})"
        if language == "en":
            return f"{ENGINEER_EN} Reason: {self.reason_en} ({self.rule_id})"
        return f"{ENGINEER_ROMAN} Wajah: {self.reason_roman} ({self.rule_id})"


def check_room(length_ft, width_ft) -> ScopeResult:
    """Room size limits from the Rules table (SCOPE-01 short span, SCOPE-02 long side)."""
    max_span = rule_value("SCOPE-01", 14.0)
    max_long = rule_value("SCOPE-02", 20.0)
    short, long_ = sorted([float(length_ft), float(width_ft)])
    if short > max_span:
        return ScopeResult(
            False,
            f"the room's short side {short:g} ft is more than {max_span:g} ft. A slab of this span needs a beam or a designed slab.",
            f"kamre ki chhoti side {short:g} ft hai jo {max_span:g} ft se zyada hai. Itne bade lanter ke liye beam ya design chahiye.",
            f"کمرے کی چھوٹی سائیڈ {short:g} فٹ ہے جو {max_span:g} فٹ سے زیادہ ہے۔ اتنے بڑے لینٹر کے لیے بیم یا ڈیزائن چاہیے۔",
            "SCOPE-01",
        )
    if long_ > max_long:
        return ScopeResult(
            False,
            f"the room's long side {long_:g} ft is more than {max_long:g} ft.",
            f"kamre ki lambi side {long_:g} ft hai jo {max_long:g} ft se zyada hai.",
            f"کمرے کی لمبی سائیڈ {long_:g} فٹ ہے جو {max_long:g} فٹ سے زیادہ ہے۔",
            "SCOPE-02",
        )
    return ScopeResult(True)


# Keyword groups that are outside Version 1. Matching is on lower-cased text.
_OUT_OF_SCOPE = [
    (
        r"(second|2nd|upper|double)\s*(storey|story|floor)|first floor|dusri manzil|doosri manzil|upar (ek |aik )?(ka |wala )?(kamra|floor|manzil)|"
        r"oopar (ek |aik )?(ka |wala )?(kamra|floor|manzil)|دوسری منزل|اوپر (کا|والا|ایک)? ?(کمرہ|فلور|منزل)",
        "a second storey or a room on top changes the loads on walls and foundation.",
        "dusri manzil ya upar kamra banane se deewaron aur bunyad par wazan badal jata hai.",
        "دوسری منزل یا اوپر کمرہ بنانے سے دیواروں اور بنیاد پر وزن بدل جاتا ہے۔",
        "SCOPE-03",
    ),
    (
        r"\bbeam\b|\bcolumn\b|\bpillar\b|bheem|سٹون|ستون|بیم|کالم|frame structure",
        "beams and columns need a structural design by an engineer.",
        "beam aur column ka design engineer hi kar sakta hai.",
        "بیم اور کالم کا ڈیزائن انجینئر ہی کر سکتا ہے۔",
        "SCOPE-04",
    ),
    (
        r"basement|tehkhana|تہہ خانہ|retaining|underground tank|zameen doz",
        "basements, retaining walls and underground tanks hold back soil and water and need a design.",
        "basement, retaining wall aur zameen doz tank ke liye design chahiye.",
        "تہہ خانہ، ریٹیننگ وال اور زیر زمین ٹینک کے لیے ڈیزائن چاہیے۔",
        "SCOPE-05",
    ),
    (
        r"(crack|daraar|darar|دراڑ)\w*.{0,30}(slab|lanter|lintel|chhat|chat|roof|bunyad|foundation|beam|لینٹر|چھت|بنیاد)|"
        r"(slab|lanter|chhat|chat|roof|bunyad|foundation|لینٹر|چھت|بنیاد).{0,30}(crack|daraar|darar|دراڑ)|"
        r"purani (deewar|chhat|building|imarat)|old (wall|roof|building|house)|jhuk gay|sagging|leaning|پرانی (دیوار|چھت|عمارت)",
        "cracks in a slab or foundation, or movement in an existing building, must be seen by an engineer on site.",
        "lanter ya bunyad mein darar, ya purani building mein jhukav, engineer ko mauqe par dikhayein.",
        "لینٹر یا بنیاد میں دراڑ، یا پرانی عمارت میں جھکاؤ، انجینئر کو موقع پر دکھائیں۔",
        "SCOPE-06",
    ),
    (
        r"commercial|plaza|\bshops?\b|dukaan|dukan|factory|godown|warehouse|school|masjid|mosque|marriage hall|shadi hall|دکان|پلازہ|فیکٹری",
        "commercial and public buildings are outside this app.",
        "commercial ya public building is app ke scope se bahar hai.",
        "کمرشل یا پبلک عمارت اس ایپ کے دائرے سے باہر ہے۔",
        "SCOPE-07",
    ),
    (
        r"is (it|this) safe|safe hai|mehfooz|محفوظ|certify|certificate|approval|approve|guarantee|zamanat",
        "the app never says a structure is safe. Only an engineer on site can certify it.",
        "yeh app kabhi nahi kehti ke structure safe hai. Sirf engineer mauqe par dekh kar certify kar sakta hai.",
        "یہ ایپ کبھی نہیں کہتی کہ عمارت محفوظ ہے۔ صرف انجینئر موقع پر دیکھ کر تصدیق کر سکتا ہے۔",
        "SCOPE-08",
    ),
    (
        r"soft soil|bhurbhuri|daldal|marsh|filled (land|ground)|bharai wali zameen|bharai ki zameen|zameen bharai|bharai ki hui|pani ki satah|water table|نرم مٹی|دلدل",
        "weak or filled soil needs a soil check and a foundation design.",
        "kamzor ya bharai wali zameen ke liye mitti ka test aur bunyad ka design chahiye.",
        "کمزور یا بھرائی والی زمین کے لیے مٹی کا ٹیسٹ اور بنیاد کا ڈیزائن چاہیے۔",
        "SCOPE-09",
    ),
    (
        r"cantilever|chajja|chhajja|balcony|balkoni|چھجا|بالکونی|overhang",
        "cantilevers and balconies need a design for their steel.",
        "chhajja ya balcony ke sariye ka design engineer kare.",
        "چھجے یا بالکونی کے سریے کا ڈیزائن انجینئر کرے۔",
        "SCOPE-10",
    ),
]


def check_question(text: str) -> ScopeResult:
    t = (text or "").lower()
    for pattern, en, roman, ur, rid in _OUT_OF_SCOPE:
        if re.search(pattern, t):
            return ScopeResult(False, en, roman, ur, rid)
    # Room sizes mentioned in a question, like "16x22 ka kamra" (not plot sizes like "30x60 plot")
    if re.search(r"plot|plaat|marla|gaz\b|yard|پلاٹ|مرلہ|گز", t):
        return ScopeResult(True)
    m = re.search(r"(\d{1,3}(?:\.\d+)?)\s*(?:x|\*|by|×|se)\s*(\d{1,3}(?:\.\d+)?)", t)
    if m:
        res = check_room(m.group(1), m.group(2))
        if not res.ok:
            return res
    return ScopeResult(True)
