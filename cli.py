"""Pocket a part from the command line.

  python cli.py part.step -o part_light.step --pattern triangle --target 0.5
"""
import argparse
import json
from pathlib import Path

from autopocket import cadio, runner
from autopocket.pocketer import PocketParams

if __name__ == "__main__":
    d = PocketParams()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help=".step/.stp/.3mf file")
    ap.add_argument("-o", "--output", help="output .step/.3mf/.stl (default: <input>_pocketed.<ext>)")
    ap.add_argument("--pattern", choices=["triangle", "grid", "single"], default=d.pattern)
    for k in ["cell_size", "rib_width", "wall", "floor", "corner_radius", "through_max_thickness"]:
        ap.add_argument("--" + k.replace("_", "-"), type=float, default=getattr(d, k))
    ap.add_argument("--no-through", action="store_true", help="never cut through-pockets")
    ap.add_argument("--material", default="Aluminum 6061", choices=list(runner.MATERIALS))
    ap.add_argument("--target", type=float, default=0.5, help="min stiffness kept, 0-1 (0 disables back-off)")
    ap.add_argument("--no-fea", action="store_true", help="skip the structural check")
    a = ap.parse_args()

    p = PocketParams(pattern=a.pattern, cell_size=a.cell_size, rib_width=a.rib_width, wall=a.wall,
                     floor=a.floor, corner_radius=a.corner_radius, through=not a.no_through,
                     through_max_thickness=a.through_max_thickness)
    src = Path(a.input)
    out = Path(a.output) if a.output else src.with_name(f"{src.stem}_pocketed{src.suffix}")
    shape = cadio.load_any(src)
    res = runner.run(shape, p, a.material, a.target, not a.no_fea,
                     lambda m, f: print(f"[{f * 100:5.1f}%] {m}", flush=True))
    cadio.save_any(res["shape"], out)
    r = res["report"]
    print(f"\nSaved {out}")
    print(f"Mass {r['mass_g'][0]:.1f} g -> {r['mass_g'][1]:.1f} g  ({r['mass_saved_pct']:.1f}% lighter, {r['pockets']} pockets)")
    if r["structure"]:
        for c in r["structure"]["cases"]:
            print(f"  {c['case']:24s} stiffness kept {c['stiffness_retained'] * 100:5.1f}%   peak stress x{c['peak_stress_ratio']:.2f}")
        print("  target met" if r["meets_target"] else "  WARNING: stiffness target not met")
    Path(out).with_suffix(".report.json").write_text(json.dumps(r, indent=2))
