"""Generate FTC-style 1/8 in sample plates: python samples/make_samples.py"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

from autopocket import cadio

OUT = Path(__file__).resolve().parent
T = 3.175  # 1/8 in


def cyl(x, y, r, h=T + 2, z=-1):
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y, z), gp_Dir(0, 0, 1)), r, h).Shape()


def cut(a, *tools):
    for t in tools:
        a = BRepAlgoAPI_Cut(a, t).Shape()
    return a


def side_plate():
    """14 x 5 in drivetrain side plate with bearing holes and M4 mounting holes."""
    w, h = 14 * 25.4, 5 * 25.4
    p = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), w, h, T).Shape()
    holes = [cyl(x, y, 2.0) for x in (12, w / 2, w - 12) for y in (12, h - 12)]
    holes += [cyl(x, h / 2, 14.0) for x in (40, w - 40)]  # bearing bores
    return cut(p, *holes)


def round_plate():
    """6 in diameter round plate with a bolt circle."""
    import math
    r = 3 * 25.4
    p = cyl(0, 0, r, T, 0)
    holes = [cyl(0, 0, 8.0)]
    holes += [cyl(60 * math.cos(a), 60 * math.sin(a), 2.0) for a in [k * math.pi / 3 for k in range(6)]]
    return cut(p, *holes)


if __name__ == "__main__":
    cadio.save_step(side_plate(), OUT / "side_plate.step")
    cadio.save_3mf(side_plate(), OUT / "side_plate.3mf")
    cadio.save_step(round_plate(), OUT / "round_plate.step")
    for name in ["example", "example1", "example2"]:
        src = OUT.parent / "examples" / f"blank_{name}.step"
        if src.exists():
            shutil.copy(src, OUT / f"blank_{name}.step")
    print("samples written")
