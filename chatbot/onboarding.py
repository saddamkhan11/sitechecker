"""Starting questions used when no AI key is set (with an AI key the agent asks them conversationally).

Steps: 0 city, 1 what to build, 2 size (room size, or plot size for a house), 3 rooms (house only),
4 wall type, 5 roof type, 6 budget, 7 start date -> 8 done.
Deterministic code: the answers create the project, so they must be exact.
"""
import datetime as dt
import re

from django.utils import timezone

from projects.scope import check_room

URDU_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

Q = {
    "roman": {
        0: "Assalam o alaikum! Main aap ki tameer mein madad karunga. Pehle chand sawal.\n\nAap kis sheher mein bana rahe hain? (misal: Karachi)",
        1: "Kya banana hai?\n1) Ek kamra\n2) Washroom\n3) Kitchen\n4) Ghar (kayi kamre, khali plot se)",
        "2room": "Andar ka size kya hai? Lambai x chaurai feet mein (misal: 12x14).",
        "2house": "Plot ka size? (misal: 30x60 feet, 5 marla, 120 gaz) — ya 'pata nahi'.",
        3: "Kaun kaun se kamre chahiye? (misal: 2 bedroom, 1 kitchen, 1 washroom, 1 drawing). Size bhi likh sakte hain: bedroom 12x14.",
        4: "Deewar kis cheez ki hogi?\n1) Eent (brick)\n2) Block\n3) Kuch aur",
        5: "Chhat kaisi hogi?\n1) RCC lanter (concrete slab)\n2) Garder / T-iron\n3) Tin ki chadar / kuch aur",
        6: "Aap ka budget kitna hai? (misal: 8 lakh, ya 'pata nahi')",
        7: "Kaam kab shuru karna hai? (misal: 2026-12-01, 'aaj' ya 'kal')",
    },
    "ur": {
        0: "السلام علیکم! میں آپ کی تعمیر میں مدد کروں گا۔ پہلے چند سوال۔\n\nآپ کس شہر میں بنا رہے ہیں؟ (مثال: کراچی)",
        1: "کیا بنانا ہے؟\n1) ایک کمرہ\n2) واش روم\n3) کچن\n4) گھر (کئی کمرے، خالی پلاٹ سے)",
        "2room": "اندر کا سائز کیا ہے؟ لمبائی x چوڑائی فٹ میں (مثال: 12x14)",
        "2house": "پلاٹ کا سائز؟ (مثال: 30x60 فٹ، 5 مرلہ، 120 گز) — یا 'پتا نہیں'",
        3: "کون کون سے کمرے چاہییں؟ (مثال: 2 بیڈروم، 1 کچن، 1 واش روم، 1 ڈرائنگ)۔ سائز بھی لکھ سکتے ہیں: بیڈروم 12x14",
        4: "دیوار کس چیز کی ہوگی؟\n1) اینٹ\n2) بلاک\n3) کچھ اور",
        5: "چھت کیسی ہوگی؟\n1) آر سی سی لینٹر\n2) گارڈر / ٹی آئرن\n3) ٹین کی چادر / کچھ اور",
        6: "آپ کا بجٹ کتنا ہے؟ (مثال: 8 لاکھ، یا 'پتا نہیں')",
        7: "کام کب شروع کرنا ہے؟ (مثال: 2026-12-01، 'آج' یا 'کل')",
    },
    "en": {
        0: "Hello! I will help you build. First, a few questions.\n\nWhich city are you building in? (e.g. Karachi)",
        1: "What do you want to build?\n1) One room\n2) Washroom\n3) Kitchen\n4) House (several rooms, from an empty plot)",
        "2room": "What is the inside size? Length x width in feet (e.g. 12x14).",
        "2house": "Plot size? (e.g. 30x60 ft, 5 marla, 120 sq yards) — or 'don't know'.",
        3: "Which rooms do you need? (e.g. 2 bedroom, 1 kitchen, 1 washroom, 1 living). You can add sizes: bedroom 12x14.",
        4: "What will the walls be made of?\n1) Brick\n2) Block\n3) Something else",
        5: "What kind of roof?\n1) RCC slab (lanter)\n2) Girder / T-iron\n3) Tin sheet / other",
        6: "What is your budget in rupees? (e.g. 8 lakh, or 'don't know')",
        7: "When will work start? (e.g. 2026-12-01, 'today' or 'tomorrow')",
    },
}

RETRY = {
    "roman": {0: "Sheher ka naam likhein, misal: Karachi.", 1: "1, 2, 3 ya 4 likhein.",
              "2room": "Size samajh nahi aaya. Is tarah likhein: 12x14 (feet mein).",
              "2house": "Plot ka size samajh nahi aaya. Misal: 30x60, 5 marla, 120 gaz ya 'pata nahi'.",
              3: "Kamre samajh nahi aaye. Misal: 2 bedroom, 1 kitchen, 1 washroom.",
              6: "Budget samajh nahi aaya. Misal: 8 lakh, 750000, ya 'pata nahi'.",
              7: "Tareekh samajh nahi aayi. Misal: 2026-12-01, 01-12-2026, 'aaj' ya 'kal'."},
    "ur": {0: "شہر کا نام لکھیں، مثال: کراچی۔", 1: "1، 2، 3 یا 4 لکھیں۔",
           "2room": "سائز سمجھ نہیں آیا۔ اس طرح لکھیں: 12x14 (فٹ میں)",
           "2house": "پلاٹ کا سائز سمجھ نہیں آیا۔ مثال: 30x60، 5 مرلہ، 120 گز یا 'پتا نہیں'",
           3: "کمرے سمجھ نہیں آئے۔ مثال: 2 بیڈروم، 1 کچن، 1 واش روم",
           6: "بجٹ سمجھ نہیں آیا۔ مثال: 8 لاکھ، 750000، یا 'پتا نہیں'",
           7: "تاریخ سمجھ نہیں آئی۔ مثال: 2026-12-01، 'آج' یا 'کل'"},
    "en": {0: "Please type the city name, e.g. Karachi.", 1: "Type 1, 2, 3 or 4.",
           "2room": "I could not read the size. Type it like 12x14 (feet).",
           "2house": "I could not read the plot size. E.g. 30x60, 5 marla, 120 sq yards or 'don't know'.",
           3: "I could not read the rooms. E.g. 2 bedroom, 1 kitchen, 1 washroom.",
           6: "I could not read the budget. E.g. 8 lakh, 750000, or 'don't know'.",
           7: "I could not read the date. E.g. 2026-12-01, 'today' or 'tomorrow'."},
}

NOT_BRICK = {
    "roman": "Yeh app sirf eent ki deewar ke liye hai [SCOPE-03]. Doosri deewar ke liye engineer zaroori hai. Agar eent ki deewar banayenge to 1 likhein.",
    "ur": "یہ ایپ صرف اینٹ کی دیوار کے لیے ہے [SCOPE-03]۔ دوسری دیوار کے لیے انجینئر ضروری ہے۔ اگر اینٹ کی دیوار بنائیں گے تو 1 لکھیں۔",
    "en": "This app only covers brick walls [SCOPE-03]. Any other wall needs an engineer. Type 1 if you will build with brick.",
}
NOT_RCC = {
    "roman": "Yeh app sirf RCC lanter ke liye hai [SCOPE-03]. Doosri chhat ke liye engineer zaroori hai. Agar RCC lanter dalenge to 1 likhein.",
    "ur": "یہ ایپ صرف آر سی سی لینٹر کے لیے ہے [SCOPE-03]۔ دوسری چھت کے لیے انجینئر ضروری ہے۔ اگر لینٹر ڈالیں گے تو 1 لکھیں۔",
    "en": "This app only covers an RCC slab roof [SCOPE-03]. Any other roof needs an engineer. Type 1 if you will pour an RCC slab.",
}
RESIZE = {
    "roman": "\nChhota size likhein (misal: 12x14) ya engineer se design karwayein.",
    "ur": "\nچھوٹا سائز لکھیں (مثال: 12x14) یا انجینئر سے ڈیزائن کروائیں۔",
    "en": "\nType a smaller size (e.g. 12x14) or get an engineer's design.",
}
TYPES = {"1": "room", "2": "washroom", "3": "kitchen", "4": "house"}

ROOM_WORDS = [
    (r"bed ?rooms?|bed|sone ka kamra|بیڈ ?روم", "bedroom"),
    (r"drawing|lounge|living|baithak|sitting|ڈرائنگ|لاؤنج|بیٹھک", "living"),
    (r"kitchen|kichen|bawarchi|کچن|باورچی", "kitchen"),
    (r"wash ?rooms?|bath ?rooms?|bath|toilet|ghusl|ghusal|latrine|واش ?روم|باتھ ?روم|غسل|ٹوائلٹ", "washroom"),
    (r"store|stor|سٹور|اسٹور", "store"),
    (r"kamr[ae]|rooms?|کمر[ہے]", "bedroom"),
]
NUM_WORDS = {"ek": 1, "aik": 1, "one": 1, "do": 2, "two": 2, "teen": 3, "three": 3, "char": 4, "chaar": 4, "four": 4,
             "panch": 5, "five": 5, "ایک": 1, "دو": 2, "تین": 3, "چار": 4, "پانچ": 5}


def first_question(language):
    return Q.get(language, Q["roman"])[0]


def _norm(text):
    return (text or "").translate(URDU_DIGITS).strip()


def parse_size(text):
    t = _norm(text).lower().replace("feet", "").replace("ft", "").replace("فٹ", "")
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:'\s*(\d+(?:\.\d+)?)\s*\"?)?\s*(?:x|\*|×|by|se|بائی|ضرب)\s*(\d+(?:\.\d+)?)\s*(?:'\s*(\d+(?:\.\d+)?)\s*\"?)?", t)
    if not m:
        return None
    a = float(m.group(1)) + (float(m.group(2)) / 12 if m.group(2) else 0)
    b = float(m.group(3)) + (float(m.group(4)) / 12 if m.group(4) else 0)
    if not (3 <= a <= 60 and 3 <= b <= 60):
        return None
    return round(max(a, b), 2), round(min(a, b), 2)


def parse_plot(text):
    """'30x60' -> (30, 60) front x depth; '5 marla' / '120 gaz' -> area; 'pata nahi' -> 'unknown'."""
    from plans.layout import plot_from_area
    from projects.models import rule_value, rule_values

    t = _norm(text).lower()
    if re.search(r"pata nahi|pata nhi|nahi pata|don'?t know|skip|پتا نہیں|معلوم نہیں|no idea|nahi", t):
        return "unknown"
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:x|\*|×|by|بائی)\s*(\d+(?:\.\d+)?)", t)
    if m:
        a, b = float(m.group(1)), float(m.group(2))
        if 10 <= a <= 200 and 10 <= b <= 200:
            return {"length_in": min(a, b) * 12, "width_in": max(a, b) * 12}
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*(marla|مرلہ|mrla)", t)
    if m:
        return plot_from_area(float(m.group(1)) * rule_value("PLOT-MARLA", 225))
    m = re.search(r"(\d+(?:\.\d+)?)\s*(gaz|yard|yards|sq ?yd|گز)", t)
    if m:
        return plot_from_area(float(m.group(1)) * 9)
    return None


def parse_rooms(text):
    """'2 bedroom, 1 kitchen aur ek washroom, bedroom 12x14' -> list of room specs."""
    from plans.layout import room_spec

    t = _norm(text).lower()
    chunks = re.split(r",|،|\band\b|\baur\b|\bor\b|\+|\bاور\b|\n|;", t)
    specs = []
    for ch in chunks:
        ch = ch.strip()
        if not ch:
            continue
        typ = next((ty for pat, ty in ROOM_WORDS if re.search(pat, ch)), None)
        if not typ:
            continue
        size = parse_size(ch)
        count = 1
        ch_wo_size = re.sub(r"\d+(?:\.\d+)?\s*(?:x|\*|×|by)\s*\d+(?:\.\d+)?", " ", ch)
        m = re.search(r"\b(\d{1,2})\b", ch_wo_size)
        if m:
            count = int(m.group(1))
        else:
            for w, n in NUM_WORDS.items():
                if re.search(rf"(^|\s){w}(\s|$)", ch_wo_size):
                    count = n
                    break
        for i in range(max(1, min(count, 8))):
            s = room_spec(None, typ, *(size if size else (None, None)))
            if count > 1:
                s["name"] = f"{s['name']} {i + 1}"
            specs.append(s)
    return specs[:12]


def parse_wall(text):
    t = _norm(text).lower()
    return "brick" if re.search(r"^\s*1\b|brick|eent|eint|\bint\b|\bent\b|اینٹ", t) else None


def parse_roof(text):
    t = _norm(text).lower()
    return "rcc_slab" if re.search(r"^\s*1\b|rcc|lanter|lenter|linter|lintar|slab|لینٹر|لنٹر|سلیب", t) else None


def parse_type(text):
    t = _norm(text).lower()
    m = re.match(r"\s*([1-4])\b", t)
    if m:
        return TYPES[m.group(1)]
    if re.search(r"ghar|house|makan|plot|مکان|گھر|پلاٹ", t):
        return "house"
    if re.search(r"wash|bath|toilet|ghusl|واش|باتھ|غسل", t):
        return "washroom"
    if re.search(r"kitchen|کچن", t):
        return "kitchen"
    if re.search(r"kamra|room|کمرہ", t):
        return "room"
    return None


def parse_budget(text):
    t = _norm(text).lower().replace(",", "")
    if re.search(r"pata nahi|pata nhi|nahi pata|don'?t know|skip|پتا نہیں|معلوم نہیں|no idea", t):
        return "unknown"
    m = re.search(r"(\d+(?:\.\d+)?)\s*(crore|karor|کروڑ|lakh|lac|lakhs|لاکھ|hazar|hazaar|thousand|k\b|ہزار)?", t)
    if not m:
        return None
    n = float(m.group(1))
    unit = m.group(2) or ""
    if unit in ("crore", "karor", "کروڑ"):
        n *= 10_000_000
    elif unit in ("lakh", "lac", "lakhs", "لاکھ"):
        n *= 100_000
    elif unit in ("hazar", "hazaar", "thousand", "k", "ہزار"):
        n *= 1000
    return int(n) if n >= 10_000 else None


def parse_date(text, today=None):
    t = _norm(text).lower()
    today = today or timezone.localdate()
    if re.search(r"\baaj\b|today|آج", t):
        return today
    if re.search(r"\bkal\b|tomorrow|کل", t):
        return today + dt.timedelta(days=1)
    try:
        m = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", t)
        if m:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        m = re.search(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})", t)
        if m:
            return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None
    return None


def _known(project, step):
    """Is the answer to this step already in the project (for example saved earlier by the AI agent)?"""
    has_plan = project.plans.exists() if project.pk else False
    if step == 0:
        return bool(project.city)
    if step == 1:
        return project.project_type != "room" or has_plan or bool(project.room_length_ft)
    if step == 2:
        return bool(project.plot_length_ft) if project.project_type == "house" else bool(project.room_length_ft) or has_plan
    if step == 3:
        return project.project_type != "house" or has_plan or (project.scope_note or "").startswith("rooms:")
    if step == 4:
        return bool(project.wall_type)
    if step == 5:
        return bool(project.roof_type)
    if step == 6:
        return project.budget_pkr is not None
    if step == 7:
        return project.start_date is not None
    return True


def next_step(project, start=0):
    """First step from `start` whose answer is still missing (8 = all done)."""
    step = start
    while step < project.ONBOARDING_DONE and _known(project, step):
        step += 1
    return step


def resume_question(project, language):
    """Pick up the fixed questions where things stand (used when the AI is not available mid-setup)."""
    project.onboarding_step = next_step(project, 0)
    project.save(update_fields=["onboarding_step"])
    if project.onboarding_step >= project.ONBOARDING_DONE:
        return _finish(project, language)
    return _question(project, project.onboarding_step, language)


def _question(project, step, language):
    q = Q.get(language, Q["roman"])
    if step == 2:
        return q["2house" if project.project_type == "house" else "2room"]
    return q[step]


def summary(project, language, plan_summary=None):
    budget = f"Rs {int(project.budget_pkr):,}" if project.budget_pkr else "-"
    start = project.start_date.isoformat() if project.start_date else "-"
    rooms = ", ".join(f"{r['name']} {r['size_ft']}" for r in (plan_summary or {}).get("rooms", []))
    area = (plan_summary or {}).get("covered_area_sqft")
    if language == "ur":
        return (f"شکریہ! آپ کا پروجیکٹ بن گیا:\nشہر: {project.city}\nکیا: {project.get_project_type_display()}\nکمرے: {rooms}\n"
                f"تعمیر شدہ رقبہ: {area} مربع فٹ\nبجٹ: {budget}\nشروع: {start}\n\nنقشہ، سامان کی فہرست اور مرحلہ وار چیک دیکھیں۔ کوئی بھی سوال پوچھیں۔")
    if language == "en":
        return (f"Thank you! Your project is ready:\nCity: {project.city}\nBuilding: {project.get_project_type_display()}\nRooms: {rooms}\n"
                f"Covered area: {area} sq ft\nBudget: {budget}\nStart: {start}\n\nOpen the plan, the material list and the stage checks. Ask me anything.")
    return (f"Shukriya! Aap ka project ban gaya:\nSheher: {project.city}\nKya: {project.get_project_type_display()}\nKamre: {rooms}\n"
            f"Covered area: {area} sq ft\nBudget: {budget}\nShuru: {start}\n\nNaqsha, material ki list aur stage checks dekhein. Koi bhi sawal poochein.")


def handle(project, text, language):
    """Apply one answer. Returns the reply text and advances project.onboarding_step."""
    retry = RETRY.get(language, RETRY["roman"])
    step = project.onboarding_step

    if step == 0:
        city = re.sub(r"[^\w\s؀-ۿ-]", "", _norm(text)).strip()
        if not city or len(city) > 60 or city.isdigit():
            return retry[0]
        project.city = city.title()
    elif step == 1:
        typ = parse_type(text)
        if not typ:
            return retry[1]
        project.project_type = typ
    elif step == 2:
        if project.project_type == "house":
            plot = parse_plot(text)
            if plot is None:
                return retry["2house"]
            if plot != "unknown":
                project.plot_length_ft = round(plot["length_in"] / 12, 2)
                project.plot_width_ft = round(plot["width_in"] / 12, 2)
        else:
            size = parse_size(text)
            if not size:
                return retry["2room"]
            res = check_room(*size)
            if not res.ok:
                project.scope_note = res.reason_en
                project.save()
                return res.message(language) + RESIZE.get(language, RESIZE["roman"])
            project.room_length_ft, project.room_width_ft = size
            project.scope_note = ""
    elif step == 3:
        specs = parse_rooms(text)
        if not specs:
            return retry[3]
        for s in specs:
            res = check_room(s["length_in"] / 12, s["width_in"] / 12)
            if not res.ok:
                return f"{s['name']}: " + res.message(language) + RESIZE.get(language, RESIZE["roman"])
        project.scope_note = "rooms:" + ";".join(f"{s['type']}|{s['name']}|{s['length_in']}|{s['width_in']}" for s in specs)
    elif step == 4:
        if not parse_wall(text):
            return NOT_BRICK.get(language, NOT_BRICK["roman"])
        project.wall_type = "brick"
    elif step == 5:
        if not parse_roof(text):
            return NOT_RCC.get(language, NOT_RCC["roman"])
        project.roof_type = "rcc_slab"
    elif step == 6:
        budget = parse_budget(text)
        if budget is None:
            return retry[6]
        project.budget_pkr = None if budget == "unknown" else budget
    elif step == 7:
        start = parse_date(text)
        if not start:
            return retry[7]
        project.start_date = start

    project.save()
    # Steps 6 and 7 may be answered "don't know" (left empty), so only look forward from the next step.
    project.onboarding_step = next_step(project, step + 1)
    project.save(update_fields=["onboarding_step"])
    if project.onboarding_step < project.ONBOARDING_DONE:
        return _question(project, project.onboarding_step, language)
    return _finish(project, language)


def _finish(project, language):
    """All answers in: design the first layout, create stages."""
    from plans import geometry
    from plans.layout import auto_layout, room_spec
    from plans.service import PlanRefused, save_plan
    from projects.models import rule_value, rule_values

    wall = rule_value("WALL-01", 9)
    existing = project.latest_plan()
    if existing:  # the AI agent already drew a plan: keep it
        project.wall_type, project.roof_type = project.wall_type or "brick", project.roof_type or "rcc_slab"
        project.onboarding_step = project.ONBOARDING_DONE
        project.in_scope = True
        if project.name in ("", "My room"):
            project.name = project.default_name()
        project.save()
        project.ensure_stages()
        project.refresh_current_stage()
        return summary(project, language, geometry.summary(existing.data))
    if project.project_type == "house":
        specs = []
        for part in (project.scope_note or "").removeprefix("rooms:").split(";"):
            bits = part.split("|")
            if len(bits) == 4:
                specs.append({"type": bits[0], "name": bits[1], "length_in": float(bits[2]), "width_in": float(bits[3])})
        specs = specs or [room_spec(None, "bedroom"), room_spec(None, "kitchen"), room_spec(None, "washroom")]
    else:
        specs = [room_spec(None, project.project_type, project.room_length_ft, project.room_width_ft)]
    plot = ({"length_in": float(project.plot_length_ft) * 12, "width_in": float(project.plot_width_ft) * 12}
            if project.plot_length_ft and project.plot_width_ft else None)
    project.scope_note = ""
    project.in_scope = True
    project.name = project.default_name()
    project.save()
    try:
        plan, _ = save_plan(project, auto_layout(specs, plot, wall, rule_values()))
    except PlanRefused as e:
        # e.g. too much covered area: keep the answers, ask again for rooms
        project.onboarding_step = 3
        project.save()
        return str(e) + RESIZE.get(language, RESIZE["roman"])
    project.ensure_stages()
    project.refresh_current_stage()
    return summary(project, language, geometry.summary(plan.data))
