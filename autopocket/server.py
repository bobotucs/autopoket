"""Local web app: upload a STEP/3MF part, pocket it, inspect and download the result."""
from __future__ import annotations

import base64
import shutil
import tempfile
import threading
import traceback
import uuid
from pathlib import Path

import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.TopAbs import TopAbs_ON
from OCP.gp import gp_Pnt

from . import cadio, runner
from .pocketer import PocketParams

STATIC = Path(__file__).parent / "static"
SAMPLES = Path(__file__).resolve().parents[1] / "samples"
WORK = Path(tempfile.gettempdir()) / "autopocket"
SESSIONS: dict[str, dict] = {}

app = FastAPI(title="AutoPocket")


def _b64(a, dtype):
    return base64.b64encode(np.ascontiguousarray(a, dtype=dtype).tobytes()).decode()


def mesh_payload(shape, pocket_faces=()):
    v, t, f = cadio.tessellate(shape)
    return {"positions": _b64(v, "<f4"), "indices": _b64(t, "<u4"), "faces": _b64(f, "<u4"),
            "pocketFaces": list(pocket_faces)}


def find_pocket_faces(original, result):
    """Faces of `result` that lie inside the original material, i.e. pocket walls/floors."""
    v, t, f = cadio.tessellate(result)
    tri = v[t]
    area = np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
    cent = tri.mean(axis=1)
    sols = cadio.solids(original)
    out = []
    for fi in np.unique(f):
        idx = np.nonzero(f == fi)[0]
        c = cent[idx[np.argmax(area[idx])]]
        on = False
        for s in sols:
            cl = BRepClass3d_SolidClassifier(s, gp_Pnt(*map(float, c)), 1e-3)
            if cl.State() == TopAbs_ON:
                on = True
                break
        if not on:
            out.append(int(fi))
    return out


def _session(sid):
    s = SESSIONS.get(sid)
    if s is None:
        raise HTTPException(404, "Unknown session - upload the file again")
    return s


@app.get("/", response_class=HTMLResponse)
def index():
    return (STATIC / "index.html").read_text(encoding="utf-8")


@app.get("/api/samples")
def samples():
    return sorted(p.name for p in SAMPLES.glob("*") if p.suffix.lower() in (".step", ".stp", ".3mf"))


@app.get("/samples/{name}")
def sample_file(name: str):
    path = SAMPLES / Path(name).name
    if not path.is_file():
        raise HTTPException(404, "No such sample")
    return FileResponse(path)


@app.get("/api/defaults")
def defaults():
    return {"params": PocketParams().to_dict(), "materials": runner.MATERIALS}


@app.post("/api/upload")
def upload(file: UploadFile = File(...)):
    name = Path(file.filename or "part.step").name
    if Path(name).suffix.lower() not in (".step", ".stp", ".3mf"):
        raise HTTPException(400, "Please upload a .step, .stp or .3mf file")
    sid = uuid.uuid4().hex[:12]
    d = WORK / sid
    d.mkdir(parents=True, exist_ok=True)
    path = d / name
    with open(path, "wb") as fh:
        shutil.copyfileobj(file.file, fh)
    try:
        shape = cadio.load_any(path)
    except Exception as e:
        raise HTTPException(400, f"Could not read the file: {e}")
    sols = cadio.solids(shape)
    if not sols:
        raise HTTPException(400, "No solid bodies found in the file (is it a closed, watertight model?)")
    lo, hi = cadio.bbox(shape)
    SESSIONS[sid] = {"dir": d, "name": name, "shape": shape, "state": "idle"}
    return {"id": sid, "name": name, "solids": len(sols), "faces": len(cadio.faces(shape)),
            "size": (hi - lo).round(3).tolist(), "volume": cadio.volume(shape),
            "mesh": mesh_payload(shape)}


@app.post("/api/pocket/{sid}")
def pocket(sid: str, body: dict):
    s = _session(sid)
    if s.get("state") == "running":
        raise HTTPException(409, "Already running")
    params = PocketParams.from_dict(body.get("params"))
    s.update(state="running", progress=0.0, message="Starting", report=None, error=None, result=None)

    def prog(msg, frac):
        s["message"], s["progress"] = msg, float(frac)

    def work():
        try:
            out = runner.run(s["shape"], params, body.get("material", "Aluminum 6061"),
                             float(body.get("target_stiffness", 0.5)),
                             bool(body.get("check_structure", True)), prog)
            prog("Preparing preview", 0.99)
            s["result"] = out["shape"]
            s["pocket_faces"] = find_pocket_faces(s["shape"], out["shape"])
            s["report"] = out["report"]
            for ext in ("step", "3mf", "stl"):
                (s["dir"] / f"result.{ext}").unlink(missing_ok=True)
            s["state"] = "done"
        except Exception as e:  # report to the UI
            traceback.print_exc()
            s["error"], s["state"] = str(e) or e.__class__.__name__, "error"

    threading.Thread(target=work, daemon=True).start()
    return {"ok": True}


@app.get("/api/status/{sid}")
def status(sid: str):
    s = _session(sid)
    return {"state": s.get("state"), "progress": s.get("progress", 0), "message": s.get("message", ""),
            "error": s.get("error"), "report": s.get("report")}


@app.get("/api/result_mesh/{sid}")
def result_mesh(sid: str):
    s = _session(sid)
    if s.get("result") is None:
        raise HTTPException(404, "No result yet")
    return mesh_payload(s["result"], s.get("pocket_faces", []))


@app.get("/api/download/{sid}/{fmt}")
def download(sid: str, fmt: str):
    s = _session(sid)
    if s.get("result") is None:
        raise HTTPException(404, "No result yet")
    if fmt not in ("step", "3mf", "stl"):
        raise HTTPException(400, "Format must be step, 3mf or stl")
    path = s["dir"] / f"result.{fmt}"
    if not path.exists():
        cadio.save_any(s["result"], path)
    stem = Path(s["name"]).stem
    return FileResponse(path, filename=f"{stem}_pocketed.{fmt}", media_type="application/octet-stream")
