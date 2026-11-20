"""Checks done by code, not AI: typed tape readings and the phone tilt sensor."""

GREEN, YELLOW, RED = "green", "yellow", "red"


def _r(status, en, roman, ur, tell=""):
    return {"status": status, "reason_en": en, "reason_roman": roman, "reason_ur": ur, "tell_mistri": tell}


def compare(mode: str, readings: list[float], rule_value: float, unit: str = "in", plan_values: list[float] | None = None) -> dict:
    """Return a result dict for a measure item.

    diff: two readings equal within rule_value (yellow up to 2x).
    min:  every reading >= rule_value (yellow down to 95%).
    max:  every reading <= rule_value (yellow up to 110%).
    plan: readings match plan_values within rule_value (yellow up to 2x).
    """
    v = float(rule_value)
    if not readings:
        raise ValueError("No readings")
    if mode == "diff":
        if len(readings) < 2:
            raise ValueError("Two readings are needed")
        d = abs(readings[0] - readings[1])
        status = GREEN if d <= v else YELLOW if d <= 2 * v else RED
        return _r(status,
                  f"The two readings differ by {d:g} {unit}; the limit is {v:g} {unit}.",
                  f"Dono naap mein {d:g} {unit} ka farq hai; had {v:g} {unit} hai.",
                  f"دونوں پیمائشوں میں {d:g} {unit} کا فرق ہے؛ حد {v:g} {unit} ہے۔",
                  "" if status == GREEN else "Kone dobara set karein, phir dono wattar naapein.")
    if mode == "min":
        low = min(readings)
        status = GREEN if low >= v else YELLOW if low >= 0.95 * v else RED
        return _r(status,
                  f"Lowest reading {low:g} {unit}; needed at least {v:g} {unit}.",
                  f"Sab se kam naap {low:g} {unit}; kam az kam {v:g} {unit} chahiye.",
                  f"سب سے کم پیمائش {low:g} {unit}؛ کم از کم {v:g} {unit} چاہیے۔",
                  "" if status == GREEN else f"Kam az kam {v:g} {unit} poora karein.")
    if mode == "max":
        high = max(readings)
        status = GREEN if high <= v else YELLOW if high <= 1.1 * v else RED
        return _r(status,
                  f"Highest reading {high:g} {unit}; the limit is {v:g} {unit}.",
                  f"Sab se zyada naap {high:g} {unit}; had {v:g} {unit} hai.",
                  f"سب سے زیادہ پیمائش {high:g} {unit}؛ حد {v:g} {unit} ہے۔",
                  "" if status == GREEN else f"{v:g} {unit} se zyada na ho, theek karein.")
    if mode == "plan":
        if not plan_values or len(readings) < len(plan_values):
            raise ValueError("Readings for every plan value are needed")
        worst = max(abs(a - b) for a, b in zip(readings, plan_values))
        status = GREEN if worst <= v else YELLOW if worst <= 2 * v else RED
        return _r(status,
                  f"Largest difference from the plan is {worst:g} {unit}; allowed {v:g} {unit}.",
                  f"Naqshe se sab se bada farq {worst:g} {unit}; ijazat {v:g} {unit}.",
                  f"نقشے سے سب سے بڑا فرق {worst:g} {unit}؛ اجازت {v:g} {unit}۔",
                  "" if status == GREEN else "Naqshe ke mutabiq lines dobara lagayein.")
    raise ValueError(f"Unknown compare mode {mode}")


def tilt(readings_deg: list[float], limit_deg: float) -> dict:
    """Readings are degrees away from vertical (0 = perfectly plumb)."""
    worst = max(abs(x) for x in readings_deg)
    v = float(limit_deg)
    status = GREEN if worst <= v else YELLOW if worst <= 2 * v else RED
    return _r(status,
              f"Largest lean measured {worst:.1f} degrees; limit {v:g} degrees. Confirm with a plumb bob.",
              f"Sab se zyada jhukav {worst:.1f} degree; had {v:g} degree. Sahul se bhi check karein.",
              f"سب سے زیادہ جھکاؤ {worst:.1f} ڈگری؛ حد {v:g} ڈگری۔ ساہل سے بھی چیک کریں۔",
              "" if status == GREEN else "Deewar seedhi nahi lag rahi, sahul laga kar theek karein.")
