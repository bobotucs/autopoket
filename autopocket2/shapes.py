"""Pocket shape rules for v2: forced symmetry, blunt tips, and a CheeseIt-style isogrid.

* **Symmetry.** v1 mirrors a layout only when the holes are (mostly) mirror twins. v2
  mirrors the rib *grid* whenever the plate outline is (nearly) symmetric: layout happens
  on the symmetric core of the outline, steered by the holes that have a mirror twin. A
  hole without a twin is not mirrored: its keep-out only reshapes the pockets around it,
  and the other side keeps a normal pocket instead of a phantom keep-out.
* **No acute tips.** Where a rib meets another rib, a hole band or the frame at a
  shallow angle, the pocket between them tapers into a long thin wedge that a 1/8 in
  end mill can't follow and that leaves a slender, flexible rib. Any pocket corner
  sharper than `MIN_TIP_ANGLE` is cut back to a round end as wide as the narrowest
  allowed pocket (8 mm), and validate.py rejects any layout that still has one.
* **No bent pockets.** A pocket that bends round a rib (a chevron or boomerang) is cut at
  the bend into two straight pockets; validate.py rejects any that is left. Only rib
  counts as a bend: a pocket wrapping round a hole band or an edge clearance is fine.
* **Isogrid.** The Onshape "CheeseIt!" FeatureScript lays a regular triangle grid over the
  face and turns each cell into a pocket by insetting it half a wall (plus tool radius),
  clipping it to the face inset by a full wall, and growing it back by the tool radius.
  `isogrid_lines` gives v2 that grid as rib centre lines (rows along the plate's long
  side, a node on the symmetry centre, so it is mirror-symmetric both ways); v2's usual
  pocket cutting then does the inset / clip / round steps.
"""
from __future__ import annotations

import math

import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from autopocket.pocketer import PlateRules, _reflect_geom

MIN_TIP_ANGLE = 45.0      # deg: sharper pocket corners are blunted
MIN_HALF_WIDTH = 4.0      # mm: pockets are at least 8 mm wide (v1's rule) ...
SYM_TOL = 0.08            # outline counts as symmetric if mirroring changes < 8 % of its area
MAX_BEND_PCT = 8.0        # rib inside a pocket's convex hull, % of the pocket area (chevrons are ~25 %)


def min_half_width(r: PlateRules):
    """... and at least 2 mm wider than the end mill when a big tool radius is chosen."""
    return max(MIN_HALF_WIDTH, r.tool_radius + 1.0)


def parts(g):
    return [p for p in getattr(g, "geoms", [g]) if isinstance(p, Polygon) and not p.is_empty]


# --------------------------------------------------------------------------- symmetry

def mirror_axes(outline: Polygon):
    """Mirror axes (point, direction) the outline is (nearly) symmetric about, best first."""
    c = np.array(outline.envelope.centroid.coords[0])
    rc = np.array(outline.minimum_rotated_rectangle.exterior.coords)
    th = math.atan2(*(rc[1] - rc[0])[::-1])
    found = []
    for ang in [0.0, math.pi / 2, th % math.pi, (th + math.pi / 2) % math.pi]:
        d = np.array([math.cos(ang), math.sin(ang)])
        if any(abs(abs(d @ e) - 1) < 1e-6 for _, e, _ in found):
            continue
        err = outline.symmetric_difference(_reflect_geom(outline, c, d)).area / outline.area
        if err < SYM_TOL:
            found.append((c, d, err))
    found.sort(key=lambda a: a[2])
    axes = []
    for c, d, _ in found:
        if not axes or abs(d @ axes[0][1]) < 1e-6:  # a second axis must be perpendicular
            axes.append((c, d))
    return axes[:2]


# --------------------------------------------------------------------------- blunt tips

def tip_depth_limit(R, rounding=0.0):
    """How far a corner of MIN_TIP_ANGLE pokes out past a radius-R opening of the pocket."""
    s = math.sin(math.radians(MIN_TIP_ANGLE) / 2)
    return (R - rounding) * (1 / s - 1)


def tips(poly: Polygon, R=MIN_HALF_WIDTH):
    """[(depth, piece)] for every corner piece that an opening of radius R cuts off."""
    ob = poly.buffer(-R, quad_segs=16).buffer(R, quad_segs=16)
    if ob.is_empty:
        return []
    out = []
    for piece in parts(poly.difference(ob)):
        depth = max(ob.distance(Point(q)) for q in piece.exterior.coords)
        out.append((depth, piece))
    return out


def blunt(cell: Polygon, R=MIN_HALF_WIDTH, rounding=0.0):
    """The cell with every corner sharper than MIN_TIP_ANGLE cut back to a round end of radius R.

    `rounding`: the cell's corners are already rounded to this radius (judged by the same
    limit the validator applies to finished pockets)."""
    lim = tip_depth_limit(R, rounding)
    spikes = [p for d, p in tips(cell, R) if d > lim]
    if not spikes:
        return [cell]
    return parts(cell.difference(unary_union(spikes).buffer(1e-6)))


def cut_pockets(region, ribs, r: PlateRules):
    """v1's pocket cutting (open with the tool radius, >= 8 mm wide, >= min area) after blunting."""
    rt, R = r.tool_radius, min_half_width(r)
    out, rounded = [], []
    for raw in parts(region.difference(ribs)):
        pieces = []
        for cell in blunt(raw, R):
            for e in parts(cell.buffer(-rt, quad_segs=16)):
                # opening can pinch a cell in two, and a rib meeting a curved hole band leaves a
                # cusp that rounding doesn't shorten much: blunt again, judged as a finished pocket
                for q in blunt(e.buffer(rt, quad_segs=16), R, rt):
                    pieces += parts(q.buffer(-rt, quad_segs=16))
        kept = []  # (rounded, sharp)
        for e in sorted(pieces, key=lambda g: -g.area):
            if e.buffer(-(R - rt)).is_empty:
                continue
            rnd = e.buffer(rt, quad_segs=16)
            if rnd.area < r.min_pocket_area:
                continue
            # two pieces of one cell would leave a web thinner than a rib between them; if
            # they are mirror twins (a cell across the symmetry axis) drop both, not one
            clash = [k for k in kept if rnd.distance(k[0]) < r.rib - 0.05]
            if clash:
                kept = [k for k in kept if not (k in clash and abs(k[0].area - rnd.area) < 0.02 * rnd.area)]
                continue
            sharp = e.buffer(rt, join_style="mitre", mitre_limit=10).simplify(0.005)
            if isinstance(sharp, Polygon):
                kept.append((rnd, orient(sharp, 1.0)))
        out += [sh for _, sh in kept]
    rounded = [o.buffer(-rt, quad_segs=16).buffer(rt, quad_segs=16) for o in out]
    return out, unary_union(rounded) if rounded else Polygon()


# --------------------------------------------------------------------------- bent pockets

def bend_gap(pocket: Polygon, fixed):
    """The part of the pocket's convex hull that is rib, not pocket or hole/edge keep-out
    (`fixed`): it is big where a pocket bends round a rib."""
    return pocket.convex_hull.difference(pocket).difference(fixed)


def bend_pct(pocket: Polygon, fixed):
    return 100 * bend_gap(pocket, fixed).area / max(pocket.area, 1e-9)


def bend_split(cell: Polygon, fixed, length, rib):
    """A rib centre line cutting a bent cell at its bend into two straighter cells, or None."""
    gaps = parts(bend_gap(cell, fixed))
    if not gaps:
        return None
    g = max(gaps, key=lambda q: q.area)
    if 100 * g.area / max(cell.area, 1e-9) <= MAX_BEND_PCT:
        return None
    hull = cell.convex_hull.exterior
    pts = np.asarray(g.exterior.coords)
    v = max(pts, key=lambda q: hull.distance(Point(q)))  # the inner corner of the bend
    u = v - np.asarray(g.centroid.coords[0])
    if np.linalg.norm(u) < 1e-6:
        return None
    u = u / np.linalg.norm(u)  # on along the bisector, away from the notch
    cut = LineString([v - u * rib, v + u * length]).intersection(cell.buffer(rib / 2))
    pieces = [q for q in getattr(cut, "geoms", [cut]) if q.geom_type == "LineString" and q.length > rib]
    if not pieces:
        return None
    return min(pieces, key=lambda q: q.distance(Point(v)))


# --------------------------------------------------------------------------- isogrid

def grid_frame(core: Polygon, axes):
    """(centre, angle) for a symmetric isogrid: node on the symmetry centre, rows along the long side."""
    rc = np.array(core.minimum_rotated_rectangle.exterior.coords)
    e1, e2 = rc[1] - rc[0], rc[2] - rc[1]
    u = e1 if np.linalg.norm(e1) >= np.linalg.norm(e2) else e2
    u = u / np.linalg.norm(u)
    if not axes:
        return np.array(core.envelope.centroid.coords[0]), math.atan2(u[1], u[0])
    c, d = axes[0]
    n = np.array([-d[1], d[0]])
    v = d if abs(u @ d) >= abs(u @ n) else n  # the axis direction closest to the long side
    return np.asarray(c), math.atan2(v[1], v[0])


def isogrid_lines(frame: Polygon, s, centre, ang):
    """Equilateral-triangle grid of side s (rib centre lines), clipped to the frame line."""
    h = s * math.sqrt(3) / 2
    x0, y0, x1, y1 = frame.bounds
    ext = max(np.hypot(x - centre[0], y - centre[1]) for x in (x0, x1) for y in (y0, y1)) + s
    K, I = math.ceil(ext / h) + 1, math.ceil(ext / s) + 1
    ca, sa = math.cos(ang), math.sin(ang)
    rot = np.array([[ca, -sa], [sa, ca]])
    lines, nodes = [], []
    for k in range(-K, K + 1):
        for i in range(-I, I + 1):
            p = np.array([i * s + (k % 2) * s / 2, k * h])
            P = centre + rot @ p
            if frame.contains(Point(P)):
                nodes.append(P)
            for dv in ((s, 0.0), (s / 2, h), (-s / 2, h)):
                Q = centre + rot @ (p + np.array(dv))
                seg = LineString([P, Q])
                if not seg.intersects(frame):
                    continue
                cut = seg.intersection(frame)
                lines += [g for g in getattr(cut, "geoms", [cut])
                          if g.geom_type == "LineString" and g.length > 1.0]
    return lines, np.array(nodes) if nodes else np.zeros((0, 2))
