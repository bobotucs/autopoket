"""Generate sample parts for trying the app: python samples/make_samples.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

from autopocket import cadio

OUT = Path(__file__).resolve().parent


def box(x, y, z, dx, dy, dz):
    return BRepPrimAPI_MakeBox(gp_Pnt(x, y, z), dx, dy, dz).Shape()


def cyl(x, y, z, r, h, d=(0, 0, 1)):
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y, z), gp_Dir(*d)), r, h).Shape()


def cut(a, *tools):
    for t in tools:
        a = BRepAlgoAPI_Cut(a, t).Shape()
    return a


def fuse(a, *others):
    for o in others:
        a = BRepAlgoAPI_Fuse(a, o).Shape()
    return a


def plate():
    """300 x 100 x 6 mm robot-style plate with bolt holes and a bearing bore."""
    p = box(0, 0, 0, 300, 100, 6)
    holes = [cyl(x, y, -1, 2.6, 8) for x in (10, 290) for y in (10, 50, 90)]
    holes.append(cyl(150, 50, -1, 14, 8))
    return cut(p, *holes)


def bracket():
    """L-bracket: 120 x 60 base (10 thick) with a 120 x 80 upright (8 thick)."""
    base = box(0, 0, 0, 120, 60, 10)
    upright = box(0, 0, 0, 120, 8, 80)
    b = fuse(base, upright)
    holes = [cyl(x, 40, -1, 3.3, 12) for x in (20, 100)]
    holes += [cyl(x, -1, 65, 3.3, 10, (0, 1, 0)) for x in (20, 100)]
    return cut(b, *holes)


def block():
    """Solid 80 x 80 x 40 mounting block with a through bore (good for blind pockets)."""
    return cut(box(0, 0, 0, 80, 80, 40), cyl(40, 40, -1, 10, 42))


if __name__ == "__main__":
    for name, shape in [("plate", plate()), ("bracket", bracket()), ("block", block())]:
        cadio.save_step(shape, OUT / f"{name}.step")
        print("wrote", name + ".step")
    cadio.save_3mf(plate(), OUT / "plate.3mf")
    print("wrote plate.3mf")
