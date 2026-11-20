"""The fixed order of work stages for one single-storey room (Version 1)."""

LAYOUT = "layout"
FOUNDATION = "foundation"
WALLS = "walls"
OPENINGS = "openings"
SLAB_STEEL = "slab_steel"
SLAB_POUR = "slab_pour"
CURING = "curing"
PLUMBING = "plumbing"
PLASTER = "plaster"

STAGES = [
    # (code, English, Urdu, Roman Urdu)
    (LAYOUT, "Layout", "نشان دہی (لے آؤٹ)", "Layout / nishan dahi"),
    (FOUNDATION, "Foundation", "بنیاد", "Bunyad"),
    (WALLS, "Brick walls", "اینٹوں کی دیواریں", "Eenton ki deewarein"),
    (OPENINGS, "Openings and lintels", "دروازے، کھڑکیاں اور لنٹل", "Darwaze, khirkiyan aur lintel"),
    (SLAB_STEEL, "Slab steel", "لینٹر کا سریا", "Lanter ka sariya"),
    (SLAB_POUR, "Slab pour", "لینٹر ڈالنا", "Lanter dalna"),
    (CURING, "Curing", "ترائی (کیورنگ)", "Tarai / curing"),
    (PLUMBING, "Plumbing and waterproofing", "پلمبنگ اور واٹر پروفنگ", "Plumbing aur waterproofing"),
    (PLASTER, "Plaster", "پلستر", "Plaster"),
]

# Stages that only apply when the plan has a washroom or kitchen.
WET_ONLY = {PLUMBING}

STAGE_CODES = [s[0] for s in STAGES]
STAGE_CHOICES = [(s[0], s[1]) for s in STAGES]
STAGE_NAMES_UR = {s[0]: s[2] for s in STAGES}
STAGE_NAMES_ROMAN = {s[0]: s[3] for s in STAGES}

# Rule categories that are not a work stage.
RULE_CATEGORY_CHOICES = STAGE_CHOICES + [
    ("scope", "Scope gate"),
    ("plan", "Plan checks"),
    ("calc", "Calculator constants"),
    ("general", "General"),
]
