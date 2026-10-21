"""Reading and writing STEP / 3MF / STL, plus tessellation helpers."""
from __future__ import annotations

import struct
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from OCP.BRep import BRep_Builder, BRep_Tool
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge,
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakeVertex,
    BRepBuilderAPI_MakeWire,
)
from OCP.BRepGProp import BRepGProp
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.GProp import GProp_GProps
from OCP.IFSelect import IFSelect_RetDone
from OCP.Interface import Interface_Static
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Reader, STEPControl_Writer
from OCP.ShapeFix import ShapeFix_Shell, ShapeFix_Solid
from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED, TopAbs_SHELL, TopAbs_SOLID
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as TopTools_IndexedMapOfShape
from OCP.TopoDS import TopoDS, TopoDS_Compound, TopoDS_Shape, TopoDS_Shell
from OCP.gp import gp_Pnt

NS_CORE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
NS_PROD = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
UNIT_TO_MM = {"micron": 0.001, "millimeter": 1.0, "centimeter": 10.0,
              "inch": 25.4, "foot": 304.8, "meter": 1000.0}


# --------------------------------------------------------------------------- shape utils

def solids(shape: TopoDS_Shape) -> list:
    out, exp = [], TopExp_Explorer(shape, TopAbs_SOLID)
    while exp.More():
        out.append(TopoDS.Solid(exp.Current()))
        exp.Next()
    return out


def faces(shape: TopoDS_Shape) -> list:
    m = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(shape, TopAbs_FACE, m)
    return [TopoDS.Face(m.FindKey(i)) for i in range(1, m.Extent() + 1)]


def make_compound(shapes) -> TopoDS_Compound:
    b, comp = BRep_Builder(), TopoDS_Compound()
    b.MakeCompound(comp)
    for s in shapes:
        b.Add(comp, s)
    return comp


def volume(shape) -> float:
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    return abs(props.Mass())


def bbox(shape):
    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    a, b = box.CornerMin(), box.CornerMax()
    return np.array([a.X(), a.Y(), a.Z()]), np.array([b.X(), b.Y(), b.Z()])


# --------------------------------------------------------------------------- tessellation

def tessellate(shape, lin_defl: float | None = None, ang_defl: float = 0.3):
    """Mesh a shape. Returns (verts[n,3], tris[m,3], face_index[m]) with per-face vertices.

    face_index refers to the order of `faces(shape)`.
    """
    if lin_defl is None:
        lo, hi = bbox(shape)
        lin_defl = max(0.01, float(np.linalg.norm(hi - lo)) * 4e-4)
    BRepMesh_IncrementalMesh(shape, lin_defl, False, ang_defl, True)
    verts, tris, fidx, base = [], [], [], 0
    for i, f in enumerate(faces(shape)):
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(f, loc)
        if tri is None:
            continue
        trsf = loc.Transformation()
        nodes = np.empty((tri.NbNodes(), 3))
        for k in range(1, tri.NbNodes() + 1):
            p = tri.Node(k).Transformed(trsf)
            nodes[k - 1] = (p.X(), p.Y(), p.Z())
        t = np.array([tri.Triangle(k).Get() for k in range(1, tri.NbTriangles() + 1)], dtype=np.int64) - 1
        if f.Orientation() == TopAbs_REVERSED:
            t = t[:, [0, 2, 1]]
        verts.append(nodes)
        tris.append(t + base)
        fidx.append(np.full(len(t), i, dtype=np.int64))
        base += len(nodes)
    if not verts:
        return np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64), np.zeros(0, dtype=np.int64)
    return np.vstack(verts), np.vstack(tris), np.concatenate(fidx)


def merge_vertices(verts, tris, tol=1e-6):
    key = np.round(verts / tol).astype(np.int64)
    _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    return verts[first], inv.reshape(-1)[tris]


# --------------------------------------------------------------------------- STEP

def load_step(path) -> TopoDS_Shape:
    r = STEPControl_Reader()
    if r.ReadFile(str(path)) != IFSelect_RetDone:
        raise ValueError(f"Could not read STEP file: {path}")
    r.TransferRoots()
    return r.OneShape()


def save_step(shape, path):
    Interface_Static.SetCVal_s("write.step.unit", "MM")
    Interface_Static.SetIVal_s("write.surfacecurve.mode", 0)  # skip redundant pcurves: much smaller files
    w = STEPControl_Writer()
    w.Transfer(shape, STEPControl_AsIs)
    if w.Write(str(path)) != IFSelect_RetDone:
        raise IOError(f"Could not write STEP file: {path}")


# --------------------------------------------------------------------------- 3MF

def _read_3mf_meshes(path):
    """Return a list of (verts, tris) in millimetres, with build transforms applied."""
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        root_model = "3D/3dmodel.model"
        if "_rels/.rels" in names:
            for rel in ET.fromstring(z.read("_rels/.rels")):
                if rel.get("Type", "").endswith("/3dmodel"):
                    root_model = rel.get("Target", root_model).lstrip("/")
        cache = {}

        def model(name):
            name = name.lstrip("/")
            if name not in cache:
                root = ET.fromstring(z.read(name))
                scale = UNIT_TO_MM.get(root.get("unit", "millimeter"), 1.0)
                objs = {}
                for obj in root.iter(f"{{{NS_CORE}}}object"):
                    mesh = obj.find(f"{{{NS_CORE}}}mesh")
                    if mesh is not None:
                        v = np.array([[float(e.get("x")), float(e.get("y")), float(e.get("z"))]
                                      for e in mesh.find(f"{{{NS_CORE}}}vertices")]) * scale
                        t = np.array([[int(e.get("v1")), int(e.get("v2")), int(e.get("v3"))]
                                      for e in mesh.find(f"{{{NS_CORE}}}triangles")], dtype=np.int64)
                        objs[obj.get("id")] = ("mesh", v, t)
                    comps = obj.find(f"{{{NS_CORE}}}components")
                    if comps is not None:
                        lst = [(c.get("objectid"), c.get(f"{{{NS_PROD}}}path") or name,
                                _transform(c.get("transform"), scale)) for c in comps]
                        objs[obj.get("id")] = ("comp", lst)
                cache[name] = (root, objs, scale)
            return cache[name]

        out = []

        def collect(file, oid, M):
            _, objs, _ = model(file)
            kind = objs[oid]
            if kind[0] == "mesh":
                v = np.c_[kind[1], np.ones(len(kind[1]))] @ M
                out.append((v, kind[2]))
            else:
                for cid, cfile, cM in kind[1]:
                    collect(cfile, cid, cM @ M)

        root, _, scale = model(root_model)
        build = root.find(f"{{{NS_CORE}}}build")
        for item in build:
            collect(item.get(f"{{{NS_PROD}}}path") or root_model, item.get("objectid"),
                    _transform(item.get("transform"), scale))
    return out


def _transform(s, scale):
    """3MF 3x4 transform string -> 4x3 matrix acting on row vectors [x y z 1]."""
    M = np.zeros((4, 3))
    M[:3] = np.eye(3)
    if s:
        vals = [float(x) for x in s.split()]
        M = np.array(vals).reshape(4, 3)
        M[3] *= scale
    return M


def mesh_to_solid(verts, tris):
    """Build a B-rep solid from a closed triangle mesh, merging coplanar triangles into faces."""
    verts, tris = merge_vertices(np.asarray(verts, float), np.asarray(tris), tol=1e-5)
    ok = (tris[:, 0] != tris[:, 1]) & (tris[:, 1] != tris[:, 2]) & (tris[:, 0] != tris[:, 2])
    tris = tris[ok]
    vtx = [BRepBuilderAPI_MakeVertex(gp_Pnt(*map(float, p))).Vertex() for p in verts]
    edges = {}

    def edge(a, b):
        key = (min(a, b), max(a, b))
        e = edges.get(key)
        if e is None:
            e = BRepBuilderAPI_MakeEdge(vtx[key[0]], vtx[key[1]]).Edge()
            edges[key] = e
        return e if a < b else TopoDS.Edge(e.Reversed())

    builder, shell = BRep_Builder(), TopoDS_Shell()
    builder.MakeShell(shell)
    for a, b, c in tris.tolist():
        try:
            w = BRepBuilderAPI_MakeWire(edge(a, b), edge(b, c), edge(c, a))
            if not w.IsDone():
                continue
            mf = BRepBuilderAPI_MakeFace(w.Wire(), True)
            if mf.IsDone():
                builder.Add(shell, mf.Face())
        except Exception:
            continue
    fix = ShapeFix_Shell(shell)
    fix.Perform()
    sf = ShapeFix_Solid()
    solid = sf.SolidFromShell(TopoDS.Shell(fix.Shell()))
    unify = ShapeUpgrade_UnifySameDomain(solid, True, True, True)
    unify.SetLinearTolerance(1e-4)
    unify.SetAngularTolerance(1e-4)
    unify.Build()
    return unify.Shape()


def load_3mf(path) -> TopoDS_Shape:
    meshes = _read_3mf_meshes(path)
    if not meshes:
        raise ValueError("3MF file contains no meshes")
    sols = []
    for v, t in meshes:
        s = mesh_to_solid(v, t)
        sols.extend(solids(s) or [s])
    return sols[0] if len(sols) == 1 else make_compound(sols)


def save_3mf(shape, path, lin_defl=None):
    objects = []
    for s in solids(shape) or [shape]:
        v, t, _ = tessellate(s, lin_defl, 0.2)
        objects.append(merge_vertices(v, t))
    parts = ['<?xml version="1.0" encoding="UTF-8"?>\n'
             f'<model unit="millimeter" xml:lang="en-US" xmlns="{NS_CORE}">\n<resources>\n']
    for i, (v, t) in enumerate(objects, 1):
        parts.append(f'<object id="{i}" type="model"><mesh><vertices>\n')
        parts.append("".join(f'<vertex x="{x:.6f}" y="{y:.6f}" z="{z:.6f}"/>\n' for x, y, z in v))
        parts.append("</vertices><triangles>\n")
        parts.append("".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>\n' for a, b, c in t))
        parts.append("</triangles></mesh></object>\n")
    parts.append("</resources>\n<build>\n")
    parts.append("".join(f'<item objectid="{i}"/>\n' for i in range(1, len(objects) + 1)))
    parts.append("</build>\n</model>\n")
    content_types = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                     '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                     '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                     '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
                     '</Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Target="/3D/3dmodel.model" Id="rel0" '
            'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", "".join(parts))


def save_stl(shape, path, lin_defl=None):
    v, t, _ = tessellate(shape, lin_defl, 0.2)
    tri = v[t]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    rec = np.zeros(len(t), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
    rec["n"], rec["v"] = n, tri
    with open(path, "wb") as fh:
        fh.write(b"autopocket".ljust(80, b" "))
        fh.write(struct.pack("<I", len(t)))
        fh.write(rec.tobytes())


# --------------------------------------------------------------------------- dispatch

def load_any(path) -> TopoDS_Shape:
    ext = Path(path).suffix.lower()
    if ext in (".step", ".stp"):
        return load_step(path)
    if ext == ".3mf":
        return load_3mf(path)
    raise ValueError(f"Unsupported file type '{ext}' (use .step, .stp or .3mf)")


def save_any(shape, path):
    ext = Path(path).suffix.lower()
    {".step": save_step, ".stp": save_step, ".3mf": save_3mf, ".stl": save_stl}[ext](shape, path)
