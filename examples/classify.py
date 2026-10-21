"""Split the openings of a pocketed plate into pockets vs. real features (holes, bearings, slots)."""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from shapely.geometry import Point, Polygon
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepTools import BRepTools
from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Line
from OCP.TopAbs import TopAbs_EDGE, TopAbs_WIRE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

from autopocket import cadio, pocketer as P

TOOL_R = 2.0


def wire_signatures(plate):
    """For each inner wire of the plate face: (2D centroid, list of ('line'|('arc', r)))."""
    face = cadio.faces(plate.solid)[plate.frame.index]
    outer = BRepTools.OuterWire_s(face)
    sigs = []
    wexp = TopExp_Explorer(face, TopAbs_WIRE)
    while wexp.More():
        w = TopoDS.Wire(wexp.Current())
        wexp.Next()
        if w.IsSame(outer):
            continue
        kinds, pts = [], []
        eexp = TopExp_Explorer(w, TopAbs_EDGE)
        while eexp.More():
            c = BRepAdaptor_Curve(TopoDS.Edge(eexp.Current()))
            eexp.Next()
            t = c.GetType()
            if t == GeomAbs_Circle:
                kinds.append(("arc", round(c.Circle().Radius(), 2)))
            elif t == GeomAbs_Line:
                kinds.append("line")
            else:
                kinds.append("other")
            for u in np.linspace(c.FirstParameter(), c.LastParameter(), 5):
                p = c.Value(u)
                pts.append([p.X(), p.Y(), p.Z()])
        pts = np.array(pts)
        fr = plate.frame
        uv = np.c_[(pts - fr.origin) @ fr.x, (pts - fr.origin) @ fr.y]
        sigs.append((uv.mean(axis=0), kinds))
    return sigs


def classify(kinds):
    arcs = [k[1] for k in kinds if isinstance(k, tuple)]
    lines = kinds.count("line")
    if lines == 0 and len(set(arcs)) == 1:
        return "hole"
    if lines == 2 and len(arcs) == 2 and arcs[0] == arcs[1]:
        return "slot"
    if sum(r <= 4.05 for r in arcs) >= 2:  # R2 (or R4) cutter corners
        return "pocket"
    return "feature"


def split(path):
    plate = P.find_plate(cadio.solids(cadio.load_any(path))[0])
    sigs = wire_signatures(plate)
    keep, pockets, kinds_out = [], [], Counter()
    for ring in plate.profile.interiors:
        poly = Polygon(ring)
        c = np.array(poly.representative_point().coords[0])
        # match ring to wire by nearest centroid that lies inside the ring
        best = min(sigs, key=lambda s: np.linalg.norm(s[0] - np.array(poly.centroid.coords[0])))
        k = classify(best[1])
        kinds_out[k] += 1
        (pockets if k == "pocket" else keep).append((ring, k))
    return plate, keep, pockets, kinds_out


if __name__ == "__main__":
    for f in sys.argv[1:]:
        plate, keep, pockets, kinds = split(f)
        print(f, dict(kinds))
