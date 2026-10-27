"""Find every plate you have pocketed in Onshape and teach AutoPocket v2 from it.

    python onshape_import.py                      # all documents you own
    python onshape_import.py --shared             # ... plus documents shared with you
    python onshape_import.py --max-docs 20        # stop after 20 documents (API call budget)
    python onshape_import.py --from-folder DIR    # same processing on STEP files already on disk

Access: create an API key pair with read permission at https://dev-portal.onshape.com/keys
and save it yourself in C:\\Users\\<you>\\.onshape_keys (outside this project) as two lines:

    ONSHAPE_ACCESS_KEY=...
    ONSHAPE_SECRET_KEY=...

Only reads and exports are done (read permission is enough); delete the key at the dev
portal to revoke access at any time. The keys are never written anywhere else.

For each Part Studio, every solid is checked: is it a flat plate, and does it have pockets
(inner loops with tool-radius corners and straight sides, told apart from holes and slots
by examples/classify.py)? Each pocketed plate is saved to knowledge/onshape/pocketed/,
its blank (outline + real holes) to knowledge/onshape/blanks/, and its pockets are added
to the knowledge base as a style reference (STYLE_REFERENCE_ONLY: how you pocket, not
proof that it is strong). --analyse also runs the FEA on your design against its blank,
so the report shows how much weight you removed and how much stiffness you kept.
A manifest remembers what was already processed, so re-runs only fetch new documents.

Search order: documents and Part Studios whose names sound like a robot (drivetrain,
chassis, shooter, turret, intake, transfer, main assembly, arm, lift ...) go first; parts
libraries (electronics, motors, sensors, goBILDA / REV parts ...) are skipped, since they
hold no hand-pocketed plates. Any document that errors, is blocked, or is rate-limited is
skipped at once with no retries (and remembered, so it isn't tried again); a Part Studio
whose export takes longer than EXPORT_TIMEOUT is skipped. Plates found twice (the same
plate in several Part Studios or documents) are kept once. Each plate gets a pattern
label: freestyle triangles, isogrid, hexagon, Voronoi or mixed.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "examples"))

BASE = "https://cad.onshape.com"
EXPORT_TIMEOUT = 45  # s: Onshape's STEP translation of one Part Studio
ROBOT_WORDS = ("drivetrain", "drive train", "chassis", "shooter", "turret", "intake", "transfer", "main assembly",
               "robot", "arm", "lift", "elevator", "slide", "outtake", "deposit", "claw", "hang", "climb", "climber",
               "gearbox", "side plate", "plate", "frame", "wrist", "pivot", "indexer", "hopper", "spindexer",
               "launcher", "flywheel", "bucket", "scoring", "linkage", "cascade", "viper", "ftc", "frc", "worlds",
               "states", "regional", "season", "202")
LIBRARY_WORDS = ("electronics", "encoder", "battery", "camera", "limelight", "octoquad", "hub", "servo", "motor",
                 "sensor", "led", "wire", "cable", "pinpoint", "power distribution", "xt30", "(gb)", "(rev)",
                 "gobilda", "rev robotics", "cots", "library", "hardware", "fastener", "screw", "bolt", "nut",
                 "bearing", "spacer", "standoff", "template", "featurescript", "logo", "sticker")


def _score(name):
    n = (name or "").lower()
    if any(w in n for w in LIBRARY_WORDS):
        return -1
    return sum(w in n for w in ROBOT_WORDS)
OUT = ROOT / "knowledge" / "onshape"
KEYS = Path.home() / ".onshape_keys"


# --------------------------------------------------------------------------- Onshape REST API

class Onshape:
    def __init__(self, keys_file=KEYS):
        if not keys_file.exists() and keys_file.with_name(keys_file.name + ".txt").exists():
            keys_file = keys_file.with_name(keys_file.name + ".txt")  # Notepad adds .txt
        keys = {}
        if keys_file.exists():
            for line in keys_file.read_text().splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    keys[k.strip()] = v.strip()
        access = os.environ.get("ONSHAPE_ACCESS_KEY") or keys.get("ONSHAPE_ACCESS_KEY")
        secret = os.environ.get("ONSHAPE_SECRET_KEY") or keys.get("ONSHAPE_SECRET_KEY")
        if not access or not secret:
            raise SystemExit(f"No Onshape API keys found. Save them in {keys_file} (see the top of this file).")
        self.access, self.secret = access, secret
        self.calls = 0

    def _headers(self, method, url, ctype):
        """Onshape's signed-request (HMAC-SHA256) authentication."""
        import hashlib
        import hmac
        import secrets
        from email.utils import formatdate
        u = urllib.parse.urlparse(url)
        nonce, date = secrets.token_hex(13), formatdate(usegmt=True)
        msg = "\n".join([method, nonce, date, ctype, u.path, u.query, ""]).lower()
        sig = base64.b64encode(hmac.new(self.secret.encode(), msg.encode(), hashlib.sha256).digest()).decode()
        return {"On-Nonce": nonce, "Date": date, "Authorization": f"On {self.access}:HmacSHA256:{sig}"}

    def request(self, method, path, body=None, raw=False):
        url = path if path.startswith("http") else BASE + path
        data = json.dumps(body).encode() if body is not None else None
        ctype = "application/json"
        req = urllib.request.Request(url, data=data, method=method, headers={
            **self._headers(method, url, ctype),
            "Accept": "application/json;charset=UTF-8; qs=0.09" if not raw else "*/*", "Content-Type": ctype})
        for attempt in range(4):  # a broken document is skipped at once; only rate limits are waited out
            try:
                self.calls += 1
                with urllib.request.urlopen(req, timeout=30) as r:
                    payload = r.read()
                return payload if raw else json.loads(payload or b"null")
            except urllib.error.HTTPError as e:
                if e.code == 429:  # Onshape asks us to slow down: that is about pace, not this document
                    wait = min(60.0, float(e.headers.get("Retry-After") or 10 * (attempt + 1)))
                    print(f"  (Onshape rate limit: waiting {wait:.0f} s)", flush=True)
                    time.sleep(wait)
                    continue
                if e.code == 402:  # the plan's API call allowance is used up: nothing more will work
                    raise SystemExit(f"Onshape's API allowance for this account is used up (402) after {self.calls} calls. "
                                     "Run again when it resets; finished documents are remembered.")
                if e.code == 401:
                    raise SystemExit("Onshape refused the request (401): check the API key and its read permission.")
                if e.code == 403:  # this document or export is off-limits (or the API quota is used up)
                    body = e.read()[:200].decode("utf-8", "replace")
                    raise PermissionError(f"403 forbidden: {body}") from None
                raise
        raise RuntimeError(f"Onshape kept rate-limiting {path}")

    def documents(self, shared=False):
        filters = [0] + ([2] if shared else [])  # 0 = my documents, 2 = shared with me
        for f in filters:
            nxt = f"/api/v6/documents?filter={f}&sortColumn=modifiedAt&sortOrder=desc&limit=20&offset=0"
            while nxt:
                page = self.request("GET", nxt)
                yield from page.get("items", [])
                nxt = page.get("next")

    def part_studios(self, did, wid):
        return self.request("GET", f"/api/v6/documents/d/{did}/w/{wid}/elements?elementType=PARTSTUDIO")

    def export_step(self, did, wid, eid):
        """STEP bytes of a whole Part Studio (one translation per Part Studio)."""
        t = self.request("POST", f"/api/v6/partstudios/d/{did}/w/{wid}/e/{eid}/translations",
                         {"formatName": "STEP", "storeInDocument": False, "stepUnit": "MILLIMETER"})
        tid, t0 = t["id"], time.time()
        while t.get("requestState") != "DONE":
            if t.get("requestState") == "FAILED":
                raise RuntimeError(t.get("failureReason") or "translation failed")
            if time.time() - t0 > EXPORT_TIMEOUT:
                raise RuntimeError("export took too long")
            time.sleep(1.5)
            t = self.request("GET", f"/api/v6/translations/{tid}")
        fid = t["resultExternalDataIds"][0]
        return self.request("GET", f"/api/v6/documents/d/{did}/externaldata/{fid}", raw=True)


# --------------------------------------------------------------------------- recognising pocketed plates

def _safe(s):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", s)[:60]


def pattern_of(pockets):
    """Rough label of a hand-made pocket pattern from its pockets' shapes."""
    import numpy as np
    from autopocket2.features import outline_sides
    if not pockets:
        return "none"
    corners = np.array([len(outline_sides(q)[1]) for q in pockets])
    areas = np.array([q.area for q in pockets])
    cv = areas.std() / areas.mean()
    tri, hexa = np.mean(corners == 3), np.mean(corners == 6)
    poly = np.mean((corners >= 4) & (corners <= 8))
    if tri >= 0.55:
        return "isogrid" if cv < 0.3 else "freestyle triangles"
    if hexa >= 0.5 and cv < 0.35:
        return "hexagon"
    if poly >= 0.5:
        return "Voronoi" if cv >= 0.2 else "regular polygons"
    return "mixed"


SEEN = set()


def process_step(step_path: Path, label: str, kb, analyse=False, min_pockets=2):
    """Save and learn from every pocketed flat plate in a STEP file. Returns found entries."""
    import classify
    from shapely.geometry import Polygon
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.gp import gp_Vec
    from autopocket import cadio, pocketer
    from autopocket2 import style

    found = []
    try:
        solids = cadio.solids(cadio.load_any(step_path))
    except Exception as e:
        print(f"    could not read: {e}")
        return found
    for i, solid in enumerate(solids):
        name = f"{label}_{i}" if len(solids) > 1 else label
        single = OUT / "tmp" / f"{_safe(name)}.step"
        single.parent.mkdir(parents=True, exist_ok=True)
        try:
            plate = pocketer.find_plate(solid)
            if plate.warnings and any("uniform" in w for w in plate.warnings):
                continue  # not a flat plate
            if not 1.0 <= plate.thickness <= 12.0:
                continue
            cadio.save_step(solid, single)
            plate, keep, pockets, kinds = classify.split(single)
        except Exception:
            continue
        if len(pockets) < min_pockets:
            continue
        from autopocket2.knowledge import plate_sha
        sha = plate_sha(plate.profile, plate.thickness)
        if sha in SEEN:
            continue  # the same plate again (another Part Studio / document)
        SEEN.add(sha)
        blank_profile = Polygon(plate.profile.exterior, [ring for ring, _ in keep])
        desc = style.descriptors(blank_profile, [Polygon(r) for r, _ in pockets])
        desc["pattern"] = pattern_of([Polygon(r) for r, _ in pockets])
        pdir, bdir = OUT / "pocketed", OUT / "blanks"
        pdir.mkdir(parents=True, exist_ok=True)
        bdir.mkdir(parents=True, exist_ok=True)
        cadio.save_step(solid, pdir / f"{_safe(name)}.step")
        face = pocketer.make_face(blank_profile, plate.frame)
        blank = BRepPrimAPI_MakePrism(face, gp_Vec(*(-plate.frame.n * plate.thickness))).Shape()
        cadio.save_step(blank, bdir / f"blank_{_safe(name)}.step")
        entry = {"name": name, "pockets": len(pockets), "holes": len(keep), "thickness": round(plate.thickness, 3),
                 "removed_pct": round(100 * desc.get("removed_frac", 0), 1), "pattern": desc["pattern"],
                 "sha": sha, "blank": f"blank_{_safe(name)}.step"}
        if analyse:
            from autopocket2 import fea2
            a = fea2.Analysis(blank_profile, plate.thickness)
            s = a.evaluate(plate.profile)
            entry["stiffness_kept_pct"] = round(100 * s["worst_stiffness_retained"], 1)
            desc["fea_stiffness_kept"] = s["worst_stiffness_retained"]
        if kb is not None:
            kb.add_style_ref(f"onshape:{name}", desc, source="onshape (hand-pocketed)")
        found.append(entry)
        print(f"    pocketed plate: {name}  {entry}")
    return found


# --------------------------------------------------------------------------- main

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--shared", action="store_true", help="also documents shared with you")
    ap.add_argument("--max-docs", type=int, default=0, help="stop after this many new documents (0 = all)")
    ap.add_argument("--analyse", action="store_true", help="FEA your designs against their blanks")
    ap.add_argument("--from-folder", help="process STEP files in this folder instead of Onshape")
    ap.add_argument("--no-learn", action="store_true", help="don't add anything to the knowledge base")
    a = ap.parse_args()

    from autopocket2.knowledge import KnowledgeBase
    kb = None if a.no_learn else KnowledgeBase()
    OUT.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    SEEN.update(e["sha"] for m in manifest.values() for e in m.get("pocketed", []) if e.get("sha"))
    found = []

    if a.from_folder:
        for p in sorted(Path(a.from_folder).glob("*.st*p")):
            print(p.name)
            found += process_step(p, p.stem, kb, a.analyse)
    else:
        api = Onshape()
        done = 0
        docs = list(api.documents(a.shared))
        docs = [d for d in docs if _score(d.get("name")) >= 0]
        docs.sort(key=lambda d: -_score(d.get("name")))  # robot-sounding documents first
        print(f"{len(docs)} documents to look through (parts libraries left out)", flush=True)

        def save():
            manifest_path.write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")

        for doc in docs:
            did, name = doc["id"], doc.get("name", doc["id"])
            ws = (doc.get("defaultWorkspace") or {}).get("id")
            stamp = doc.get("modifiedAt")
            if not ws or manifest.get(did, {}).get("modifiedAt") == stamp:
                continue
            print(f"{name}", flush=True)
            entries = []
            try:
                studios = [el for el in api.part_studios(did, ws) if _score(el.get("name")) >= 0]
                studios.sort(key=lambda el: -_score(el.get("name")))
                for el in studios:
                    try:
                        data = api.export_step(did, ws, el["id"])
                    except PermissionError:
                        raise
                    except Exception as e:
                        print(f"  {el.get('name')}: export failed ({e})")
                        continue
                    path = OUT / "tmp" / f"{_safe(name)}_{_safe(el.get('name', el['id']))}.step"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
                    print(f"  {el.get('name')}", flush=True)
                    entries += process_step(path, f"{name}_{el.get('name', el['id'])}", kb, a.analyse)
            except SystemExit:
                save()
                raise
            except Exception as e:  # blocked, rate-limited, broken: skip the whole document
                print(f"  skipped ({str(e)[:80]})", flush=True)
                manifest[did] = {"name": name, "modifiedAt": stamp, "pocketed": entries, "skipped": str(e)[:200]}
                save()
                found += entries
                continue
            manifest[did] = {"name": name, "modifiedAt": stamp, "pocketed": entries}
            save()
            found += entries
            done += 1
            if a.max_docs and done >= a.max_docs:
                break
        print(f"\n{api.calls} Onshape API calls used.")
    print(f"\nFound {len(found)} pocketed plates.")
    if kb is not None:
        print("Knowledge base:", kb.stats())


if __name__ == "__main__":
    main()
