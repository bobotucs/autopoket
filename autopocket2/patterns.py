"""Hexagon and Voronoi rib patterns (rib centre lines), mirror-symmetric like the others.

* **Hexagon** (as in the CheeseIt FeatureScript's hex option): a honeycomb of cells
  `s` apart centre to centre, with a cell centred on the plate's symmetry centre. A
  honeycomb has mirror lines every 30 deg, so it is symmetric about both plate axes in
  either orientation (flat side along the long edge, or turned 90 deg).
* **Voronoi**: each pocket is the region closer to its seed point than to any other, so
  ribs run halfway between neighbouring seeds. Seeds are placed in one half (or quarter)
  of the plate with at least `s` between them, mirrored onto the other halves, then
  relaxed with Lloyd's algorithm (each seed moves to its cell's centroid, then the
  diagram is rebuilt), which evens the cells out into a near-hexagonal organic web.
  Structurally this matters: honeycomb and Voronoi webs carry load by bending, so per
  unit weight they are less stiff than triangle grids, and the more irregular a Voronoi
  pattern the less stiff it gets. Relaxed seeds keep it as regular as the shape allows.
  The guided variant packs seeds closer where the blank plate carries more load (the
  SpacingField), so those areas get smaller cells and more ribs.

Both return (rib lines, nodes) for layout.Layout; pocket cutting, blunt tips, hole
support, rib pruning and every hard rule then work as for the triangle patterns.
"""
from __future__ import annotations

import math

import numpy as np
import shapely
from shapely.geometry import LineString, MultiPoint, Point, box
from shapely.ops import unary_union

from autopocket.pocketer import _half_plane, _reflect

LLOYD_STEPS = 12
AXIS_SLACK = 0.05  # mm: a Voronoi edge this close to a mirror axis is taken to lie on it


def _clip(segs, frame):
    """Unique segments, clipped to the frame line, as LineStrings."""
    seen, out = set(), []
    for a, b in segs:
        key = tuple(sorted((tuple(np.round(a, 3)), tuple(np.round(b, 3)))))
        if key in seen or np.linalg.norm(np.asarray(a) - np.asarray(b)) < 1e-6:
            continue
        seen.add(key)
        seg = LineString([a, b])
        if not seg.intersects(frame):
            continue
        cut = seg.intersection(frame)
        out += [g for g in getattr(cut, "geoms", [cut]) if g.geom_type == "LineString" and g.length > 1.0]
    return out


def hex_lines(frame, s, centre, ang):
    """Honeycomb of cells s apart (centre to centre), one cell centred on `centre`."""
    a = s / math.sqrt(3)  # side = circumradius
    x0, y0, x1, y1 = frame.bounds
    ext = max(np.hypot(x - centre[0], y - centre[1]) for x in (x0, x1) for y in (y0, y1)) + 2 * s
    ca, sa = math.cos(ang), math.sin(ang)
    rot = np.array([[ca, -sa], [sa, ca]])
    I, J = math.ceil(ext / (1.5 * a)) + 1, math.ceil(ext / s) + 1
    corner = [np.array([a * math.cos(math.radians(60 * k)), a * math.sin(math.radians(60 * k))]) for k in range(6)]
    segs, nodes = [], []
    for i in range(-I, I + 1):
        for j in range(-J, J + 1):
            c = np.array([1.5 * a * i, s * (j + (i % 2) / 2)])
            if np.hypot(*c) > ext:
                continue
            P = [centre + rot @ (c + q) for q in corner]
            segs += [(P[k], P[(k + 1) % 6]) for k in range(6)]
            nodes += [p for p in P if frame.contains(Point(p))]
    nodes = np.unique(np.round(np.array(nodes), 6), axis=0) if nodes else np.zeros((0, 2))
    return _clip(segs, frame), nodes


def _polys(g):
    """Every polygon in a (possibly nested) geometry collection."""
    if g.geom_type == "Polygon":
        return [] if g.is_empty else [g]
    return [q for sub in getattr(g, "geoms", []) for q in _polys(sub)]


def _mirror_all(pts, axes):
    out = [np.asarray(p, float) for p in pts]
    for c, d in axes:
        out = out + [_reflect(p, c, d)[0] for p in out]
    if not out:
        return np.zeros((0, 2))
    return np.unique(np.round(np.array(out), 6), axis=0)


def _snap(p, axes, tol):
    """Put a seed that is almost on a mirror axis exactly on it (else it and its image sit too close)."""
    for c, d in axes:
        n = np.array([-d[1], d[0]])
        off = (p - c) @ n
        if abs(off) < tol:
            p = p - off * n
    return p


def _canonical(p, axes):
    return all((np.asarray(p) - c) @ np.array([-d[1], d[0]]) >= -1e-6 for c, d in axes)


def voronoi_lines(allowed, frame, s, axes, sfn=None, seed=0):
    """Lloyd-relaxed, mirror-symmetric Voronoi web with seeds about s apart (or sfn-local)."""
    if allowed.is_empty or frame.is_empty:
        return [], np.zeros((0, 2))
    rng = np.random.default_rng(seed + int(s * 10))
    spacing = (lambda p: float(sfn.at(p))) if sfn is not None else (lambda p: float(s))
    x0, y0, x1, y1 = allowed.bounds
    n_try = int(40 * allowed.area / (s * s)) + 200
    cand = np.c_[rng.uniform(x0, x1, n_try), rng.uniform(y0, y1, n_try)]
    cand = cand[shapely.contains_xy(allowed, cand[:, 0], cand[:, 1])]
    cand = [p for p in cand if _canonical(p, axes)]
    seeds = []
    for p in cand:  # dart throwing: keep a point if it is far enough from every kept seed and image
        p = _snap(p, axes, 0.3 * spacing(p))
        mine = _mirror_all([p], axes)
        if all(np.min(np.linalg.norm(mine - q, axis=1)) >= 0.9 * min(spacing(p), spacing(q)) for q in seeds) \
                and (len(mine) == 1 or np.min([np.linalg.norm(mine[i] - mine[j]) for i in range(len(mine))
                                               for j in range(i + 1, len(mine))]) >= 0.9 * spacing(p)):
            seeds.append(p)
    if not seeds:
        return [], np.zeros((0, 2))
    bound = box(*frame.buffer(4 * s).bounds)
    weighted = sfn is not None and getattr(sfn, "beta", 0) > 0
    for _ in range(LLOYD_STEPS):
        full = _mirror_all(seeds, axes)
        if len(full) < 2:
            break
        cells = shapely.voronoi_polygons(MultiPoint(full), extend_to=bound, ordered=True)
        cells = list(getattr(cells, "geoms", [cells]))
        moved = []
        for p in seeds:
            k = int(np.argmin(np.linalg.norm(full - p, axis=1)))
            cell = cells[k].intersection(allowed) if k < len(cells) else None
            if cell is None or cell.is_empty or cell.area < 1e-6:
                moved.append(p)
                continue
            if weighted:  # density ~ 1/spacing^2: seeds drift toward the busier side of their cell
                cx0, cy0, cx1, cy1 = cell.bounds
                g = np.mgrid[cx0:cx1:12j, cy0:cy1:12j].reshape(2, -1).T
                g = g[shapely.contains_xy(cell, g[:, 0], g[:, 1])]
                if len(g):
                    w = 1.0 / np.maximum(sfn(g), 1e-6) ** 2
                    q = (g * w[:, None]).sum(axis=0) / w.sum()
                else:
                    q = np.array(cell.centroid.coords[0])
            else:
                q = np.array(cell.centroid.coords[0])
            q = _snap(q, axes, 0.3 * spacing(q))
            moved.append(q if _canonical(q, axes) else p)
        seeds = moved
    full = _mirror_all(seeds, axes)
    if len(full) < 2:
        return [], np.zeros((0, 2))
    cells = shapely.voronoi_polygons(MultiPoint(full), extend_to=bound)
    segs = []
    for cell in _polys(cells):
        c = np.asarray(cell.exterior.coords)
        segs += [(c[i], c[i + 1]) for i in range(len(c) - 1)]
    # mirrored seeds sit on common circles, and the diagram breaks those ties one way:
    # keep the web of one half (quarter) only and mirror it, so it is exactly symmetric
    quarter = frame
    ext = 4 * max(frame.bounds[2] - frame.bounds[0], frame.bounds[3] - frame.bounds[1])
    for c, d in axes:
        quarter = quarter.intersection(_half_plane(c, d, ext))
    # the edge between a seed and its own mirror image lies on the axis, a hair either side
    # of it in floating point: clip with a little slack and put such edges exactly on the axis,
    # or they get dropped and the two cells merge into one bent (chevron) pocket
    lines = []
    for ln in _clip(segs, quarter.buffer(AXIS_SLACK).intersection(frame)):
        q = np.asarray(ln.coords, float)
        for c, d in axes:
            n = np.array([-d[1], d[0]])
            off = (q - c) @ n
            if np.all(np.abs(off) <= AXIS_SLACK):
                q = q - off[:, None] * n
        lines.append(LineString(q))
    for c, d in axes:
        lines = lines + [LineString(_reflect(np.asarray(ln.coords), c, d)) for ln in lines]
    lines = _clip([(np.asarray(ln.coords[0]), np.asarray(ln.coords[-1])) for ln in lines], frame.buffer(AXIS_SLACK))
    ends = np.array([q for ln in lines for q in (ln.coords[0], ln.coords[-1])]) if lines else np.zeros((0, 2))
    nodes = np.unique(np.round(ends, 6), axis=0) if len(ends) else np.zeros((0, 2))
    return lines, nodes


def allowed_area(dom):
    """Where Voronoi seeds may go: the pocketable region minus the mirrored hole pairs' keep-outs.

    A hole without a twin doesn't move the seeds (the web stays symmetric); its band just
    reshapes the cells it lands on."""
    keep = dom.grid_keepouts()
    return dom.region.difference(unary_union(keep)) if keep else dom.region
