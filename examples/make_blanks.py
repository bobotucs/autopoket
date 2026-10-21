"""Turn the hand-pocketed reference plates back into blanks (outline + real features only)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from shapely.geometry import Polygon
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.gp import gp_Vec

import classify
from autopocket import cadio, pocketer as P

HERE = Path(__file__).resolve().parent
for name in ["example", "example1", "example2", "ref_kiwi", "ref_top", "ref_supes"]:
    plate, keep, pockets, kinds = classify.split(HERE / f"{name}.step")
    blank = Polygon(plate.profile.exterior, [ring for ring, _ in keep])
    face = P.make_face(blank, plate.frame)
    solid = BRepPrimAPI_MakePrism(face, gp_Vec(*(-plate.frame.n * plate.thickness))).Shape()
    cadio.save_step(solid, HERE / f"blank_{name}.step")
    print(name, dict(kinds), "-> blank with", len(keep), "features")
