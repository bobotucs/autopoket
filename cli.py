"""Pocket a flat FTC plate from the command line.

  python cli.py plate.step -o plate_light.step --material "Aluminum 6061-T6" --target 0.33
"""
import argparse
import json
from pathlib import Path

from autopocket import cadio, runner

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help=".step/.stp/.3mf plate")
    ap.add_argument("-o", "--output", help="output .step/.3mf/.stl (default: <input>_pocketed.<ext>)")
    ap.add_argument("--material", default="Aluminum 6061-T6", choices=list(runner.MATERIALS))
    ap.add_argument("--target", type=float, default=0.33, help="min stiffness kept, 0-1")
    a = ap.parse_args()

    src = Path(a.input)
    out = Path(a.output) if a.output else src.with_name(f"{src.stem}_pocketed{src.suffix}")
    res = runner.run(cadio.load_any(src), a.material, a.target,
                     lambda m, f: print(f"[{f * 100:5.1f}%] {m}", flush=True))
    cadio.save_any(res["shape"], out)
    r = res["report"]
    print(f"\nSaved {out}")
    print(f"Mass {r['mass_g'][0]:.1f} g -> {r['mass_g'][1]:.1f} g  ({r['mass_saved_pct']:.1f}% lighter, "
          f"{r['pockets']} pockets, {r['spacing']} mm truss spacing)")
    for c in r["structure"]["cases"]:
        print(f"  {c['case']:22s} stiffness kept {c['stiffness_retained'] * 100:5.1f}%   peak stress x{c['peak_stress_ratio']:.2f}")
    print("  target met" if r["meets_target"] else "  WARNING: stiffness target not met")
    for w in r["warnings"]:
        print("  note:", w)
    Path(out).with_suffix(".report.json").write_text(json.dumps(r, indent=2))
