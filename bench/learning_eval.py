"""Is v2's learning actually helping? Leave-one-plate-out tests on the knowledge base.

    python bench/learning_eval.py                   # surrogate test only (fast, no FEA)
    python bench/learning_eval.py --replan          # + re-pocket each sample plate twice

Split by plate, never by design: hundreds of near-identical variants of one plate would
otherwise make any model look good.

1. Surrogate: for every plate, the surrogate is fitted on all *other* plates and asked about
   this one's FEA-checked designs. Reports the stiffness error, how many FEA runs the skip
   rule would have saved, and how many designs it would wrongly have skipped (must be 0).
2. --replan: each sample plate is pocketed with a knowledge base holding every other plate
   (its own rows removed) and with no knowledge at all; compares weight saved, FEA runs and
   time. Writes bench/learning_results.md.
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from autopocket import cadio  # noqa: E402
from autopocket2 import runner  # noqa: E402
from autopocket2.knowledge import DEFAULT_DB, KnowledgeBase, plate_sha  # noqa: E402
from autopocket2.learning import Surrogate  # noqa: E402
from autopocket.pocketer import find_plate  # noqa: E402


def surrogate_test(kb):
    rows = kb.labelled()
    pd = {p["id"]: p["descriptors"] for p in kb.plates()}
    sur = Surrogate(rows, pd)
    return sur.lopo(), len(rows), len(set(r["plate_id"] for r in rows))


def without_plate(db, sha):
    """A temporary copy of the knowledge base with one plate's history removed."""
    tmp = Path(tempfile.mkdtemp()) / "kb.db"
    shutil.copy(db, tmp)
    con = sqlite3.connect(tmp)
    row = con.execute("SELECT id FROM plate WHERE sha=?", (sha,)).fetchone()
    if row:
        pid = row[0]
        runs = [r[0] for r in con.execute("SELECT id FROM run WHERE plate_id=?", (pid,))]
        for rid in runs:
            con.execute("DELETE FROM candidate WHERE run_id=?", (rid,))
            con.execute("DELETE FROM choice WHERE run_id=?", (rid,))
        con.execute("DELETE FROM run WHERE plate_id=?", (pid,))
        con.execute("DELETE FROM plate WHERE id=?", (pid,))
    con.commit()
    con.close()
    return tmp


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--replan", action="store_true")
    ap.add_argument("plates", nargs="*")
    a = ap.parse_args()
    kb = KnowledgeBase(a.db)
    test, n_rows, n_plates = surrogate_test(kb)
    lines = ["# Does v2's learning help? (leave-one-plate-out)", "",
             f"Knowledge base: {n_plates} plates, {n_rows} FEA-checked designs.", "",
             "## Surrogate, each plate predicted from the others only", "",
             f"- designs tested: {test['tested']}",
             f"- mean stiffness error: {100 * (test['mae_stiffness'] or 0):.1f} percentage points",
             f"- FEA runs the skip rule would save: {test['would_skip']}",
             f"- designs it would wrongly skip (met the target): {test['wrong_skips']}", ""]
    print("\n".join(lines), flush=True)
    if a.replan:
        lines += ["## Re-pocketing each plate: learned from the other plates vs. no knowledge", "",
                  "| Plate | no knowledge | with knowledge (plate held out) | FEA runs | time |", "|---|---|---|---|---|"]
        paths = [Path(p) for p in a.plates] or sorted((ROOT / "samples").glob("*.step"))
        for p in paths:
            shape = cadio.load_any(p)
            pl = find_plate(cadio.solids(shape)[0])
            held = KnowledgeBase(without_plate(a.db, plate_sha(pl.profile, pl.thickness)))
            res = {}
            for tag, k in (("none", None), ("learned", held)):
                t = time.time()
                _, var, b, d = runner.plan(shape, knowledge=k, source="eval", name=p.name)
                v = var[b]
                res[tag] = (v["mass_saved_pct"], v["structure"]["worst_stiffness_retained"],
                            d["candidates_evaluated"], time.time() - t, v["meets_target"])
            fmt = lambda r: f"{r[0]:.1f}% / {100 * r[1]:.0f}%{'' if r[4] else ' (below target)'}"  # noqa: E731
            row = (f"| {p.name} | {fmt(res['none'])} | {fmt(res['learned'])} | "
                   f"{res['none'][2]} → {res['learned'][2]} | {res['none'][3]:.0f}s → {res['learned'][3]:.0f}s |")
            lines.append(row)
            print(row, flush=True)
    (ROOT / "bench" / "learning_results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
