"""How v2 gets better with every plate it pockets (and every option the user picks).

Three kinds of learning, all fitted fresh from the knowledge database at the start of every
run, so each new plate is planned with everything learned from the ones before it:

1. **Within one plate (adaptive search).** After the spacing grid, the planner bisects the
   spacing where a family crosses the stiffness target, so the pick lands close to the
   target instead of wherever the fixed grid happened to stop (runner.py).
2. **Across plates (strategy prior + surrogate).** Plates are compared by descriptors (size,
   aspect, holes, protection, symmetry, load mode). Families that never won on the most
   similar past plates are searched on a coarser grid, winners first. A k-nearest-neighbour
   surrogate predicts a design's stiffness from its geometry before any FEA, with an
   uncertainty and an out-of-distribution check; designs it is confidently sure miss the
   target by a wide margin are not analysed. The surrogate only *prunes*, never approves:
   every design that can be picked still gets full FEA and every hard check. Its gate opens
   only when a leave-one-plate-out test on past data shows it would never have skipped a
   design that actually met the target.
3. **The user's style (style.py).** Ties between designs that already pass everything are
   broken by closeness to the user's own hand-pocketed plates, with weights refitted from
   the options the user picks.

Only FEA-backed rows train anything (knowledge.py evidence tiers).
"""
from __future__ import annotations

import math
from collections import Counter

import numpy as np
from shapely.geometry import Polygon

from . import validate
from .features import classify_hole
from .knowledge import KnowledgeBase
from .style import Preference, descriptors

FAMILIES = ("truss", "guided", "isogrid", "isogrid-turned", "hex", "hex-turned", "voronoi", "voronoi-guided")
PLATE_KEYS = ("log_area", "aspect", "fill", "n_bearing", "n_fastener", "hole_frac", "protected_frac",
              "sym_axes", "engineering")
CAND_KEYS = ("removed_frac", "spacing_rel", "eso_step", "pockets_per_dm2", "rib_density")

K_NEIGHBOURS = 7
MIN_PLATES = 4            # the surrogate may skip FEA only after this many distinct plates ...
MIN_ROWS = 120            # ... and this many FEA-labelled designs
SKIP_RATIO = 0.8          # skip only if even (prediction + 2 sigma) < 0.8 x target
PRIOR_NEIGHBOURS = 3      # similar plates consulted for the strategy prior
PRUNE_WITH_PRIOR = False  # see Learner._prior


# --------------------------------------------------------------------------- descriptors

def plate_descriptors(plate, dom, engineering):
    prof = plate.profile
    outline = Polygon(prof.exterior)
    rc = np.array(outline.minimum_rotated_rectangle.exterior.coords)
    e = sorted([np.linalg.norm(rc[1] - rc[0]), np.linalg.norm(rc[2] - rc[1])])
    kinds = [classify_hole(Polygon(h))[0] for h in prof.interiors]
    return {"log_area": math.log(prof.area), "aspect": e[1] / max(e[0], 1e-6),
            "fill": outline.area / max(e[0] * e[1], 1e-6),
            "n_bearing": kinds.count("bearing"), "n_fastener": kinds.count("fastener"),
            "hole_frac": 1 - prof.area / outline.area, "protected_frac": dom.protected().area / prof.area,
            "sym_axes": len(dom.axes), "engineering": int(bool(engineering)), "thickness": plate.thickness}


def candidate_features(lay, family, spacing, eso_step):
    """Geometry-only features of a design (available before any FEA)."""
    r = lay.r
    pockets = validate.rounded(lay.outlines, r)
    region = max(lay.region.area, 1e-6)
    removed = sum(p.area for p in pockets) / lay.profile.area
    f = {"removed_frac": removed, "spacing_rel": spacing / math.sqrt(region), "eso_step": eso_step,
         "pockets_per_dm2": len(pockets) / (lay.profile.area / 1e4),
         "rib_density": sum(ln.length for ln in lay.lines) * r.rib / region}
    for fam in FAMILIES:
        f["fam_" + fam] = float(family == fam)
    return f


def style_of(lay):
    return descriptors(lay.profile, validate.rounded(lay.outlines, lay.r))


def _vec(feat, pdesc):
    return np.array([feat.get(k, 0.0) for k in CAND_KEYS] + [feat.get("fam_" + f, 0.0) for f in FAMILIES]
                    + [pdesc.get(k, 0.0) for k in PLATE_KEYS], float)


# column weights: the design's own geometry matters more than the plate's context
_W = np.array([3.0, 1.5, 1.0, 1.0, 1.0] + [1.0] * len(FAMILIES) + [0.5] * len(PLATE_KEYS))


# --------------------------------------------------------------------------- surrogate

class Surrogate:
    """kNN regression of log(stiffness retained) with an uncertainty and a novelty distance."""

    def __init__(self, rows, plate_desc):
        self.X, self.y, self.g, self.t = [], [], [], []
        for r in rows:
            pd = plate_desc.get(r["plate_id"])
            if pd is None or not r["features"]:
                continue
            self.X.append(_vec(r["features"], pd))
            self.y.append(math.log(max(r["stiffness"], 1e-3)))
            self.g.append(r["plate_id"])
            self.t.append(r.get("target") or 0.33)
        self._refit()

    def _refit(self):
        self.Xa = np.array(self.X) if self.X else np.zeros((0, len(_W)))
        self.ya, self.ga = np.array(self.y), np.array(self.g)
        if len(self.Xa):
            self.mu = self.Xa.mean(axis=0)
            self.sd = np.maximum(self.Xa.std(axis=0), 1e-6)

    def add(self, feat, pdesc, stiffness, plate_id):
        """A design just analysed in this run (within-plate learning)."""
        self.X.append(_vec(feat, pdesc))
        self.y.append(math.log(max(stiffness, 1e-3)))
        self.g.append(plate_id)
        self._refit()

    def _z(self, X):
        return (X - self.mu) / self.sd * _W

    def predict(self, x, mask=None):
        """(mean log-stiffness, sigma, distance to nearest neighbour) or None."""
        X, y = self.Xa, self.ya
        if mask is not None:
            X, y = X[mask], y[mask]
        if len(X) < K_NEIGHBOURS:
            return None
        d = np.linalg.norm(self._z(X) - self._z(x[None]), axis=1)
        idx = np.argsort(d)[:K_NEIGHBOURS]
        w = 1 / (d[idx] + 0.05)
        m = float((w * y[idx]).sum() / w.sum())
        var = float((w * (y[idx] - m) ** 2).sum() / w.sum())
        return m, math.sqrt(var + (0.1 * d[idx[0]]) ** 2), float(d[idx[0]])

    def lopo(self):
        """Leave-one-plate-out test of the skip rule: (rows tested, would skip, wrongly skipped, MAE, novelty q95)."""
        n = skip = wrong = 0
        err, nn = [], []
        for g in np.unique(self.ga):
            test, train = self.ga == g, self.ga != g
            for x, y, t in zip(self.Xa[test], self.ya[test], np.array(self.t)[test]):
                p = self.predict(x, train)
                if p is None:
                    continue
                m, s, d = p
                n += 1
                err.append(abs(math.exp(m) - math.exp(y)))
                nn.append(d)
                if math.exp(m + 2 * s) < SKIP_RATIO * t:
                    skip += 1
                    wrong += math.exp(y) >= t
        q95 = float(np.percentile(nn, 95)) if nn else 0.0
        return {"tested": n, "would_skip": skip, "wrong_skips": int(wrong),
                "mae_stiffness": float(np.mean(err)) if err else None, "novelty_q95": q95}


# --------------------------------------------------------------------------- learner

class Learner:
    """Everything learned so far, applied to one new run."""

    def __init__(self, kb: KnowledgeBase, plate, dom, engineering):
        self.kb = kb
        self.pdesc = plate_descriptors(plate, dom, engineering)
        plates = kb.plates()
        pdescs = {p["id"]: p["descriptors"] for p in plates}
        rows = kb.labelled()
        self.n_plates = len({r["plate_id"] for r in rows})
        self.sur = Surrogate(rows, pdescs)
        self.test = self.sur.lopo() if self.n_plates >= 2 else None
        self.gate = bool(self.test and self.n_plates >= MIN_PLATES and len(self.sur.y) >= MIN_ROWS
                         and self.test["wrong_skips"] == 0 and self.test["would_skip"] > 0)
        self.novelty = self.test["novelty_q95"] if self.test else 0.0
        self.prior = self._prior(pdescs)
        self.pref = Preference(kb.style_refs(), kb.choice_pairs(), [r["style"] for r in rows])
        self.skipped = 0
        self.ood_seen = 0
        self.plate_id = None

    def _prior(self, pdescs):
        """Families ranked by how often they won on the most similar past plates."""
        wins = self.kb.winners()
        if not wins:
            return {"neighbours": [], "order": list(FAMILIES), "coarse": []}
        keys = [k for k in PLATE_KEYS]
        known = {w["plate_id"]: pdescs[w["plate_id"]] for w in wins if w["plate_id"] in pdescs}
        P = np.array([[d.get(k, 0.0) for k in keys] for d in known.values()] + [[self.pdesc[k] for k in keys]])
        sd = np.maximum(P.std(axis=0), 1e-6)
        me = P[-1]
        dist = {pid: float(np.linalg.norm((np.array([d.get(k, 0.0) for k in keys]) - me) / sd))
                for pid, d in known.items()}
        near = sorted(dist, key=dist.get)[:PRIOR_NEIGHBOURS]
        votes = Counter(w["family"] for w in wins if w["plate_id"] in near)
        order = sorted(FAMILIES, key=lambda f: -votes.get(f, 0))
        # a coarser grid for families that never won here saved FEA runs but lost weight on held-out
        # plates (bench/learning_results.md: 43.5 -> 40.1 % on side_plate), so for now the prior
        # only orders the search; it may prune again once learning_eval shows no loss
        coarse = [f for f in FAMILIES if votes.get(f, 0) == 0] if PRUNE_WITH_PRIOR and len(near) >= PRIOR_NEIGHBOURS else []
        return {"neighbours": [{"plate_id": p, "distance": round(dist[p], 2)} for p in near],
                "wins": dict(votes), "order": order, "coarse": coarse}

    def screen(self, feat, target):
        """(skip?, prediction) for a design that passed the hard rules, before its FEA."""
        p = self.sur.predict(_vec(feat, self.pdesc))
        if p is None:
            return False, None
        m, s, d = p
        pred = (math.exp(m), s)
        if d > self.novelty * 1.0 and self.novelty > 0:
            self.ood_seen += 1
            return False, pred  # unlike anything seen before: analyse it
        if self.gate and math.exp(m + 2 * s) < SKIP_RATIO * target:
            self.skipped += 1
            return True, pred
        return False, pred

    def learn(self, feat, stiffness):
        self.sur.add(feat, self.pdesc, stiffness, self.plate_id)

    def style_score(self, style):
        return self.pref.score(style) if self.pref.ok else None

    def summary(self):
        st = self.kb.stats()
        return {"knowledge": st, "plates_learned_from": self.n_plates,
                "surrogate_test": self.test, "surrogate_gate_open": self.gate,
                "fea_skipped": self.skipped, "novel_designs": self.ood_seen,
                "prior": self.prior, "style": self.pref.summary()}
