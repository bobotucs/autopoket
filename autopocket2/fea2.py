"""Plate FEA for v2: v1's hex model, clamped at *either* end, plus element energies.

v1 clamps the -x end of the long axis only, which is an arbitrary choice: a plate whose
stiff half happens to sit at +x scores differently from its mirror image. v2 runs the
three generic cases (out-of-plane bending, in-plane bending, torsion) from both ends
and uses the worst one, and also returns where the strain energy goes, which steers the
truss layout (denser where the blank plate works hard) and the rib pruning.

**Engineering mode.** When the user marks which holes are bolted mounts and which are
loaded bearing bores, the generic cantilevers are replaced by the plate's own load
paths: every mount is held over a washer-sized ring around the hole (not just its edge,
which would put a singular point support there), and each bearing bore is loaded in
turn in four in-plane directions and out of plane. In-plane bearing loads are spread
over the bore as a cosine pressure on the loaded half, the way a shaft bears on a
housing, instead of a uniform pull on the whole hole. One factorisation serves every
case. Forces are 1 N, so results scale linearly to any load the user gives.

**Solid-shell material law.** One layer of linear bricks can't let the plate thin under
bending (Poisson thickness locking): it comes out ~10 % too stiff in bending and carries
a spurious through-thickness stress. v2's bricks use the plate law instead: plane stress
in the plate (E/(1-nu^2)), a through-thickness stiffness with no Poisson coupling, so
sigma_z ~ 0 as in shell elements. v1's element (autopocket/fea.py) is left as it is.

**Stress recovery.** v1 evaluates stress at each element's centre, which in a one-layer
model is the plate's mid-plane, where bending and twisting stresses are zero (a probe in
the research found out-of-plane bending stress under-reported 16-18x). v2 evaluates the
in-plane strains at the top and bottom faces (transverse shear stays at the centre, where
the reduced-integration element defines it), takes the worse face, and uses only fully
solid cells away from loads and supports for its 99th percentile: the stair-stepped edge
cells of a raster mesh are artificial corners whose stresses don't converge.

Still a screening estimate (raster mesh, single layer, idealised supports), not a
certified analysis.
"""
from __future__ import annotations

import math

import numpy as np
import scipy.sparse.linalg as spla
import shapely
from scipy import ndimage
from scipy.interpolate import RegularGridInterpolator
from shapely import affinity

from autopocket import fea

CASE_NAMES = ("Out-of-plane bending", "In-plane bending", "Torsion")
WASHER_MM = 3.0                    # a bolted mount holds this far beyond the hole edge (assumed)
BEARING_DIRS = (0, 45, 90, 135)    # in-plane bearing load directions, deg (+-F give the same stiffness)


def _dmat_shell(nu=fea.NU):
    """Plate (plane stress in x-y) law with an uncoupled through-thickness stiffness, E = 1."""
    D = np.zeros((6, 6))
    c = 1 / (1 - nu ** 2)
    D[0, 0] = D[1, 1] = c
    D[0, 1] = D[1, 0] = nu * c
    D[2, 2] = 1.0
    D[3, 3] = D[4, 4] = D[5, 5] = 1 / (2 * (1 + nu))
    return D


DMAT = _dmat_shell()


def hex_ke(dims):
    """v1's brick (selective reduced integration of shear) with the solid-shell law."""
    dims = np.asarray(dims, float)
    vol = dims.prod()
    g = 1 / np.sqrt(3)
    Ke = np.zeros((24, 24))
    for xi in [(x, y, z) for x in (-g, g) for y in (-g, g) for z in (-g, g)]:
        B = fea._bmat(np.array(xi), dims)
        Ke += B[:3].T @ DMAT[:3, :3] @ B[:3] * vol / 8
    Bc = fea._bmat(np.zeros(3), dims)
    Ke += Bc[3:].T @ DMAT[3:, 3:] @ Bc[3:] * vol
    return Ke, Bc


class Model(fea.Model):
    """fea.Model assembled with the solid-shell brick."""

    def __init__(self, fill2d, grid, min_fill=0.02):
        import scipy.sparse as sp
        nx, ny = grid["n"]
        nz = grid["layers"]
        h, t = grid["h"], grid["t"]
        Ke, self.Bc = hex_ke([h, h, t / nz])
        ex, ey = np.nonzero(fill2d > min_fill)
        ex, ey, ez = np.repeat(ex, nz), np.repeat(ey, nz), np.tile(np.arange(nz), len(ex))
        self.rho = fill2d[ex, ey]
        self.elem_ijk = np.c_[ex, ey, ez]
        nid = lambda i, j, k: (i * (ny + 1) + j) * (nz + 1) + k  # noqa: E731
        conn = np.stack([nid(ex + c[0], ey + c[1], ez + c[2]) for c in fea.CORNERS], axis=1)
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


def surface_bmats(dims):
    """Strain-displacement matrices at the top and bottom face centres of a hex element.

    Rows 0-3 (normal strains and in-plane shear) are taken at the face, rows 4-5
    (transverse shear) at the element centre, matching the selective reduced integration."""
    dims = np.asarray(dims, float)
    Bc = fea._bmat(np.zeros(3), dims)
    out = []
    for z in (1.0, -1.0):
        B = Bc.copy()
        B[:4] = fea._bmat(np.array([0.0, 0.0, z]), dims)[:4]
        out.append(B)
    return out


def surface_von_mises(m: fea.Model, u, bmats):
    """Von Mises stress per element, the worse of its top and bottom faces (E = 1 units)."""
    ue = u[m.edof]
    worst = np.zeros(len(ue))
    for B in bmats:
        sx, sy, sz, txy, tyz, txz = ((ue @ B.T @ DMAT.T) * m.rho[:, None]).T
        vm = np.sqrt(0.5 * ((sx - sy) ** 2 + (sy - sz) ** 2 + (sz - sx) ** 2) + 3 * (txy ** 2 + tyz ** 2 + txz ** 2))
        worst = np.maximum(worst, vm)
    return worst


def _fix(m: fea.Model, fixed_global):
    """fea.Model.fix with a symmetric fill-reducing ordering: same exact LU, ~3-4x faster."""
    m.g2l = {g: l for l, g in enumerate(m.node_global)}
    fixed = np.array([m.g2l[g] for g in fixed_global if g in m.g2l], dtype=int)
    fixed_dofs = (fixed[:, None] * 3 + np.arange(3)).ravel()
    m.free = np.setdiff1d(np.arange(3 * m.n_nodes), fixed_dofs)
    lu = spla.splu(m.K[m.free][:, m.free].tocsc(), permc_spec="MMD_AT_PLUS_A")
    m.solver = lu.solve


def _cases(model: fea.Model, grid, end):
    """(fixed nodes, {name: loads}) for a cantilever clamped at end -1 (-x) or +1 (+x)."""
    xyz = model.xyz
    lo, hi = xyz[:, 0].min(), xyz[:, 0].max()
    band = max(0.05 * (hi - lo), 1.01 * grid["h"])
    clamp = xyz[:, 0] <= lo + band if end < 0 else xyz[:, 0] >= hi - band
    load = xyz[:, 0] >= hi - band if end < 0 else xyz[:, 0] <= lo + band
    fixed = model.node_global[clamp]
    tip, tip_xyz = model.node_global[load], xyz[load]
    cases = {}
    for name, axis in zip(CASE_NAMES[:2], (2, 1)):
        F = np.zeros(3)
        F[axis] = 1.0 / len(tip)
        cases[name] = {int(g): F for g in tip}
    r = tip_xyz - tip_xyz.mean(0)
    r[:, 0] = 0
    tv = np.cross([1.0, 0, 0], r)
    norm = (np.linalg.norm(r, axis=1) ** 2).sum()
    cases[CASE_NAMES[2]] = {int(g): v / max(norm, 1e-12) for g, v in zip(tip, tv)}
    return fixed, cases


def _hole_load(nodes, pts, c, v, a):
    """1 N along plate-frame vector v on one hole: in-plane part as a cosine pressure on the
    side of the hole it pushes against, out-of-plane part spread evenly over the hole's ring."""
    v = np.asarray(v, float)
    v = v / max(np.linalg.norm(v), 1e-12)
    out = {}
    inp = math.hypot(v[0], v[1])
    if inp > 1e-6:
        th = math.atan2(v[1], v[0]) - a  # plate-frame direction -> grid frame
        phi = np.arctan2(pts[:, 1] - c[1], pts[:, 0] - c[0])
        w = np.maximum(np.cos(phi - th), 0.0)
        if w.sum() > 0:
            d = np.array([math.cos(th), math.sin(th), 0.0]) * inp
            for g, wi in zip(nodes, w):
                if wi > 0:
                    out[int(g)] = d * wi / w.sum()
    if abs(v[2]) > 1e-6:
        for g in nodes:
            out[int(g)] = out.get(int(g), np.zeros(3)) + np.array([0.0, 0.0, v[2] / len(nodes)])
    return out


def _hole_cases(model: fea.Model, grid, mounts, bearings, dirs=None):
    """(fixed nodes, {name: loads}) for the user's supports (held) and load holes (loaded).

    Without `dirs`, each load hole is pushed on its own in 4 in-plane directions and out of
    plane (an envelope, for when the direction is unknown). With `dirs` = [(label, plate-frame
    vector)], each direction is one case with the force shared by all load holes at once,
    e.g. a chassis' weight coming down through its mounting holes."""
    ang, ctr = grid["ang"], grid["ctr"]
    h = grid["h"]
    xy = model.xyz[:, :2]

    def to_grid(poly):
        return affinity.rotate(poly, -ang, origin=ctr)

    fixed = []
    for m in mounts:
        ring = to_grid(m).buffer(max(WASHER_MM, 1.5 * h))
        fixed.append(model.node_global[shapely.contains_xy(ring, xy[:, 0], xy[:, 1])])
    fixed = np.unique(np.concatenate(fixed)) if fixed else np.zeros(0, int)
    cases = {}
    a = np.radians(ang)
    if dirs:
        holes = []
        for b in bearings:
            bg = to_grid(b)
            sel = shapely.contains_xy(bg.buffer(max(1.5, 1.5 * h)), xy[:, 0], xy[:, 1])
            if sel.any():
                holes.append((model.node_global[sel], xy[sel], np.array(bg.centroid.coords[0])))
        for label, v in dirs:
            case = {}
            for nodes, pts, c in holes:
                for g, F in _hole_load(nodes, pts, c, v, a).items():
                    case[g] = case.get(g, np.zeros(3)) + F / len(holes)
            if case:
                cases[f"{label} load"] = case
        return fixed, cases
    for k, b in enumerate(bearings):
        bg = to_grid(b)
        band = bg.buffer(max(1.5, 1.5 * h))
        sel = shapely.contains_xy(band, xy[:, 0], xy[:, 1])
        nodes, pts = model.node_global[sel], xy[sel]
        if not len(nodes):
            continue
        c = np.array(bg.centroid.coords[0])
        phi = np.arctan2(pts[:, 1] - c[1], pts[:, 0] - c[0])
        for deg in BEARING_DIRS:
            th = np.radians(deg) - a  # plate-frame direction -> grid frame
            w = np.maximum(np.cos(phi - th), 0.0)  # cosine pressure on the loaded half of the bore
            if w.sum() <= 0:
                continue
            d = np.array([np.cos(th), np.sin(th), 0.0])
            cases[f"Bearing {k + 1}: in-plane {deg}°"] = {int(g): d * wi / w.sum() for g, wi in zip(nodes, w) if wi > 0}
        cases[f"Bearing {k + 1}: out-of-plane"] = {int(g): np.array([0.0, 0.0, 1.0 / len(nodes)]) for g in nodes}
    return fixed, cases


class Analysis:
    """Blank-plate FE baseline; evaluate() compares a pocketed profile against it.

    `mounts` / `bearings`: hole polygons (plate frame). With both given, the plate is held
    at the mounts and loaded at the bearings (engineering mode); otherwise it is clamped
    at either end of its long axis (generic screening).
    """

    ENDS = (-1, 1)

    def __init__(self, profile, thickness, target_cells=6000, max_cells=16000, rib=8.0, mounts=(), bearings=(),
                 dirs=None):
        self.grid = fea.make_grid(profile, thickness, target_cells, max_cells, rib)
        h, t = self.grid["h"], self.grid["t"]
        self.Ke, _ = hex_ke([h, h, t])
        self.bmats = surface_bmats([h, h, t])
        m0 = Model(fea.raster(profile, self.grid), self.grid)
        self.setups = {}
        built = []
        if mounts and bearings:
            fixed, cases = _hole_cases(m0, self.grid, list(mounts), list(bearings), dirs)
            if len(fixed) and cases:
                built.append(("holes", fixed, cases))
        self.engineering = bool(built)
        if not built:
            built = [(end, *_cases(m0, self.grid, end)) for end in self.ENDS]
        for key, fixed, cases in built:
            loaded = np.array(sorted({g for c in cases.values() for g in c}))
            zone = np.isin(m0.node_global, fixed) | np.isin(m0.node_global, loaded)
            zone_e = np.isin(m0.conn, np.nonzero(zone)[0]).any(axis=1)
            self.setups[key] = {"fixed": fixed, "cases": cases,
                                "zone_ij": {tuple(x) for x in m0.elem_ijk[zone_e, :2].tolist()}}
        self.ref = {}
        res = self._solve(m0)
        for key, (c, p, _) in res.items():
            self.ref[key] = (c, p)
        self.blank_energy = self._energy_map(m0, res)

    def _solve(self, m):
        """{(setup, case): (compliance, p99 surface von Mises in solid cells outside load/support zones,
        element energy)}."""
        present = set(m.node_global.tolist())
        out = {}
        for end, st in self.setups.items():
            _fix(m, st["fixed"])
            zone = np.array([tuple(x) in st["zone_ij"] for x in m.elem_ijk[:, :2].tolist()], dtype=bool)
            for name, loads in st["cases"].items():
                kept = {g: F for g, F in loads.items() if g in present}
                tot0 = sum(np.linalg.norm(F) for F in loads.values())
                tot1 = sum(np.linalg.norm(F) for F in kept.values())
                u, f = m.solve({g: F * tot0 / max(tot1, 1e-12) for g, F in kept.items()})
                ue = u[m.edof]
                energy = m.rho * np.einsum("ei,ij,ej->e", ue, self.Ke, ue)
                keep = ~zone & (m.rho >= 0.99)  # interior cells only: raster edge cells are fake corners
                if not keep.any():
                    keep = ~zone
                s = surface_von_mises(m, u, self.bmats)[keep]
                out[(end, name)] = (float(f @ u), float(np.percentile(s, 99)) if len(s) else 1.0, energy)
        return out

    def _energy_map(self, m, res):
        """Envelope over load cases of strain energy per unit material, mean ~1, on the (nx, ny) grid."""
        nx, ny = self.grid["n"]
        env = np.zeros((nx, ny))
        mass = m.rho.sum()
        for c, _, e in res.values():
            dens = e / np.maximum(m.rho, 1e-6) / max(c, 1e-30) * mass
            g = np.zeros((nx, ny))
            np.maximum.at(g, (m.elem_ijk[:, 0], m.elem_ijk[:, 1]), dens)
            env = np.maximum(env, g)
        fill = np.zeros((nx, ny))
        fill[m.elem_ijk[:, 0], m.elem_ijk[:, 1]] = m.rho
        return env, fill

    def evaluate(self, profile, want_energy=False):
        m = Model(fea.raster(profile, self.grid), self.grid)
        res = self._solve(m)
        cases = []
        for (key, name), (c1, p1, _) in res.items():
            c0, p0 = self.ref[(key, name)]
            label = name if key == "holes" else f"{name} ({'left' if key < 0 else 'right'} clamped)"
            # compliance / p99 stress are per 1 N with E = 1 MPa: x F, / E give mm and MPa
            cases.append({"case": label,
                          "stiffness_retained": c0 / c1 if c1 > 0 else 0.0,
                          "peak_stress_ratio": p1 / p0 if p0 > 0 else 1.0,
                          "compliance": c1, "compliance_blank": c0, "p99": p1, "p99_blank": p0})
        out = {"cells": int(np.prod(self.grid["n"])), "cell_size": self.grid["h"], "cases": cases,
               "worst_stiffness_retained": min(c["stiffness_retained"] for c in cases),
               "worst_peak_stress_ratio": max(c["peak_stress_ratio"] for c in cases)}
        if want_energy:
            out["energy"] = self._energy_map(m, res)
        return out

    # ------------------------------------------------------------------ field lookup

    def field(self, energy_map, smooth_mm=0.0, clip_pct=97.0):
        """Callable f(points (n, 2) in plate coords) -> smoothed relative energy density."""
        env, fill = energy_map
        h = self.grid["h"]
        solid = fill > 0.3
        cap = np.percentile(env[solid], clip_pct) if solid.any() else 1.0
        e = np.minimum(env, cap) * (fill > 0.02)
        if smooth_mm > 0:
            sig = smooth_mm / h
            num = ndimage.gaussian_filter(e * fill, sig, mode="constant")
            den = ndimage.gaussian_filter(fill, sig, mode="constant")
            e = num / np.maximum(den, 1e-6)
        nx, ny = self.grid["n"]
        lo = self.grid["lo"]
        xs = lo[0] + (np.arange(nx) + 0.5) * h
        ys = lo[1] + (np.arange(ny) + 0.5) * h
        interp = RegularGridInterpolator((xs, ys), e, bounds_error=False, fill_value=None)
        ang = np.radians(self.grid["ang"])
        ctr = np.array(self.grid["ctr"].coords[0])
        rot = np.array([[np.cos(-ang), -np.sin(-ang)], [np.sin(-ang), np.cos(-ang)]])

        def f(pts):
            pts = np.atleast_2d(np.asarray(pts, float))
            q = (pts - ctr) @ rot.T + ctr
            return interp(q)

        return f


def field_maps(analysis: Analysis, profile):
    """Everything needed to draw a profile's response: per load case, the surface von Mises
    stress of every cell and the displacement of every node (E = 1, 1 N units).

    Returns {"grid", "fill" (nx, ny), "cases": [{"name", "vm" (nx, ny), "u" (nx+1, ny+1, 2, 3),
    "p99_blank", "c_blank"}]}; cells/nodes without material are NaN."""
    g = analysis.grid
    nx, ny = g["n"]
    fill = fea.raster(profile, g)
    m = Model(fill, g)
    present = set(m.node_global.tolist())
    k = m.node_global % 2
    j = (m.node_global // 2) % (ny + 1)
    i = m.node_global // (2 * (ny + 1))
    cases = []
    for key, st in analysis.setups.items():
        _fix(m, st["fixed"])
        for name, loads in st["cases"].items():
            kept = {gg: F for gg, F in loads.items() if gg in present}
            tot0 = sum(np.linalg.norm(F) for F in loads.values())
            tot1 = sum(np.linalg.norm(F) for F in kept.values())
            u, _ = m.solve({gg: F * tot0 / max(tot1, 1e-12) for gg, F in kept.items()})
            vm = np.full((nx, ny), np.nan)
            vm[m.elem_ijk[:, 0], m.elem_ijk[:, 1]] = surface_von_mises(m, u, analysis.bmats)
            U = np.full((nx + 1, ny + 1, 2, 3), np.nan)
            U[i, j, k] = u.reshape(-1, 3)
            c0, p0 = analysis.ref[(key, name)]
            label = name if key == "holes" else f"{name} ({'left' if key < 0 else 'right'} clamped)"
            cases.append({"name": label, "vm": vm, "u": U, "p99_blank": p0, "c_blank": c0})
    return {"grid": g, "fill": fill, "cases": cases}
