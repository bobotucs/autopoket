"""Train v2 on the plates you pocketed in Onshape, and compare its designs with yours.

    python bench/train_onshape.py            # every plate found by onshape_import.py
    python bench/train_onshape.py --max 5

For each hand-pocketed plate found in Onshape, the rebuilt blank is pocketed by v2 (with
learning on, so every design lands in the knowledge base), using your own design's
stiffness as the target: "keep at least as much stiffness as you did". The table shows
whether v2 removes more or less weight than you at that stiffness, and which pattern it
used. Writes knowledge/onshape/comparison.md.
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
from autopocket2 import runner  # noqa: E402
from autopocket2.knowledge import KnowledgeBase  # noqa: E402

OUT = ROOT / "knowledge" / "onshape"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max", type=int, default=0)
    a = ap.parse_args()
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    import re
    plates = [e for m in manifest.values() for e in m.get("pocketed", [])
              if e.get("stiffness_kept_pct") and e["removed_pct"] >= 8]  # skip barely-pocketed plates
    for e in plates:  # entries from before the blank name was recorded
        e.setdefault("blank", "blank_" + re.sub(r"[^A-Za-z0-9_.-]+", "_", e["name"])[:60] + ".step")
    if a.max:
        plates = plates[:a.max]
    kb = KnowledgeBase()
    rows = ["# v2 vs your Onshape designs", "",
            "Same FEA for both (worst of 6 generic load cases); v2's target = the stiffness your design kept.", "",
            "| Plate | your pattern | yours: removed / stiffness | v2: removed / stiffness | v2 layout | difference |",
            "|---|---|---|---|---|---|"]
    for e in plates:
        blank = OUT / "blanks" / e["blank"]
        if not blank.exists():
            continue
        target = e["stiffness_kept_pct"] / 100
        t = time.time()
        try:
            pl, var, b, d = runner.plan(cadio.load_any(blank), target_stiffness=target, knowledge=kb,
                                        source="onshape-train", name=e["name"])
        except Exception as ex:
            print(f"{e['name']}: failed ({ex})", flush=True)
            continue
        v = var[b]
        diff = v["mass_saved_pct"] - e["removed_pct"] if v["meets_target"] else None
        row = (f"| {e['name'][:40]} | {e.get('pattern', '?')} | {e['removed_pct']:.1f}% / {e['stiffness_kept_pct']:.0f}% | "
               f"{v['mass_saved_pct']:.1f}% / {100 * v['structure']['worst_stiffness_retained']:.0f}%"
               f"{'' if v['meets_target'] else ' (below)'} | {v['label']} | "
               f"{'—' if diff is None else f'{diff:+.1f} pts'} |")
        rows.append(row)
        print(row, f"({time.time() - t:.0f}s)", flush=True)
    rows += ["", f"Knowledge base after training: {kb.stats()}"]
    (OUT / "comparison.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print("\n".join(rows[-1:]))


if __name__ == "__main__":
    main()
