"""Turn a plain-English description of what a plate does into a load setup.

    "chassis side plate, 15 kg robot, weight comes down through the screw holes,
     wheels ride in the bearings"

-> purpose chassis; supports = bearing bores (the wheel axles hold the plate up);
   loads = screw holes (the frame's weight comes in there); direction down;
   force 15 kg x 9.81 / 2 side plates = 74 N on this plate.

This is a deterministic rule-based reader, not a language model: it looks for a purpose,
for which holes hold the plate and which ones the load comes in through, for direction
words, and for a force (N, kg or lb). Anything not said falls back to a default for that
kind of plate, and every assumption is listed in `notes` so the user can see and correct it.
Directions are words relative to how the plate is shown on screen ("down" = screen down);
the page turns them into plate-frame vectors from its camera.
"""
from __future__ import annotations

import re

G = 9.81

# purpose -> (keywords, support hole kind, load hole kind, default directions, what it means)
PURPOSES = {
    "chassis side plate": (("chassis", "side plate", "drivetrain", "drive train", "drive plate", "wheel", "frame plate"),
                           "bearing", "fastener", ["down"],
                           "the robot's weight comes in through the frame's screw holes and the wheel axles in the bearings hold it up"),
    "gearbox plate": (("gearbox", "gear box", "transmission", "gear plate", "reduction"),
                      "fastener", "bearing", ["all"],
                      "gear forces push on the bearings in every direction as the gears turn; the plate is bolted at its screw holes"),
    "arm plate": (("arm", "pivot", "elbow", "wrist", "shoulder", "linkage"),
                  "bearing", "fastener", ["down"],
                  "the arm hangs from its pivot bearing and its weight / payload pulls down through the screw holes"),
    "lift plate": (("lift", "elevator", "slide", "cascade", "viper", "linear"),
                   "fastener", "bearing", ["down"],
                   "string or belt tension pulls down on the pulley bearings; the plate is bolted at its screw holes"),
    "intake plate": (("intake", "roller", "claw", "outtake", "scoring", "gripper"),
                     "fastener", "bearing", ["all"],
                     "the rollers load their bearings in changing directions; the plate is bolted at its screw holes"),
    "bracket": (("bracket", "motor mount", "mount plate", "electronics", "battery", "hub"),
                "fastener", "fastener", ["down"],
                "a bolted bracket carrying weight downward"),
}
DIRECTIONS = [  # (direction, phrases)
    ("all", ("all directions", "any direction", "every direction", "don't know", "dont know", "unknown direction")),
    ("in", ("into the plate", "into the face", "push on the face", "pushes on the face", "out of plane", "out-of-plane",
            "perpendicular", "face on", "through the face")),
    ("out", ("out of the plate", "away from the face", "pulls the face")),
    ("down", ("down", "downward", "gravity", "weight", "drops", "falls", "below")),
    ("up", ("upward", " up ", "lifts", "lift up", "pushes up", "above")),
    ("left", ("left",)),
    ("right", ("right",)),
    ("sideways", ("sideways", "side to side", "side-to-side", "lateral", "side load", "side impact")),
]
HOLE_WORDS = {
    "bearing": ("bearing", "bearings", "axle", "axles", "shaft", "shafts", "bore", "bores", "pulley", "pulleys", "gear", "gears"),
    "fastener": ("screw", "screws", "screw hole", "bolt", "bolts", "standoff", "standoffs", "mounting hole", "mounting holes",
                 "mount", "mounts", "rivet", "rivets", "fastener", "fasteners", "channel", "frame"),
}
SUPPORT_VERBS = ("held", "hold", "holds", "bolted", "bolt", "mounted", "mount", "fixed", "fix", "supported", "support",
                 "supports", "attached", "attach", "clamped", "clamp", "sits on", "rests on", "ride", "rides", "carried by",
                 "hangs from", "hang from", "pivots on")
LOAD_VERBS = ("load", "loads", "loaded", "force", "forces", "weight", "push", "pushes", "pull", "pulls", "comes",
              "come", "goes", "applied", "acts", "act", "presses", "hits", "impact", "torque", "stress")
IMPACT = ("impact", "collision", "collide", "crash", "drop", "slam", "hit", "shock", "bump")


def _kind_mentions(text):
    """[(position, kind)] for every mention of a hole kind."""
    out = []
    for kind, words in HOLE_WORDS.items():
        for w in sorted(words, key=len, reverse=True):
            for m in re.finditer(r"\b" + re.escape(w) + r"\b", text):
                if not any(abs(m.start() - p) < 3 for p, _ in out):
                    out.append((m.start(), kind))
    return sorted(out)


def _role_of(text, pos):
    """'support' or 'load' for a hole mention, from the nearest verb before it in its clause."""
    start = max(text.rfind(c, 0, pos) for c in ",.;:!?\n")
    clause = text[start + 1:pos]
    best, where = None, -1
    for verbs, role in ((SUPPORT_VERBS, "support"), (LOAD_VERBS, "load")):
        for v in verbs:
            i = clause.rfind(v)
            if i > where:
                best, where = role, i
    return best


def interpret(text: str, holes: list):
    """Load setup for one plate. `holes`: features.describe()['holes'] (id, kind, d ...)."""
    t = " " + text.lower().replace("’", "'") + " "
    notes = []
    purpose = None
    for name, (keys, *_rest) in PURPOSES.items():
        if any(k in t for k in keys):
            purpose = name
            break
    sup_kind, load_kind, dirs, meaning = (PURPOSES[purpose][1:] if purpose else (None, None, None, None))
    # explicit "held at the X" / "load through the Y"
    said_sup, said_load = None, None
    for pos, kind in _kind_mentions(t):
        role = _role_of(t, pos)
        if role == "support" and said_sup is None:
            said_sup = kind
        elif role == "load" and said_load is None:
            said_load = kind
    if said_sup and not said_load:
        said_load = "fastener" if said_sup == "bearing" else "bearing"
    if said_load and not said_sup:
        said_sup = "fastener" if said_load == "bearing" else "bearing"
    sup_kind, load_kind = said_sup or sup_kind, said_load or load_kind
    # directions
    found = []
    for d, phrases in DIRECTIONS:
        if any(ph in t for ph in phrases) and d not in found:
            found.append(d)
    if "sideways" in found:
        found = [d for d in found if d != "sideways"] + [d for d in ("left", "right") if d not in found]
    if "all" in found:
        found = ["all"]
    if found:
        dirs = found
    elif dirs:
        notes.append(f"direction not given: assumed {', '.join(dirs)} for a {purpose}")
    # holes of each kind
    by_kind = {k: [h["id"] for h in holes if h["kind"] == k] for k in ("bearing", "fastener", "hole", "slot", "cutout")}
    if not sup_kind or not load_kind:
        return {"ok": False, "purpose": purpose, "notes": notes + [
            "couldn't tell which holes hold the plate and where the load comes in; try e.g. "
            "'held by the screw holes, load comes down through the bearings'"]}
    supports = by_kind.get(sup_kind, [])
    loads = by_kind.get(load_kind, [])
    if sup_kind == load_kind:  # e.g. a bracket: split its screw holes, upper ones carry the load
        ids = by_kind.get(sup_kind, [])
        half = len(ids) // 2
        supports, loads = ids[:half] or ids, ids[half:] or ids
        notes.append("support and load holes are the same kind: split them in half; adjust in the hole picker")
    if not supports:
        alt = by_kind["fastener"] or by_kind["hole"]
        notes.append(f"no {sup_kind} holes found to hold the plate: used the screw holes instead")
        supports = [i for i in alt if i not in loads]
    if not loads:
        alt = by_kind["bearing"] or by_kind["hole"] or by_kind["fastener"]
        notes.append(f"no {load_kind} holes found for the load: used other holes instead")
        loads = [i for i in alt if i not in supports]
    # force
    force, per_hole = None, bool(re.search(r"\b(per|each)\s+(bearing|hole|screw|bolt|axle|wheel)", t))
    m = re.search(r"(\d+(?:\.\d+)?)\s*(kn|n|newtons?|kg|kgs|kilograms?|lb|lbs|pounds?)\b", t)
    if m:
        val, unit = float(m.group(1)), m.group(2)
        force = val * (1000 if unit == "kn" else G if unit.startswith("k") else 4.448 if unit.startswith(("lb", "pound")) else 1)
        if unit.startswith(("k", "lb", "pound")) and unit != "kn":
            notes.append(f"{val:g} {unit} x g = {force:.0f} N")
        if purpose == "chassis side plate" and "robot" in t and not per_hole:
            force /= 2
            notes.append("robot weight shared by 2 side plates: half on this plate (assumed)")
        if per_hole and loads:
            force *= len(loads)
            notes.append(f"{val:g} per hole x {len(loads)} load holes")
    if any(w in t for w in IMPACT):
        if force:
            force *= 2
        notes.append("impact mentioned: load doubled (suddenly applied load, factor 2, assumed)")
    words = {"down": "downward", "up": "upward", "left": "to the left", "right": "to the right",
             "in": "into the plate", "out": "out of the plate", "all": "in every direction"}
    summary = (f"{(purpose or 'plate').capitalize()}: held at {len(supports)} {sup_kind} hole(s), "
               f"load {' and '.join(words.get(d, d) for d in (dirs or ['all']))} "
               f"through {len(loads)} {load_kind} hole(s)" + (f", {force:.0f} N total" if force else "") + ".")
    return {"ok": True, "purpose": purpose, "meaning": meaning, "support_ids": supports, "load_ids": loads,
            "support_kind": sup_kind, "load_kind": load_kind, "dirs": dirs or ["all"],
            "force_n": round(force, 1) if force else None, "notes": notes, "summary": summary}
