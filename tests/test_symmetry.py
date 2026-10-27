"""Regression checks for v2's symmetry and pocket-shape rules.

    python tests/test_symmetry.py        (or: python -m pytest tests)

Symmetry means the rib grid between the holes, not mirrored holes: a hole without a
twin gets no phantom keep-out on the other side, and no pocket may bend round a rib.
"""
import sys
from pathlib import Path

import numpy as np
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from autopocket.pocketer import PlateRules, _reflect_geom  # noqa: E402
from autopocket2.features import Domain  # noqa: E402
from autopocket2.layout import SpacingField, absorb_squeezed, pocket_layout, voronoi_layout  # noqa: E402
from autopocket2.patterns import allowed_area, voronoi_lines  # noqa: E402
from autopocket2.shapes import bend_pct  # noqa: E402
from autopocket2.validate import check  # noqa: E402

R = PlateRules()


def _plate(holes, w=240.0, h=90.0):
    """A w x h plate centred on the origin with round holes [(x, y, d)]."""
    return Polygon(box(-w / 2, -h / 2, w / 2, h / 2).exterior,
                   [list(Point(x, y).buffer(d / 2, quad_segs=16).exterior.coords)[::-1] for x, y, d in holes])


# four corner holes (a hair off true mirror positions, as measured CAD often is) + one lone hole
CORNERS = [(-100, -33, 4.2), (100, -33.8, 4.2), (-100.9, 33, 4.2), (100, 33.6, 4.2)]
LONE = (60, 15, 4.2)


def test_lone_hole_is_not_mirrored():
    dom = Domain(_plate(CORNERS + [LONE]), R)
    keep = unary_union(dom.keepouts)
    assert keep.contains(Point(LONE[:2]))
    for mx, my in [(-LONE[0], LONE[1]), (LONE[0], -LONE[1]), (-LONE[0], -LONE[1])]:
        assert not keep.intersects(Point(mx, my).buffer(3)), "phantom keep-out at a mirror spot"
    assert dom.protected().area < dom.profile.area


def test_near_twins_pair_up_and_set_the_axes():
    dom = Domain(_plate(CORNERS + [LONE]), R)
    assert len(dom.axes) == 2  # 4 of the 5 holes pair up across both axes
    lone = [i for i, b in enumerate(dom.blobs) if b.contains(Point(LONE[:2]))]
    assert [dom.paired[i] for i in lone] == [False]
    assert sum(dom.paired) == 4
    # a pair 0.9 mm off still gets matching keep-outs: the joint shape is exactly symmetric
    k = unary_union(dom.grid_keepouts())
    for c, d in dom.axes:
        assert k.symmetric_difference(_reflect_geom(k, c, d)).area < 1.0


def test_axis_the_holes_ignore_is_not_used():
    # holes symmetric top/bottom but bunched to one side: the left/right axis isn't a grid axis
    holes = [(-80, -30, 4.2), (-80, 30, 4.2), (-20, -30, 4.2), (-20, 30, 4.2), (90, 0, 4.2)]
    dom = Domain(_plate(holes), R)
    assert len(dom.axes) == 1
    c, d = dom.axes[0]
    assert abs(d[1]) < 1e-6  # the horizontal line: top/bottom mirror


def test_voronoi_keeps_ribs_on_the_axes():
    dom = Domain(_plate(CORNERS), R)
    lines, _ = voronoi_lines(allowed_area(dom), dom.frame, R.spacing, dom.axes)
    for c, d in dom.axes:
        n = np.array([-d[1], d[0]])
        on = [ln for ln in lines if all(abs((np.asarray(q) - c) @ n) < 1e-6 for q in ln.coords)]
        if on:
            break
    else:
        raise AssertionError("no Voronoi rib on any symmetry axis (cells across it merge into chevrons)")


def test_no_bent_pockets():
    plate = _plate(CORNERS + [LONE])
    dom = Domain(plate, R)
    fixed = dom.fixed(R.tool_radius + 0.5)
    sfn = SpacingField(R.spacing)
    for lay in (pocket_layout(dom, R, sfn), voronoi_layout(dom, R, sfn)):
        assert lay.outlines
        assert max(bend_pct(o, fixed) for o in lay.outlines) <= 8.0
        val = check(plate, lay.outlines, R, dom)
        assert "max_pocket_bend_pct" in val["checks"] and val["checks"]["max_pocket_bend_pct"]["ok"]
        # no tiny leftover squeezed between a hole band and two ribs
        med, keep = np.median([o.area for o in lay.outlines]), unary_union(dom.keepouts)
        assert not [o for o in lay.outlines if o.area < 0.3 * med and o.distance(keep) <= R.tool_radius + 1.0]


def test_squeezed_leftovers_merge_only_as_an_option():
    plate = _plate(CORNERS + [LONE])
    dom = Domain(plate, R)
    lay = pocket_layout(dom, R, SpacingField(R.spacing))
    n_lines = len(lay.lines)
    merged = absorb_squeezed(lay)
    assert len(lay.lines) == n_lines  # the plain layout is left as it was
    if merged is not None:
        assert len(merged.lines) < n_lines and check(plate, merged.outlines, R, dom)["ok"]


def test_validator_rejects_a_chevron():
    plate = _plate([])
    dom = Domain(plate, R)
    chevron = Polygon([(-40, 25), (-10, 25), (20, 0), (-10, -25), (-40, -25), (-10, 0)])
    val = check(plate, [chevron], R, dom)
    assert "max_pocket_bend_pct" in val["failed"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
