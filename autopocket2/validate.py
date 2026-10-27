"""Hard-constraint checks on a finished 2D pocket layout (works on v1 and v2 output alike).

Every rule is measured on the final geometry, not assumed from how it was built, and a
layout that breaks any of them is rejected, never traded against weight saved:

  * pockets keep each hole, outline side and corner's own clearance (default
    `offset + rib/2` = 8 mm; set per feature in features.Clearances);
  * the web between two pockets is at least one rib (8 mm);
  * every inside corner is at least the tool radius, and the tool fits every pocket;
  * pockets are at least 8 mm wide (tool diameter + 2 mm for big tools) and `min_pocket_area` big;
  * what is left of the plate is one connected piece;
  * every hole is held on several sides (no pocket wraps more than 120 deg around it);
  * no pocket corner is sharper than 45 deg (no thin wedge tips, see shapes.py);
  * no pocket bends round a rib: rib inside a pocket's convex hull <= 8 % of the pocket
    (a chevron is ~25 %; wrapping round a hole band or edge clearance doesn't count);
  * when every hole has its mirror twin across the grid's axes, the pockets are symmetric
    too (< 2 % of pocket area off). A hole without a twin reshapes the pockets beside it,
    so then the mismatch is only reported.
"""
from __future__ import annotations

import numpy as np
import shapely
from shapely.geometry import Polygon
from shapely.ops import polylabel, unary_union

from autopocket.pocketer import PlateRules, _max_gap, _reflect_geom, hole_support

from .features import Domain
from .shapes import MAX_BEND_PCT, bend_pct, min_half_width, tip_depth_limit, tips

TOL = 0.05  # mm


def rounded(outlines, r: PlateRules):
    return [o.buffer(-r.tool_radius, quad_segs=16).buffer(r.tool_radius, quad_segs=16) for o in outlines]


def support(dom: Domain, void):
    """(holes held on several sides, total holes)."""
    ok = 0
    for b in dom.blobs:
        n = sum(1 for h in dom.holes if b.contains(h.representative_point()))
        if n and hole_support(b, void)[1] <= _max_gap(b, dom.region) + 1e-6:
            ok += n
    return ok, len(dom.holes)


def check(profile: Polygon, outlines, r: PlateRules, dom: Domain | None = None):
    """{'ok': bool, 'checks': {name: {'value', 'limit', 'ok'}}, 'failed': [names]}.

    `dom` carries the per-feature clearances; without it every feature gets v1's uniform one."""
    dom = dom or Domain(profile, r)
    pockets = [p for p in rounded(outlines, r) if not p.is_empty]
    U = unary_union(pockets) if pockets else Polygon()
    checks = {}

    def add(name, value, limit, ok):
        checks[name] = {"value": None if value is None else round(float(value), 3), "limit": limit, "ok": bool(ok)}

    if pockets:
        need = [(U.distance(h), dom.clear.hole(i)) for i, h in enumerate(dom.holes)]
        need += [(U.distance(sd), dom.clear.side(k)) for k, sd in enumerate(dom.sides)]
        need += [(U.distance(shapely.Point(*dom.corners[k])), R) for k, R in dom.clear.corners.items()
                 if 0 <= k < len(dom.corners)]
        margin = min(d - c for d, c in need)
        add("clearance_margin_mm", margin, 0.0, margin >= -TOL)
        add("closest_edge_or_hole_mm", min(d for d, _ in need), None, True)
        tree = shapely.STRtree(pockets)
        web = np.inf
        for i, p in enumerate(pockets):
            for j in tree.query(p.buffer(r.rib + 1.0)):
                if j > i:
                    web = min(web, p.distance(pockets[j]))
        add("min_web_between_pockets_mm", web if np.isfinite(web) else None, r.rib,
            not np.isfinite(web) or web >= r.rib - TOL)
        R = min_half_width(r)
        width = min(2 * p.exterior.distance(polylabel(p, 0.05)) for p in pockets)
        add("min_pocket_width_mm", width, 2 * R, width >= 2 * R - 2 * TOL)
        # opening by (radius - tol) must not change any pocket: no corner tighter than the tool
        rt = r.tool_radius - TOL
        lost = max(p.area - p.buffer(-rt).buffer(rt, quad_segs=16).area for p in pockets)
        add("tool_radius_area_lost_mm2", lost, 0.5, lost <= 0.5)
        small = min(p.area for p in pockets)
        add("min_pocket_area_mm2", small, r.min_pocket_area, small >= r.min_pocket_area - 1.0)
        lim = tip_depth_limit(R, r.tool_radius) + 0.3
        tip = max((d for p in pockets for d, _ in tips(p, R)), default=0.0)
        add("sharpest_tip_depth_mm", tip, round(lim, 2), tip <= lim)
        fixed = dom.fixed(r.tool_radius + 0.5)
        bend = max(bend_pct(p, fixed) for p in pockets)
        add("max_pocket_bend_pct", bend, MAX_BEND_PCT, bend <= MAX_BEND_PCT)
        axes = dom.axes
        if axes:  # pockets mirror onto themselves across the grid's axes
            u = unary_union(pockets)
            m = u
            for c, d in axes:
                m = m.intersection(_reflect_geom(m, c, d))
            mismatch = 100 * (u.area - m.area) / max(u.area, 1e-9)
            if all(dom.paired):
                add("pocket_symmetry_mismatch_pct", mismatch, 2.0, mismatch <= 2.0)
            else:  # lone holes: the grid is symmetric, the pockets beside those holes aren't
                add("pocket_symmetry_mismatch_pct", mismatch, None, True)
        rest = profile.difference(U)
        parts = len(getattr(rest, "geoms", [rest]))
        add("residual_pieces", parts, 1, parts == 1)
    ok_n, all_n = support(dom, U)
    add("holes_supported", ok_n, all_n, ok_n == all_n)
    failed = [k for k, v in checks.items() if not v["ok"]]
    return {"ok": not failed, "checks": checks, "failed": failed}
