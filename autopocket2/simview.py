"""High-resolution results for the simulation view.

The analysis runs on a finer grid than the planner's (about 2.7x the cells), and its results
are drawn on a triangle mesh of the plate's true shape (real hole and pocket edges, ~2 mm
triangles) instead of square cells: stresses are averaged from the cells onto the grid
nodes and interpolated to the mesh vertices, so colours vary smoothly; displacements are
interpolated the same way, so the mesh can bend with them.

`hot_spots` ranks the holes (bearings, screw holes ...) and ribs by the highest stress
around them, which is what to look at first.
"""
from __future__ import annotations

import math

import numpy as np
import shapely
import triangle
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from . import fea2
from .features import classify_hole

SIM_CELLS = (16000, 32000)
MESH_AREA = 2.5  # mm^2, largest drawing triangle


def surface_mesh(profile: Polygon, max_area=MESH_AREA, tol=0.08):
    """(vertices (n, 2), triangles (m, 3)) covering the profile, holes left open."""
    prof = profile.simplify(tol)
    verts, segs, holes = [], [], []
    for k, ring in enumerate([prof.exterior, *prof.interiors]):
        c = np.asarray(ring.coords)[:-1]
        base = len(verts)
        verts += c.tolist()
        segs += [(base + i, base + (i + 1) % len(c)) for i in range(len(c))]
        if k:
            holes.append(Polygon(ring).representative_point().coords[0])
    data = {"vertices": np.array(verts), "segments": np.array(segs)}
    if holes:
        data["holes"] = np.array(holes)
    m = triangle.triangulate(data, f"pq25a{max_area}")
    return m["vertices"], m["triangles"]


def _to_grid(pts, g):
    ang = math.radians(g["ang"])
    ctr = np.array(g["ctr"].coords[0])
    rot = np.array([[math.cos(-ang), -math.sin(-ang)], [math.sin(-ang), math.cos(-ang)]])
    q = (pts - ctr) @ rot.T + ctr
    return (q[:, 0] - g["lo"][0]) / g["h"], (q[:, 1] - g["lo"][1]) / g["h"]


def _sample(nodal, fi, fj):
    """Bilinear sample of a (nx+1, ny+1[, k]) nodal array; NaN nodes are skipped."""
    nx1, ny1 = nodal.shape[:2]
    i0 = np.clip(np.floor(fi).astype(int), 0, nx1 - 2)
    j0 = np.clip(np.floor(fj).astype(int), 0, ny1 - 2)
    fx, fy = np.clip(fi - i0, 0, 1), np.clip(fj - j0, 0, 1)
    acc = np.zeros((len(fi),) + nodal.shape[2:])
    wsum = np.zeros(len(fi))
    for di, dj, w in ((0, 0, (1 - fx) * (1 - fy)), (1, 0, fx * (1 - fy)), (0, 1, (1 - fx) * fy), (1, 1, fx * fy)):
        v = nodal[i0 + di, j0 + dj]
        ok = np.all(np.isfinite(v), axis=-1) if v.ndim > 1 else np.isfinite(v)
        ww = np.where(ok, w, 0.0) + 1e-9 * ok
        acc += (np.nan_to_num(v).T * ww).T
        wsum += ww
    out = (acc.T / np.maximum(wsum, 1e-12)).T
    out[wsum < 1e-12] = np.nan
    return out


def nodal_stress(vm, fill):
    """Cell stresses averaged onto grid nodes (weighted by how solid each cell is)."""
    nx, ny = vm.shape
    w = np.where(np.isfinite(vm), np.clip(fill, 0, 1), 0.0)
    v = np.nan_to_num(vm) * w
    num, den = np.zeros((nx + 1, ny + 1)), np.zeros((nx + 1, ny + 1))
    for di in (0, 1):
        for dj in (0, 1):
            num[di:di + nx, dj:dj + ny] += v
            den[di:di + nx, dj:dj + ny] += w
    out = num / np.where(den > 0, den, 1)
    out[den <= 0] = np.nan
    return out


def results(analysis, profile):
    """Per load case: stress and displacement at the vertices of the true-shape mesh."""
    maps = fea2.field_maps(analysis, profile)
    g = maps["grid"]
    V, T = surface_mesh(profile)
    fi, fj = _to_grid(V, g)
    ang = math.radians(g["ang"])
    cases = []
    for c in maps["cases"]:
        s = _sample(nodal_stress(c["vm"], maps["fill"]), fi, fj)
        u = _sample(c["u"][:, :, 1, :], fi, fj)  # top face
        ux, uy = u[:, 0], u[:, 1]  # grid frame -> plate frame
        u = np.c_[ux * math.cos(ang) - uy * math.sin(ang), ux * math.sin(ang) + uy * math.cos(ang), u[:, 2]]
        cases.append({"name": c["name"], "stress": s, "u": u, "p99_blank": c["p99_blank"]})
    return {"V": V, "T": T, "cases": cases}


def hot_spots(profile: Polygon, V, stress, rib=8.0, n=6):
    """Holes and ribs ranked by the highest stress near them. `profile` is the original plate,
    so its interiors are the real holes (pockets count as ribs / pocket edges)."""
    out = []
    holes = [Polygon(r) for r in profile.interiors]
    near_all = []
    for i, h in enumerate(holes):
        kind, d = classify_hole(h)
        zone = h.buffer(rib * 1.5).difference(h)
        near = shapely.contains_xy(zone, V[:, 0], V[:, 1])
        near_all.append(near)
        if near.any() and np.isfinite(stress[near]).any():
            k = np.nanargmax(np.where(near, stress, -np.inf))
            label = {"bearing": "Bearing / shaft bore", "fastener": "Screw hole", "slot": "Slot"}.get(kind, "Hole")
            out.append({"label": f"{label} Ø{d:.1f}", "hole": i, "x": float(V[k, 0]), "y": float(V[k, 1]),
                        "value": float(stress[k])})
    rest = ~np.any(near_all, axis=0) if near_all else np.ones(len(V), bool)
    s2 = np.where(rest & np.isfinite(stress), stress, -np.inf)
    taken = []
    for _ in range(3):  # the most stressed ribs / webs away from holes, spread apart
        k = int(np.argmax(s2))
        if not np.isfinite(s2[k]):
            break
        out.append({"label": "Rib / pocket edge", "hole": None, "x": float(V[k, 0]), "y": float(V[k, 1]), "value": float(stress[k])})
        taken.append(V[k])
        s2[np.linalg.norm(V - V[k], axis=1) < 25] = -np.inf
    out.sort(key=lambda h: -h["value"])
    return out[:n]
