"""v2 truss layout: v1's constrained triangulation, steered by where the plate works.

What changes from v1 (autopocket/pocketer.py, which v2 reuses but never modifies):

  * **Load-guided spacing.** The blank plate's strain-energy field (fea2) sets a local
    truss spacing: tighter triangles where the plate carries load, bigger pockets where
    it barely does. v1 uses one spacing everywhere. The field is mirrored onto itself on
    symmetric plates, so v1's half-and-mirror layout still works.
  * **Rib pruning (evolutionary structural optimisation).** After a layout is analysed,
    the interior ribs that store the least strain energy are removed a few at a time,
    each removal checked against the pocket-shape and hole-support rules.
  * **Symmetric grid, blunt-tipped pockets** (shapes.py): the rib grid is mirrored whenever
    the outline allows; a hole without a mirror twin only reshapes the pockets next to it
    (no phantom keep-out on the other side). No pocket corner sharper than 45 deg.
  * **Isogrid family** (CheeseIt-style regular triangle grid) as another layout to try, plus
    **hexagon** and **Voronoi** webs (patterns.py).
  * **Per-feature clearances** (features.py): every hole, outline side and corner can keep
    its own amount of material; rib width and tool radius are settable too.

The rib graph (centre lines) stays the authoritative design; pockets are derived from it.
"""
from __future__ import annotations

import math

import numpy as np
import shapely
import triangle
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import polylabel, unary_union

from autopocket.pocketer import (
    MAX_POCKET_LENGTH,
    MERGE_INRADIUS,
    PlateRules,
    _add_strut,
    _half_plane,
    _max_gap,
    _on_frame,
    _reflect,
    _split_cell,
    hole_support,
)

from .features import Domain
from .patterns import allowed_area, hex_lines, voronoi_lines
from .shapes import MAX_BEND_PCT, bend_pct, bend_split, cut_pockets, grid_frame, isogrid_lines, parts
from .validate import check

GUIDE_BETA = 0.15           # spacing ~ energy^-beta; 0 = v1's uniform spacing
GUIDE_BETAS = (0.0, GUIDE_BETA)  # the planner tries both: neither wins on every plate
SCALE_MIN, SCALE_MAX = 0.7, 1.5
ESO_FRACTION = 0.12         # share of removable ribs taken out per pruning step
ESO_MAX_INRADIUS = 0.5      # x local spacing: a merged pocket may not get fatter than this
ESO_MAX_LENGTH = 2.5        # x local spacing
SQUEEZED = 0.3              # x median pocket area: smaller pockets pressed against a hole band are
                            # leftovers between the hole and two ribs, merged into a neighbour or left solid


# --------------------------------------------------------------------------- spacing field

class SpacingField:
    """Local truss spacing (mm) over the plate, from a relative energy field."""

    def __init__(self, S, field=None, axes=(), region=None, beta=GUIDE_BETA):
        self.S, self.beta, self.axes, self.field = S, beta, list(axes), field
        self.norm = 1.0
        if field is not None and beta > 0 and region is not None and not region.is_empty:
            x0, y0, x1, y1 = region.bounds
            xs, ys = np.meshgrid(np.linspace(x0, x1, 40), np.linspace(y0, y1, 40))
            pts = np.c_[xs.ravel(), ys.ravel()]
            pts = pts[shapely.contains_xy(region, pts[:, 0], pts[:, 1])]
            if len(pts):
                self.norm = float(np.median(self._raw(pts))) or 1.0

    def _raw(self, pts):
        pts = np.atleast_2d(pts)
        imgs = [pts]
        for c, d in self.axes:  # average over the mirror images: symmetric field, symmetric layout
            imgs = imgs + [_reflect(p, c, d) for p in imgs]
        return np.mean([self.field(p) for p in imgs], axis=0)

    def __call__(self, pts):
        pts = np.atleast_2d(np.asarray(pts, float))
        if self.field is None or self.beta <= 0:
            return np.full(len(pts), float(self.S))
        rel = np.maximum(self._raw(pts) / self.norm, 1e-6)
        return self.S * np.clip(rel ** -self.beta, SCALE_MIN, SCALE_MAX)

    def at(self, p):
        return float(self(np.asarray(p, float))[0])


# --------------------------------------------------------------------------- triangulation

def _resample_ring(coords, sfn, factor, min_pts=3, corner_turn=25.0):
    """Points along a closed ring: every real corner, and between corners points spaced by
    `factor` x the local truss spacing (placed by integrating 1/spacing along the ring)."""
    c = np.array(coords)[:-1] if np.allclose(coords[0], coords[-1]) else np.array(coords)
    n = len(c)
    turn = np.zeros(n)
    for i in range(n):
        a, b = c[i] - c[i - 1], c[(i + 1) % n] - c[i]
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        if na > 1e-9 and nb > 1e-9:
            turn[i] = math.degrees(math.acos(np.clip(a @ b / (na * nb), -1, 1)))
    line = LineString(np.vstack([c, c[:1]]))
    L = line.length
    corners = [line.project(Point(c[i])) for i in range(n) if turn[i] > corner_turn]
    m = max(8, int(L))  # ~1 mm samples for the spacing integral
    t = np.linspace(0, L, m + 1)
    pts = np.array([line.interpolate(x).coords[0] for x in t[:-1]])
    w = 1.0 / (factor * sfn(pts))
    cum = np.concatenate([[0], np.cumsum(w) * (L / m)])  # cum[k] ~ integral up to t[k]

    def at(d):
        return np.array(line.interpolate(d % L).coords[0])

    def place(d0, d1):
        """Points strictly between arc positions d0 < d1, evenly in the 1/spacing measure."""
        u0, u1 = np.interp(d0, t, cum), np.interp(d1, t, cum)
        if d1 > L:
            u1 = cum[-1] + np.interp(d1 - L, t, cum)
        k = max(1, math.ceil(u1 - u0 - 0.25))
        out = []
        for j in range(1, k):
            u = u0 + (u1 - u0) * j / k
            d = np.interp(u, cum, t) if u <= cum[-1] else L + np.interp(u - cum[-1], cum, t)
            out.append(at(d))
        return out

    if not corners:
        out = [at(0.0)] + place(0.0, L)
    else:
        corners = sorted(corners)
        out = []
        for j, d0 in enumerate(corners):
            d1 = corners[j + 1] if j + 1 < len(corners) else corners[0] + L
            out.append(at(d0))
            out += place(d0, d1)
    if len(out) < min_pts:
        out = [at(L * j / min_pts) for j in range(min_pts)]
    return out


def _tri_area(s):
    return math.sqrt(3) / 4 * s * s * 2.0  # same cap as v1: typical triangles come out ~half of it


def _triangulate(poly, extra_pts, sfn, S):
    verts, segs, holes = [], [], []
    for k, ring in enumerate([poly.exterior, *poly.interiors]):
        pts = _resample_ring(list(ring.coords), sfn, 1.0 if k == 0 else 0.8, min_pts=3 if k == 0 else 4)
        base = len(verts)
        verts += pts
        segs += [(base + i, base + (i + 1) % len(pts)) for i in range(len(pts))]
        if k:
            holes.append(np.array(Polygon(ring).representative_point().coords[0]))
    verts += [p for p in extra_pts if poly.contains(Point(p)) and poly.boundary.distance(Point(p)) > 0.3 * sfn.at(p)]
    data = {"vertices": np.array(verts, float), "segments": np.array(segs, int)}
    if holes:
        data["holes"] = np.array(holes)
    mesh = triangle.triangulate(data, f"pq20a{_tri_area(S * SCALE_MAX):.3f}")
    for _ in range(3):  # refine where the local spacing asks for smaller triangles
        V, T = mesh["vertices"], mesh["triangles"]
        want = np.array([_tri_area(s) for s in sfn(V[T].mean(axis=1))])
        a, b = V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]]
        area = 0.5 * np.abs(a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0])
        if (area <= want * 1.05).all():
            break
        mesh = dict(mesh, triangle_max_area=want)
        mesh = triangle.triangulate(mesh, "rpq20a")
    return mesh["vertices"], mesh["triangles"]


def _prune_mesh(V, T, r: PlateRules, sfn):
    """v1's cell merging, with every threshold taken from the local spacing."""
    half = r.rib / 2
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
        pole = polylabel(g, tolerance=0.5)
        S = sfn(np.array(pole.coords[0]))[0]
        rect = np.array(g.minimum_rotated_rectangle.exterior.coords)
        if max(np.linalg.norm(rect[1] - rect[0]), np.linalg.norm(rect[2] - rect[1])) > MAX_POCKET_LENGTH * S + 2 * half:
            return False
        return g.exterior.distance(pole) <= MERGE_INRADIUS * S + half

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


def truss_edges(dom: Domain, r: PlateRules, sfn: SpacingField):
    """Rib centre lines and truss nodes (v1's method with a spatially varying spacing)."""
    S, half = r.spacing, r.rib / 2
    outline, axes, frame, region = dom.core, dom.axes, dom.frame, dom.region
    if frame.is_empty:
        return [], np.zeros((0, 2))

    big, points = [], []
    for b, sb, paired in zip(dom.blobs, dom.sym_blobs, dom.paired):
        rect = np.array(b.minimum_rotated_rectangle.exterior.coords)
        size = max(np.linalg.norm(rect[1] - rect[0]), np.linalg.norm(rect[2] - rect[1]))
        ctr = b.centroid if b.contains(b.centroid) else b.representative_point()
        if paired and size > 0.9 * sfn.at(ctr.coords[0]):
            core = sb.buffer(-half)  # the band's rib centre line becomes a mesh boundary
            if not core.is_empty:
                big.append(core)
        elif not _on_frame(b, region):
            # a truss node; a hole without a twin gets a plain rib junction at its mirror spot,
            # so the grid stays symmetric but nothing is kept out there
            p = np.array(ctr.coords[0])
            for c, d in axes:
                if (p - c) @ np.array([-d[1], d[0]]) < -1e-6:
                    p = _reflect(p, c, d)[0]
            points.append(p)
    merged = []
    for p in points:
        for k, (q, n) in enumerate(merged):
            if np.linalg.norm(p - q / n) < 0.4 * sfn.at(p):
                merged[k] = (q + p, n + 1)
                break
        else:
            merged.append((p.copy(), 1))
    points = [q / n for q, n in merged]
    domain = frame.difference(unary_union(big)) if big else frame
    extent = 4 * max(outline.bounds[2] - outline.bounds[0], outline.bounds[3] - outline.bounds[1])
    for c, d in axes:
        domain = domain.intersection(_half_plane(c, d, extent))
    edges = []
    for poly in getattr(domain, "geoms", [domain]):
        if not isinstance(poly, Polygon) or poly.area < 1.0:
            continue
        try:
            V, T = _triangulate(poly, points, sfn, S)
        except Exception:
            continue
        edges += [(V[i], V[j]) for i, j in _prune_mesh(V, T, r, sfn)]
    for c, d in axes:
        edges = edges + [(_reflect(a, c, d)[0], _reflect(b, c, d)[0]) for a, b in edges]
    lines = [LineString([a, b]) for a, b in edges if np.linalg.norm(a - b) > 1e-6]
    nodes = np.unique(np.round(np.array([q for e in edges for q in e]), 6), axis=0) if edges else np.zeros((0, 2))
    return lines, nodes


# --------------------------------------------------------------------------- pockets

class Layout:
    """A rib graph and the pockets derived from it."""

    def __init__(self, dom: Domain, r, lines, nodes, sfn):
        self.dom, self.r, self.lines, self.nodes, self.sfn = dom, r, list(lines), nodes, sfn
        self.profile, self.axes, self.region, self.frame = dom.profile, dom.axes, dom.region, dom.frame
        self.blobs = dom.blobs        # hole bands: must be held
        self.keepouts = dom.keepouts  # the same bands: no pockets here (holes are not mirrored)
        self.rebuild()

    def ribs(self, lines=None):
        half = self.r.rib / 2
        return unary_union([ln.buffer(half, quad_segs=16) for ln in (self.lines if lines is None else lines)]
                           + self.keepouts)

    def rebuild(self):
        out, void = cut_pockets(self.region, self.ribs(), self.r)
        self.squeezed = _squeezed(self, out)
        if self.squeezed:  # left solid; absorb_squeezed may take out a rib to merge them instead
            out = [o for o in out if not any(o is q for q in self.squeezed)]
            rt = self.r.tool_radius
            rounded = [o.buffer(-rt, quad_segs=16).buffer(rt, quad_segs=16) for o in out]
            void = unary_union(rounded) if rounded else Polygon()
        self.outlines, self.void = out, void

    def mirrored(self, added, axes=None):
        for c, d in (self.axes if axes is None else axes):
            added = added + [LineString(_reflect(np.array(ln.coords), c, d)) for ln in added]
        return added

    def canonical(self, p, axes=None):
        return all((np.asarray(p) - c) @ np.array([-d[1], d[0]]) >= -1e-6
                   for c, d in (self.axes if axes is None else axes))


def _squeezed(lay: Layout, outlines):
    """Pockets much smaller than the layout's median that sit against a hole band: the odd
    leftovers between a hole and two ribs (small cells along the outline are fine)."""
    if len(outlines) < 3 or not lay.keepouts:
        return []
    med = float(np.median([o.area for o in outlines]))
    keep = unary_union(lay.keepouts)
    reach = lay.r.tool_radius + 1.0
    return [o for o in outlines if o.area < SQUEEZED * med and o.distance(keep) <= reach]


def absorb_squeezed(lay: Layout) -> Layout | None:
    """A copy of `lay` with the rib between each squeezed leftover and a neighbour taken out, so
    the two become one proper pocket, wherever that keeps every rule (None if none can go).

    The planner analyses this as a separate design, like a rib-pruning step: the rib it takes
    out may be one that carries load, and then the version with the leftover solid wins."""
    reach = lay.r.rib / 2 + lay.r.tool_radius + 1.0
    tried, start = set(), lay
    for _ in range(4):
        if not lay.squeezed:
            break
        base, best = sum(o.area for o in lay.outlines), None
        for q in lay.squeezed:
            for j, ln in enumerate(lay.lines):
                key = _line_key(ln)
                if key in tried or ln.distance(q) > reach:
                    continue
                tried.add(key)
                gone = {_line_key(m) for m in lay.mirrored([ln])}
                t = Layout.__new__(Layout)
                t.__dict__.update(lay.__dict__)
                t.lines = [x for x in lay.lines if _line_key(x) not in gone]
                t.rebuild()
                gain = sum(o.area for o in t.outlines) - base
                if gain <= 0 or (best is not None and gain <= best[0]):
                    continue
                if not any(o.contains(q.representative_point()) for o in t.outlines):
                    continue  # the leftover has to become part of a real pocket
                if unsupported(t) or not check(t.profile, t.outlines, t.r, t.dom)["ok"]:
                    continue
                best = (gain, t)
        if best is None:
            break
        lay = best[1]
    return None if lay is start else lay


def pocket_layout(dom: Domain, r: PlateRules, sfn: SpacingField) -> Layout:
    """v1's pocket_outlines (split oversized cells, strut unsupported holes) on a guided truss."""
    lines, nodes = truss_edges(dom, r, sfn)
    lay = Layout(dom, r, lines, nodes, sfn)
    ribs = lay.ribs()
    fixed = dom.fixed(r.tool_radius + 0.5)
    for _ in range(6):
        cells = [c for c in parts(lay.region.difference(ribs)) if c.area >= r.min_pocket_area]
        tree = shapely.STRtree(cells)
        added = []
        for cell in cells:
            # a cell is split once and mirrored across the axes it has a twin across; one
            # reshaped by a lone hole is split on its own
            ax = dom.twin_axes(cell, cells, 0.5, tree)
            if not lay.canonical(np.array(cell.centroid.coords[0]), ax):
                continue
            local = PlateRules(**{**r.to_dict(), "spacing": sfn.at(polylabel(cell, 0.5).coords[0])})
            bend = bend_split(cell, fixed, 2 * local.spacing, r.rib)  # a bent cell is cut at its bend first
            added += lay.mirrored([bend] if bend is not None else _split_cell(cell, local), ax)
        if not added:
            break
        lay.lines += added
        ribs = unary_union([ribs] + [ln.buffer(r.rib / 2, quad_segs=16) for ln in added])
    lay.rebuild()
    _support_holes(lay)
    return lay


def _support_holes(lay: Layout):
    """Struts into any feature that a pocket wraps more than v1's limit around."""
    for k in range(6):
        added = []  # a strut is mirrored onto the hole's twins (none for a lone hole)
        for b, ax in zip(lay.blobs, lay.dom.twins):
            if k == 0 and not lay.canonical(b.centroid.coords[0], ax):
                continue  # its twin's strut is mirrored onto it; it gets its own later if still needed
            struts, gap, mid = hole_support(b, lay.void)
            if gap <= _max_gap(b, lay.region):
                continue
            ln = _add_strut(b, mid, lay.lines + added, lay.nodes, lay.frame, lay.sfn.at(b.centroid.coords[0]))
            if ln is not None and ln.length > 1e-3:
                added += lay.mirrored([ln], ax)
        if not added:
            if k == 0:
                continue  # the holes skipped above still get their turn
            return
        lay.lines += added
        lay.rebuild()


def unsupported(lay: Layout):
    return [b for b in lay.blobs if hole_support(b, lay.void)[1] > _max_gap(b, lay.region) + 1e-6]


# --------------------------------------------------------------------------- rib pruning (ESO)

def _line_key(ln: LineString):
    """Direction-independent key of a straight rib, to find mirror twins without an O(n^2) scan."""
    a, b = (tuple(np.round(q, 2)) for q in np.array(ln.coords)[[0, -1]])
    return min(a, b), max(a, b)


def prune_ribs(lay: Layout, energy, fraction=None) -> Layout | None:
    """A copy of `lay` with its least-loaded interior ribs removed, or None if none can go.

    `energy(points)` is the relative strain energy density of the analysed layout. Ribs on
    the frame line or around big features are never touched; at most one rib is taken out
    of any pocket per step, and the merged pocket must stay compact.
    """
    fraction = ESO_FRACTION if fraction is None else fraction
    r, half = lay.r, lay.r.rib / 2
    blob_u = unary_union(lay.keepouts) if lay.keepouts else Polygon()
    inside = lay.region.buffer(-0.5)
    by_key = {}
    for j, ln in enumerate(lay.lines):
        by_key.setdefault(_line_key(ln), set()).add(j)
    groups, seen = [], set()
    for i, ln in enumerate(lay.lines):
        if i in seen or ln.length < r.rib:
            continue
        mid = np.array(ln.interpolate(0.5, normalized=True).coords[0])
        if not lay.canonical(mid) or not inside.contains(Point(mid)) or blob_u.contains(Point(mid)):
            continue
        imgs = lay.mirrored([ln])
        idx = {i} | {j for m in imgs for j in by_key.get(_line_key(m), ())}
        seen |= idx
        ts = np.linspace(0.0, 1.0, 9)
        pts = np.array([ln.interpolate(t, normalized=True).coords[0] for t in ts])
        keep = [k for k, p in enumerate(pts) if min(np.linalg.norm(p - pts[0]), np.linalg.norm(p - pts[-1])) > r.rib]
        if not keep:
            continue
        groups.append((float(np.mean(energy(pts[keep]))), sorted(idx), mid))
    if not groups:
        return None
    groups.sort(key=lambda g: g[0])
    cells = lay.region.difference(lay.ribs())
    cells = [c for c in getattr(cells, "geoms", [cells]) if isinstance(c, Polygon) and not c.is_empty]
    tree = shapely.STRtree(cells)
    used, drop, quota = set(), [], max(1, round(fraction * len(groups)))
    free = lay.region.difference(blob_u)
    fixed = lay.dom.fixed(r.tool_radius + 0.5)

    def compact(piece):
        if piece.area < 0.75 * piece.convex_hull.area or bend_pct(piece, fixed) > MAX_BEND_PCT:
            return False
        pole = polylabel(piece, tolerance=0.5)
        S = lay.sfn.at(pole.coords[0])
        rect = np.array(piece.minimum_rotated_rectangle.exterior.coords)
        if max(np.linalg.norm(rect[1] - rect[0]), np.linalg.norm(rect[2] - rect[1])) > ESO_MAX_LENGTH * S + 2 * half:
            return False
        return piece.exterior.distance(pole) <= ESO_MAX_INRADIUS * S + half

    for score, idx, mid in groups:
        if len(drop) >= quota:
            break
        # the mirror images can sit beside a lone hole and merge different cells: check them all
        touch, bridges = set(), []
        for j in idx:
            ln = lay.lines[j]
            m = Point(ln.interpolate(0.5, normalized=True).coords[0])
            near = {int(k) for k in tree.query(m.buffer(half + 1.0), predicate="intersects")}
            if near:
                touch |= near
                bridges.append(ln.buffer(half).intersection(free))
        if not touch or used.intersection(touch):
            continue
        merged = unary_union([cells[k] for k in touch] + bridges).buffer(0.01).buffer(-0.01)
        if not all(compact(p) for p in parts(merged)):
            continue
        used.update(touch)
        drop.append(idx)
    if not drop:
        return None
    new = Layout.__new__(Layout)
    new.__dict__.update(lay.__dict__)
    gone = {j for idx in drop for j in idx}
    new.lines = [ln for j, ln in enumerate(lay.lines) if j not in gone]
    new.rebuild()
    # put back any removed rib whose loss leaves a feature hanging
    for _ in range(3):
        bad = unsupported(new)
        if not bad:
            break
        zone = unary_union([b.buffer(r.rib + 1.0) for b in bad])
        back = [lay.lines[j] for j in gone if lay.lines[j].intersects(zone)]
        if not back:
            break
        new.lines += back
        gone -= {j for j in gone if lay.lines[j].intersects(zone)}
        new.rebuild()
    if not gone or unsupported(new):
        return None
    return new


def isogrid_layout(dom: Domain, r: PlateRules, sfn: SpacingField, turn=False) -> Layout:
    """CheeseIt-style regular triangle grid of side r.spacing, symmetric about the plate's axes."""
    centre, ang = grid_frame(dom.core, dom.axes)
    lines, nodes = isogrid_lines(dom.frame, r.spacing, centre, ang + (math.pi / 2 if turn else 0.0))
    lay = Layout(dom, r, lines, nodes, sfn)
    _support_holes(lay)
    return lay


def hex_layout(dom: Domain, r: PlateRules, sfn: SpacingField, turn=False) -> Layout:
    """CheeseIt-style honeycomb, cells r.spacing apart, symmetric about the plate's axes."""
    centre, ang = grid_frame(dom.core, dom.axes)
    lines, nodes = hex_lines(dom.frame, r.spacing, centre, ang + (math.pi / 2 if turn else 0.0))
    lay = Layout(dom, r, lines, nodes, sfn)
    _support_holes(lay)
    return lay


def voronoi_layout(dom: Domain, r: PlateRules, sfn: SpacingField) -> Layout:
    """Lloyd-relaxed Voronoi web, seeds ~r.spacing apart (closer where loaded if sfn is guided)."""
    guided = sfn if getattr(sfn, "beta", 0) > 0 and sfn.field is not None else None
    lines, nodes = voronoi_lines(allowed_area(dom), dom.frame, r.spacing, dom.axes, guided)
    lay = Layout(dom, r, lines, nodes, sfn)
    _support_holes(lay)
    return lay
