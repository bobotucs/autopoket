"""Truss-style through-pockets for flat plates (FTC style).

The plate profile is taken from its largest flat face. A rib network is laid out
like a hand-drawn truss:

  * a frame rib runs around the outline, its centre line `offset` inside the edge;
  * every hole/cutout gets a ring rib, its centre line `offset` outside the hole;
  * nodes are placed at hole centres, along the frame line and on a sparse interior
    lattice, then joined by a Delaunay triangulation (mirrored for symmetric plates);
  * every rib is `rib` wide.

What is left between the ribs becomes the pockets. They are opened with the tool
radius so an end mill of that radius can cut every corner, then cut all the way
through the plate.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np
import shapely
from scipy.spatial import Delaunay
from shapely import affinity
from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge,
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakeVertex,
    BRepBuilderAPI_MakeWire,
)
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.GC import GC_MakeArcOfCircle
from OCP.GeomAbs import GeomAbs_Plane
from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector
from OCP.TopAbs import TopAbs_REVERSED
from OCP.TopLoc import TopLoc_Location
from OCP.collections import List_TopoDS_Shape
from OCP.gp import gp_Ax3, gp_Dir, gp_Lin, gp_Pln, gp_Pnt, gp_Vec

from . import cadio


@dataclass
class PlateRules:
    rib: float = 8.0           # width of every rib, mm
    offset: float = 4.0        # rib centre line distance from plate edges and hole edges, mm
    tool_radius: float = 2.0   # end-mill radius = minimum inside corner radius, mm
    spacing: float = 55.0      # target distance between truss nodes, mm
    min_pocket_area: float = 150.0  # mm^2, smaller pockets are not worth the machining

    def to_dict(self):
        return asdict(self)


@dataclass
class FaceFrame:
    index: int
    origin: np.ndarray
    x: np.ndarray
    y: np.ndarray
    n: np.ndarray          # outward normal
    outline: Polygon | MultiPolygon

    def to3d(self, uv, offset=0.0):
        uv = np.atleast_2d(uv)
        return self.origin + uv[:, :1] * self.x + uv[:, 1:2] * self.y + offset * self.n

    def ax3(self, offset=0.0):
        o = self.origin + offset * self.n
        z = np.cross(self.x, self.y)
        return gp_Ax3(gp_Pnt(*o), gp_Dir(*z), gp_Dir(*self.x))


@dataclass
class Plate:
    solid: object
    frame: FaceFrame
    profile: Polygon      # outline with holes, in frame coordinates
    thickness: float
    warnings: list


def _np(p):
    return np.array([p.X(), p.Y(), p.Z()])


# --------------------------------------------------------------------------- plate detection

def planar_faces(shape, lin_defl):
    """Planar faces with their 2D outline in a local frame."""
    BRepMesh_IncrementalMesh(shape, lin_defl, False, 0.2, True)
    out = []
    for i, f in enumerate(cadio.faces(shape)):
        surf = BRepAdaptor_Surface(f)
        if surf.GetType() != GeomAbs_Plane:
            continue
        pos = surf.Plane().Position()
        o, x, y = _np(pos.Location()), _np(pos.XDirection()), _np(pos.YDirection())
        n = np.cross(x, y)
        if f.Orientation() == TopAbs_REVERSED:
            n = -n
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(f, loc)
        if tri is None:
            continue
        trsf = loc.Transformation()
        pts = np.array([_np(tri.Node(k).Transformed(trsf)) for k in range(1, tri.NbNodes() + 1)])
        uv = np.c_[(pts - o) @ x, (pts - o) @ y]
        idx = np.array([tri.Triangle(k).Get() for k in range(1, tri.NbTriangles() + 1)]) - 1
        polys = [p for p in (Polygon(uv[t]) for t in idx) if p.area > 1e-9]
        if not polys:
            continue
        outline = unary_union(polys).buffer(1e-4, join_style="mitre").buffer(-1e-4, join_style="mitre")
        out.append(FaceFrame(i, o, x, y, n, outline))
    return out


def thickness_at(shape, p, n):
    ix = IntCurvesFace_ShapeIntersector()
    ix.Load(shape, 1e-6)
    ix.Perform(gp_Lin(gp_Pnt(*(p - n * 1e-3)), gp_Dir(*(-n))), 0.0, 1e9)
    ws = [ix.WParameter(i) for i in range(1, ix.NbPnt() + 1)]
    ws = [w for w in ws if w > 1e-4]
    return min(ws) if ws else None


def find_plate(solid) -> Plate:
    lo, hi = cadio.bbox(solid)
    lin = max(0.01, float(np.linalg.norm(hi - lo)) * 1e-4)
    frames = planar_faces(solid, lin)
    if not frames:
        raise ValueError("No flat face found - AutoPocket only works on flat plates")
    fr = max(frames, key=lambda f: f.outline.area)
    profile = fr.outline
    if isinstance(profile, MultiPolygon):
        profile = max(profile.geoms, key=lambda g: g.area)
    warnings = []
    t = thickness_at(solid, fr.to3d(profile.representative_point().coords[0])[0], fr.n)
    if t is None:
        raise ValueError("Could not measure the plate thickness")
    size = np.array(profile.bounds[2:]) - np.array(profile.bounds[:2])
    if abs(cadio.volume(solid) - profile.area * t) > 0.03 * profile.area * t:
        warnings.append("Part is not a uniform flat plate; pockets are cut through the whole profile anyway.")
    if size.max() > 18 * 25.4 + 0.5:
        warnings.append(f"Plate is {size.max() / 25.4:.1f} in long - bigger than the 18 in FTC sizing box.")
    return Plate(solid, fr, orient(profile, 1.0), t, warnings)


# --------------------------------------------------------------------------- 2D truss layout

def _ring_nodes(ring: Polygon, spacing, skip_convex=False):
    """Nodes along a polygon boundary: every real corner plus evenly spaced points between."""
    c = np.array(ring.exterior.coords)[:-1]
    n = len(c)
    turn = np.zeros(n)
    for i in range(n):
        a, b = c[i] - c[i - 1], c[(i + 1) % n] - c[i]
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        if na > 1e-9 and nb > 1e-9:
            turn[i] = math.degrees(math.acos(np.clip(a @ b / (na * nb), -1, 1)))
    corners = [i for i in range(n) if turn[i] > 25]
    ccw = ring.exterior.is_ccw
    convex = set()
    for i in corners:
        a, b = c[i] - c[i - 1], c[(i + 1) % n] - c[i]
        if (a[0] * b[1] - a[1] * b[0] > 0) == ccw:
            convex.add(i)
    line = ring.exterior
    if not corners:  # smooth outline (circle, oval): even spacing
        k = max(3, round(line.length / spacing))
        return [np.array(line.interpolate(line.length * j / k).coords[0]) for j in range(k)]
    nodes = []
    dist = [line.project(Point(c[i])) for i in corners]
    for j, i in enumerate(corners):
        d0 = dist[j]
        d1 = dist[(j + 1) % len(corners)] + (line.length if j + 1 == len(corners) else 0)
        if i not in convex or not skip_convex:  # ribs never run into outside corners
            nodes.append(c[i])
        k = max(1, round((d1 - d0) / spacing))
        for m in range(1, k):
            nodes.append(np.array(line.interpolate((d0 + (d1 - d0) * m / k) % line.length).coords[0]))
    return nodes


def _mirror_axes(profile: Polygon):
    """Mirror axes (point, direction) the profile is symmetric about."""
    c = np.array(profile.envelope.centroid.coords[0])
    rect = profile.minimum_rotated_rectangle
    rc = np.array(rect.exterior.coords)
    th = math.atan2(*(rc[1] - rc[0])[::-1])
    axes = []
    for ang in [0.0, math.pi / 2, th % math.pi, (th + math.pi / 2) % math.pi]:
        d = np.array([math.cos(ang), math.sin(ang)])
        # reflection across the line through c with direction d
        m = np.array([[2 * d[0] ** 2 - 1, 2 * d[0] * d[1]], [2 * d[0] * d[1], 2 * d[1] ** 2 - 1]])
        mirrored = affinity.affine_transform(profile, [*m.ravel(), *(c - m @ c)])
        if profile.symmetric_difference(mirrored).area < 2e-3 * profile.area:
            # a second axis must be perpendicular to the first (half -> quarter)
            if not axes or abs(d @ axes[0][1]) < 1e-6:
                axes.append((c, d))
    return axes[:2]


def _reflect(pts, c, d):
    pts = np.atleast_2d(pts)
    v = pts - c
    return c + 2 * np.outer(v @ d, d) - v


def truss_edges(profile: Polygon, r: PlateRules):
    """Rib centre lines (list of LineStrings) for a plate profile."""
    S = r.spacing
    outer = Polygon(profile.exterior)
    frame = outer.buffer(-r.offset, join_style="mitre", mitre_limit=10)
    if frame.is_empty:
        return [], []
    if isinstance(frame, MultiPolygon):
        frame = max(frame.geoms, key=lambda g: g.area)
    cutouts = [Polygon(h) for h in profile.interiors]

    # nodes, highest priority first
    nodes = []

    def add(p, min_d):
        if frame.buffer(1e-6).contains(Point(p)) and all(np.linalg.norm(p - q) >= min_d for q in nodes):
            nodes.append(np.asarray(p, float))

    for h in cutouts:
        eq_r = math.sqrt(h.area / math.pi)
        if eq_r < 0.35 * S:
            add(np.array(h.centroid.coords[0]), 0.0)
        else:  # large cutout: nodes around its ring rib
            for p in _ring_nodes(h.buffer(r.offset), S):
                add(p, 0.4 * S)
    for p in _ring_nodes(frame, 1.25 * S, skip_convex=True):  # fewer ribs meet the frame: bigger edge pockets
        add(p, 0.55 * S)
    # sparse interior lattice
    inner = frame.buffer(-0.45 * S)
    if not inner.is_empty:
        minx, miny, maxx, maxy = inner.bounds
        cx, cy = np.array(frame.envelope.centroid.coords[0])
        h = S * math.sqrt(3) / 2
        for j in range(-int((cy - miny) / h) - 1, int((maxy - cy) / h) + 2):
            for i in range(-int((cx - minx) / S) - 2, int((maxx - cx) / S) + 3):
                p = np.array([cx + i * S + (S / 2 if j % 2 else 0), cy + j * h])
                if inner.contains(Point(p)):
                    add(p, 0.7 * S)
    nodes = np.array(nodes)

    axes = _mirror_axes(profile)
    if axes:
        # work on one half (or quarter) and mirror, so the truss is symmetric
        for c, d in axes:
            nrm = np.array([-d[1], d[0]])
            s = (nodes - c) @ nrm
            near = np.abs(s) < 0.2 * S
            nodes[near] -= np.outer(s[near], nrm)        # snap onto the axis
            # make sure the axis meets the frame with a node at both ends
            for sgn in (-1, 1):
                far = c - d * 1e4 * sgn
                hit = LineString([far, c]).intersection(frame.exterior)
                if not hit.is_empty:
                    pts = [np.array(g.coords[0]) for g in getattr(hit, "geoms", [hit])]
                    p = min(pts, key=lambda q: np.linalg.norm(q - far))
                    if np.linalg.norm(nodes - p, axis=1).min() >= 0.4 * S:
                        nodes = np.vstack([nodes, p])
        keep = np.ones(len(nodes), bool)
        for c, d in axes:  # one half (or quarter), axis nodes included
            keep &= ((nodes - c) @ np.array([-d[1], d[0]])) >= -1e-6
        half = nodes[keep]
        half = np.unique(np.round(half, 6), axis=0)
        edges = _delaunay_edges(half)
        for c, d in axes:
            edges = edges + [(_reflect(a, c, d)[0], _reflect(b, c, d)[0]) for a, b in edges]
        nodes = np.vstack([half] + [_reflect(half, c, d) for c, d in axes])
    else:
        edges = _delaunay_edges(nodes)
    lines = [LineString([a, b]) for a, b in edges if np.linalg.norm(a - b) > 1e-6]
    # drop ribs that run outside the plate (concave outlines)
    lines = [ln for ln in lines if frame.buffer(0.5).contains(ln.interpolate(0.5, normalized=True))]
    return lines, nodes


def _delaunay_edges(pts):
    if len(pts) < 3:
        return [(pts[0], pts[1])] if len(pts) == 2 else []
    tri = Delaunay(pts)
    es = set()
    for s in tri.simplices:
        # skip sliver triangles along straight boundaries
        a, b, c = pts[s]
        u, v = b - a, c - a
        area = abs(u[0] * v[1] - u[1] * v[0]) / 2
        longest = max(np.linalg.norm(b - a), np.linalg.norm(c - b), np.linalg.norm(a - c))
        if area < 0.08 * longest ** 2:
            continue
        for i, j in ((0, 1), (1, 2), (2, 0)):
            es.add(tuple(sorted((int(s[i]), int(s[j])))))
    return [(pts[i], pts[j]) for i, j in es]


MAX_GAP_DEG = 120.0  # no pocket may wrap more than this far around a hole, so every hole
                     # is held by material on at least three sides


def _cut_pockets(region, ribs, r: PlateRules):
    """Pocket polygons (sharp, to be rounded with the tool radius) and their rounded union."""
    rt = r.tool_radius
    out, rounded = [], []
    cells = region.difference(ribs)
    for cell in getattr(cells, "geoms", [cells]):
        if not isinstance(cell, Polygon) or cell.is_empty:
            continue
        eroded = cell.buffer(-rt, quad_segs=16)
        for e in getattr(eroded, "geoms", [eroded]):
            if not isinstance(e, Polygon) or e.is_empty or e.buffer(-(4.0 - rt)).is_empty:  # >= 8 mm wide
                continue
            sharp = e.buffer(rt, join_style="mitre", mitre_limit=10).simplify(0.005)
            rnd = e.buffer(rt, quad_segs=16)
            if isinstance(sharp, Polygon) and rnd.area >= r.min_pocket_area:
                out.append(orient(sharp, 1.0))
                rounded.append(rnd)
    return out, unary_union(rounded) if rounded else Polygon()


def hole_support(hole: Polygon, void, r: PlateRules, samples=120):
    """(struts, largest unsupported gap in degrees, gap centre angle) around one hole.

    Walks a ring just outside the hole's keep-out band; every stretch that is solid
    material (a rib, the frame, another hole's ring) counts as one strut.
    """
    ring = hole.buffer(r.offset + r.rib / 2 + 0.75, quad_segs=32).exterior
    c = np.array(hole.centroid.coords[0])
    pts = np.array([ring.interpolate(t, normalized=True).coords[0]
                    for t in np.linspace(0, 1, samples, endpoint=False)])
    ang = np.degrees(np.arctan2(pts[:, 1] - c[1], pts[:, 0] - c[0])) % 360
    order = np.argsort(ang)
    ang, pts = ang[order], pts[order]
    sup = ~shapely.contains_xy(void, pts[:, 0], pts[:, 1]) if not void.is_empty else np.ones(len(pts), bool)
    if sup.all():
        return 99, 0.0, None
    if not sup.any():
        return 0, 360.0, 0.0
    start = int(np.argmax(sup & ~np.roll(sup, 1)))  # first sample of some supported run
    sup, ang = np.roll(sup, -start), np.roll(ang, -start)
    struts, gaps, i, n = 0, [], 0, len(sup)
    while i < n:
        j = i
        while j + 1 < n and sup[j + 1] == sup[i]:
            j += 1
        if sup[i]:
            struts += 1
        else:
            a0, a1 = ang[i - 1] if i else ang[i], ang[(j + 1) % n]
            width = (a1 - a0) % 360
            gaps.append((width, (a0 + width / 2) % 360))
        i = j + 1
    width, mid = max(gaps)
    return struts, width, mid


def _add_strut(c, mid_deg, lines, nodes, frame, keep_r, S):
    """A short rib from hole centre c into the gap at angle mid_deg.

    Runs straight out to the nearest rib or the frame; falls back to a nearby node.
    """
    u = np.array([math.cos(math.radians(mid_deg)), math.sin(math.radians(mid_deg))])
    ray = LineString([c + u * keep_r, c + u * 3 * S])
    hit = ray.intersection(unary_union([frame.exterior] + lines))
    pts = [np.array(xy) for g in getattr(hit, "geoms", [hit]) if not g.is_empty for xy in g.coords]
    if pts:
        return LineString([c, min(pts, key=lambda q: np.linalg.norm(q - c))])
    best, best_score = None, 1e9
    for q in nodes:
        v = q - c
        d = np.linalg.norm(v)
        if d < keep_r + 4 or d > 2.5 * S:
            continue
        off = math.degrees(math.acos(np.clip(v @ u / d, -1, 1)))
        if off <= 35 and off / 30 + d / S < best_score:
            best, best_score = q, off / 30 + d / S
    return None if best is None else LineString([c, best])


def pocket_outlines(profile: Polygon, r: PlateRules):
    """2D pocket polygons (sharp-cornered, to be rounded with r.tool_radius)."""
    half = r.rib / 2
    outer = Polygon(profile.exterior)
    region = outer.buffer(-(r.offset + half), join_style="mitre", mitre_limit=10)
    frame = outer.buffer(-r.offset, join_style="mitre", mitre_limit=10)
    holes = [Polygon(h) for h in profile.interiors]
    keepouts = [h.buffer(r.offset + half, quad_segs=32) for h in holes]
    lines, nodes = truss_edges(profile, r)
    ribs = unary_union([ln.buffer(half, quad_segs=16) for ln in lines] + keepouts)
    out, void = _cut_pockets(region, ribs, r)
    # make sure no hole hangs off one or two ribs: add struts into the biggest gaps
    for _ in range(6):
        added = []
        for h in holes:
            struts, gap, mid = hole_support(h, void, r)
            if gap <= MAX_GAP_DEG:
                continue
            c = np.array(h.centroid.coords[0])
            keep_r = math.sqrt(h.area / math.pi) + r.offset + half
            ln = _add_strut(c, mid, lines + added, nodes, frame, keep_r, r.spacing)
            if ln is not None and ln.length > 1e-3:
                added.append(ln)
        if not added:
            break
        lines = lines + added
        ribs = unary_union([ribs] + [ln.buffer(half, quad_segs=16) for ln in added])
        out, void = _cut_pockets(region, ribs, r)
    return out, lines, nodes


# --------------------------------------------------------------------------- 3D

def _rounded_ring(c, r):
    """Closed 2D ring -> segments ('line', p, q) / ('arc', p, mid, q) with corners rounded to r."""
    n = len(c)
    corners = []
    for i in range(n):
        a, b, d = c[i - 1], c[i], c[(i + 1) % n]
        la, ld = np.linalg.norm(a - b), np.linalg.norm(d - b)
        if r <= 0.05 or la < 1e-9 or ld < 1e-9:
            corners.append((b,))
            continue
        u1, u2 = (a - b) / la, (d - b) / ld
        half = math.acos(np.clip(u1 @ u2, -1, 1)) / 2
        if half > math.radians(84):  # nearly straight: no rounding needed
            corners.append((b,))
            continue
        rr = r
        t = rr / math.tan(half)
        if t > min(la, ld) + 1e-6:  # not enough room: shrink (only happens at material-side corners)
            rr = 0.49 * min(la, ld) * math.tan(half)
            t = rr / math.tan(half)
        if rr < 0.05:
            corners.append((b,))
            continue
        w = (u1 + u2) / np.linalg.norm(u1 + u2)
        centre = b + w * rr / math.sin(half)
        corners.append((b + u1 * t, centre - w * rr, b + u2 * t))
    segs = []
    for i in range(n):
        cur, nxt = corners[i], corners[(i + 1) % n]
        if len(cur) == 3:
            segs.append(("arc", *cur))
        segs.append(("line", cur[-1], nxt[0]))
    return _merge_arcs(segs)


def _merge_arcs(segs, max_turn=12.0):
    """Replace runs of short, evenly turning line segments (polygonised arcs) with true arcs."""
    def direction(sg):
        d = sg[-1] - sg[1]
        return d / max(np.linalg.norm(d), 1e-12)

    def turn(a, b):
        da, db = direction(a), direction(b)
        return math.degrees(math.atan2(da[0] * db[1] - da[1] * db[0], da @ db))

    out, i, n = [], 0, len(segs)
    while i < n:
        j = i
        if segs[i][0] == "line":
            L = np.linalg.norm(segs[i][-1] - segs[i][1])
            t0 = None
            while (j + 1 < n and segs[j + 1][0] == "line"
                   and abs(np.linalg.norm(segs[j + 1][-1] - segs[j + 1][1]) - L) < 0.05 * L + 1e-6):
                t = turn(segs[j], segs[j + 1])
                if not 0.3 < abs(t) < max_turn or (t0 is not None and abs(t - t0) > 0.2 * abs(t0) + 0.05):
                    break
                t0 = t if t0 is None else t0
                j += 1
        if j - i >= 2:  # at least three segments in the run
            pts = [segs[k][1] for k in range(i, j + 1)] + [segs[j][-1]]
            if np.linalg.norm(pts[0] - pts[-1]) < 1e-6:  # whole circle: two half arcs
                h = len(pts) // 2
                out.append(("arc", pts[0], pts[h // 2], pts[h]))
                out.append(("arc", pts[h], pts[(h + len(pts) - 1) // 2], pts[-1]))
            else:
                out.append(("arc", pts[0], pts[len(pts) // 2], pts[-1]))
        else:
            out.extend(segs[i:j + 1])
        i = j + 1
    return out


def make_face(poly: Polygon, frame: FaceFrame, offset=0.0, radius=0.0):
    """Planar face from a 2D polygon with sharp corners rounded to `radius` (true arcs)."""
    pln = gp_Pln(frame.ax3(offset))

    def P(q):
        return gp_Pnt(*frame.to3d(q, offset)[0])

    def wire(coords):
        segs = _rounded_ring(np.array(coords[:-1]), radius)
        mw = BRepBuilderAPI_MakeWire()
        first = last = None
        for k, sg in enumerate(segs):
            if np.linalg.norm(sg[1] - sg[-1]) < 1e-6:
                continue
            v1 = last or BRepBuilderAPI_MakeVertex(P(sg[1])).Vertex()
            if first is None:
                first = v1
            closing = all(np.linalg.norm(x[1] - x[-1]) < 1e-6 for x in segs[k + 1:])
            v2 = first if closing else BRepBuilderAPI_MakeVertex(P(sg[-1])).Vertex()
            if sg[0] == "line":
                e = BRepBuilderAPI_MakeEdge(v1, v2).Edge()
            else:
                arc = GC_MakeArcOfCircle(P(sg[1]), P(sg[2]), P(sg[3])).Value()
                e = BRepBuilderAPI_MakeEdge(arc, v1, v2).Edge()
            mw.Add(e)
            last = v2
        return mw.Wire()

    mf = BRepBuilderAPI_MakeFace(pln, wire(poly.exterior.coords), True)
    for ring in poly.interiors:
        mf.Add(wire(ring.coords))
    return mf.Face()


def boolean_cut(solid, tools):
    args, tl = List_TopoDS_Shape(), List_TopoDS_Shape()
    args.Append(solid)
    for t in tools:
        tl.Append(t)
    op = BRepAlgoAPI_Cut()
    op.SetArguments(args)
    op.SetTools(tl)
    op.SetRunParallel(True)
    op.SetFuzzyValue(1e-5)
    op.Build()
    if not op.IsDone():
        return None
    sols = cadio.solids(op.Shape())
    if not sols:
        return None
    res = max(sols, key=cadio.volume)
    return res if BRepCheck_Analyzer(res).IsValid() else None


def pocket_plate(plate: Plate, r: PlateRules, outlines=None):
    """Cut the truss pockets through the plate. Returns (solid, n_pockets, layout)."""
    lines = nodes = None
    if outlines is None:
        outlines, lines, nodes = pocket_outlines(plate.profile, r)
    fr, t = plate.frame, plate.thickness
    tools = []
    for poly in outlines:
        try:
            face = make_face(poly, fr, 0.5, r.tool_radius)
        except Exception:
            face = make_face(poly, fr, 0.5)
        tools.append(BRepPrimAPI_MakePrism(face, gp_Vec(*(-fr.n * (t + 1.0)))).Shape())
    if not tools:
        return plate.solid, 0, (outlines, lines, nodes)
    res = boolean_cut(plate.solid, tools)
    if res is None:  # fall back to one pocket at a time
        res, n = plate.solid, 0
        for tool in tools:
            r2 = boolean_cut(res, [tool])
            if r2 is not None:
                res, n = r2, n + 1
        return res, n, (outlines, lines, nodes)
    return res, len(tools), (outlines, lines, nodes)
