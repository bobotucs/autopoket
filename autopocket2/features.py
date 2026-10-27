"""Plate features the user can protect one by one: holes, outline sides and outline corners.

Every feature has a *clearance*: how much solid material is kept between it and the
nearest pocket (v1's fixed rule is 8 mm = 4 mm offset + half an 8 mm rib). The user can
change it per hole, per side of the outline and per corner (a corner clearance is a
radius of solid material around the corner point). `Domain` turns the clearances into
the area pockets may use and the rib centre lines along the edges. The rib grid is
mirrored across the axes the holes are symmetric about (when the outline is too); a hole
without a twin is never mirrored, so it only shapes the pockets right next to it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import substring, unary_union

from autopocket.pocketer import PlateRules, _reflect_geom

from .shapes import mirror_axes, parts

CORNER_TURN = 30.0   # deg: the outline turning this much ...
CORNER_SPAN = 12.0   # mm: ... within this much outline length is one corner (sharp or filleted)
MIN_CLEARANCE = 1.0  # mm
TWIN_TOL = 3.0       # mm: a hole's mirror image within this of another hole makes them a pair
GRID_SYM_SHARE = 0.75  # the grid is mirrored across an axis if this share of the holes pair up across it


# --------------------------------------------------------------------------- clearances

@dataclass
class Clearances:
    """Material kept between any pocket and each feature, mm (missing = `default`)."""
    default: float = 8.0
    holes: dict = field(default_factory=dict)     # hole index (profile.interiors order) -> mm
    sides: dict = field(default_factory=dict)     # outline side index -> mm
    corners: dict = field(default_factory=dict)   # outline corner index -> radius mm (no entry = none)

    @classmethod
    def from_rules(cls, r: PlateRules):
        return cls(default=r.offset + r.rib / 2)

    @classmethod
    def from_dict(cls, d, r: PlateRules):
        if not d:
            return cls.from_rules(r)

        def clean(m):
            out = {}
            for k, v in (m or {}).items():
                if v is not None and v != "":
                    out[int(k)] = max(MIN_CLEARANCE, min(200.0, float(v)))
            return out
        default = float(d.get("default") or (r.offset + r.rib / 2))
        return cls(max(MIN_CLEARANCE, min(200.0, default)), clean(d.get("holes")), clean(d.get("sides")),
                   clean(d.get("corners")))

    def to_dict(self):
        return {"default": self.default, "holes": self.holes, "sides": self.sides, "corners": self.corners}

    def hole(self, i):
        return self.holes.get(i, self.default)

    def side(self, i):
        return self.sides.get(i, self.default)

    @property
    def custom(self):
        return len(self.holes) + len(self.sides) + len(self.corners)


# --------------------------------------------------------------------------- features

def outline_sides(outline: Polygon):
    """(sides as LineStrings, corner points) of the outline, split where it turns >= CORNER_TURN
    within CORNER_SPAN of length. A filleted corner counts as one corner at the fillet's middle."""
    ring = orient(outline, 1.0).exterior
    c = np.array(ring.coords)[:-1]
    seg = np.roll(c, -1, axis=0) - c
    keep = np.linalg.norm(seg, axis=1) > 1e-9
    c, seg = c[keep], seg[keep]
    n = len(c)
    line = LineString(np.vstack([c, c[:1]]))
    P = line.length
    if n < 3 or P <= 0:
        return [line], []
    ang = np.arctan2(seg[:, 1], seg[:, 0])
    turn = np.degrees((ang - np.roll(ang, 1) + np.pi) % (2 * np.pi) - np.pi)  # signed turn at vertex i
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(seg, axis=1))[:-1]])   # arc position of vertex i
    cands = []
    for i in range(n):
        d = (s - s[i] + P / 2) % P - P / 2  # signed circular distance to vertex i
        win = np.abs(d) <= CORNER_SPAN / 2
        W = turn[win].sum()
        if abs(W) >= CORNER_TURN:
            w = np.abs(turn[win])
            pos = (s[i] + (d[win] * w).sum() / max(w.sum(), 1e-12)) % P
            cands.append((abs(W), pos))
    corners = []
    for W, pos in sorted(cands, reverse=True):
        if all(abs((pos - q + P / 2) % P - P / 2) > CORNER_SPAN for q in corners):
            corners.append(pos)
    corners.sort()
    if not corners:
        return [line], []
    sides = []
    for k, a in enumerate(corners):
        b = corners[(k + 1) % len(corners)]
        if b > a:
            sides.append(substring(line, a, b))
        else:  # wraps past the ring's start point
            pa, pb = substring(line, a, P), substring(line, 0, b)
            pts = list(pa.coords) + list(pb.coords)[1:] if pb.length > 1e-9 else list(pa.coords)
            sides.append(LineString(pts) if len(pts) > 1 else pa)
    pts = [np.array(line.interpolate(q).coords[0]) for q in corners]
    return sides, pts


def classify_hole(h: Polygon):
    """(kind, equivalent diameter mm): fastener, bearing (bearing/shaft bore), hole, slot or cutout."""
    d = 2 * math.sqrt(h.area / math.pi)
    roundness = 4 * math.pi * h.area / max(h.length ** 2, 1e-12)
    if roundness > 0.9:
        if d <= 6.5:
            return "fastener", d
        if d >= 9.0:
            return "bearing", d
        return "hole", d
    rc = np.array(h.minimum_rotated_rectangle.exterior.coords)
    e = sorted([np.linalg.norm(rc[1] - rc[0]), np.linalg.norm(rc[2] - rc[1])])
    if e[0] > 0 and e[1] / e[0] > 1.8 and h.area > 0.8 * e[0] * e[1] * 0.85:
        return "slot", d
    return "cutout", d


def _coords(g, tol=0.05):
    return [[round(x, 3), round(y, 3)] for x, y in g.simplify(tol).coords]


def describe(plate):
    """JSON for the UI: the plate's frame (to map clicks), holes, sides and corners."""
    prof = plate.profile
    fr = plate.frame
    sides, corners = outline_sides(Polygon(prof.exterior))
    holes = []
    for i, ring in enumerate(prof.interiors):
        h = Polygon(ring)
        kind, d = classify_hole(h)
        ctr = h.centroid if h.contains(h.centroid) else h.representative_point()
        holes.append({"id": i, "kind": kind, "d": round(d, 2), "center": [round(v, 3) for v in ctr.coords[0]],
                      "ring": _coords(ring)})
    return {"frame": {"origin": fr.origin.tolist(), "x": fr.x.tolist(), "y": fr.y.tolist(), "n": fr.n.tolist()},
            "thickness": plate.thickness, "outline": _coords(prof.exterior),
            "holes": holes,
            "sides": [{"id": k, "coords": _coords(sd), "length": round(sd.length, 1)} for k, sd in enumerate(sides)],
            "corners": [{"id": k, "point": [round(float(v), 3) for v in p]} for k, p in enumerate(corners)]}


# --------------------------------------------------------------------------- domain

class Domain:
    """Where pockets may go on one plate, for a rib width and a set of clearances.

    axes      mirror axes of the rib grid: axes of the outline that the holes are (mostly)
              symmetric about too; none if the holes follow no symmetry
    region    area pockets may use, before the keep-outs around holes
    frame     rib centre line along the outline (the truss is laid out inside it)
    blobs     clearance bands of the holes (merged where they overlap); each must stay held
    twins     per blob, the axes it has a mirror twin across (itself, if it sits on the axis);
              its support struts are mirrored across those
    paired    per blob, whether it has a twin across every axis; only these steer the
              symmetric rib grid
    sym_blobs per blob, its band joined with its twins' mirrored bands, so a pair that is a
              hair off true mirror images (as measured from CAD) still gets matching pockets
    keepouts  `sym_blobs` merged: no pocket may enter them. A hole with no twin is not
              mirrored, so the other side keeps a normal pocket instead of a phantom keep-out
    """

    def __init__(self, profile: Polygon, r: PlateRules, clear: Clearances | None = None):
        self.profile, self.r = profile, r
        self.clear = clear or Clearances.from_rules(r)
        half = r.rib / 2
        outline = Polygon(profile.exterior)
        self.holes = [Polygon(h) for h in profile.interiors]
        self.sides, self.corners = outline_sides(outline)
        bands = [h.buffer(self.clear.hole(i), quad_segs=32) for i, h in enumerate(self.holes)]
        self.blobs = parts(unary_union(bands)) if bands else []

        def twins_across(c, d):
            return sum(any(_reflect_geom(b, c, d).hausdorff_distance(q) <= TWIN_TOL for q in self.blobs)
                       for b in self.blobs)

        # symmetry follows the holes: an outline axis the screw holes don't respect isn't one
        self.axes = [(c, d) for c, d in mirror_axes(outline)
                     if twins_across(c, d) >= GRID_SYM_SHARE * len(self.blobs)]

        def inset(extra):
            cut = [sd.buffer(max(self.clear.side(k) - extra, 0.01), quad_segs=16) for k, sd in enumerate(self.sides)]
            cut += [Point(self.corners[k]).buffer(max(R - extra, 0.01), quad_segs=32)
                    for k, R in self.clear.corners.items() if 0 <= k < len(self.corners)]
            return outline.difference(unary_union(cut))

        region, frame, core = inset(0.0), inset(half), outline
        for c, d in self.axes:  # the outline's protected edges are kept symmetric (the grid needs it)
            region = region.intersection(_reflect_geom(region, c, d))
            frame = frame.intersection(_reflect_geom(frame, c, d))
            core = core.intersection(_reflect_geom(core, c, d))
        self.twins = [self.twin_axes(b, self.blobs) for b in self.blobs]
        self.paired = [len(t) == len(self.axes) for t in self.twins]
        self.sym_blobs = [unary_union(self.images(b, t)) for b, t in zip(self.blobs, self.twins)]
        self.keepouts = parts(unary_union(self.sym_blobs)) if self.sym_blobs else []
        self.region = region
        fp = parts(frame)
        self.frame = max(fp, key=lambda g: g.area) if fp else Polygon()
        cp = parts(core)
        self.core = max(cp, key=lambda g: g.area) if cp else outline

    def images(self, g, axes=None):
        """`g` and its mirror images over the plate's axes, or just `axes` (g first)."""
        out = [g]
        for c, d in (self.axes if axes is None else axes):
            out = out + [_reflect_geom(q, c, d) for q in out]
        return out

    def twin_axes(self, g, pool, tol=TWIN_TOL, tree=None):
        """The axes across which `g` has a mirror twin in `pool`, within `tol` mm everywhere
        (itself, if it sits on the axis). Both axes only if the image across both is there too."""
        def found(m):
            cand = (pool[k] for k in tree.query(m.buffer(tol))) if tree is not None else pool
            return any(m.hausdorff_distance(q) <= tol for q in cand)

        out = [(c, d) for c, d in self.axes if found(_reflect_geom(g, c, d))]
        if len(out) == 2 and not found(self.images(g)[3]):
            out = out[:1]
        return out

    def grid_keepouts(self):
        """The blobs that steer the symmetric rib grid: mirrored pairs and holes on an axis."""
        return [b for b, ok in zip(self.sym_blobs, self.paired) if ok]

    def fixed(self, grow=0.0):
        """Plate area kept solid by the edge and hole clearances (not by ribs), grown by `grow`."""
        g = self.profile.difference(self.region)
        if self.keepouts:
            g = g.union(unary_union(self.keepouts))
        return g.buffer(grow) if grow else g

    def protected(self):
        """Plate area no pocket may touch (for drawing)."""
        allowed = self.region.difference(unary_union(self.keepouts)) if self.keepouts else self.region
        return self.profile.difference(allowed)

    def hole_clearance(self, i):
        return self.clear.hole(i)


def protected_shapes(domain: Domain, tol=0.1):
    """Protected area as [{outer, holes}] rings for the UI overlay."""
    out = []
    for p in parts(domain.protected()):
        p = p.simplify(tol)
        if isinstance(p, MultiPolygon):
            ps = list(p.geoms)
        else:
            ps = [p]
        for q in ps:
            if q.is_empty or q.area < 0.5:
                continue
            out.append({"outer": _coords(q.exterior, tol), "holes": [_coords(i, tol) for i in q.interiors]})
    return out
