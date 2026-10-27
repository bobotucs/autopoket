"""What a pocket layout looks like, and which look the user prefers.

Style is learned separately from structure and only ever breaks ties between designs that
already pass every hard rule and the stiffness target (rules -> feasible designs -> style).

* `descriptors` turns a layout into a few numbers: pocket density, typical pocket size,
  size uniformity, roundness, corners per pocket, web and edge-margin widths.
* `reference_designs` measures the user's own hand-pocketed plates in examples/ (the
  pockets are separated from real holes by examples/classify.py). These are style
  references only: a hand-made pocket says nothing about structural safety.
* `Preference` scores a layout by its distance from the user's style, with one weight per
  descriptor. The weights start equal and are refitted (Bradley-Terry: P(B over A) =
  sigmoid(score B - score A)) every time the user picks a different option than the
  automatic one or downloads it.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import Polygon
from shapely.ops import unary_union

from .features import outline_sides

STYLE_KEYS = ("pockets_per_dm2", "log_pocket_area", "size_cv", "compactness", "corners", "web_mm", "margin_mm")
EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def descriptors(profile: Polygon, pockets):
    """Style numbers for a set of pocket polygons in a plate profile."""
    pockets = [p for p in pockets if not p.is_empty and p.area > 1.0]
    if not pockets:
        return {}
    A = np.array([p.area for p in pockets])
    comp = [4 * math.pi * p.area / max(p.length ** 2, 1e-9) for p in pockets]
    corners = [len(outline_sides(p)[1]) for p in pockets]
    tree = shapely.STRtree(pockets)
    web = []
    for i, p in enumerate(pockets):
        near = [p.distance(pockets[j]) for j in tree.query(p.buffer(60.0)) if j != i]
        if near:
            web.append(min(near))
    edges = unary_union([profile.exterior, *profile.interiors])
    margin = [p.distance(edges) for p in pockets]
    return {"pockets_per_dm2": len(pockets) / (profile.area / 1e4),
            "log_pocket_area": float(np.log(np.median(A))),
            "size_cv": float(A.std() / A.mean()),
            "compactness": float(np.mean(comp)),
            "corners": float(np.mean(corners)),
            "web_mm": float(np.median(web)) if web else 0.0,
            "margin_mm": float(np.median(margin)),
            "removed_frac": float(A.sum() / profile.area)}


def reference_designs():
    """{name: descriptors} of the user's hand-pocketed reference plates in examples/."""
    sys.path.insert(0, str(EXAMPLES))
    import classify  # examples/classify.py
    out = {}
    for path in sorted(EXAMPLES.glob("*.step")):
        if path.name.startswith("blank_"):
            continue
        plate, keep, pockets, _ = classify.split(path)
        if not pockets:
            continue
        blank = Polygon(plate.profile.exterior, [ring for ring, _ in keep])
        out[path.stem] = descriptors(blank, [Polygon(ring) for ring, _ in pockets])
    return out


class Preference:
    """Score = -sum_k w_k * ((d_k - mu_k) / s_k)^2, mu = the user's reference style."""

    def __init__(self, refs, pairs=(), population=()):
        refs = [r for r in refs if r]
        self.keys = [k for k in STYLE_KEYS if all(k in r for r in refs)] if refs else []
        self.ok = bool(self.keys)
        if not self.ok:
            return
        R = np.array([[r[k] for k in self.keys] for r in refs])
        self.mu = R.mean(axis=0)
        pop = [p for p in population if p and all(k in p for k in self.keys)]
        P = np.array([[p[k] for k in self.keys] for p in pop]) if len(pop) > 5 else R
        self.s = np.maximum(np.vstack([P, R]).std(axis=0), 1e-3)
        self.w = np.ones(len(self.keys))
        self.n_pairs = 0
        self.fit(pairs)

    def _dev(self, d):
        x = np.array([d.get(k, m) for k, m in zip(self.keys, self.mu)])
        return ((x - self.mu) / self.s) ** 2

    def fit(self, pairs, lam=1.0, steps=300, lr=0.05):
        """Bradley-Terry on (preferred, rejected) style pairs, weights kept >= 0 and pulled toward 1."""
        Z = [self._dev(rej) - self._dev(pref) for pref, rej in pairs if pref and rej]
        self.n_pairs = len(Z)
        if not Z:
            return
        Z = np.array(Z)
        w = self.w.copy()
        for _ in range(steps):
            p = 1 / (1 + np.exp(-(Z @ w)))
            grad = ((1 - p)[:, None] * Z).sum(axis=0) - lam * (w - 1)
            w = np.maximum(w + lr * grad / max(len(Z), 1), 0.0)
        self.w = w

    def score(self, d):
        if not self.ok or not d:
            return None
        return float(-self.w @ self._dev(d))

    def summary(self):
        if not self.ok:
            return None
        return {"reference": dict(zip(self.keys, np.round(self.mu, 3).tolist())),
                "weights": dict(zip(self.keys, np.round(self.w, 3).tolist())), "choices_learned": self.n_pairs}
