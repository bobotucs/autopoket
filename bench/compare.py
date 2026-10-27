"""Compare AutoPocket v1 and v2 on the same plates with the same independent grader.

    python bench/compare.py                      # every plate in samples/
    python bench/compare.py samples/side_plate.step --target 0.33

Both versions plan as they normally would (their own FEA, their own pick). Then every
design they offer is re-graded identically:

  * hard rules measured on the final geometry (autopocket2/validate.py);
  * a finer FE mesh than either planner uses, three load cases from *both* clamp ends,
    worst case reported (v1's planner only clamps one end, so its own numbers can be
    optimistic for plates that are stiffer at one end).

Output: a table per plate (chosen designs) plus each version's weight-vs-stiffness
front, written to bench/results.md and bench/results.json.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from autopocket import cadio  # noqa: E402
from autopocket import runner as v1  # noqa: E402
from autopocket.pocketer import PlateRules  # noqa: E402
from autopocket2 import fea2, validate  # noqa: E402
from autopocket2 import runner as v2  # noqa: E402

GRADE_CELLS = (14000, 36000)
# rules v2 added on the user's request; v1 never aimed for them, so they are flagged
# but don't remove v1 designs from the comparison
SHAPE_RULES = {"sharpest_tip_depth_mm", "pocket_symmetry_mismatch_pct"}


class Grader:
    def __init__(self, plates):
        self.plates = plates
        self.an = [fea2.Analysis(p.profile, p.thickness, *GRADE_CELLS) for p in plates]

    def __call__(self, layouts, rules):
        r = PlateRules(**rules)
        worst, v0, v1_, ok, failed = None, 0.0, 0.0, True, []
        for p, a, outlines in zip(self.plates, self.an, layouts):
            val = validate.check(p.profile, outlines, r)
            ok &= val["ok"]
            failed += val["failed"]
            prof = v2._pocketed_profile(p.profile, outlines, r)
            v0 += p.profile.area * p.thickness
            v1_ += prof.area * p.thickness
            s = a.evaluate(prof)
            if worst is None or s["worst_stiffness_retained"] < worst["worst_stiffness_retained"]:
                worst = s
        failed = sorted(set(failed))
        return {"mass_saved_pct": 100 * (1 - v1_ / v0), "stiffness": worst["worst_stiffness_retained"],
                "stress": worst["worst_peak_stress_ratio"], "rules_ok": bool(ok), "failed": failed,
                "core_ok": not set(failed) - SHAPE_RULES}


def front(points):
    """Best stiffness reachable at or above each weight saving (for a fair side-by-side)."""
    pts = sorted(points, key=lambda q: -q["mass_saved_pct"])
    out, best = [], -1.0
    for q in pts:
        if q["core_ok"] and q["stiffness"] > best:
            best = q["stiffness"]
            out.append(q)
    return sorted(out, key=lambda q: q["mass_saved_pct"])


def best_at(fr, target):
    ok = [q for q in fr if q["stiffness"] >= target]
    return max(ok, key=lambda q: q["mass_saved_pct"]) if ok else None


def run_plate(path, target):
    shape = cadio.load_any(path)
    out = {"plate": path.name}
    t = time.time()
    plates, var1, b1 = v1.plan(shape, target_stiffness=target)
    out["v1_seconds"] = time.time() - t
    t = time.time()
    plates2, var2, b2, diag = v2.plan(shape, target_stiffness=target)
    out["v2_seconds"] = time.time() - t
    out["v2_diag"] = diag
    g = Grader(plates)
    g1 = [g(v["layouts"], v["rules"]) | {"label": f"{v['spacing']} mm"} for v in var1]
    g2 = [g(v["layouts"], v["rules"]) | {"label": v["label"]} for v in var2]
    out["v1_chosen"], out["v2_chosen"] = g1[b1], g2[b2]
    out["v1_all"], out["v2_all"] = g1, g2
    out["v1_best_at_target"] = best_at(front(g1), target)
    out["v2_best_at_target"] = best_at(front(g2), target)
    return out


def fmt(q):
    if q is None:
        return "—"
    short = {"sharpest_tip_depth_mm": "sharp tips", "pocket_symmetry_mismatch_pct": "asymmetric"}
    flag = "" if q["rules_ok"] else " ⚠ " + ", ".join(short.get(f, f) for f in q["failed"])
    return f"{q['mass_saved_pct']:.1f}% / {100 * q['stiffness']:.0f}% / ×{q['stress']:.1f}{flag}"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plates", nargs="*")
    ap.add_argument("--target", type=float, default=0.33)
    a = ap.parse_args()
    paths = [Path(p) for p in a.plates] or sorted(p for p in (ROOT / "samples").glob("*.step"))
    rows = []
    for p in paths:
        print(f"== {p.name}", flush=True)
        res = run_plate(p, a.target)
        rows.append(res)
        print(f"   v1 chosen {fmt(res['v1_chosen'])}  ({res['v1_seconds']:.0f}s)   "
              f"v2 chosen {fmt(res['v2_chosen'])}  ({res['v2_seconds']:.0f}s)", flush=True)
        print(f"   best meeting target (graded): v1 {fmt(res['v1_best_at_target'])}   "
              f"v2 {fmt(res['v2_best_at_target'])}", flush=True)
    lines = [f"# AutoPocket v1 vs v2 (target {100 * a.target:.0f}% stiffness)", "",
             "Cells: weight saved / stiffness kept (worst of 6 load cases, fine mesh) / peak stress ratio.",
             "⚠ = breaks a rule (sharp tips = a pocket corner under 45°, asymmetric = pockets not mirror-symmetric "
             "on a symmetric outline). v1 designs breaking only those two still count in the v1 columns.", "",
             "| Plate | v1 pick | v2 pick | v1 best meeting target | v2 best meeting target | time v1 / v2 |",
             "|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['plate']} | {fmt(r['v1_chosen'])} | {fmt(r['v2_chosen'])} | "
                     f"{fmt(r['v1_best_at_target'])} | {fmt(r['v2_best_at_target'])} | "
                     f"{r['v1_seconds']:.0f}s / {r['v2_seconds']:.0f}s |")
    lines += ["", "## Weight-vs-stiffness fronts (graded)", ""]
    for r in rows:
        lines.append(f"**{r['plate']}**  ")
        for v in ("v1", "v2"):
            fr = front(r[f"{v}_all"])
            lines.append(f"{v}: " + ", ".join(f"{q['mass_saved_pct']:.1f}%→{100 * q['stiffness']:.0f}%" for q in fr) + "  ")
        lines.append("")
    out = Path(__file__).parent
    (out / "results.md").write_text("\n".join(lines), encoding="utf-8")
    (out / "results.json").write_text(json.dumps(rows, indent=1, default=str), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
