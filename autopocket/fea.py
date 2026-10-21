"""Quick finite-element check comparing a blank plate with its pocketed version.

The plate profile (2D, in the plate's own frame) is rasterised into cells with
fractional fill, extruded into a layer of hex8 elements through the thickness
and solved as a linear-elastic model under three generic cantilever load cases:
out-of-plane bending, in-plane bending and torsion, clamped at one end of the
long axis and loaded at the other. Shear terms use reduced integration so thin
elements don't lock in bending.

The output is *relative*: how much stiffness the pocketed plate keeps and how much
the peak stress rises. It is an estimate, not a certified analysis.
"""
from __future__ import annotations

import math

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
import shapely
from shapely import affinity

NU = 0.3
CORNERS = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
                    [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]])


def _dmat(nu=NU):
    lam, mu = nu / ((1 + nu) * (1 - 2 * nu)), 1 / (2 * (1 + nu))
    D = np.zeros((6, 6))
    D[:3, :3] = lam
    D[np.arange(3), np.arange(3)] += 2 * mu
    D[3:, 3:] = np.eye(3) * mu
    return D


DMAT = _dmat()


def _bmat(xi, dims):
    s = CORNERS * 2 - 1
    B = np.zeros((6, 24))
    for k in range(8):
        f = 1 + s[k] * xi
        d = np.array([s[k, 0] * f[1] * f[2], s[k, 1] * f[0] * f[2], s[k, 2] * f[0] * f[1]]) / 8
        dx, dy, dz = d * 2 / dims
        B[0, 3 * k], B[1, 3 * k + 1], B[2, 3 * k + 2] = dx, dy, dz
        B[3, 3 * k], B[3, 3 * k + 1] = dy, dx
        B[4, 3 * k + 1], B[4, 3 * k + 2] = dz, dy
        B[5, 3 * k], B[5, 3 * k + 2] = dz, dx
    return B


def hex_ke(dims):
    """Stiffness (E = 1) of a box element; selective reduced integration of shear."""
    dims = np.asarray(dims, float)
    vol = dims.prod()
    g = 1 / math.sqrt(3)
    Ke = np.zeros((24, 24))
    for xi in [(x, y, z) for x in (-g, g) for y in (-g, g) for z in (-g, g)]:
        B = _bmat(np.array(xi), dims)
        Ke += B[:3].T @ DMAT[:3, :3] @ B[:3] * vol / 8
    Bc = _bmat(np.zeros(3), dims)
    Ke += Bc[3:].T @ DMAT[3:, 3:] @ Bc[3:] * vol
    return Ke, Bc


# --------------------------------------------------------------------------- rasterising

def _align(profile):
    """Angle (deg) that puts the plate's long axis along x, and the rotation centre."""
    rect = profile.minimum_rotated_rectangle
    c = np.array(rect.exterior.coords)
    e1, e2 = c[1] - c[0], c[2] - c[1]
    e = e1 if np.hypot(*e1) >= np.hypot(*e2) else e2
    return math.degrees(math.atan2(e[1], e[0])), profile.centroid


def make_grid(profile, thickness, target_cells=6000, max_cells=16000, rib=8.0):
    ang, ctr = _align(profile)
    minx, miny, maxx, maxy = affinity.rotate(profile, -ang, origin=ctr).bounds
    area = (maxx - minx) * (maxy - miny)
    h = math.sqrt(area / target_cells)
    h = min(h, rib / 3)                       # ribs at least ~3 cells wide...
    h = max(h, math.sqrt(area / max_cells))   # ...unless the plate is huge
    nx, ny = max(2, math.ceil((maxx - minx) / h)), max(2, math.ceil((maxy - miny) / h))
    return {"ang": ang, "ctr": ctr, "lo": np.array([minx, miny]), "h": h, "n": (nx, ny),
            "t": thickness, "layers": 1}


def raster(profile, grid, ss=4):
    """Fraction of each in-plane cell covered by the profile, shape (nx, ny)."""
    poly = affinity.rotate(profile, -grid["ang"], origin=grid["ctr"])
    nx, ny = grid["n"]
    h = grid["h"]
    xs = grid["lo"][0] + (np.arange(nx * ss) + 0.5) * h / ss
    ys = grid["lo"][1] + (np.arange(ny * ss) + 0.5) * h / ss
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    shapely.prepare(poly)
    inside = shapely.contains_xy(poly, X, Y)
    return inside.reshape(nx, ss, ny, ss).mean(axis=(1, 3))


# --------------------------------------------------------------------------- model

class Model:
    def __init__(self, fill2d, grid, min_fill=0.02):
        nx, ny = grid["n"]
        nz = grid["layers"]
        h, t = grid["h"], grid["t"]
        Ke, self.Bc = hex_ke([h, h, t / nz])
        ex, ey = np.nonzero(fill2d > min_fill)
        ex, ey, ez = np.repeat(ex, nz), np.repeat(ey, nz), np.tile(np.arange(nz), len(ex))
        self.rho = fill2d[ex, ey]
        self.elem_ijk = np.c_[ex, ey, ez]
        nid = lambda i, j, k: (i * (ny + 1) + j) * (nz + 1) + k
        conn = np.stack([nid(ex + c[0], ey + c[1], ez + c[2]) for c in CORNERS], axis=1)
        used, inv = np.unique(conn, return_inverse=True)
        self.conn = inv.reshape(conn.shape)
        k = used % (nz + 1)
        j = (used // (nz + 1)) % (ny + 1)
        i = used // ((nz + 1) * (ny + 1))
        self.node_global = used
        self.xyz = np.c_[grid["lo"][0] + i * h, grid["lo"][1] + j * h, k * t / nz]
        self.n_nodes = len(used)
        self.edof = (self.conn[:, :, None] * 3 + np.arange(3)).reshape(len(ex), 24)
        rows = np.repeat(self.edof, 24, axis=1).ravel()
        cols = np.tile(self.edof, (1, 24)).ravel()
        vals = (self.rho[:, None, None] * Ke[None]).ravel()
        self.K = sp.coo_matrix((vals, (rows, cols)), shape=(3 * self.n_nodes,) * 2).tocsr()

    def fix(self, fixed_global):
        """Clamp the given global nodes and prepare the solver (reused for every load case)."""
        self.g2l = {g: l for l, g in enumerate(self.node_global)}
        fixed = np.array([self.g2l[g] for g in fixed_global if g in self.g2l], dtype=int)
        fixed_dofs = (fixed[:, None] * 3 + np.arange(3)).ravel()
        self.free = np.setdiff1d(np.arange(3 * self.n_nodes), fixed_dofs)
        self.solver = _Solver(self.K[self.free][:, self.free].tocsr(), self.xyz[self.free // 3])

    def solve(self, loads_global):
        f = np.zeros(3 * self.n_nodes)
        for g, F in loads_global.items():
            if g in self.g2l:
                f[3 * self.g2l[g]:3 * self.g2l[g] + 3] += F
        u = np.zeros(3 * self.n_nodes)
        u[self.free] = self.solver(f[self.free])
        return u, f

    def stresses(self, u):
        s = (u[self.edof] @ self.Bc.T @ DMAT.T) * self.rho[:, None]
        sx, sy, sz, txy, tyz, txz = s.T
        return np.sqrt(0.5 * ((sx - sy) ** 2 + (sy - sz) ** 2 + (sz - sx) ** 2)
                       + 3 * (txy ** 2 + tyz ** 2 + txz ** 2))


class _Solver:
    """Sparse LU factorisation: set up once, solve every load case cheaply."""

    def __init__(self, K, xyz):
        self.lu = spla.splu(K.tocsc(), permc_spec="COLAMD")

    def __call__(self, f):
        return self.lu.solve(f)


def load_cases(model: Model, grid):
    """Clamped at the -x end of the long axis, loaded at the +x end."""
    xyz = model.xyz
    lo, hi = xyz[:, 0].min(), xyz[:, 0].max()
    band = max(0.05 * (hi - lo), 1.01 * grid["h"])
    fixed = model.node_global[xyz[:, 0] <= lo + band]
    tip_mask = xyz[:, 0] >= hi - band
    tip, tip_xyz = model.node_global[tip_mask], xyz[tip_mask]
    cases = {}
    for name, axis in [("Out-of-plane bending", 2), ("In-plane bending", 1)]:
        F = np.zeros(3)
        F[axis] = 1.0 / len(tip)
        cases[name] = {int(g): F for g in tip}
    r = tip_xyz - tip_xyz.mean(0)
    r[:, 0] = 0
    tv = np.cross([1.0, 0, 0], r)
    norm = (np.linalg.norm(r, axis=1) ** 2).sum()
    cases["Torsion"] = {int(g): v / max(norm, 1e-12) for g, v in zip(tip, tv)}
    return fixed, cases


class Baseline:
    """FE model of the blank plate; evaluate() compares a pocketed profile against it."""

    def __init__(self, profile, thickness):
        self.grid = make_grid(profile, thickness)
        self.m0 = Model(raster(profile, self.grid), self.grid)
        self.fixed, self.cases = load_cases(self.m0, self.grid)
        self.m0.fix(self.fixed)
        # ignore stresses right at the clamp and load patches (artificial singularities)
        tip = np.array(list(next(iter(self.cases.values())).keys()))
        zone = np.isin(self.m0.node_global, self.fixed) | np.isin(self.m0.node_global, tip)
        self.zone_elems0 = np.isin(self.m0.conn, np.nonzero(zone)[0]).any(axis=1)
        self.zone_ij = {tuple(x) for x in self.m0.elem_ijk[self.zone_elems0, :2].tolist()}
        self.ref = {}
        for name, loads in self.cases.items():
            u0, f0 = self.m0.solve(loads)
            s0 = self.m0.stresses(u0)[~self.zone_elems0]
            self.ref[name] = (float(f0 @ u0), float(np.percentile(s0, 99)) if len(s0) else 1.0)

    def evaluate(self, profile):
        m1 = Model(raster(profile, self.grid), self.grid)
        m1.fix(self.fixed)
        zone1 = np.array([tuple(x) in self.zone_ij for x in m1.elem_ijk[:, :2].tolist()], dtype=bool)
        present = set(m1.node_global.tolist())
        out = []
        for name, loads in self.cases.items():
            # renormalise loads onto nodes that still exist in the pocketed plate
            kept = {g: F for g, F in loads.items() if g in present}
            tot0 = sum(np.linalg.norm(F) for F in loads.values())
            tot1 = sum(np.linalg.norm(F) for F in kept.values())
            u1, f1 = m1.solve({g: F * tot0 / max(tot1, 1e-12) for g, F in kept.items()})
            s1 = m1.stresses(u1)[~zone1]
            c0, p0 = self.ref[name]
            c1 = float(f1 @ u1)
            p1 = float(np.percentile(s1, 99)) if len(s1) else 1.0
            out.append({"case": name,
                        "stiffness_retained": c0 / c1 if c1 > 0 else 0.0,
                        "peak_stress_ratio": p1 / p0 if p0 > 0 else 1.0})
        return {"cells": int(np.prod(self.grid["n"])), "cell_size": self.grid["h"], "cases": out,
                "worst_stiffness_retained": min(c["stiffness_retained"] for c in out),
                "worst_peak_stress_ratio": max(c["peak_stress_ratio"] for c in out)}
