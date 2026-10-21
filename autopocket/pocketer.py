"""Automatic lightening pockets for planar faces of a B-rep solid.

For every eligible planar face:
  1. The face outline is projected to 2D and inset by `wall` (holes grow by `wall`,
     so bolt holes keep a ring of material around them).
  2. A rib pattern (isogrid triangles or a rectangular grid) splits the inset
     region into pocket cells; cells too small for the cutter are dropped.
  3. The material under each cell is measured with rays. Thin, uniform plates get
     through-pockets; everything else gets blind pockets leaving `floor` material.
  4. Each pocket is checked against the *current* solid with a slightly enlarged
     test volume so it never breaks into holes, other pockets or outer walls.
  5. Pocket outlines get corner fillets of `corner_radius` (≈ end-mill radius)
     and are cut from the solid.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

import numpy as np
import shapely
from shapely import affinity
from shapely.geometry import LineString, MultiPolygon, Polygon, box as sbox
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge,
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakeVertex,
    BRepBuilderAPI_MakeWire,
)
from OCP.GC import GC_MakeArcOfCircle
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.GeomAbs import GeomAbs_Plane
from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector
from OCP.TopAbs import TopAbs_REVERSED
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS
from OCP.collections import List_TopoDS_Shape
from OCP.gp import gp_Ax3, gp_Dir, gp_Lin, gp_Pln, gp_Pnt, gp_Vec

from . import cadio


@dataclass
class PocketParams:
    pattern: str = "triangle"        # "triangle" (isogrid), "grid", or "single"
    cell_size: float = 35.0          # pattern pitch, mm
    rib_width: float = 3.0           # material between neighbouring pockets, mm
    wall: float = 4.0                # material kept along face edges and around holes, mm
    floor: float = 1.5               # material left under blind pockets, mm
    corner_radius: float = 2.0       # inside corner radius (>= end-mill radius), mm
    through: bool = True             # allow through-pockets on thin uniform plates
    through_max_thickness: float = 13.0
    min_depth: float = 0.8           # skip blind pockets shallower than this, mm
    min_pocket_area: float = 25.0    # mm^2
    min_face_area: float = 300.0     # mm^2
    excluded_faces: list = field(default_factory=list)  # face indices (cadio.faces order)

    @classmethod
    def from_dict(cls, d):
        names = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in (d or {}).items() if k in names})

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


# --------------------------------------------------------------------------- face analysis

def planar_faces(shape, lin_defl):
    """Collect planar faces with their 2D outline in a local frame."""
    BRepMesh_IncrementalMesh(shape, lin_defl, False, 0.2, True)
    out = []
    for i, f in enumerate(cadio.faces(shape)):
        surf = BRepAdaptor_Surface(f)
        if surf.GetType() != GeomAbs_Plane:
            continue
        pos = surf.Plane().Position()
        o = _np(pos.Location())
        x = _np(pos.XDirection())
        y = _np(pos.YDirection())
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
        polys = [Polygon(uv[t]) for t in idx]
        polys = [p for p in polys if p.area > 1e-9]
        if not polys:
            continue
        outline = unary_union(polys).buffer(1e-4, join_style="mitre").buffer(-1e-4, join_style="mitre")
        out.append(FaceFrame(i, o, x, y, n, outline))
    return out


def _np(p):
    return np.array([p.X(), p.Y(), p.Z()])


# --------------------------------------------------------------------------- 2D pattern

def _main_angle(region):
    rect = region.minimum_rotated_rectangle
    c = np.array(rect.exterior.coords)
    e1, e2 = c[1] - c[0], c[2] - c[1]
    e = e1 if np.hypot(*e1) >= np.hypot(*e2) else e2
    return math.atan2(e[1], e[0])


def _lines(center, normal_angle, spacing, extent, offset=0.0):
    """Parallel lines (as LineStrings) with given normal direction, spaced `spacing` apart."""
    n = np.array([math.cos(normal_angle), math.sin(normal_angle)])
    d = np.array([-n[1], n[0]])
    k = int(extent / spacing) + 2
    out = []
    for j in range(-k, k + 1):
        p = center + n * (offset + j * spacing)
        out.append(LineString([p - d * extent, p + d * extent]))
    return out


def rib_network(region, p: PocketParams):
    if p.pattern == "single":
        return None
    minx, miny, maxx, maxy = region.bounds
    extent = math.hypot(maxx - minx, maxy - miny) + p.cell_size
    c = np.array(region.centroid.coords[0])
    th = _main_angle(region)
    if p.pattern == "grid":
        # fit a whole number of cells along each principal direction
        rot = affinity.rotate(region, -th, origin=tuple(c), use_radians=True)
        rx0, ry0, rx1, ry1 = rot.bounds
        lines = []
        for axis, (a0, a1) in enumerate([(rx0, rx1), (ry0, ry1)]):
            L = a1 - a0
            n = max(1, round(L / p.cell_size))
            for i in range(1, n):
                v = a0 + L * i / n
                if axis == 0:
                    lines.append(LineString([(v, ry0 - 1), (v, ry1 + 1)]))
                else:
                    lines.append(LineString([(rx0 - 1, v), (rx1 + 1, v)]))
        if not lines:
            return None
        net = unary_union([ln.buffer(p.rib_width / 2, cap_style="flat") for ln in lines])
        return affinity.rotate(net, th, origin=tuple(c), use_radians=True)
    # isogrid: three line families 60 deg apart, all passing through the centroid
    h = p.cell_size * math.sqrt(3) / 2
    lines = []
    for k in range(3):
        lines += _lines(c, th + math.pi / 2 + k * 2 * math.pi / 3, h, extent)
    return unary_union([ln.buffer(p.rib_width / 2, cap_style="flat") for ln in lines])


def pocket_cells(outline, p: PocketParams):
    region = outline.buffer(-p.wall, join_style="mitre", mitre_limit=5)
    if region.is_empty:
        return []
    ribs = rib_network(region, p)
    cells = region.difference(ribs) if ribs is not None else region
    out = []
    r = max(p.corner_radius, 0.05)
    for c in _polys(cells):
        # must fit the cutter with some margin, and be big enough to matter
        if c.buffer(-1.15 * r).is_empty or c.area < p.min_pocket_area:
            continue
        opened = c.buffer(-r, join_style="mitre", mitre_limit=5).buffer(r, join_style="mitre", mitre_limit=5)
        for q in _polys(opened):
            q = orient(q.simplify(0.01), 1.0)
            if q.area >= p.min_pocket_area and not q.buffer(-r).is_empty:
                out.append(q)
    return out


def _polys(g):
    if g is None or g.is_empty:
        return []
    if isinstance(g, Polygon):
        return [g]
    return [x for x in getattr(g, "geoms", []) if isinstance(x, Polygon) and not x.is_empty]


# --------------------------------------------------------------------------- 3D helpers

class Thickness:
    """Ray-cast material thickness below a face."""

    def __init__(self, shape):
        self.ix = IntCurvesFace_ShapeIntersector()
        self.ix.Load(shape, 1e-6)

    def at(self, p, n):
        start = p - n * 1e-3
        self.ix.Perform(gp_Lin(gp_Pnt(*start), gp_Dir(*(-n))), 0.0, 1e9)
        ws = [self.ix.WParameter(i) for i in range(1, self.ix.NbPnt() + 1)]
        ws = [w for w in ws if w > 1e-4]
        return min(ws) if ws else None


def sample_points(poly, n=24):
    inner = poly.buffer(-0.3)
    if inner.is_empty:
        inner = poly
    minx, miny, maxx, maxy = inner.bounds
    k = max(2, int(math.sqrt(n * (maxx - minx) * (maxy - miny) / max(inner.area, 1e-9))))
    xs, ys = np.meshgrid(np.linspace(minx, maxx, k), np.linspace(miny, maxy, k))
    pts = [pt for pt in zip(xs.ravel(), ys.ravel()) if inner.contains(shapely.Point(pt))]
    pts.append(inner.representative_point().coords[0])
    for g in _polys(inner):
        pts += list(g.exterior.coords)[:-1:max(1, len(g.exterior.coords) // 16)]
    return np.array(pts)


def _rounded_ring(c, r):
    """Closed 2D ring -> list of segments ('line', p, q) / ('arc', p, mid, q) with corners of radius r."""
    n = len(c)
    corners = []  # (p_in, mid, p_out) or (vertex,)
    for i in range(n):
        a, b, d = c[i - 1], c[i], c[(i + 1) % n]
        la, ld = np.linalg.norm(a - b), np.linalg.norm(d - b)
        if r <= 0.05 or la < 1e-9 or ld < 1e-9:
            corners.append((b,))
            continue
        u1, u2 = (a - b) / la, (d - b) / ld
        half = math.acos(np.clip(u1 @ u2, -1, 1)) / 2
        if half > math.radians(84):  # nearly straight: no fillet needed
            corners.append((b,))
            continue
        rr = min(r, 0.49 * min(la, ld) * math.tan(half))
        if rr < 0.05:
            corners.append((b,))
            continue
        t = rr / math.tan(half)
        w = (u1 + u2) / np.linalg.norm(u1 + u2)
        centre = b + w * rr / math.sin(half)
        corners.append((b + u1 * t, centre - w * rr, b + u2 * t))
    segs = []
    for i in range(n):
        cur, nxt = corners[i], corners[(i + 1) % n]
        if len(cur) == 3:
            segs.append(("arc", *cur))
        segs.append(("line", cur[-1], nxt[0]))
    return segs


def make_face(poly: Polygon, frame: FaceFrame, offset=0.0, radius=0.0):
    """Planar face from a 2D polygon, with sharp corners rounded to `radius` (true arcs)."""
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


def prism(face, frame: FaceFrame, depth):
    return BRepPrimAPI_MakePrism(face, gp_Vec(*(-frame.n * depth))).Shape()


def fully_inside(solid, tools, tol=0.998):
    """True when the union of tool volumes lies inside `solid`."""
    tv = sum(cadio.volume(t) for t in tools)
    if tv <= 0:
        return True
    common = BRepAlgoAPI_Common(solid, cadio.make_compound(tools))
    return common.IsDone() and cadio.volume(common.Shape()) >= tol * tv


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
    res = op.Shape()
    sols = cadio.solids(res)
    if not sols:
        return None
    res = max(sols, key=cadio.volume) if len(sols) > 1 else sols[0]
    return res if BRepCheck_Analyzer(res).IsValid() else None


# --------------------------------------------------------------------------- main

@dataclass
class Pocket:
    face: int
    depth: float
    through: bool
    area: float


def pocket_solid(solid, p: PocketParams, face_offset=0, progress=None):
    """Return (pocketed_solid, [Pocket]) for one solid."""
    lo, hi = cadio.bbox(solid)
    lin = max(0.01, float(np.linalg.norm(hi - lo)) * 2e-4)
    frames = [f for f in planar_faces(solid, lin)
              if f.index + face_offset not in set(p.excluded_faces) and f.outline.area >= p.min_face_area]
    frames.sort(key=lambda f: -f.outline.area)
    excluded = set(p.excluded_faces)
    protected = [f for i, f in enumerate(cadio.faces(solid)) if i + face_offset in excluded]
    protected = cadio.make_compound(protected) if protected else None
    current, made = solid, []
    for fi, fr in enumerate(frames):
        if progress:
            progress(f"Face {fi + 1}/{len(frames)}", fi / max(len(frames), 1))
        cells = pocket_cells(fr.outline, p)
        if not cells:
            continue
        thick = Thickness(current)
        margin = 0.45 * min(p.wall, p.rib_width)
        accepted = []  # (poly, depth, through)
        for cell in cells:
            ts = [thick.at(fr.to3d(uv)[0], fr.n) for uv in sample_points(cell)]
            if not ts or any(t is None for t in ts):
                continue  # part of this cell is already void (e.g. a pocket cut from the other side)
            tmin, tmax = min(ts), max(ts)
            through = (p.through and tmin <= p.through_max_thickness
                       and tmax - tmin <= 0.02 * tmax + 0.05)
            if through and protected is not None:
                # a through-pocket must not break out through a protected face
                tool = prism(make_face(cell, fr, 0.0), fr, tmin + 0.5)
                if BRepExtrema_DistShapeShape(tool, protected).Value() < 1e-3:
                    through = False
            depth = tmin if through else tmin - p.floor
            if not through and depth < p.min_depth:
                continue
            accepted.append([cell, depth, through])
        if not accepted:
            continue

        def test_tool(cell, depth, through):
            test_depth = depth - 0.1 if through else depth + 0.9 * p.floor - 0.05
            f = make_face(orient(cell.buffer(margin, join_style="mitre", mitre_limit=5), 1.0), fr, -0.05)
            return prism(f, fr, test_depth)

        # validate: quick group check, then per pocket with depth back-off
        if not fully_inside(current, [test_tool(*a) for a in accepted]):
            ok = []
            for cell, depth, through in accepted:
                for _ in range(4):
                    if fully_inside(current, [test_tool(cell, depth, through)]):
                        ok.append([cell, depth, through])
                        break
                    if through:
                        through, depth = False, depth - p.floor
                    else:
                        depth *= 0.6
                    if depth < p.min_depth:
                        break
            accepted = ok
        tools = []
        for cell, depth, through in accepted:
            top = 0.02
            try:
                filleted = make_face(cell, fr, top, p.corner_radius)
            except Exception:
                filleted = make_face(cell, fr, top)
            cut_depth = depth + top + (0.5 if through else 0.0)
            tools.append(prism(filleted, fr, cut_depth))
            made.append(Pocket(fr.index + face_offset, round(depth, 3), through, round(cell.area, 2)))
        if not tools:
            continue
        res = boolean_cut(current, tools)
        if res is None:  # fall back to one pocket at a time
            n_before = len(made) - len(tools)
            kept, res = [], current
            for t, m in zip(tools, made[n_before:]):
                r2 = boolean_cut(res, [t])
                if r2 is not None:
                    res = r2
                    kept.append(m)
            made[n_before:] = kept
        current = res
    return current, made


def pocket_shape(shape, p: PocketParams, progress=None):
    """Pocket every solid of a shape. Face indices refer to cadio.faces(shape)."""
    all_faces = cadio.faces(shape)
    sols = cadio.solids(shape)
    results, pockets = [], []
    for si, s in enumerate(sols):
        # face index offset so that excluded_faces map to faces of the whole shape
        local = cadio.faces(s)
        mapping = {}
        for li, lf in enumerate(local):
            for gi, gf in enumerate(all_faces):
                if lf.IsSame(gf):
                    mapping[li] = gi
                    break
        q = PocketParams.from_dict(p.to_dict())
        q.excluded_faces = [li for li, gi in mapping.items() if gi in set(p.excluded_faces)]

        def prog(msg, frac, si=si):
            if progress:
                progress(f"Solid {si + 1}/{len(sols)} · {msg}", (si + frac) / len(sols))

        res, made = pocket_solid(s, q, 0, prog)
        for m in made:
            m.face = mapping.get(m.face, m.face)
        results.append(res)
        pockets += made
    out = results[0] if len(results) == 1 else cadio.make_compound(results)
    return out, pockets
