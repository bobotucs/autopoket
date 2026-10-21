"""Pocket a part, check it with FEA, and back off until the stiffness target is met."""
from __future__ import annotations

import time

from . import cadio, fea
from .pocketer import PocketParams, pocket_shape

MATERIALS = {  # density, g/cm^3
    "Aluminum 6061": 2.70,
    "Aluminum 7075": 2.81,
    "Steel": 7.85,
    "Stainless steel": 8.00,
    "Titanium Ti-6Al-4V": 4.43,
    "Polycarbonate": 1.20,
    "PLA": 1.24,
    "PETG": 1.27,
    "Nylon / PA12": 1.01,
    "ABS": 1.04,
}

# successively more conservative variants tried when the stiffness target is missed
LADDER = [
    {},
    {"rib_width": 1.5, "wall": 1.25},
    {"rib_width": 2.0, "wall": 1.5, "cell_size": 0.85},
    {"rib_width": 2.0, "wall": 1.5, "cell_size": 0.85, "floor": 1.5, "through": False},
    {"rib_width": 2.8, "wall": 2.0, "cell_size": 0.75, "floor": 2.5, "through": False},
]


def _variant(base: PocketParams, step: dict) -> PocketParams:
    p = PocketParams.from_dict(base.to_dict())
    for k, v in step.items():
        if isinstance(v, bool):
            setattr(p, k, v and getattr(p, k))
        else:
            setattr(p, k, round(getattr(p, k) * v, 3))
    return p


def run(shape, params: PocketParams, material="Aluminum 6061", target_stiffness=0.5,
        check_structure=True, progress=None):
    """Returns dict(shape=..., report=...)."""
    t0 = time.time()
    say = progress or (lambda msg, frac: None)
    density = MATERIALS.get(material, 2.70)
    v0 = cadio.volume(shape)
    baseline = None
    if check_structure:
        say("Analysing original part", 0.02)
        baseline = fea.Baseline(shape)
    ladder = LADDER if (check_structure and target_stiffness > 0) else LADDER[:1]
    attempts, best = [], None
    n_steps = len(ladder) + 1

    def attempt(p, k):
        lo = 0.05 + 0.9 * k / n_steps
        span = 0.9 / n_steps

        def sub(msg, frac):
            say(f"Attempt {k + 1}: {msg}", lo + span * 0.6 * frac)

        res, pockets = pocket_shape(shape, p, sub)
        v1 = cadio.volume(res)
        structure = None
        if baseline is not None and pockets:
            say(f"Attempt {k + 1}: structural check", lo + span * 0.65)
            structure = baseline.evaluate(res)
        ok = structure is None or structure["worst_stiffness_retained"] >= target_stiffness
        info = {"params": p.to_dict(), "pockets": len(pockets),
                "mass_saved_pct": 100 * (1 - v1 / v0), "structure": structure, "meets_target": ok}
        attempts.append(info)
        return res, pockets, info

    def retained(c):
        return c[2]["structure"]["worst_stiffness_retained"] if c[2]["structure"] else 1.0

    for k, step in enumerate(ladder):
        cand = attempt(_variant(params, step), k)
        if cand[2]["meets_target"]:
            best = cand
            prev = ladder[k - 1] if k else None
            # the ladder is coarse: try halfway between the last miss and this pass
            if prev is not None and prev.get("through", True) == step.get("through", True):
                mid = {key: (step.get(key, 1.0) * prev.get(key, 1.0)) ** 0.5
                       for key in set(step) | set(prev) if key != "through"}
                if "through" in step:
                    mid["through"] = step["through"]
                c2 = attempt(_variant(params, mid), k + 1)
                if c2[2]["meets_target"] and c2[2]["mass_saved_pct"] > cand[2]["mass_saved_pct"]:
                    best = c2
            break
        if best is None or retained(cand) > retained(best):
            best = cand
    res, pockets, chosen = best
    v1 = cadio.volume(res)
    say("Done", 1.0)
    report = {
        "material": material,
        "density_g_cm3": density,
        "volume_mm3": [v0, v1],
        "mass_g": [v0 * density / 1000, v1 * density / 1000],
        "mass_saved_g": (v0 - v1) * density / 1000,
        "mass_saved_pct": 100 * (1 - v1 / v0),
        "pockets": len(pockets),
        "through_pockets": sum(1 for p in pockets if p.through),
        "faces_pocketed": sorted({p.face for p in pockets}),
        "structure": chosen["structure"],
        "target_stiffness": target_stiffness,
        "meets_target": chosen["meets_target"],
        "params_used": chosen["params"],
        "attempts": attempts,
        "seconds": time.time() - t0,
    }
    return {"shape": res, "report": report}
