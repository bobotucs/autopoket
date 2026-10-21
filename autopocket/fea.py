"""Quick voxel finite-element check comparing an original and a pocketed part.

Both shapes are voxelised on the same grid (fractional fill from exact ray/mesh
intersections) and solved as linear-elastic hex8 models under three generic
cantilever load cases: bending about the weak axis, bending about the strong
axis, and torsion. The result is a *relative* comparison: how much stiffness is
kept and how much peak stress rises. It is an estimate, not a certified analysis.
"""
from __future__ import annotations

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from . import cadio

try:
    import pyamg
except ImportError:  # pragma: no cover
    pyamg = None

NU = 0.3


# --------------------------------------------------------------------------- voxelisation

def make_grid(shape, target_voxels=36000):
    lo, hi = cadio.bbox(shape)
    size = hi - lo
    h = float((np.prod(np.maximum(size, 1e-6)) / target_voxels) ** (1 / 3))
    h = min(h, float(size.min()) / 3)  # at least 3 voxels through the thinnest direction
    dims = np.maximum(np.ceil(size / h).astype(int), 1)
    while np.prod(dims) > 4 * target_voxels:  # very thin parts: coarsen in-plane instead
        h *= 1.15
        dims = np.maximum(np.ceil(size / h).astype(int), 1)
    lo = lo - (dims * h - size) / 2
    return {"lo": lo, "h": h, "dims": dims}


def voxelize(shape, grid, ss=3):
    """Fraction of each voxel filled with material, shape (nx, ny, nz)."""
    V, T, _ = cadio.tessellate(shape, grid["h"] / 20, 0.3)
    lo, h, dims = grid["lo"], grid["h"], grid["dims"]
    ray = int(np.argmin(dims))
    a, b = [k for k in range(3) if k != ray]
    na, nb, nr = dims[a] * ss, dims[b] * ss, dims[ray]
    # column positions (sub-sampled, jittered off exact edges)
    ca = lo[a] + (np.arange(na) + 0.5) * h / ss + 1.234e-5
    cb = lo[b] + (np.arange(nb) + 0.5) * h / ss + 2.345e-5
    tri = V[T]
    hits = [[] for _ in range(na * nb)]
    for t in tri:
        A, B, C = t[:, a], t[:, b], t[:, ray]
        i0 = max(int(np.searchsorted(ca, A.min())), 0)
        i1 = int(np.searchsorted(ca, A.max(), "right"))
        j0 = max(int(np.searchsorted(cb, B.min())), 0)
        j1 = int(np.searchsorted(cb, B.max(), "right"))
        if i1 <= i0 or j1 <= j0:
            continue
        den = (B[1] - B[2]) * (A[0] - A[2]) + (A[2] - A[1]) * (B[0] - B[2])
        if abs(den) < 1e-14:
            continue
        X, Y = np.meshgrid(ca[i0:i1], cb[j0:j1], indexing="ij")
        l1 = ((B[1] - B[2]) * (X - A[2]) + (A[2] - A[1]) * (Y - B[2])) / den
        l2 = ((B[2] - B[0]) * (X - A[2]) + (A[0] - A[2]) * (Y - B[2])) / den
        l3 = 1 - l1 - l2
        m = (l1 >= 0) & (l2 >= 0) & (l3 >= 0)
        if not m.any():
            continue
        z = l1 * C[0] + l2 * C[1] + l3 * C[2]
        ii, jj = np.nonzero(m)
        for i, j, zz in zip(ii + i0, jj + j0, z[m]):
            hits[i * nb + j].append(zz)
    edges = lo[ray] + np.arange(nr + 1) * h
    fill = np.zeros((na, nb, nr))
    for idx, zs in enumerate(hits):
        if len(zs) < 2:
            continue
        zs = np.sort(zs)
        if len(zs) % 2:
            zs = zs[:-1]
        z0, z1 = zs[0::2], zs[1::2]
        cov = np.clip(edges[:, None] - z0[None, :], 0, (z1 - z0)[None, :]).sum(axis=1)
        fill[idx // nb, idx % nb] = np.diff(cov) / h
    fill = fill.reshape(dims[a], ss, dims[b], ss, nr).mean(axis=(1, 3))
    # reorder to (x, y, z)
    order = [a, b, ray]
    return np.clip(np.transpose(fill, np.argsort(order)), 0, 1)


# --------------------------------------------------------------------------- hex8 FE

def _hex8_ke(nu=NU):
    E = 1.0
    lam, mu = E * nu / ((1 + nu) * (1 - 2 * nu)), E / (2 * (1 + nu))
    D = np.zeros((6, 6))
    D[:3, :3] = lam
    D[np.arange(3), np.arange(3)] += 2 * mu
    D[3:, 3:] = np.eye(3) * mu
    corners = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
                        [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]], float)
    s = corners * 2 - 1
    g = 1 / np.sqrt(3)
    Ke = np.zeros((24, 24))
    Bc = None
    for gp in [(x, y, z) for x in (-g, g) for y in (-g, g) for z in (-g, g)] + [None]:
        xi = np.zeros(3) if gp is None else np.array(gp)
        dN = np.empty((8, 3))
        for k in range(8):
            f = 1 + s[k] * xi
            dN[k] = [s[k, 0] * f[1] * f[2], s[k, 1] * f[0] * f[2], s[k, 2] * f[0] * f[1]]
        dN = dN / 8 * 2  # d/dxi -> d/dx for unit cube (dx/dxi = 1/2)
        B = np.zeros((6, 24))
        for k in range(8):
            dx, dy, dz = dN[k]
            B[0, 3 * k], B[1, 3 * k + 1], B[2, 3 * k + 2] = dx, dy, dz
            B[3, 3 * k], B[3, 3 * k + 1] = dy, dx
            B[4, 3 * k + 1], B[4, 3 * k + 2] = dz, dy
            B[5, 3 * k], B[5, 3 * k + 2] = dz, dx
        if gp is None:
            Bc = B
        else:
            Ke += B.T @ D @ B / 8
    return Ke, D, Bc, corners.astype(int)


KE, DMAT, BC, CORNERS = _hex8_ke()


class Model:
    def __init__(self, fill, grid, min_fill=0.02):
        nx, ny, nz = fill.shape
        self.h = grid["h"]
        ex, ey, ez = np.nonzero(fill > min_fill)
        self.rho = fill[ex, ey, ez]
        self.elem_ijk = np.c_[ex, ey, ez]
        nid = lambda i, j, k: (i * (ny + 1) + j) * (nz + 1) + k
        conn = np.stack([nid(ex + c[0], ey + c[1], ez + c[2]) for c in CORNERS], axis=1)
        used, inv = np.unique(conn, return_inverse=True)
        self.conn = inv.reshape(conn.shape)
        k = used % (nz + 1)
        j = (used // (nz + 1)) % (ny + 1)
        i = used // ((nz + 1) * (ny + 1))
        self.node_global = used
        self.xyz = grid["lo"] + np.c_[i, j, k] * self.h
        self.n_nodes = len(used)
        edof = (self.conn[:, :, None] * 3 + np.arange(3)).reshape(len(ex), 24)
        self.edof = edof
        rows = np.repeat(edof, 24, axis=1).ravel()
        cols = np.tile(edof, (1, 24)).ravel()
        vals = (self.rho[:, None, None] * KE[None] * self.h).ravel()
        self.K = sp.coo_matrix((vals, (rows, cols)), shape=(3 * self.n_nodes,) * 2).tocsr()

    def fix(self, fixed_global):
        """Clamp the given global nodes and prepare the solver (reused for every load case)."""
        self.g2l = {g: l for l, g in enumerate(self.node_global)}
        fixed = np.array([self.g2l[g] for g in fixed_global if g in self.g2l], dtype=int)
        fixed_dofs = (fixed[:, None] * 3 + np.arange(3)).ravel()
        self.free = np.setdiff1d(np.arange(3 * self.n_nodes), fixed_dofs)
        self.solver = _Solver(self.K[self.free][:, self.free].tocsr(), self.xyz[self.free // 3])

    def solve(self, loads_global):
        """loads_global: {global node id: force(3)}. Returns (u, f)."""
        f = np.zeros(3 * self.n_nodes)
        for g, F in loads_global.items():
            if g in self.g2l:
                f[3 * self.g2l[g]:3 * self.g2l[g] + 3] += F
        u = np.zeros(3 * self.n_nodes)
        u[self.free] = self.solver(f[self.free])
        return u, f

    def stresses(self, u):
        ue = u[self.edof]
        strain = ue @ BC.T / self.h
        s = (strain @ DMAT.T) * self.rho[:, None]
        sx, sy, sz, txy, tyz, txz = s.T
        return np.sqrt(0.5 * ((sx - sy) ** 2 + (sy - sz) ** 2 + (sz - sx) ** 2)
                       + 3 * (txy ** 2 + tyz ** 2 + txz ** 2))


class _Solver:
    """Factor once, solve many right-hand sides."""

    def __init__(self, K, xyz):
        self.K, self.ml = K, None
        if pyamg is not None:
            # rigid body modes help AMG for elasticity
            n = K.shape[0]
            B = np.zeros((n, 6))
            comp = np.arange(n) % 3
            for c in range(3):
                B[comp == c, c] = 1
            x, y, z = xyz[:, 0], xyz[:, 1], xyz[:, 2]
            B[comp == 0, 3], B[comp == 1, 3] = -y[comp == 0], x[comp == 1]
            B[comp == 1, 4], B[comp == 2, 4] = -z[comp == 1], y[comp == 2]
            B[comp == 0, 5], B[comp == 2, 5] = z[comp == 0], -x[comp == 2]
            try:
                self.ml = pyamg.smoothed_aggregation_solver(K, B=B, max_coarse=500)
            except Exception:
                self.ml = None

    def __call__(self, f):
        if self.ml is not None:
            return self.ml.solve(f, tol=1e-6, accel="cg", maxiter=300)
        d = self.K.diagonal()
        M = sp.diags(1 / np.where(d > 0, d, 1))
        x, _ = spla.cg(self.K, f, M=M, rtol=1e-7, maxiter=8000)
        return x


# --------------------------------------------------------------------------- load cases

def load_cases(model: Model, grid):
    """Generic cantilever: fixed at one end of the longest axis, loaded at the other."""
    xyz = model.xyz
    span = xyz.max(0) - xyz.min(0)
    order = np.argsort(span)[::-1]  # long, mid, short
    L = order[0]
    lo, hi = xyz[:, L].min(), xyz[:, L].max()
    band = max(0.05 * (hi - lo), 1.01 * grid["h"])
    fixed = model.node_global[xyz[:, L] <= lo + band]
    tip_mask = xyz[:, L] >= hi - band
    tip = model.node_global[tip_mask]
    tip_xyz = xyz[tip_mask]
    c = tip_xyz.mean(0)
    cases = {}
    for name, axis in [("Bending (weak axis)", order[2]), ("Bending (strong axis)", order[1])]:
        F = np.zeros(3)
        F[axis] = 1.0 / len(tip)
        cases[name] = {int(g): F for g in tip}
    axis_dir = np.zeros(3)
    axis_dir[L] = 1
    r = tip_xyz - c
    r[:, L] = 0
    t = np.cross(axis_dir, r)
    norm = (np.linalg.norm(r, axis=1) ** 2).sum()
    cases["Torsion"] = {int(g): tv / max(norm, 1e-12) for g, tv in zip(tip, t)}
    return fixed, cases


class Baseline:
    """FE model of the original part; evaluate() compares a modified part against it."""

    def __init__(self, original, progress=None, target_voxels=36000):
        self.grid = make_grid(original, target_voxels)
        if progress:
            progress("Voxelising original", 0.0)
        self.m0 = Model(voxelize(original, self.grid), self.grid)
        self.fixed, self.cases = load_cases(self.m0, self.grid)
        if progress:
            progress("Solving original", 0.3)
        self.m0.fix(self.fixed)
        # ignore stresses right at the clamp and load patches (artificial singularities)
        tip = np.array(list(next(iter(self.cases.values())).keys()))
        zone = np.isin(self.m0.node_global, self.fixed) | np.isin(self.m0.node_global, tip)
        self.zone_elems0 = np.isin(self.m0.conn, np.nonzero(zone)[0]).any(axis=1)
        self.zone_ijk = {tuple(x) for x in self.m0.elem_ijk[self.zone_elems0].tolist()}
        self.ref = {}
        for name, loads in self.cases.items():
            u0, f0 = self.m0.solve(loads)
            s0 = self.m0.stresses(u0)[~self.zone_elems0]
            self.ref[name] = (float(f0 @ u0), float(np.percentile(s0, 99)) if len(s0) else 1.0)

    def evaluate(self, modified, progress=None):
        if progress:
            progress("Voxelising pocketed part", 0.0)
        m1 = Model(voxelize(modified, self.grid), self.grid)
        if progress:
            progress("Solving pocketed part", 0.3)
        m1.fix(self.fixed)
        zone1 = np.array([tuple(x) in self.zone_ijk for x in m1.elem_ijk.tolist()], dtype=bool)
        present = set(m1.node_global.tolist())
        out = []
        for name, loads in self.cases.items():
            # renormalise loads to nodes that still exist in the modified model
            kept = {g: F for g, F in loads.items() if g in present}
            tot0 = sum(np.linalg.norm(F) for F in loads.values())
            tot1 = sum(np.linalg.norm(F) for F in kept.values())
            loads1 = {g: F * tot0 / max(tot1, 1e-12) for g, F in kept.items()}
            u1, f1 = m1.solve(loads1)
            c1 = float(f1 @ u1)
            s1 = m1.stresses(u1)[~zone1]
            p1 = float(np.percentile(s1, 99)) if len(s1) else 1.0
            c0, p0 = self.ref[name]
            out.append({"case": name,
                        "stiffness_retained": c0 / c1 if c1 > 0 else 0.0,
                        "peak_stress_ratio": p1 / p0 if p0 > 0 else 1.0})
        return {"voxel_size": self.grid["h"], "voxels": int(np.prod(self.grid["dims"])),
                "elements": [len(self.m0.rho), len(m1.rho)], "cases": out,
                "worst_stiffness_retained": min(c["stiffness_retained"] for c in out),
                "worst_peak_stress_ratio": max(c["peak_stress_ratio"] for c in out)}


def compare(original, modified, progress=None, target_voxels=36000):
    """Return per-load-case stiffness retention and peak stress increase."""
    return Baseline(original, progress, target_voxels).evaluate(modified, progress)
