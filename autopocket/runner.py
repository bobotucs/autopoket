"""Try a range of truss spacings, check each with FEA, keep the lightest that stays stiff enough."""
from __future__ import annotations

import time

from shapely.ops import unary_union

from . import cadio, fea
from .pocketer import PlateRules, find_plate, pocket_outlines, pocket_plate, support_report

# density g/cm^3, Young's modulus GPa, yield / tensile strength MPa (typical values)
MATERIALS = {
    "Aluminum 6061-T6": {"density": 2.70, "E": 68.9, "strength": 276,
                         "note": "Yield strength"},
    "Delrin (acetal)": {"density": 1.41, "E": 3.1, "strength": 72,
                        "note": "Delrin 150 homopolymer, tensile yield"},
    "Polycarbonate": {"density": 1.20, "E": 2.4, "strength": 62,
                      "note": "Tensile yield"},
    "PLA (3D printed)": {"density": 1.24, "E": 3.5, "strength": 50,
                         "note": "Printed parts vary with infill and layer direction"},
    "PETG (3D printed)": {"density": 1.27, "E": 2.1, "strength": 50,
                          "note": "Printed parts vary with infill and layer direction"},
    "Carbon fiber sheet": {"density": 1.55, "E": 55.0, "strength": 500,
                           "note": "Woven twill, quasi-isotropic; varies with layup"},
}

SPACINGS = [32, 36, 40, 44, 48, 53, 58, 64, 72]  # truss node spacing candidates, mm


def _pocketed_profile(profile, outlines, tool_radius):
    rounded = [o.buffer(-tool_radius, quad_segs=8).buffer(tool_radius, quad_segs=8) for o in outlines]
    return profile.difference(unary_union(rounded)) if rounded else profile


def plan(shape, material="Aluminum 6061-T6", target_stiffness=0.33, rules: PlateRules | None = None,
         progress=None):
    """Lay out and FEA-check every candidate spacing. Returns (plates, variants, best_index)."""
    say = progress or (lambda msg, frac: None)
    base = rules or PlateRules()
    sols = cadio.solids(shape)
    if not sols:
        raise ValueError("No solid bodies found in the file")
    plates = [find_plate(s) for s in sols]
    density = MATERIALS.get(material, MATERIALS["Aluminum 6061-T6"])["density"]
    say("Analysing the blank plate", 0.02)
    baselines = [fea.Baseline(p.profile, p.thickness) for p in plates]
    variants = []
    for k, S in enumerate(SPACINGS):
        say(f"Trying {S} mm truss spacing", 0.05 + 0.9 * k / len(SPACINGS))
        r = PlateRules(**{**base.to_dict(), "spacing": S})
        layouts, structure, v0, v1, n = [], None, 0.0, 0.0, 0
        holes, holes_ok = 0, 0
        for p, b in zip(plates, baselines):
            outlines, lines, nodes = pocket_outlines(p.profile, r)
            prof = _pocketed_profile(p.profile, outlines, r.tool_radius)
            ok_n, all_n = support_report(p.profile, outlines, r)
            holes_ok += ok_n
            holes += all_n
            v0 += p.profile.area * p.thickness
            v1 += prof.area * p.thickness
            n += len(outlines)
            layouts.append(outlines)
            s = b.evaluate(prof) if outlines else None
            if s and (structure is None or s["worst_stiffness_retained"] < structure["worst_stiffness_retained"]):
                structure = s
        if n == 0:
            continue
        # same pocket set as a smaller spacing gives nothing new
        if variants and variants[-1]["pockets"] == n and abs(variants[-1]["mass_saved_pct"] - 100 * (1 - v1 / v0)) < 0.05:
            continue
        variants.append({
            "spacing": S, "rules": r.to_dict(), "pockets": n, "layouts": layouts,
            "holes": holes, "holes_supported": holes_ok,
            "mass_saved_pct": 100 * (1 - v1 / v0),
            "mass_g": [v0 * density / 1000, v1 * density / 1000],
            "structure": structure,
            "meets_target": structure["worst_stiffness_retained"] >= target_stiffness,
        })
    if not variants:
        raise ValueError("No pockets fit - the plate is too small for 8 mm ribs and 4 mm offsets")
    ok = [i for i, v in enumerate(variants) if v["meets_target"]]
    if ok:
        best = max(ok, key=lambda i: variants[i]["mass_saved_pct"])
    else:
        best = max(range(len(variants)), key=lambda i: variants[i]["structure"]["worst_stiffness_retained"])
    return plates, variants, best


def build(plates, variant):
    """Cut the chosen variant's pockets into the plates. Returns (shape, n_pockets)."""
    r = PlateRules(**variant["rules"])
    out, n = [], 0
    for p, outlines in zip(plates, variant["layouts"]):
        res, k, _ = pocket_plate(p, r, outlines)
        out.append(res)
        n += k
    return (out[0] if len(out) == 1 else cadio.make_compound(out)), n


def report(plates, variants, chosen, material, target_stiffness, shape_out, t0):
    density = MATERIALS[material]["density"]
    v0 = sum(cadio.volume(p.solid) for p in plates)
    v1 = cadio.volume(shape_out)
    v = variants[chosen]
    return {
        "material": material,
        "material_props": MATERIALS[material],
        "thickness_mm": [round(p.thickness, 3) for p in plates],
        "volume_mm3": [v0, v1],
        "mass_g": [v0 * density / 1000, v1 * density / 1000],
        "mass_saved_g": (v0 - v1) * density / 1000,
        "mass_saved_pct": 100 * (1 - v1 / v0),
        "pockets": v["pockets"],
        "spacing": v["spacing"],
        "holes": v["holes"],
        "holes_supported": v["holes_supported"],
        "structure": v["structure"],
        "target_stiffness": target_stiffness,
        "meets_target": v["meets_target"],
        "rules": v["rules"],
        "chosen": chosen,
        "variants": [{k: x[k] for k in ("spacing", "pockets", "mass_saved_pct", "meets_target")}
                     | {"stiffness": x["structure"]["worst_stiffness_retained"]} for x in variants],
        "warnings": sorted({w for p in plates for w in p.warnings}),
        "seconds": time.time() - t0,
    }


def run(shape, material="Aluminum 6061-T6", target_stiffness=0.33, progress=None, variant=None):
    """Plan, pick the best (or the requested) variant, cut it. Returns dict(shape, report, ...)."""
    t0 = time.time()
    plates, variants, best = plan(shape, material, target_stiffness, progress=progress)
    chosen = best if variant is None else variant
    if progress:
        progress("Cutting pockets", 0.97)
    out, _ = build(plates, variants[chosen])
    return {"shape": out, "plates": plates, "variants": variants, "best": best,
            "report": report(plates, variants, chosen, material, target_stiffness, out, t0)}
