"""Persistent evidence store: every plate, run, candidate design and user choice.

This is where v2's learning lives (the language model driving it doesn't change between
sessions; this database does). One SQLite file, `knowledge/autopocket.db`, records:

  plate      geometry hash, name, descriptors (size, holes, symmetry, protection ...)
  run        settings, load model, what the learner did, the design picked
  candidate  every design generated: family, spacing, pruning step, geometry features,
             style descriptors, FEA result, and its evidence tier
  choice     the user picking another option, or downloading one
  style_ref  style descriptors of the user's own hand-pocketed plates

Evidence tiers decide what may be learned from. Only rows a real FEA produced are ever
training labels; a surrogate's prediction is never fed back as truth (that is how a
self-training model talks itself into its own mistakes).
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from pathlib import Path

import numpy as np

DEFAULT_DB = Path(__file__).resolve().parents[1] / "knowledge" / "autopocket.db"

GEOMETRY_REJECTED = "GEOMETRY_REJECTED"          # broke a hard rule, never analysed
FEA_FEASIBLE = "FEA_RELIABLE_FEASIBLE"           # analysed, meets the stiffness target
FEA_INFEASIBLE = "FEA_RELIABLE_INFEASIBLE"       # analysed, below the target
SURROGATE_SKIPPED = "SURROGATE_SKIPPED"          # predicted hopeless, not analysed: never a label
STYLE_REFERENCE = "STYLE_REFERENCE_ONLY"         # a hand-made design: style, not structure
LABELLED = (FEA_FEASIBLE, FEA_INFEASIBLE)

SCHEMA = """
CREATE TABLE IF NOT EXISTS plate (
    id INTEGER PRIMARY KEY, sha TEXT UNIQUE, name TEXT, thickness REAL,
    descriptors TEXT, created REAL);
CREATE TABLE IF NOT EXISTS run (
    id INTEGER PRIMARY KEY, plate_id INTEGER, n_plates INTEGER, created REAL, version TEXT,
    source TEXT, settings TEXT, load_mode TEXT, target REAL, seconds REAL,
    auto_candidate INTEGER, learning TEXT);
CREATE TABLE IF NOT EXISTS candidate (
    id INTEGER PRIMARY KEY, run_id INTEGER, plate_id INTEGER, family TEXT, spacing REAL,
    eso_step INTEGER, parent_id INTEGER, label TEXT, status TEXT, failed TEXT,
    mass_saved REAL, stiffness REAL, stress REAL, fine_stiffness REAL,
    features TEXT, style TEXT, predicted REAL, pred_sigma REAL);
CREATE TABLE IF NOT EXISTS choice (
    id INTEGER PRIMARY KEY, run_id INTEGER, preferred INTEGER, rejected INTEGER,
    kind TEXT, created REAL);
CREATE TABLE IF NOT EXISTS style_ref (
    id INTEGER PRIMARY KEY, name TEXT UNIQUE, source TEXT, descriptors TEXT, created REAL);
CREATE INDEX IF NOT EXISTS cand_run ON candidate(run_id);
CREATE INDEX IF NOT EXISTS cand_plate ON candidate(plate_id);
"""


def plate_sha(profile, thickness):
    """Hash of the plate's 2D profile (rounded to 0.01 mm) and thickness: same plate, same id."""
    rings = [profile.exterior, *profile.interiors]
    h = hashlib.sha256(f"{thickness:.2f}".encode())
    for ring in sorted(rings, key=lambda r: -abs(r.length)):
        h.update(np.round(np.asarray(ring.coords), 2).tobytes())
    return h.hexdigest()


def _j(x):
    return json.dumps(x, default=float)


class KnowledgeBase:
    def __init__(self, path=DEFAULT_DB):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.db.executescript(SCHEMA)

    # ------------------------------------------------------------------ writes
    def _ins(self, sql, args):
        with self.lock:
            cur = self.db.execute(sql, args)
            self.db.commit()
            return cur.lastrowid

    def plate_id(self, sha, name, thickness, descriptors):
        with self.lock:
            row = self.db.execute("SELECT id FROM plate WHERE sha=?", (sha,)).fetchone()
            if row:
                self.db.execute("UPDATE plate SET descriptors=? WHERE id=?", (_j(descriptors), row["id"]))
                self.db.commit()
                return row["id"]
        return self._ins("INSERT INTO plate(sha,name,thickness,descriptors,created) VALUES(?,?,?,?,?)",
                         (sha, name, thickness, _j(descriptors), time.time()))

    def start_run(self, plate_id, n_plates, version, source, settings, load_mode, target):
        return self._ins("INSERT INTO run(plate_id,n_plates,created,version,source,settings,load_mode,target) "
                         "VALUES(?,?,?,?,?,?,?,?)",
                         (plate_id, n_plates, time.time(), version, source, _j(settings), load_mode, target))

    def add_candidate(self, run_id, plate_id, c, status, features=None, style=None, predicted=None):
        s = c.get("structure") or {}
        cv = c.get("convergence") or {}
        return self._ins(
            "INSERT INTO candidate(run_id,plate_id,family,spacing,eso_step,parent_id,label,status,failed,mass_saved,"
            "stiffness,stress,fine_stiffness,features,style,predicted,pred_sigma) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, plate_id, c.get("family"), c.get("spacing"), c.get("eso_step"), c.get("parent_db_id"),
             c.get("label"), status, _j(c.get("failed") or []), c.get("mass_saved_pct"),
             s.get("worst_stiffness_retained"), s.get("worst_peak_stress_ratio"), cv.get("fine_stiffness"),
             _j(features or {}), _j(style or {}),
             None if predicted is None else predicted[0], None if predicted is None else predicted[1]))

    def set_fine(self, cand_id, fine):
        with self.lock:
            self.db.execute("UPDATE candidate SET fine_stiffness=? WHERE id=?", (fine, cand_id))
            self.db.commit()

    def finish_run(self, run_id, auto_candidate, seconds, learning):
        with self.lock:
            self.db.execute("UPDATE run SET auto_candidate=?, seconds=?, learning=? WHERE id=?",
                            (auto_candidate, seconds, _j(learning), run_id))
            self.db.commit()

    def add_choice(self, run_id, preferred, rejected, kind):
        return self._ins("INSERT INTO choice(run_id,preferred,rejected,kind,created) VALUES(?,?,?,?,?)",
                         (run_id, preferred, rejected, kind, time.time()))

    def add_style_ref(self, name, descriptors, source="user example"):
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO style_ref(name,source,descriptors,created) VALUES(?,?,?,?)",
                            (name, source, _j(descriptors), time.time()))
            self.db.commit()

    # ------------------------------------------------------------------ reads
    def rows(self, sql, args=()):
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    def labelled(self):
        """Every FEA-backed candidate (the only rows that may train a model)."""
        out = self.rows("SELECT c.*, r.target AS target FROM candidate c JOIN run r ON r.id = c.run_id "
                        f"WHERE c.status IN ({','.join('?' * len(LABELLED))}) AND c.stiffness IS NOT NULL", LABELLED)
        for r in out:
            r["features"] = json.loads(r["features"] or "{}")
            r["style"] = json.loads(r["style"] or "{}")
        return out

    def plates(self):
        out = self.rows("SELECT * FROM plate")
        for r in out:
            r["descriptors"] = json.loads(r["descriptors"] or "{}")
        return out

    def winners(self):
        """Per finished run: the plate and the picked candidate's family / spacing / mass."""
        return self.rows("SELECT r.id AS run_id, r.plate_id, r.load_mode, c.family, c.spacing, c.eso_step, "
                         "c.mass_saved, c.stiffness FROM run r JOIN candidate c ON c.id = r.auto_candidate")

    def choice_pairs(self):
        """(preferred style, rejected style) for every explicit user preference."""
        out = []
        for r in self.rows("SELECT p.style AS ps, q.style AS qs FROM choice ch JOIN candidate p ON p.id = ch.preferred "
                           "JOIN candidate q ON q.id = ch.rejected WHERE ch.rejected IS NOT NULL "
                           "AND ch.preferred != ch.rejected"):
            out.append((json.loads(r["ps"] or "{}"), json.loads(r["qs"] or "{}")))
        return out

    def style_refs(self):
        return [json.loads(r["descriptors"]) for r in self.rows("SELECT descriptors FROM style_ref")]

    def stats(self):
        q = lambda sql, a=(): self.rows(sql, a)[0]["n"]  # noqa: E731
        return {"plates": q("SELECT COUNT(*) AS n FROM plate"),
                "runs": q("SELECT COUNT(*) AS n FROM run"),
                "fea_designs": q(f"SELECT COUNT(*) AS n FROM candidate WHERE status IN ({','.join('?' * len(LABELLED))})",
                                 LABELLED),
                "choices": q("SELECT COUNT(*) AS n FROM choice"),
                "style_refs": q("SELECT COUNT(*) AS n FROM style_ref")}
