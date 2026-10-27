"""Fill v2's knowledge base: the user's hand-made style references, then plates pocketed.

    python bench/seed_knowledge.py                 # style refs + every plate in samples/
    python bench/seed_knowledge.py my_plate.step   # style refs + these plates

Each plate is pocketed with learning on (so later plates already learn from earlier ones)
and recorded with source "seed". The database is knowledge/autopocket.db unless --db.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from autopocket import cadio  # noqa: E402
from autopocket2 import runner, style  # noqa: E402
from autopocket2.knowledge import DEFAULT_DB, KnowledgeBase  # noqa: E402


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plates", nargs="*")
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--target", type=float, default=0.33)
    a = ap.parse_args()
    kb = KnowledgeBase(a.db)
    for name, d in style.reference_designs().items():
        kb.add_style_ref(name, d)
    print("style references:", kb.stats()["style_refs"], flush=True)
    paths = [Path(p) for p in a.plates] or sorted((ROOT / "samples").glob("*.step"))
    for p in paths:
        t = time.time()
        plates, variants, best, diag = runner.plan(cadio.load_any(p), target_stiffness=a.target,
                                                   knowledge=kb, source="seed", name=p.name)
        v, L = variants[best], diag["learning"]
        print(f"{p.name:24s} {time.time() - t:5.0f}s  {v['label']:32s} {v['mass_saved_pct']:5.1f}% lighter, "
              f"{100 * v['structure']['worst_stiffness_retained']:3.0f}% stiff | surrogate "
              f"{'on' if L['surrogate_gate_open'] else 'off'}, skipped {L['fea_skipped']} | order {L['prior']['order']}",
              flush=True)
    print(kb.stats())


if __name__ == "__main__":
    main()
