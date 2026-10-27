"""Pocket a flat FTC plate with AutoPocket v2 from the command line.

  python cli_v2.py plate.step -o plate_light.step --material "Aluminum 6061-T6" --target 0.33

Every run is recorded in knowledge/autopocket.db and the next run learns from it
(--no-learn to plan without the knowledge base).
"""
import argparse
import json
from pathlib import Path

from autopocket import cadio
from autopocket2 import runner
from autopocket2.knowledge import KnowledgeBase

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help=".step/.stp/.3mf plate")
    ap.add_argument("-o", "--output", help="output .step/.3mf/.stl (default: <input>_pocketed_v2.<ext>)")
    ap.add_argument("--material", default="Aluminum 6061-T6", choices=list(runner.MATERIALS))
    ap.add_argument("--target", type=float, default=0.33, help="min stiffness kept, 0-1")
    ap.add_argument("--no-learn", action="store_true", help="don't use or update the knowledge base")
    ap.add_argument("--pattern", default="auto", choices=list(runner.PATTERNS),
                    help="auto (lightest of all that passes), isogrid, triangles, hexagon or voronoi")
    a = ap.parse_args()

    src = Path(a.input)
    out = Path(a.output) if a.output else src.with_name(f"{src.stem}_pocketed_v2{src.suffix}")
    res = runner.run(cadio.load_any(src), a.material, a.target,
                     lambda m, f: print(f"[{f * 100:5.1f}%] {m}", flush=True),
                     knowledge=None if a.no_learn else KnowledgeBase(), source="cli", name=src.name,
                     pattern=a.pattern)
    cadio.save_any(res["shape"], out)
    r = res["report"]
    print(f"\nSaved {out}")
    print(f"Mass {r['mass_g'][0]:.1f} g -> {r['mass_g'][1]:.1f} g  ({r['mass_saved_pct']:.1f}% lighter, "
          f"{r['pockets']} pockets, layout {r['spacing']})")
    print(f"Status: {r['status']}")
    for c in r["structure"]["cases"]:
        print(f"  {c['case']:40s} stiffness kept {c['stiffness_retained'] * 100:5.1f}%   peak stress x{c['peak_stress_ratio']:.2f}")
    if r["convergence"]:
        cv = r["convergence"]
        print(f"  finer mesh ({cv['fine_cells']} cells): stiffness kept {cv['fine_stiffness'] * 100:.1f}% "
              f"({cv['difference_pct']:+.1f}% vs planner)")
    print("  target met" if r["meets_target"] else "  WARNING: stiffness target not met")
    d = r["diagnostics"]
    print(f"  {d['candidates_evaluated']} designs analysed, {d['feasible']} meet the target; rejected by rule: {d['rejections'] or 'none'}")
    L = r.get("learning")
    if L:
        k = L["knowledge"]
        print(f"  learning: {k['plates']} plates / {k['fea_designs']} FEA-checked designs on record; "
              f"surrogate {'on' if L['surrogate_gate_open'] else 'off'} ({L['fea_skipped']} FEA runs skipped); "
              f"family order {L['prior']['order']}")
    for w in r["warnings"]:
        print("  note:", w)
    Path(out).with_suffix(".report.json").write_text(json.dumps(r, indent=2))
