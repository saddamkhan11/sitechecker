"""Website language: English, Urdu, both side by side, or Roman Urdu.

The site language (menus, buttons, page text) is separate from the chat language:
a user can read the site in "English + اردو" and chat in Roman Urdu.
Strings live in TR below: English -> (Roman Urdu, Urdu). Unknown strings show in English.
"""
UI_LANGS = ("both", "en", "ur", "roman")
DEFAULT_UI = "both"
SEP = " · "

TR = {
    # navigation and common
    "Home": ("Home", "ہوم"), "Chat": ("Chat", "چیٹ"), "Plan": ("Naqsha", "نقشہ"), "Material": ("Material", "سامان"),
    "Checks": ("Checks", "جانچ"), "Diary": ("Diary", "ڈائری"), "Logout": ("Logout", "لاگ آؤٹ"), "Login": ("Login", "لاگ ان"),
    "Language": ("Zaban", "زبان"), "Save": ("Save karein", "محفوظ کریں"), "Back": ("Wapas", "واپس"), "Edit": ("Badlein", "تبدیل کریں"),
    "Stage": ("Stage", "مرحلہ"), "Offline": ("Offline", "آف لائن"), "Show": ("Dikhayein", "دکھائیں"),
    "From": ("Se", "سے"), "To": ("Tak", "تک"), "Total": ("Kul", "کل"), "Date": ("Tareekh", "تاریخ"), "Note": ("Note", "نوٹ"),
    "Delete?": ("Mitayein?", "حذف کریں؟"),
    # home / accounts
    "Construction Checker": ("Construction Checker", "تعمیر چیکر"),
    "Design a single-storey house, one room, a washroom or a kitchen by chat or voice, know the right material and cost, and check the mistri's work stage by stage.":
        ("Ek-manzila ghar, ek kamra, washroom ya kitchen chat ya awaz se design karein, sahi material aur lagat jaanein, aur mistri ka kaam stage-wise check karein.",
         "ایک منزلہ گھر، کمرہ، واش روم یا کچن چیٹ یا آواز سے ڈیزائن کریں، صحیح سامان اور لاگت جانیں، اور مستری کا کام مرحلہ وار چیک کریں۔"),
    "New account": ("Naya account", "نیا اکاؤنٹ"), "Create account": ("Account banayein", "اکاؤنٹ بنائیں"),
    "No account yet?": ("Account nahi hai?", "اکاؤنٹ نہیں ہے؟"), "Already have an account?": ("Pehle se account hai?", "پہلے سے اکاؤنٹ ہے؟"),
    "Chat and voice": ("Chat aur awaz", "چیٹ اور آواز"), "Speak or type; the agent does the work": ("Bol kar ya likh kar; agent khud kaam karta hai", "بول کر یا لکھ کر؛ ایجنٹ خود کام کرتا ہے"),
    "Whole house, rooms, washroom, printable": ("Poora ghar, kamre, washroom, printable", "پورا گھر، کمرے، واش روم، پرنٹ کے قابل"),
    "Bricks, cement, sand, crush, steel": ("Eent, cement, ret, bajri, sariya", "اینٹ، سیمنٹ، ریت، بجری، سریا"),
    "Camera check": ("Camera check", "کیمرہ جانچ"), "Photo check at every stage": ("Har stage par tasveer se jaanch", "ہر مرحلے پر تصویر سے جانچ"),
    "Single-storey building (80 to 1500 sq ft), brick walls, RCC slab. The app never says a structure is \"safe\": it says what it checked and what it found. A bigger or double-storey building needs an engineer.":
        ("Ek-manzila tameer (80 se 1500 sq ft), eent ki deewar, RCC lanter. Yeh app kabhi nahi kehti ke structure \"safe\" hai: yeh batati hai ke kya check kiya aur kya nazar aaya. Bari ya do-manzila tameer ke liye engineer zaroori hai.",
         "ایک منزلہ تعمیر (80 سے 1500 مربع فٹ)، اینٹ کی دیوار، آر سی سی لینٹر۔ یہ ایپ کبھی نہیں کہتی کہ عمارت \"محفوظ\" ہے: یہ بتاتی ہے کہ کیا چیک کیا اور کیا نظر آیا۔ بڑی یا دو منزلہ عمارت کے لیے انجینئر ضروری ہے۔"),
    "Mobile number": ("Mobile number", "موبائل نمبر"), "Mobile number (03xxxxxxxxx)": ("Mobile number (03xxxxxxxxx)", "موبائل نمبر (03xxxxxxxxx)"),
    "Password": ("Password", "پاس ورڈ"), "Your name": ("Aap ka naam", "آپ کا نام"), "Chat language": ("Chat ki zaban", "چیٹ کی زبان"),
    # offline
    "No internet": ("Internet nahi hai", "انٹرنیٹ نہیں ہے"),
    "Photos you took are kept on the phone and upload by themselves when the signal comes back.":
        ("Jo tasveerein aap ne li hain woh phone mein rakhi hain aur signal aate hi khud upload ho jayengi.",
         "جو تصویریں آپ نے لیں وہ فون میں رکھی ہیں اور سگنل آتے ہی خود اپلوڈ ہو جائیں گی۔"),
    "Try again": ("Dobara koshish", "دوبارہ کوشش"),
    # photos
    "Camera": ("Camera", "کیمرہ"), "Gallery": ("Gallery", "گیلری"), "Take photo": ("Tasveer lein", "تصویر لیں"),
    "Live camera": ("Live camera", "لائیو کیمرہ"), "Phone camera": ("Phone camera", "فون کیمرہ"),
    "From gallery (not verified)": ("Gallery se (tasdeeq nahi)", "گیلری سے (تصدیق نہیں)"),
    "Live camera photos get the server time. Gallery photos are marked 'not verified'.":
        ("Live camera ki tasveer par server ka waqt lagta hai. Gallery ki tasveer 'tasdeeq nahi' likhi jati hai.",
         "لائیو کیمرہ کی تصویر پر سرور کا وقت لگتا ہے۔ گیلری کی تصویر 'تصدیق نہیں' لکھی جاتی ہے۔"),
    "Hold the phone steady, then press the round button": ("Phone seedha pakrein, phir gol button dabayein", "فون سیدھا پکڑیں، پھر گول بٹن دبائیں"),
    "Photo from the gallery: its date can not be verified.": ("Gallery ki tasveer: is ki tareekh ki tasdeeq nahi ho sakti.", "گیلری کی تصویر: اس کی تاریخ کی تصدیق نہیں ہو سکتی۔"),
    "days older than the upload: it may be an old photo.": ("din purani hai upload se: shayad purani tasveer ho.", "دن اپلوڈ سے پرانی ہے: شاید پرانی تصویر ہو۔"),
    "Photo (optional)": ("Tasveer (agar ho)", "تصویر (اختیاری)"),
    # plan print / report
    "Download PDF / Print": ("PDF / Print", "پی ڈی ایف / پرنٹ"),
    "In the print dialog choose \"Save as PDF\".": ("Print mein \"Save as PDF\" chunein.", "پرنٹ میں \"Save as PDF\" چنیں۔"),
    "Rooms": ("Kamre", "کمرے"), "Room": ("Kamra", "کمرہ"), "Inside size (ft)": ("Andar ka size (ft)", "اندر کا سائز (فٹ)"),
    "Area": ("Raqba", "رقبہ"), "Doors and windows": ("Darwaze aur khirkiyan", "دروازے اور کھڑکیاں"), "Wall": ("Deewar", "دیوار"),
    "From corner": ("Kone se", "کونے سے"), "Lintel": ("Lintel", "لنٹل"),
    "Construction notes (Rules table)": ("Tameer ke notes (Rules table)", "تعمیری نوٹس (رولز ٹیبل)"),
    "Plan checks": ("Naqsha checks", "نقشے کی جانچ"),
    "This is a setting-out plan, not a structural design. Rules marked pending need engineer review. The app never certifies a structure as safe.":
        ("Yeh nishan-dahi ka naqsha hai, structural design nahi. 'Pending' rules ki engineer review zaroori hai. App kabhi structure ko safe certify nahi karti.",
         "یہ نشان دہی کا نقشہ ہے، اسٹرکچرل ڈیزائن نہیں۔ 'زیر التوا' رولز کا انجینئر جائزہ ضروری ہے۔ ایپ کبھی عمارت کو محفوظ قرار نہیں دیتی۔"),
    "Site report": ("Site report", "سائٹ رپورٹ"), "This period": ("Is muddat mein", "اس مدت میں"), "Total received": ("Kul aaya", "کل آیا"),
    "Estimate": ("Andaza", "اندازہ"), "Used %": ("Istemal %", "استعمال %"), "Payments this period": ("Is muddat ki payments", "اس مدت کی ادائیگیاں"),
    "Material estimate (all)": ("Material ka andaza (kul)", "سامان کا اندازہ (کل)"), "Checks this period": ("Is muddat ke checks", "اس مدت کی جانچ"),
    "No checks in this period.": ("Is muddat mein koi check nahi.", "اس مدت میں کوئی جانچ نہیں۔"),
    "No diary entries in this period.": ("Is muddat mein koi entry nahi.", "اس مدت میں کوئی اندراج نہیں۔"),
    "Stage now": ("Abhi ka stage", "موجودہ مرحلہ"),
    "Photo results mean \"no problem seen in this photo\" — they are not an engineer's approval and never mean \"safe\". Quantities are estimates from the Rules table; rules marked pending need engineer review.":
        ("Tasveer ke nateeje ka matlab \"is tasveer mein masla nazar nahi aaya\" hai — yeh engineer ki manzoori nahi aur kabhi \"safe\" ka matlab nahi. Miqdaar Rules table se andaza hai.",
         "تصویر کے نتیجے کا مطلب \"اس تصویر میں مسئلہ نظر نہیں آیا\" ہے — یہ انجینئر کی منظوری نہیں اور کبھی \"محفوظ\" کا مطلب نہیں۔ مقدار رولز ٹیبل سے اندازہ ہے۔"),
    # rules page
    "Rules table": ("Rules table", "رولز ٹیبل"), "reviewed": ("review shuda", "جائزہ شدہ"), "pending review": ("review baqi", "جائزہ باقی"),
    "These rules come from general practice. Rules not yet reviewed by an engineer say \"pending review\".":
        ("Yeh rules aam tajurbe se hain. Engineer ki review ke baghair rule ke saath \"review baqi\" likha hai.",
         "یہ رولز عام تجربے سے ہیں۔ انجینئر کے جائزے کے بغیر رول کے ساتھ \"جائزہ باقی\" لکھا ہے۔"),
    # statuses and choices shown from the database
    "Not started": ("Shuru nahi hua", "شروع نہیں ہوا"), "In progress": ("Jaari", "جاری"), "Done": ("Mukammal", "مکمل"),
    "Checking...": ("Check ho raha hai...", "جانچ ہو رہی ہے..."), "No problem seen": ("Koi masla nazar nahi aaya", "کوئی مسئلہ نظر نہیں آیا"),
    "Not sure - check again": ("Yaqeen nahi - dobara check karein", "یقین نہیں - دوبارہ چیک کریں"),
    "Problem seen": ("Masla nazar aaya", "مسئلہ نظر آیا"), "Could not check": ("Check nahi ho saka", "جانچ نہیں ہو سکی"),
    "Photo checked by AI": ("Tasveer AI se check", "تصویر اے آئی سے جانچ"),
    "User types measurements, code compares": ("Naap likhein, app muqabla karegi", "پیمائش لکھیں، ایپ موازنہ کرے گی"),
    "Phone tilt sensor held on the wall": ("Phone deewar par rakh kar jhukav", "فون دیوار پر رکھ کر جھکاؤ"),
    "Material received": ("Material aaya", "سامان آیا"), "Payment": ("Payment", "ادائیگی"), "Photo": ("Tasveer", "تصویر"),
    "Bricks (nos)": ("Eent (adad)", "اینٹ (عدد)"), "Cement (bags)": ("Cement (bori)", "سیمنٹ (بوری)"), "Sand (cft)": ("Ret (cft)", "ریت (مکعب فٹ)"),
    "Crush (cft)": ("Bajri (cft)", "بجری (مکعب فٹ)"), "Steel (kg)": ("Sariya (kg)", "سریا (کلو)"), "Other": ("Kuch aur", "دیگر"),
    "Mistri / labour": ("Mistri / mazdoori", "مستری / مزدوری"), "Transport": ("Transport / kiraya", "ٹرانسپورٹ / کرایہ"),
    "Bricks": ("Eent", "اینٹ"), "Cement": ("Cement", "سیمنٹ"), "Sand": ("Ret", "ریت"), "Crush (bajri)": ("Bajri", "بجری"), "Steel (sariya)": ("Sariya", "سریا"),
    "brick": ("Eent", "اینٹ"), "cement": ("Cement", "سیمنٹ"), "sand": ("Ret", "ریت"), "crush": ("Bajri", "بجری"), "steel": ("Sariya", "سریا"),
    "One room": ("Ek kamra", "ایک کمرہ"), "Washroom": ("Washroom", "واش روم"), "Kitchen": ("Kitchen", "کچن"),
    "Single-storey house": ("Ek-manzila ghar", "ایک منزلہ گھر"),
    "Bedroom": ("Bedroom", "بیڈروم"), "Living room": ("Drawing / lounge", "لاؤنج"), "Store": ("Store", "سٹور"),
    "Scope gate": ("Scope gate", "دائرہ کار"), "Plan checks ": ("Naqsha checks", "نقشے کی جانچ"),
    "Calculator constants": ("Calculator ke number", "کیلکولیٹر کے عدد"), "General": ("Aam", "عام"),
    "Layout": ("Layout", "لے آؤٹ"), "Foundation": ("Bunyad", "بنیاد"), "Brick walls": ("Eent ki deewarein", "اینٹ کی دیواریں"),
    "Openings and lintels": ("Darwaze aur lintel", "دروازے اور لنٹل"), "Slab steel": ("Lanter ka sariya", "لینٹر کا سریا"),
    "Slab pour": ("Lanter dalna", "لینٹر ڈالنا"), "Curing": ("Tarai", "ترائی"), "Plumbing and waterproofing": ("Plumbing aur waterproofing", "پلمبنگ اور واٹر پروفنگ"),
    "Plaster": ("Plaster", "پلستر"),
    "Starting questions": ("Shuru ke sawal", "ابتدائی سوال"), "AI with rules": ("AI rules ke saath", "اے آئی رولز کے ساتھ"),
    "Rules table (no AI)": ("Rules table (AI ke baghair)", "رولز ٹیبل (اے آئی کے بغیر)"), "Daily limit": ("Rozana had", "روزانہ حد"),
    "action(s)": ("kaam", "کام"),
    "Inside": ("Andar", "اندر"), "Outside": ("Bahar", "باہر"), "covered": ("covered", "تعمیر شدہ"), "room(s)": ("kamre", "کمرے"),
    "brick": ("eent", "اینٹ"), "Walls": ("Deewarein", "دیواریں"),
    "Trench": ("Khudai", "کھدائی"), "deep": ("gehri", "گہری"), "wide": ("chauri", "چوڑی"),
    # measure labels (checklist items)
    "Diagonal 1 (inches)": ("Wattar 1 (inch)", "وتر 1 (انچ)"), "Diagonal 2 (inches)": ("Wattar 2 (inch)", "وتر 2 (انچ)"),
    "Inner length (inches)": ("Andar ki lambai (inch)", "اندر کی لمبائی (انچ)"), "Inner width (inches)": ("Andar ki chaurai (inch)", "اندر کی چوڑائی (انچ)"),
    "Trench depth (inches)": ("Khudai ki gehrai (inch)", "کھدائی کی گہرائی (انچ)"), "Trench width at bottom (inches)": ("Khudai ki chaurai neeche (inch)", "کھدائی کی چوڑائی نیچے (انچ)"),
    "Left bearing (inches)": ("Baayein tikao (inch)", "بائیں ٹکاؤ (انچ)"), "Right bearing (inches)": ("Daayein tikao (inch)", "دائیں ٹکاؤ (انچ)"),
    "Largest main bar spacing (inches)": ("Main sariye ka sab se bara faasla (inch)", "مین سریے کا سب سے بڑا فاصلہ (انچ)"),
    "Fall over 10 ft (inches)": ("10 ft mein dhalan (inch)", "10 فٹ میں ڈھلوان (انچ)"),
    "Read": ("Parhein", "پڑھیں"), "degrees": ("degree", "ڈگری"),
    # construction notes on the printed plan
    "Trench depth": ("Khudai ki gehrai", "کھدائی کی گہرائی"), "Trench width": ("Khudai ki chaurai", "کھدائی کی چوڑائی"),
    "PCC bed": ("PCC ki tah", "پی سی سی کی تہہ"), "Foundation brickwork": ("Bunyad ki chunai", "بنیاد کی چنائی"),
    "Plinth above ground": ("Plinth zameen se", "پلنتھ زمین سے"), "DPC": ("DPC", "ڈی پی سی"), "Wall thickness": ("Deewar ki motai", "دیوار کی موٹائی"),
    "Mortar joint (max)": ("Masale ka jor (zyada se zyada)", "مسالے کا جوڑ (زیادہ سے زیادہ)"), "Lintel depth": ("Lintel ki gehrai", "لنٹل کی گہرائی"),
    "Slab thickness": ("Lanter ki motai", "لینٹر کی موٹائی"), "Main bars spacing": ("Main sariye ka faasla", "مین سریے کا فاصلہ"),
    "Distribution bars spacing": ("Distribution sariye ka faasla", "ڈسٹری بیوشن سریے کا فاصلہ"), "Cover under steel": ("Sariye ke neeche cover", "سریے کے نیچے کور"),
    "Props apart (max)": ("Balliyon ka faasla (zyada se zyada)", "بلیوں کا فاصلہ (زیادہ سے زیادہ)"), "Keep props": ("Balliyan rakhein", "بلیاں رکھیں"),
    "Cure slab": ("Lanter ki tarai", "لینٹر کی ترائی"), "days": ("din", "دن"),
    "\"From corner\" = from the room's top-left inside corner (N/S walls from the left, E/W walls from the top). Lintel length includes the bearing on each side.":
        ("\"Kone se\" = kamre ke upar-baayein andar wale kone se (N/S deewar baayein se, E/W upar se). Lintel ki lambai mein dono taraf ka tikao shamil hai.",
         "\"کونے سے\" = کمرے کے اوپر بائیں اندرونی کونے سے (N/S دیوار بائیں سے، E/W اوپر سے)۔ لنٹل کی لمبائی میں دونوں طرف کا ٹکاؤ شامل ہے۔"),
    # calculator notes and labels
    "Quantities include wastage from the Rules table and are rounded up.": ("Miqdaar mein wastage shamil hai aur upar round ki gayi hai.", "مقدار میں ضیاع شامل ہے اور اوپر گول کی گئی ہے۔"),
    "Walls shared by two rooms are counted once.": ("Do kamron ki saanjhi deewar ek baar gini gayi hai.", "دو کمروں کی مشترکہ دیوار ایک بار گنی گئی ہے۔"),
    "Excavation is shown for labour planning; it uses no material.": ("Khudai mazdoori ke liye dikhayi gayi hai; is mein material nahi lagta.", "کھدائی مزدوری کے لیے دکھائی گئی ہے؛ اس میں سامان نہیں لگتا۔"),
    "Doors, windows, flooring, tiles, electrical and plumbing fittings are not included.": ("Darwaze, khirkiyan, farsh, tiles, bijli aur plumbing ka saman shamil nahi.", "دروازے، کھڑکیاں، فرش، ٹائلیں، بجلی اور پلمبنگ کا سامان شامل نہیں۔"),
    "Brickwork": ("Chunai", "چنائی"), "Slab concrete": ("Lanter concrete", "لینٹر کنکریٹ"), "Excavation": ("Khudai", "کھدائی"),
    "Slab bars": ("Lanter ke sariye", "لینٹر کے سریے"), "main": ("main", "مین"), "distribution": ("distribution", "ڈسٹری بیوشن"),
    # chat example buttons
    "5 marla plot, 2 bedroom house": ("5 marla plot par 2 bedroom ghar", "5 مرلہ پلاٹ پر 2 بیڈروم کا گھر"),
    "Only one washroom 5x7": ("Sirf ek washroom 5x7", "صرف ایک واش روم 5x7"), "One room 12x14": ("Ek kamra 12x14", "ایک کمرہ 12x14"),
    "How many bricks will it take?": ("Kitni eent lagengi?", "کتنی اینٹیں لگیں گی؟"), "Add one more washroom": ("Ek washroom aur add karo", "ایک واش روم اور شامل کرو"),
    "How deep should the foundation be?": ("Bunyad kitni gehri ho?", "بنیاد کتنی گہری ہو؟"), "Steel bar spacing in the slab?": ("Lanter mein sariye ka faasla kitna ho?", "لینٹر میں سریے کا فاصلہ کتنا ہو؟"),
    # result
    "Rule used": ("Istemal shuda rule", "استعمال شدہ رول"), "Server time": ("Server waqt", "سرور وقت"), "Photo source": ("Tasveer kahan se", "تصویر کہاں سے"),
}


def tr(text, lang):
    """Translate one English UI string."""
    if lang == "en" or not text:
        return text
    roman, ur = TR.get(text, (text, text))
    if lang == "roman":
        return roman
    if lang == "ur":
        return ur
    return text if ur == text else f"{text}{SEP}{ur}"


def pick(en, roman, ur, lang):
    """Choose between three ready versions of a text."""
    if lang == "en":
        return en
    if lang == "roman":
        return roman or en
    if lang == "ur":
        return ur or roman or en
    ur = ur or ""
    return f"{en}{SEP}{ur}" if ur and ur != en else en


def ui_language(request):
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        return user.ui_language if user.ui_language in UI_LANGS else DEFAULT_UI
    return request.session.get("ui_language", DEFAULT_UI) if hasattr(request, "session") else DEFAULT_UI


def context(request):
    """Template context processor: ui_lang is used by the {% t %} and {% tr %} tags on every page."""
    from django.conf import settings

    lang = ui_language(request)
    return {"sv": getattr(settings, "STATIC_VERSION", "1"), "ui_lang": lang, "ui_rtl": lang == "ur", "ui_choices": [("both", "English + اردو"), ("en", "English"),
                                                                   ("ur", "اردو"), ("roman", "Roman Urdu")]}
