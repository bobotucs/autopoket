"""Local web app: upload a flat STEP/3MF plate, pocket it, inspect and download the result."""
from __future__ import annotations

import base64
import shutil
import tempfile
import threading
import time
import traceback
import uuid
from pathlib import Path

import numpy as np
import shapely
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from . import cadio, runner
from .pocketer import PlateRules, find_plate

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


def find_pocket_faces(plates, result):
    """Faces of `result` that are pocket walls: side faces lying inside the blank profile."""
    v, t, f = cadio.tessellate(result)
    tri = v[t]
    area = np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
    cent = tri.mean(axis=1)
    out = []
    for fi in np.unique(f):
        idx = np.nonzero(f == fi)[0]
        c = cent[idx[np.argmax(area[idx])]]
        for p in plates:
            fr = p.frame
            h = (c - fr.origin) @ fr.n
            if -p.thickness + 1e-3 < h < -1e-3 or abs(h) > 1e-3 and abs(h + p.thickness) > 1e-3:
                uv = shapely.Point((c - fr.origin) @ fr.x, (c - fr.origin) @ fr.y)
                if p.profile.boundary.distance(uv) > 0.05 and p.profile.buffer(0.05).contains(uv):
                    out.append(int(fi))
                    break
    return out


def _session(sid):
    s = SESSIONS.get(sid)
    if s is None:
        raise HTTPException(404, "Unknown session - upload the file again")
    return s


@app.get("/", response_class=HTMLResponse)
def index():
    return (STATIC / "index.html").read_text(encoding="utf-8")


@app.get("/api/defaults")
def defaults():
    return {"rules": PlateRules().to_dict(), "materials": runner.MATERIALS}


@app.get("/api/samples")
def samples():
    return sorted(p.name for p in SAMPLES.glob("*") if p.suffix.lower() in (".step", ".stp", ".3mf"))


@app.get("/samples/{name}")
def sample_file(name: str):
    path = SAMPLES / Path(name).name
    if not path.is_file():
        raise HTTPException(404, "No such sample")
    return FileResponse(path)


@app.post("/api/upload")
def upload(file: UploadFile = File(...)):
    name = Path(file.filename or "plate.step").name
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
        sols = cadio.solids(shape)
        if not sols:
            raise ValueError("No solid bodies found (is it a closed, watertight model?)")
        plates = [find_plate(s) for s in sols]
    except Exception as e:
        raise HTTPException(400, f"Could not read the plate: {e}")
    info = []
    for p in plates:
        b = p.profile.bounds
        info.append({"size": [round(b[2] - b[0], 2), round(b[3] - b[1], 2)],
                     "thickness": round(p.thickness, 3),
                     "holes": len(p.profile.interiors)})
    SESSIONS[sid] = {"dir": d, "name": name, "shape": shape, "state": "idle"}
    return {"id": sid, "name": name, "plates": info,
            "warnings": sorted({w for p in plates for w in p.warnings}),
            "mesh": mesh_payload(shape)}


def _finish(s, shape_out, chosen):
    s["result"] = shape_out
    s["pocket_faces"] = find_pocket_faces(s["plates"], shape_out)
    s["report"] = runner.report(s["plates"], s["variants"], chosen, s["material"],
                                s["target"], shape_out, s["t0"])
    for ext in ("step", "3mf", "stl"):
        (s["dir"] / f"result.{ext}").unlink(missing_ok=True)


@app.post("/api/pocket/{sid}")
def pocket(sid: str, body: dict):
    s = _session(sid)
    if s.get("state") == "running":
        raise HTTPException(409, "Already running")
    material = body.get("material", "Aluminum 6061-T6")
    if material not in runner.MATERIALS:
        material = "Aluminum 6061-T6"
    s.update(state="running", progress=0.0, message="Starting", report=None, error=None, result=None,
             material=material, target=float(body.get("target_stiffness", 0.33)), t0=time.time())

    def prog(msg, frac):
        s["message"], s["progress"] = msg, float(frac)

    def work():
        try:
            out = runner.run(s["shape"], material, s["target"], prog)
            s["plates"], s["variants"] = out["plates"], out["variants"]
            prog("Preparing preview", 0.99)
            _finish(s, out["shape"], out["best"])
            s["state"] = "done"
        except Exception as e:  # report to the UI
            traceback.print_exc()
            s["error"], s["state"] = str(e) or e.__class__.__name__, "error"

    threading.Thread(target=work, daemon=True).start()
    return {"ok": True}


@app.post("/api/variant/{sid}/{k}")
def variant(sid: str, k: int):
    """Switch to another spacing the planner already evaluated."""
    s = _session(sid)
    if s.get("state") != "done" or not (0 <= k < len(s.get("variants", []))):
        raise HTTPException(400, "No such option")
    s["t0"] = time.time()
    shape_out, _ = runner.build(s["plates"], s["variants"][k])
    _finish(s, shape_out, k)
    return {"report": s["report"], "mesh": mesh_payload(shape_out, s["pocket_faces"])}


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
