"""Truss-style through-pockets for flat plates (FTC style).

The plate profile is taken from its largest flat face. Then:

  * every hole/cutout gets a keep-out band (`offset` + half a rib); bands that overlap
    merge into one blob, so a bearing with its bolt circle or a bolt cluster is
    treated as a single feature, and bands that reach the frame become bumps on it;
  * the area between the frame line and the big features' band lines is meshed with a
    constrained quality triangulation; small holes and clusters are fixed mesh nodes;
  * mesh edges are pruned where two cells can merge into one still-compact pocket, so
    narrow gaps between features become whole pockets instead of scraps;
  * symmetric plates (outline and most holes) are laid out on one half and mirrored;
  * oversized pockets are split, and any feature that a pocket wraps around too far
    gets an extra strut, so every hole is held from several sides;
  * every rib is `rib` wide; pockets are opened with the tool radius and cut through.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np
import shapely
import triangle
from shapely import affinity
from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import polylabel, unary_union

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

def _reflect_matrix(c, d):
    m = np.array([[2 * d[0] ** 2 - 1, 2 * d[0] * d[1]], [2 * d[0] * d[1], 2 * d[1] ** 2 - 1]])
    return [*m.ravel(), *(c - m @ c)]


def _reflect_geom(g, c, d):
    return affinity.affine_transform(g, _reflect_matrix(c, d))


def _mirror_axes(outline: Polygon):
    """Mirror axes (point, direction) the plate outline is symmetric about."""
    c = np.array(outline.envelope.centroid.coords[0])
    rect = outline.minimum_rotated_rectangle
    rc = np.array(rect.exterior.coords)
    th = math.atan2(*(rc[1] - rc[0])[::-1])
    axes = []
    for ang in [0.0, math.pi / 2, th % math.pi, (th + math.pi / 2) % math.pi]:
        d = np.array([math.cos(ang), math.sin(ang)])
        if outline.symmetric_difference(_reflect_geom(outline, c, d)).area < 5e-3 * outline.area:
            # a second axis must be perpendicular to the first (half -> quarter)
            if not axes or abs(d @ axes[0][1]) < 1e-6:
                axes.append((c, d))
    return axes[:2]


def _reflect(pts, c, d):
    pts = np.atleast_2d(pts)
    v = pts - c
    return c + 2 * np.outer(v @ d, d) - v


SMALL_FEATURE_R = 6.0  # holes up to this radius may be mirrored as phantom holes
MIRROR_MATCH = 0.6     # share of holes that must have a mirror twin to use an axis


def _same(a: Polygon, b: Polygon, tol=0.15):
    return a.symmetric_difference(b).area < tol * max(a.area, b.area)


def plan_features(profile: Polygon):
    """Features to lay the truss around, and the mirror axes to use.

    If the outline is symmetric and every larger feature (bearing, slot, cutout) has a
    mirror twin, the layout is mirrored. Small holes without a twin are mirrored as
    "phantom" holes: they steer the ribs so both halves match, but get no boss.
    """
    outline = Polygon(profile.exterior)
    feats = [Polygon(h) for h in profile.interiors]
    axes = []
    for c, d in _mirror_axes(outline):
        twin = [any(_same(_reflect_geom(f, c, d), g) for g in feats) for f in feats]
        big_ok = all(t for t, f in zip(twin, feats) if math.sqrt(f.area / math.pi) > SMALL_FEATURE_R)
        # mirror only when the holes really are (mostly) symmetric about this axis too
        if big_ok and (not feats or sum(twin) >= MIRROR_MATCH * len(feats)):
            axes.append((c, d))
    for c, d in axes:
        extra = []
        for f in feats:
            m = _reflect_geom(f, c, d)
            if not any(_same(m, g) for g in feats + extra):
                extra.append(m)
        feats = feats + extra
    return outline, feats, axes


def real_features(profile: Polygon):
    return [Polygon(h) for h in profile.interiors]


def _blobs(feats, r):
    """Keep-out bands around features; overlapping bands merge into one blob (a hole cluster)."""
    keep = unary_union([f.buffer(r.offset + r.rib / 2, quad_segs=32) for f in feats])
    return [g for g in getattr(keep, "geoms", [keep]) if isinstance(g, Polygon) and not g.is_empty]


def _region(outline, r):
    return outline.buffer(-(r.offset + r.rib / 2), join_style="mitre", mitre_limit=10)


def _on_frame(blob, region):
    """True when a blob runs into the frame band (a hole near the edge)."""
    return blob.difference(region).area > 1.0


def _resample_ring(coords, step, min_pts=3, corner_turn=25.0):
    """Points along a closed ring: every real corner, plus even spacing (<= step) between."""
    c = np.array(coords)[:-1] if np.allclose(coords[0], coords[-1]) else np.array(coords)
    n = len(c)
    turn = np.zeros(n)
    for i in range(n):
        a, b = c[i] - c[i - 1], c[(i + 1) % n] - c[i]
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        if na > 1e-9 and nb > 1e-9:
            turn[i] = math.degrees(math.acos(np.clip(a @ b / (na * nb), -1, 1)))
    line = LineString(np.vstack([c, c[:1]]))
    corners = [i for i in range(n) if turn[i] > corner_turn]
    if not corners:
        k = max(min_pts, round(line.length / step))
        return [np.array(line.interpolate(line.length * j / k).coords[0]) for j in range(k)]
    out = []
    dist = [line.project(Point(c[i])) for i in corners]
    for j, i in enumerate(corners):
        d0 = dist[j]
        d1 = dist[(j + 1) % len(corners)] + (line.length if j + 1 == len(corners) else 0)
        out.append(c[i])
        k = max(1, math.ceil((d1 - d0) / step - 0.25))
        for m in range(1, k):
            out.append(np.array(line.interpolate((d0 + (d1 - d0) * m / k) % line.length).coords[0]))
    if len(out) < min_pts:
        k = min_pts
        out = [np.array(line.interpolate(line.length * j / k).coords[0]) for j in range(k)]
    return out


def _half_plane(c, d, size):
    """Polygon covering the side of the axis (c, d) that has (p - c) . n >= 0."""
    nrm = np.array([-d[1], d[0]])
    return Polygon([c - d * size, c + d * size, c + d * size + nrm * size, c - d * size + nrm * size])


def _prune_mesh(V, T, r: PlateRules):
    """Drop interior mesh edges whose two cells may merge into one still-compact pocket.

    Open areas keep their triangles (merging two would make a pocket too big), while
    narrow gaps between bearing bands and hole clusters become whole pockets instead
    of being chopped into scraps too small to cut. Returns the kept edges (index pairs).
    """
    S, half = r.spacing, r.rib / 2
    max_inr = MERGE_INRADIUS * S + half      # measured on rib centre lines
    max_len = MAX_POCKET_LENGTH * S + 2 * half
    tri_of = {}
    for k, t in enumerate(T):
        for i, j in ((0, 1), (1, 2), (2, 0)):
            tri_of.setdefault(tuple(sorted((int(t[i]), int(t[j])))), []).append(k)
    parent = list(range(len(T)))
    poly = {k: Polygon(V[t]) for k, t in enumerate(T)}

    def find(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    def compact(g):
        if not isinstance(g, Polygon) or g.area < 1e-6:
            return False
        if g.area < 0.8 * g.convex_hull.area:
            return False
        rect = np.array(g.minimum_rotated_rectangle.exterior.coords)
        if max(np.linalg.norm(rect[1] - rect[0]), np.linalg.norm(rect[2] - rect[1])) > max_len:
            return False
        return g.exterior.distance(polylabel(g, tolerance=0.5)) <= max_inr

    removed = set()
    interior = [e for e, ts in tri_of.items() if len(ts) == 2]
    for e in sorted(interior, key=lambda e: np.linalg.norm(V[e[0]] - V[e[1]])):
        a, b = find(tri_of[e][0]), find(tri_of[e][1])
        if a == b:
            removed.add(e)
            continue
        merged = unary_union([poly[a], poly[b]]).buffer(1e-6).buffer(-1e-6)
        if compact(merged):
            parent[b] = a
            poly[a] = merged
            removed.add(e)
    return [e for e in tri_of if e not in removed]


def truss_edges(profile: Polygon, r: PlateRules):
    """Rib centre lines and truss nodes for a plate profile.

    The space the ribs may use (inside the frame line, outside every big feature's band
    line) is meshed with a constrained quality triangulation, so triangles come out
    evenly sized, nothing crosses a feature and no area is left without ribs. Small
    holes and tight hole clusters are fixed mesh nodes, so ribs run into them from
    several sides. Symmetric plates are meshed on one half (or quarter) and mirrored.
    """
    S, half = r.spacing, r.rib / 2
    outline, feats, axes = plan_features(profile)
    frame = outline.buffer(-r.offset, join_style="mitre", mitre_limit=10)
    if frame.is_empty:
        return [], np.zeros((0, 2))
    if isinstance(frame, MultiPolygon):
        frame = max(frame.geoms, key=lambda g: g.area)
    region = _region(outline, r)

    big, points = [], []
    for b in _blobs(feats, r):
        rect = np.array(b.minimum_rotated_rectangle.exterior.coords)
        size = max(np.linalg.norm(rect[1] - rect[0]), np.linalg.norm(rect[2] - rect[1]))
        if size > 0.9 * S:
            big.append(b.buffer(-half))  # the band's centre line becomes a mesh boundary
        elif not _on_frame(b, region):  # small hole / cluster: one fixed node in the middle
            ctr = b.centroid if b.contains(b.centroid) else b.representative_point()
            points.append(np.array(ctr.coords[0]))
        # small blobs merged into the frame band are just bumps on the frame
    # merge hole nodes that sit almost on top of each other (e.g. a hole and its mirror twin)
    merged = []
    for p in points:
        for k, (q, n) in enumerate(merged):
            if np.linalg.norm(p - q / n) < 0.4 * S:
                merged[k] = (q + p, n + 1)
                break
        else:
            merged.append((p.copy(), 1))
    points = [q / n for q, n in merged]
    domain = frame.difference(unary_union(big)) if big else frame
    extent = 4 * max(outline.bounds[2] - outline.bounds[0], outline.bounds[3] - outline.bounds[1])
    for c, d in axes:
        domain = domain.intersection(_half_plane(c, d, extent))
        points = [p for p in points if (p - c) @ np.array([-d[1], d[0]]) >= -1e-6]
    max_area = math.sqrt(3) / 4 * S * S * 2.0  # a cap, not a target: typical triangles come out ~half of it
    edges = []
    for poly in getattr(domain, "geoms", [domain]):
        if not isinstance(poly, Polygon) or poly.area < 1.0:
            continue
        verts, segs, holes = [], [], []
        for k, ring in enumerate([poly.exterior, *poly.interiors]):
            pts = _resample_ring(list(ring.coords), S if k == 0 else 0.8 * S, min_pts=3 if k == 0 else 4)
            base = len(verts)
            verts += pts
            segs += [(base + i, base + (i + 1) % len(pts)) for i in range(len(pts))]
            if k:
                holes.append(np.array(Polygon(ring).representative_point().coords[0]))
        inner = poly.buffer(-0.3 * S)
        verts += [p for p in points if inner.contains(Point(p))]
        data = {"vertices": np.array(verts, float), "segments": np.array(segs, int)}
        if holes:
            data["holes"] = np.array(holes)
        try:
            mesh = triangle.triangulate(data, f"pq20a{max_area:.3f}")
        except Exception:
            continue
        V = mesh["vertices"]
        edges += [(V[i], V[j]) for i, j in _prune_mesh(V, mesh["triangles"], r)]
    for c, d in axes:
        edges = edges + [(_reflect(a, c, d)[0], _reflect(b, c, d)[0]) for a, b in edges]
    lines = [LineString([a, b]) for a, b in edges if np.linalg.norm(a - b) > 1e-6]
    nodes = np.unique(np.round(np.array([q for e in edges for q in e]), 6), axis=0) if edges else np.zeros((0, 2))
    return lines, nodes


MAX_GAP_DEG = 120.0        # no pocket may wrap more than this far around a feature, so every
                           # hole is held by material on at least three sides
MAX_GAP_FRAME_DEG = 180.0  # features merged into the frame band are held along that side


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


def hole_support(blob: Polygon, void, r=None, samples=144):
    """(struts, largest unsupported gap in degrees, gap centre point) around a feature.

    `blob` is the feature's keep-out band (a hole cluster counts as one blob). Walks a
    ring just outside it; every stretch of solid material (a rib, the frame, another
    feature's band) counts as one strut. Gaps are measured as a share of the ring, in
    degrees, so they also work for slots and odd-shaped clusters.
    """
    ring = blob.buffer(0.75, quad_segs=32).exterior
    pts = np.array([ring.interpolate(t, normalized=True).coords[0]
                    for t in np.linspace(0, 1, samples, endpoint=False)])
    sup = ~shapely.contains_xy(void, pts[:, 0], pts[:, 1]) if not void.is_empty else np.ones(len(pts), bool)
    if sup.all():
        return 99, 0.0, None
    if not sup.any():
        return 0, 360.0, pts[0]
    start = int(np.argmax(sup & ~np.roll(sup, 1)))  # first sample of some supported run
    sup, pts = np.roll(sup, -start), np.roll(pts, -start, axis=0)
    step = 360.0 / samples
    struts, gaps, i, n = 0, [], 0, len(sup)
    while i < n:
        j = i
        while j + 1 < n and sup[j + 1] == sup[i]:
            j += 1
        if sup[i]:
            struts += 1
        else:
            gaps.append(((j - i + 2) * step, pts[(i + j) // 2]))
        i = j + 1
    width, mid = max(gaps, key=lambda g: g[0])
    return struts, width, mid


def _max_gap(blob, region):
    # a feature merged into the frame band is held along the whole frame side
    return MAX_GAP_FRAME_DEG if _on_frame(blob, region) else MAX_GAP_DEG


def _add_strut(blob: Polygon, mid_pt, lines, nodes, frame, S):
    """A short rib from the feature into its biggest gap, out to the nearest rib or the frame."""
    c = np.array(blob.centroid.coords[0]) if blob.contains(blob.centroid) else np.array(
        blob.representative_point().coords[0])
    u = np.asarray(mid_pt) - c
    if np.linalg.norm(u) < 1e-9:
        return None
    u = u / np.linalg.norm(u)
    ray = LineString([c, c + u * (np.linalg.norm(np.asarray(mid_pt) - c) + 3 * S)])
    hit = ray.intersection(unary_union([frame.exterior] + lines))
    inner = blob.buffer(-0.5)
    pts = [np.array(xy) for g in getattr(hit, "geoms", [hit]) if not g.is_empty for xy in g.coords]
    pts = [q for q in pts if not inner.contains(Point(q))]
    if pts:
        return LineString([c, min(pts, key=lambda q: np.linalg.norm(q - c))])
    best, best_score = None, 1e9
    for q in nodes:
        v = q - c
        d = np.linalg.norm(v)
        if blob.buffer(4).contains(Point(q)) or d > 2.5 * S:
            continue
        off = math.degrees(math.acos(np.clip(v @ u / d, -1, 1)))
        if off <= 35 and off / 30 + d / S < best_score:
            best, best_score = q, off / 30 + d / S
    return None if best is None else LineString([c, best])


MAX_POCKET_INRADIUS = 0.36  # x spacing: fatter pockets get a node in the middle
MERGE_INRADIUS = 0.30       # x spacing: two mesh cells merge only while the result stays this slim
MAX_POCKET_LENGTH = 2.0     # x spacing: longer pockets get a cross rib


def _cell_corners(cell: Polygon, min_turn=35.0):
    """Convex corners of a pocket cell (where its bounding ribs meet)."""
    c = np.array(orient(cell, 1.0).exterior.coords)[:-1]
    out = []
    for i in range(len(c)):
        a, b = c[i] - c[i - 1], c[(i + 1) % len(c)] - c[i]
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        if na < 1e-9 or nb < 1e-9:
            continue
        cross = a[0] * b[1] - a[1] * b[0]
        turn = math.degrees(math.acos(np.clip(a @ b / (na * nb), -1, 1)))
        if cross > 0 and turn > min_turn:
            out.append(c[i])
    return out


def _split_cell(cell: Polygon, r: PlateRules):
    """Ribs that break an oversized pocket cell into truss-like pieces (or [] if it is fine)."""
    S, half = r.spacing, r.rib / 2
    pole = polylabel(cell, tolerance=0.5)
    p = np.array(pole.coords[0])
    inrad = cell.exterior.distance(pole)
    rect = np.array(cell.minimum_rotated_rectangle.exterior.coords)
    e1, e2 = rect[1] - rect[0], rect[2] - rect[1]
    long_e = e1 if np.linalg.norm(e1) >= np.linalg.norm(e2) else e2
    length = np.linalg.norm(long_e)
    if inrad > MAX_POCKET_INRADIUS * S:
        # node in the middle, ribs out to the cell's corners (spread around it)
        corners = sorted(_cell_corners(cell), key=lambda q: math.atan2(q[1] - p[1], q[0] - p[0]))
        if len(corners) < 3:
            ring = cell.exterior
            corners = [np.array(ring.interpolate(t, normalized=True).coords[0]) for t in (0, 1 / 3, 2 / 3)]
        picked = []
        for q in sorted(corners, key=lambda q: -np.linalg.norm(q - p)):
            ang = math.atan2(q[1] - p[1], q[0] - p[0])
            if all(abs((ang - a + math.pi) % (2 * math.pi) - math.pi) > math.radians(70) for a, _ in picked):
                picked.append((ang, q))
        lines = []
        for _, q in picked[:5]:
            u = (q - p) / max(np.linalg.norm(q - p), 1e-9)
            lines.append(LineString([p, q + u * (half + 1.0)]))  # reach into the ribs at the corner
        return lines
    if length > MAX_POCKET_LENGTH * S:
        # long, slim pocket: one rib straight across the middle
        u = long_e / length
        nrm = np.array([-u[1], u[0]])
        c = np.array(cell.centroid.coords[0]) if cell.contains(cell.centroid) else p
        span = np.linalg.norm(e1) + np.linalg.norm(e2)
        cut = LineString([c - nrm * span, c + nrm * span]).intersection(cell.buffer(half + 1.0))
        segs = [g for g in getattr(cut, "geoms", [cut]) if g.geom_type == "LineString" and not g.is_empty]
        return [max(segs, key=lambda g: g.length)] if segs else []
    return []


def pocket_outlines(profile: Polygon, r: PlateRules):
    """2D pocket polygons (sharp-cornered, to be rounded with r.tool_radius)."""
    half = r.rib / 2
    outline, _, axes = plan_features(profile)
    region = _region(outline, r)
    frame = outline.buffer(-r.offset, join_style="mitre", mitre_limit=10)
    if isinstance(frame, MultiPolygon):
        frame = max(frame.geoms, key=lambda g: g.area)
    blobs = _blobs(real_features(profile), r)
    lines, nodes = truss_edges(profile, r)
    ribs = unary_union([ln.buffer(half, quad_segs=16) for ln in lines] + blobs)
    # break up oversized pockets the triangulation left open (one half on symmetric plates)
    for _ in range(6):
        cells = region.difference(ribs)
        added = []
        for cell in getattr(cells, "geoms", [cells]):
            if not isinstance(cell, Polygon) or cell.area < r.min_pocket_area:
                continue
            ctr = np.array(cell.centroid.coords[0])
            if any((ctr - c) @ np.array([-d[1], d[0]]) < -1e-6 for c, d in axes):
                continue
            added += _split_cell(cell, r)
        if not added:
            break
        for c, d in axes:
            added = added + [LineString(_reflect(np.array(ln.coords), c, d)) for ln in added]
        lines = lines + added
        ribs = unary_union([ribs] + [ln.buffer(half, quad_segs=16) for ln in added])
    out, void = _cut_pockets(region, ribs, r)
    # make sure no feature hangs off one or two ribs: add struts into the biggest gaps
    for _ in range(6):
        added = []
        for b in blobs:
            struts, gap, mid = hole_support(b, void)
            if gap <= _max_gap(b, region):
                continue
            ln = _add_strut(b, mid, lines + added, nodes, frame, r.spacing)
            if ln is not None and ln.length > 1e-3:
                added.append(ln)
        if not added:
            break
        for c, d in axes:  # keep symmetric plates symmetric
            added = added + [LineString(_reflect(np.array(ln.coords), c, d)) for ln in added]
        lines = lines + added
        ribs = unary_union([ribs] + [ln.buffer(half, quad_segs=16) for ln in added])
        out, void = _cut_pockets(region, ribs, r)
    return out, lines, nodes


def support_report(profile: Polygon, outlines, r: PlateRules):
    """(features held well, total features) for a finished layout."""
    region = _region(Polygon(profile.exterior), r)
    void = unary_union([o.buffer(-r.tool_radius).buffer(r.tool_radius) for o in outlines]) if outlines else Polygon()
    real = real_features(profile)
    ok = 0
    for b in _blobs(real, r):
        n = sum(1 for h in real if b.contains(h.representative_point()))
        if n and hole_support(b, void)[1] <= _max_gap(b, region) + 1e-6:
            ok += n
    return ok, len(real)


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
                   and abs(np.linalg.norm(segs[j + 1][-1] - segs[j + 1][1]) - L) < 0.4 * L + 1e-6):
                t = turn(segs[j], segs[j + 1])
                if not 0.3 < abs(t) < max_turn or (t0 is not None and (t > 0) != (t0 > 0)):
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
            if not BRepCheck_Analyzer(face).IsValid():
                raise ValueError("invalid outline")
        except Exception:  # fall back to the tool-radius opening as a plain polygon
            rounded = poly.buffer(-r.tool_radius).buffer(r.tool_radius, quad_segs=8).simplify(0.01)
            if not isinstance(rounded, Polygon) or rounded.is_empty:
                continue
            face = make_face(orient(rounded, 1.0), fr, 0.5)
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
