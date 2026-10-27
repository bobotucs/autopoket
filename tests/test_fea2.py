"""Regression checks for v2's plate FEA against hand calculations.

    python tests/test_fea2.py        (or: python -m pytest tests)

The model works in E = 1 (MPa) with 1 N loads, so deflections are compared as
compliance * E and stresses directly in MPa per N.
"""
import sys
from pathlib import Path

import numpy as np
from shapely.geometry import Polygon, box

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from autopocket import fea  # noqa: E402
from autopocket2 import fea2  # noqa: E402

L, B, T = 300.0, 24.0, 3.175  # cantilever strip, mm


def _strip_model(h):
    profile = box(0, 0, L, B)
    grid = fea.make_grid(profile, T, target_cells=int(L * B / h ** 2), max_cells=200000)
    m = fea2.Model(fea.raster(profile, grid), grid)
    xyz = m.xyz
    lo, hi = xyz[:, 0].min(), xyz[:, 0].max()
    clamp = m.node_global[xyz[:, 0] <= lo + 1e-6]
    tip = m.node_global[xyz[:, 0] >= hi - 1e-6]
    fea2._fix(m, clamp)
    return m, grid, tip


def _tip_case(m, tip, axis):
    F = np.zeros(3)
    F[axis] = 1.0 / len(tip)
    u, f = m.solve({int(g): F for g in tip})
    return u, float(f @ u)


def test_out_of_plane_cantilever():
    m, grid, tip = _strip_model(2.0)
    u, c = _tip_case(m, tip, 2)
    I = B * T ** 3 / 12
    nu = fea.NU
    # a strip this wide (b/t = 7.6) sits between beam (E I) and cylindrical-plate (E I / (1 - nu^2))
    exact = L ** 3 / (3 * I)
    assert 0.97 * exact * (1 - nu ** 2) < c < 1.05 * exact, (c / exact)
    # surface bending stress sigma_x two cells from the clamp ~ M c / I
    h = grid["h"]
    x = m.elem_ijk[:, 0] * h + h / 2 + grid["lo"][0]
    near = np.abs(x - (grid["lo"][0] + 2.5 * h)) < h / 2
    ue = u[m.edof][near]
    top = fea2.surface_bmats([h, h, T])[0]
    sx = np.abs((ue @ top.T @ fea2.DMAT.T)[:, 0]).mean()
    want = (L - 2.5 * h) * (T / 2) / I
    assert abs(sx / want - 1) < 0.10, (sx, want)
    vm = fea2.surface_von_mises(m, u, fea2.surface_bmats([h, h, T]))[near].mean()
    assert 0.85 * want < vm < 1.05 * want, (vm, want)  # sigma_y = 0 .. nu sigma_x across the width
    # the old mid-plane recovery misses it almost entirely
    assert m.stresses(u)[near].mean() < 0.2 * want


def test_in_plane_cantilever():
    m, grid, tip = _strip_model(2.0)
    u, c = _tip_case(m, tip, 1)
    I = T * B ** 3 / 12
    G = 1 / (2 * (1 + fea.NU))
    exact = L ** 3 / (3 * I) + L / (5 / 6 * G * B * T)  # Timoshenko beam
    # in-plane the strip is a plane-stress beam; the plate law stiffens the axial strain by up
    # to 1/(1 - nu^2) where the width can't contract freely (only near the clamp here)
    assert 0.93 * exact < c < 1.03 * exact, (c / exact)


def test_mirror_invariance():
    prof = Polygon([(0, 0), (200, 0), (200, 80), (0, 80)]).difference(box(30, 30, 50, 50))
    mirrored = Polygon([(200 - x, y) for x, y in prof.exterior.coords],
                       [[(200 - x, y) for x, y in r.coords] for r in prof.interiors])
    a, b = fea2.Analysis(prof, T), fea2.Analysis(mirrored, T)
    ca = sorted(v[0] for v in a.ref.values())
    cb = sorted(v[0] for v in b.ref.values())
    assert np.allclose(ca, cb, rtol=0.02), (ca, cb)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
