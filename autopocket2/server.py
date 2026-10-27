"""v2 web app: same UI and endpoints as v1 (autopocket/server.py), v2 planner behind them.

Samples, status and meshes are v1's handlers reused as-is. v2 adds: the plate's features on
upload (holes, outline sides, corners, so the page can pick them), a live preview of the
protected area for the chosen rib width / clearances, those settings passed to the
planner, and learning: every run is recorded in the knowledge base, and picking another
option or downloading one is recorded as a style preference.
"""
from __future__ import annotations

import threading
import time
import traceback
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
import numpy as np

from autopocket import cadio
from autopocket import server as base
from autopocket.pocketer import PlateRules, find_plate

from . import features, runner
from .knowledge import KnowledgeBase

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="AutoPocket v2")
for path, fn in [("/api/defaults", base.defaults), ("/api/samples", base.samples),
                 ("/samples/{name}", base.sample_file), ("/api/status/{sid}", base.status),
                 ("/api/result_mesh/{sid}", base.result_mesh)]:
    app.get(path)(fn)
KB = KnowledgeBase()


def _remember(s, k, kind):
    """Record the user choosing variant k (over the automatic pick) as a style preference."""
    run_id = (s.get("diagnostics") or {}).get("run_id")
    vs = s.get("variants") or []
    if run_id is None or not (0 <= k < len(vs)):
        return
    auto = vs[s["best"]].get("db_id") if 0 <= s.get("best", -1) < len(vs) else None
    mine = vs[k].get("db_id")
    if mine is not None:
        KB.add_choice(run_id, mine, auto if auto != mine else None, kind)


@app.get("/api/download/{sid}/{fmt}")
def download(sid: str, fmt: str):
    s = base._session(sid)
    if s.get("result") is not None and fmt in ("step", "3mf", "stl") and not s.get("downloaded"):
        _remember(s, s.get("chosen", s.get("best", 0)), "downloaded")
        s["downloaded"] = True
    return base.download(sid, fmt)


@app.get("/api/knowledge")
def knowledge():
    return KB.stats()


def _ready(s):
    if s.get("result") is None or not s.get("variants"):
        raise HTTPException(404, "No result yet")
    return s["variants"][s.get("chosen", s.get("best", 0))]


@app.get("/api/pockets/{sid}")
def pockets(sid: str):
    """Pocket outlines of the shown design, per plate, in machining order (cut animation)."""
    s = base._session(sid)
    v = _ready(s)
    return {"plates": runner.cut_order(s["plates"], v), "tool_radius": v["rules"]["tool_radius"]}


def _f32(a):
    return base._b64(np.nan_to_num(np.asarray(a, np.float32), nan=np.nan), "<f4")


@app.get("/api/sim/{sid}")
def sim(sid: str, plate: int = 0, which: str = "pocketed", case: int = -1):
    """High-resolution results of one plate (original or pocketed) for one load case, or the
    worst case (-1), on a triangle mesh of the plate's true shape.

    Stress is MPa and displacement mm when a load in newtons was given in engineering mode;
    otherwise both are relative to the original plate (1 = its typical peak stress / its
    largest deflection in that case)."""
    from . import simview
    s = base._session(sid)
    v = _ready(s)
    key = s.get("chosen", 0)
    if s.get("sim_key") != key:
        s["sim"], s["sim_key"] = runner.simulate(s["plates"], v, s.get("loads")), key
    sims = s["sim"]
    if not (0 <= plate < len(sims)):
        raise HTTPException(400, "No such plate")
    P = sims[plate]
    which = "original" if which == "original" else "pocketed"
    R, O = P[which], P["original"]
    lm = (s.get("diagnostics") or {}).get("load_model") or {}
    force = lm.get("force_n") if P["engineering"] else None
    mat = runner.MATERIALS[s.get("material", "Aluminum 6061-T6")]
    E = mat["E"] * 1000.0

    def stress(c):
        return c["stress"] * force if force else c["stress"] / max(c["p99_blank"], 1e-30)

    def disp(c, ref):
        if force:
            return c["u"] * force / E
        return c["u"] / max(np.nanmax(np.linalg.norm(np.nan_to_num(ref["u"]), axis=1)), 1e-30)

    cases = R["cases"]
    if 0 <= case < len(cases):
        st, u = stress(cases[case]), disp(cases[case], O["cases"][case])
    else:
        st, u = np.nanmax(np.stack([stress(c) for c in cases]), axis=0), None
    hot = simview.hot_spots(P["profiles"]["original"], R["V"], st, P["rib"])  # real holes only, not pockets
    return {"V": _f32(R["V"]), "T": base._b64(R["T"], "<u4"), "stress": _f32(st),
            "u": None if u is None else _f32(u),
            "cases": [c["name"] for c in cases], "case": case, "which": which, "hot": hot,
            "supports": P["supports"], "loads": P["loads"], "dirs": P["dirs"],
            "absolute": bool(force), "force_n": force, "E_mpa": E, "strength_mpa": mat["strength"],
            "mode": "engineering" if P["engineering"] else "generic"}


def _clamp(v, lo, hi, default):
    try:
        return max(lo, min(hi, float(v)))
    except (TypeError, ValueError):
        return default


def parse_settings(body: dict, n_plates: int):
    """(PlateRules, [Clearances per plate]) from the page's rules panel and feature picks."""
    rr = body.get("rules") or {}
    d = PlateRules()
    rib = _clamp(rr.get("rib"), 3.0, 25.0, d.rib)
    tool = _clamp(rr.get("tool_radius"), 0.3, 8.0, d.tool_radius)
    clear = _clamp(rr.get("clearance"), features.MIN_CLEARANCE, 100.0, d.offset + d.rib / 2)
    rules = PlateRules(rib=rib, tool_radius=tool, offset=clear - rib / 2)
    given = body.get("clearances") or []
    cls = []
    for i in range(n_plates):
        c = given[i] if i < len(given) and isinstance(given[i], dict) else {}
        cls.append(features.Clearances.from_dict({**c, "default": clear}, rules))
    return rules, cls


def parse_loads(body: dict, n_plates: int):
    """[{"mounts": [hole ids], "bearings": [hole ids], "force_n": N or None}] per plate."""
    force = _clamp(body.get("force_n"), 0.0, 1e5, 0.0) or None
    given = body.get("loads") or []
    out = []
    for i in range(n_plates):
        g = given[i] if i < len(given) and isinstance(given[i], dict) else {}
        ids = lambda k: [int(x) for x in (g.get(k) or []) if str(x).lstrip("-").isdigit()]  # noqa: E731
        dirs = []
        for d in (g.get("dirs") or [])[:6]:
            try:
                vec = [float(x) for x in d.get("v", [])][:3]
            except (TypeError, ValueError, AttributeError):
                continue
            if len(vec) == 3 and any(abs(x) > 1e-6 for x in vec):
                dirs.append({"label": str(d.get("label", "Applied"))[:24], "v": vec})
        out.append({"mounts": ids("mounts"), "bearings": ids("bearings"), "force_n": force, "dirs": dirs,
                    "purpose": str(body.get("purpose") or "")[:40] or None})
    return out


@app.post("/api/interpret/{sid}")
def interpret(sid: str, body: dict):
    """Read a plain-English description of the plate's job into a load setup (per plate)."""
    from .loadspec import interpret as read
    s = base._session(sid)
    text = str(body.get("text", ""))[:1000]
    return {"plates": [read(text, features.describe(p)["holes"]) for p in s.get("plates0") or []]}


@app.post("/api/upload")
def upload(file: UploadFile = File(...)):
    out = base.upload(file)
    s = base.SESSIONS[out["id"]]
    s["plates0"] = [find_plate(x) for x in cadio.solids(s["shape"])]
    out["features"] = [features.describe(p) for p in s["plates0"]]
    d = PlateRules()
    out["defaults"] = {"rib": d.rib, "tool_radius": d.tool_radius, "clearance": d.offset + d.rib / 2}
    return out


@app.post("/api/protected/{sid}")
def protected(sid: str, body: dict):
    """Plate area no pocket may touch for these settings (drawn over the plate)."""
    s = base._session(sid)
    plates = s.get("plates0") or []
    rules, cls = parse_settings(body, len(plates))
    return {"plates": [features.protected_shapes(features.Domain(p.profile, rules, cl))
                       for p, cl in zip(plates, cls)]}


@app.get("/", response_class=HTMLResponse)
def index():
    return (STATIC / "index.html").read_text(encoding="utf-8")


def _finish(s, shape_out, chosen, cad):
    s["result"], s["chosen"], s["downloaded"] = shape_out, chosen, False
    s["pocket_faces"] = base.find_pocket_faces(s["plates"], shape_out)
    s["report"] = runner.report(s["plates"], s["variants"], chosen, s["material"], s["target"],
                                shape_out, s["t0"], s.get("diagnostics"), cad)
    for ext in ("step", "3mf", "stl"):
        (s["dir"] / f"result.{ext}").unlink(missing_ok=True)


@app.post("/api/pocket/{sid}")
def pocket(sid: str, body: dict):
    s = base._session(sid)
    if s.get("state") == "running":
        raise HTTPException(409, "Already running")
    material = body.get("material", "Aluminum 6061-T6")
    if material not in runner.MATERIALS:
        material = "Aluminum 6061-T6"
    s.update(state="running", progress=0.0, message="Starting", report=None, error=None, result=None,
             material=material, target=float(body.get("target_stiffness", 0.33)), t0=time.time())
    rules, cls = parse_settings(body, len(s.get("plates0") or []))
    loads = parse_loads(body, len(s.get("plates0") or []))
    s["clearances"] = cls
    s["loads"], s["sim"], s["sim_key"] = loads, None, None
    pattern = body.get("pattern") if body.get("pattern") in runner.PATTERNS else "auto"

    def prog(msg, frac):
        s["message"], s["progress"] = msg, float(frac)

    def work():
        try:
            out = runner.run(s["shape"], material, s["target"], prog, rules=rules, clearances=cls, loads=loads,
                             knowledge=KB, source="web", name=s["name"], pattern=pattern)
            s["plates"], s["variants"], s["diagnostics"] = out["plates"], out["variants"], out["diagnostics"]
            s["best"] = out["best"]
            prog("Preparing preview", 0.99)
            _finish(s, out["shape"], out["best"], out["cad_check"])
            s["state"] = "done"
        except Exception as e:  # report to the UI
            traceback.print_exc()
            s["error"], s["state"] = str(e) or e.__class__.__name__, "error"

    threading.Thread(target=work, daemon=True).start()
    return {"ok": True}


@app.get("/api/ribs/{sid}")
def ribs(sid: str):
    """Rib centre lines of the shown design, per plate, plus symmetry axes (Edit view)."""
    s = base._session(sid)
    v = _ready(s)
    from autopocket.pocketer import PlateRules as PR
    r = PR(**v["rules"])
    cls = s.get("clearances") or []
    axes = []
    for i, p in enumerate(s["plates"]):
        dom = features.Domain(p.profile, r, cls[i] if i < len(cls) else None)
        axes.append([[list(map(float, c)), list(map(float, d))] for c, d in dom.axes])
    return {"plates": v.get("lines") or [[] for _ in s["plates"]], "axes": axes, "rib": r.rib,
            "label": v.get("label")}


@app.post("/api/edit/{sid}")
def edit(sid: str, body: dict):
    """Rebuild the pockets from the user's rib lines, analyse and cut them (a new option)."""
    s = base._session(sid)
    v = _ready(s)
    lines = []
    for g in (body.get("plates") or [])[:len(s["plates"])]:
        segs = []
        for seg in (g.get("lines") or [])[:2000]:
            try:
                pts = [[float(x), float(y)] for x, y in seg][:2]
            except (TypeError, ValueError):
                continue
            if len(pts) == 2:
                segs.append(pts)
        lines.append(segs)
    try:
        c, lays = runner.edit_design(s["plates"], v, lines, s.get("clearances"), s.get("loads"),
                                     s.get("target", 0.33), bool(body.get("mirror", True)))
    except ValueError as e:
        raise HTTPException(400, str(e))
    n = sum(1 for x in s["variants"] if x.get("family") == "edit")
    c["label"] = "Your edit" + (f" {n + 1}" if n else "")
    run_id = (s.get("diagnostics") or {}).get("run_id")
    if run_id is not None:  # the user's own layout: a strong preference signal for learning
        from .knowledge import FEA_FEASIBLE, FEA_INFEASIBLE
        from .learning import style_of
        pid = (KB.rows("SELECT plate_id FROM run WHERE id=?", (run_id,)) or [{}])[0].get("plate_id")
        c["db_id"] = KB.add_candidate(run_id, pid, c, FEA_FEASIBLE if c["meets_target"] else FEA_INFEASIBLE,
                                      None, style_of(lays[0]))
        auto = s["variants"][s["best"]].get("db_id") if 0 <= s.get("best", -1) < len(s["variants"]) else None
        KB.add_choice(run_id, c["db_id"], auto, "edited")
    s["variants"].append(c)
    k = len(s["variants"]) - 1
    s["t0"] = time.time()
    shape_out, _, cad = runner.build(s["plates"], c)
    _finish(s, shape_out, k, cad)
    return {"report": s["report"], "mesh": base.mesh_payload(shape_out, s["pocket_faces"])}


@app.post("/api/variant/{sid}/{k}")
def variant(sid: str, k: int):
    s = base._session(sid)
    if s.get("state") != "done" or not (0 <= k < len(s.get("variants", []))):
        raise HTTPException(400, "No such option")
    s["t0"] = time.time()
    if k != s.get("best"):
        _remember(s, k, "switched")
    shape_out, _, cad = runner.build(s["plates"], s["variants"][k])
    _finish(s, shape_out, k, cad)
    return {"report": s["report"], "mesh": base.mesh_payload(shape_out, s["pocket_faces"])}
