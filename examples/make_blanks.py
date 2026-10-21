"""Turn the pocketed example plates back into blanks (outline + round holes only)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from shapely.geometry import Polygon
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.gp import gp_Vec

from autopocket import cadio, pocketer as P

HERE = Path(__file__).resolve().parent
for name in ["example", "example1", "example2"]:
    plate = P.find_plate(cadio.solids(cadio.load_any(HERE / f"{name}.step"))[0])
    prof = plate.profile
    holes = []
    for ring in prof.interiors:
        pts = np.array(ring.coords)
        d = np.linalg.norm(pts - np.array(Polygon(ring).centroid.coords[0]), axis=1)
        if d.std() < 0.02 * d.mean():  # round hole: keep; anything else is a pocket
            holes.append(ring)
    blank = Polygon(prof.exterior, holes)
    face = P.make_face(blank, plate.frame)
    solid = BRepPrimAPI_MakePrism(face, gp_Vec(*(-plate.frame.n * plate.thickness))).Shape()
    cadio.save_step(solid, HERE / f"blank_{name}.step")
    print(name, "holes", len(holes), "thickness", round(plate.thickness, 3))
