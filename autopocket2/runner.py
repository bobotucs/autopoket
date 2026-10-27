"""v2 planner: generate -> geometry/DFM screen -> FEA -> prune -> rank feasible designs.

For every spacing a uniform truss, a load-guided truss and a CheeseIt-style isogrid (two
orientations) are built and checked against the hard rules
(validate.py) before any FEA is spent on it. Layouts that pass are analysed from both
clamp ends; while one still meets the stiffness target, its least-loaded ribs are pruned
and the result re-checked and re-analysed. Only designs that pass every hard check and
the stiffness target compete, on weight saved (lower peak stress breaks near-ties). If
none does, the stiffest design is offered and the report says what blocked the rest:
no rule is relaxed to get an answer. The winner is re-analysed on a finer mesh.

Rib width, tool radius and the clearance kept around every hole, outline side and corner
come from the caller (the web app's rules panel and feature picker); see features.py.

Learning: with a knowledge base (learning.py, knowledge.py) every design is recorded with
its evidence tier, the search order and grid come from what won on similar past plates, a
surrogate may skip FEA on designs it is confident miss the target, and near-ties are broken
by the user's learned style. Within each plate the spacing is bisected where a family
crosses the stiffness target, with or without a knowledge base.

Load model: with no hole roles the plate gets generic screening loads (clamped at either
end). When the user marks bolted mounts and loaded bearing bores, the FEA holds the plate
at the mounts and loads it at the bearings (fea2), so the layout guidance, rib pruning
and stiffness target all follow the plate's real load paths. Every input is reported
with where it came from (user, assumed, generic), and an absolute stress / deflection
estimate is given only when the user supplies a bearing load in newtons.
"""
from __future__ import annotations

import time
from collections import Counter

from shapely.geometry import Polygon
from shapely.ops import unary_union

from autopocket import cadio
from autopocket import runner as v1runner
from autopocket.pocketer import PlateRules, find_plate

from . import fea2, validate
from .features import Clearances, Domain
from .knowledge import FEA_FEASIBLE, FEA_INFEASIBLE, GEOMETRY_REJECTED, SURROGATE_SKIPPED, plate_sha
from .learning import Learner, candidate_features, style_of
from .layout import (GUIDE_BETA, SpacingField, absorb_squeezed, hex_layout, isogrid_layout, pocket_layout,
                     prune_ribs, voronoi_layout)

MATERIALS = v1runner.MATERIALS
SPACINGS = [24, 28] + v1runner.SPACINGS  # guidance widens pockets in quiet areas, so start tighter
ESO_STEPS = 3            # rib-pruning rounds per spacing
GUIDE_SMOOTH_MM = 25.0   # smoothing of the blank plate's energy field
NEAR_TIE_PCT = 0.3       # designs this close in weight saved are ranked by peak stress ...
STYLE_TIE_PCT = 1.0      # ... or, once the user's style is known, this close are ranked by style
REFINE_ROUNDS = 2        # spacing bisections per family where it crosses the stiffness target
FINE_CELLS = (18000, 48000)  # FE mesh for the finer-mesh check of the pick
MAX_FINE_CHECKS = 4      # picks tried on the finer mesh before giving up (and flagging it)
VERSION = "2.2"
# layout families tried at every spacing; none wins on every plate, so they compete
FAMILIES = ("truss", "guided", "isogrid", "isogrid-turned", "hex", "hex-turned", "voronoi", "voronoi-guided")
FAMILY_NAMES = {"truss": "triangle truss", "guided": "load-guided triangle truss", "isogrid": "isogrid",
                "isogrid-turned": "isogrid (turned 90°)", "hex": "hexagon", "hex-turned": "hexagon (turned 90°)",
                "voronoi": "Voronoi", "voronoi-guided": "load-guided Voronoi"}
FAMILY_LABELS = {"truss": "triangles", "guided": "triangles guided", "isogrid": "isogrid",
                 "isogrid-turned": "isogrid turned", "hex": "hexagon", "hex-turned": "hexagon turned",
                 "voronoi": "Voronoi", "voronoi-guided": "Voronoi guided"}
# the pattern picked in the app -> the families searched ("auto" = all, lightest that passes wins)
PATTERNS = {"auto": FAMILIES,
            "isogrid": ("isogrid", "isogrid-turned"),
            "triangles": ("truss", "guided"),
            "hexagon": ("hex", "hex-turned"),
            "voronoi": ("voronoi", "voronoi-guided")}
# bending-dominated webs (stiffer per gram as triangles): searched coarsely in "auto"
# unless they have won on similar plates before
SECONDARY = ("hex", "hex-turned", "voronoi", "voronoi-guided")
SMALL_CELLS = [16, 20]  # hexagon / Voronoi webs need smaller cells than triangles to stay as stiff


def _pocketed_profile(profile, outlines, r):
    pockets = validate.rounded(outlines, r)
    return profile.difference(unary_union(pockets)) if pockets else profile


def _evaluate(plates, analyses, lays, r, label, rejections, learner=None, target=None, meta=None, strict=True):
    """Screen and analyse one design (one layout per plate).

    Returns (candidate or None, record): the record says why there is no candidate (a hard
    rule, or the surrogate being confident it misses the target) for the knowledge base."""
    checks = []
    for p, lay in zip(plates, lays):
        val = validate.check(p.profile, lay.outlines, r, lay.dom)
        checks.append(val)
        if not val["ok"]:
            for k in val["failed"]:
                rejections[k] += 1
            if strict:
                return None, {"status": GEOMETRY_REJECTED, "failed": val["failed"]}
    if not any(lay.outlines for lay in lays):
        rejections["no_pockets_fit"] += 1
        return None, {"status": GEOMETRY_REJECTED, "failed": ["no_pockets_fit"]}
    feat = style = pred = None
    if learner is not None:
        feat, style = candidate_features(lays[0], *meta), style_of(lays[0])
        skip, pred = learner.screen(feat, target)
        if skip:
            rejections["surrogate_skip"] += 1
            return None, {"status": SURROGATE_SKIPPED, "features": feat, "style": style, "predicted": pred}
    v0 = v1 = 0.0
    n, holes, holes_ok = 0, 0, 0
    structure, energies = None, []
    for p, a, lay, val in zip(plates, analyses, lays, checks):
        h = val["checks"]["holes_supported"]
        holes_ok, holes = holes_ok + int(h["value"]), holes + int(h["limit"])
        prof = _pocketed_profile(p.profile, lay.outlines, r)
        v0 += p.profile.area * p.thickness
        v1 += prof.area * p.thickness
        n += len(lay.outlines)
        s = a.evaluate(prof, want_energy=True) if lay.outlines else None
        energies.append(s.pop("energy") if s else None)
        if s and (structure is None or s["worst_stiffness_retained"] < structure["worst_stiffness_retained"]):
            structure = s
    return {"label": label, "spacing": r.spacing, "rules": r.to_dict(), "pockets": n,
            "layouts": [lay.outlines for lay in lays], "holes": holes, "holes_supported": holes_ok,
            "lines": [[[list(map(float, q)) for q in ln.coords] for ln in lay.lines] for lay in lays],
            "mass_saved_pct": 100 * (1 - v1 / v0), "volume": [v0, v1], "structure": structure,
            "validation": checks, "_lays": lays, "_energy": energies,
            "_feat": feat, "_style": style, "_pred": pred}, {"status": None}


def _front(cands):
    """Designs no other design beats on both weight saved and stiffness."""
    def key(c):
        return c["mass_saved_pct"], c["structure"]["worst_stiffness_retained"]
    out = []
    for c in cands:
        m, s = key(c)
        if not any(key(o)[0] >= m and key(o)[1] >= s and key(o) != (m, s) for o in cands):
            out.append(c)
    return out


def plan(shape, material="Aluminum 6061-T6", target_stiffness=0.33, rules: PlateRules | None = None,
         progress=None, families=None, eso_steps=ESO_STEPS, verify=True, clearances=None, loads=None,
         knowledge=None, source="api", name=None, pattern="auto"):
    """Returns (plates, variants, best_index, diagnostics).

    `clearances`: one features.Clearances per plate (None = the rules' uniform clearance).
    `loads`: per plate {"mounts": [hole ids], "bearings": [hole ids], "force_n": N or None}
    (engineering mode on a plate that has both mounts and bearings).
    `knowledge`: a knowledge.KnowledgeBase to learn from and record into (None = no learning)."""
    t_start = time.time()
    say = progress or (lambda msg, frac: None)
    base = rules or PlateRules()
    sols = cadio.solids(shape)
    if not sols:
        raise ValueError("No solid bodies found in the file")
    plates = [find_plate(s) for s in sols]
    density = MATERIALS.get(material, MATERIALS["Aluminum 6061-T6"])["density"]
    say("Analysing the blank plate", 0.02)
    loads = list(loads or [])
    loads += [{}] * (len(plates) - len(loads))
    roles = [_roles(p, ld) for p, ld in zip(plates, loads)]
    analyses = [fea2.Analysis(p.profile, p.thickness, rib=base.rib, **rl) for p, rl in zip(plates, roles)]
    blank_fields = [a.field(a.blank_energy, smooth_mm=GUIDE_SMOOTH_MM) for a in analyses]
    clearances = list(clearances or [])
    clearances += [Clearances.from_rules(base)] * (len(plates) - len(clearances))
    doms = [Domain(p.profile, base, cl) for p, cl in zip(plates, clearances)]
    rejections, cands = Counter(), []
    families = families or PATTERNS.get(pattern, FAMILIES)
    learner = run_id = None
    if knowledge is not None:
        learner = Learner(knowledge, plates[0], doms[0], any(a.engineering for a in analyses))
        learner.plate_id = knowledge.plate_id(plate_sha(plates[0].profile, plates[0].thickness),
                                              name or "plate", plates[0].thickness, learner.pdesc)
        run_id = knowledge.start_run(learner.plate_id, len(plates), VERSION, source,
                                     {"rules": base.to_dict(), "clearances": [cl.to_dict() for cl in clearances],
                                      "loads": loads}, "engineering" if learner.pdesc["engineering"] else "generic",
                                     target_stiffness)

    def record(c, rec, fam, S, step, parent, label):
        if knowledge is None:
            return None
        if c is None:
            c = {"family": fam, "spacing": S, "eso_step": step, "label": label, "failed": rec.get("failed"),
                 "parent_db_id": parent}
            return knowledge.add_candidate(run_id, learner.plate_id, c, rec["status"], rec.get("features"),
                                           rec.get("style"), rec.get("predicted"))
        status = FEA_FEASIBLE if c["meets_target"] else FEA_INFEASIBLE
        return knowledge.add_candidate(run_id, learner.plate_id, c, status, c["_feat"], c["_style"], c["_pred"])

    def explore(fam, S):
        """One spacing of one family: the base layout, then (once) merging the leftovers squeezed
        against holes into proper pockets, then rib pruning, while it meets the target."""
        r = PlateRules(**{**base.to_dict(), "spacing": S})
        beta = GUIDE_BETA if fam in ("guided", "voronoi-guided") else 0.0
        lays = []
        for dom, f in zip(doms, blank_fields):
            sfn = SpacingField(S, f, dom.axes, dom.region, beta)
            if fam.startswith("isogrid"):
                lays.append(isogrid_layout(dom, r, sfn, turn=fam.endswith("turned")))
            elif fam.startswith("hex"):
                lays.append(hex_layout(dom, r, sfn, turn=fam.endswith("turned")))
            elif fam.startswith("voronoi"):
                lays.append(voronoi_layout(dom, r, sfn))
            else:
                lays.append(pocket_layout(dom, r, sfn))
        out, parent, merged, pruned, plain = [], None, False, 0, None
        for step in range(eso_steps + 2):
            label = (f"{S} mm {FAMILY_LABELS[fam]}".strip() + (" · merged" if merged else "")
                     + (f" · pruned ×{pruned}" if pruned else ""))
            c, rec = _evaluate(plates, analyses, lays, r, label, rejections, learner, target_stiffness, (fam, S, step))
            if c is None:
                record(None, rec, fam, S, step, parent, label)
            else:
                c["meets_target"] = c["structure"]["worst_stiffness_retained"] >= target_stiffness
                c.update(target=target_stiffness, eso_step=step, family=fam, parent_db_id=parent,
                         mass_g=[c["volume"][0] * density / 1000, c["volume"][1] * density / 1000])
                if learner is not None:
                    learner.learn(c["_feat"], c["structure"]["worst_stiffness_retained"])
                c["db_id"] = parent = record(c, None, fam, S, step, parent, label)
                cands.append(c)
                out.append(c)
            if c is None or not c["meets_target"]:
                if plain is None:
                    break
                # merging the leftovers cost a rib that carries load: prune the plain layout instead
                (lays, energy), merged, plain = plain, False, None
            elif pruned == eso_steps:
                break
            else:
                energy = c["_energy"]
                new = [absorb_squeezed(lay) or lay for lay in lays] if step == 0 else lays
                if any(x is not y for x, y in zip(new, lays)):
                    merged, plain, lays = True, (lays, energy), new
                    continue
                plain = None
            new = []
            for a, lay, e in zip(analyses, lays, energy):
                p = prune_ribs(lay, a.field(e, smooth_mm=r.rib / 2)) if e is not None else None
                new.append(p or lay)
            if all(x is y for x, y in zip(new, lays)):
                break
            pruned += 1
            lays = new
        for c in out:
            c.pop("_lays"), c.pop("_energy")
        return max((c["mass_saved_pct"] for c in out if c["meets_target"]), default=None)

    prior = learner.prior if learner else {"order": list(families), "coarse": [], "wins": {}}
    order = [f for f in prior["order"] if f in families] + [f for f in families if f not in prior["order"]]
    coarse = set(prior.get("coarse", []))
    if len(families) > 2:  # "auto": bending-dominated webs only get a full grid once they have won
        coarse |= {f for f in SECONDARY if not prior.get("wins", {}).get(f)}
    spacings = {f: (SMALL_CELLS + SPACINGS if f in SECONDARY else SPACINGS) for f in order}
    grid = {f: (spacings[f][::2] if f in coarse else spacings[f]) for f in order}
    total = sum(len(g) for g in grid.values()) + REFINE_ROUNDS * len(order)
    done, tried = 0, {f: {} for f in order}
    for fam in order:
        for S in grid[fam]:
            say(f"Trying {S} mm {FAMILY_NAMES[fam]}", 0.05 + 0.85 * done / total)
            done += 1
            tried[fam][S] = explore(fam, S)
    # within-plate search: bisect the spacing where each family crosses the stiffness target
    refined = 0
    for fam in order:
        for _ in range(REFINE_ROUNDS):
            Ss = sorted(tried[fam])
            good = [S for S in Ss if tried[fam][S] is not None]
            if not good:
                break
            # the widest spacing that still meets the target (the crossing) and the lightest
            # one so far (pruning can make a tighter grid win): bisect above each
            mids = []
            for best_S in dict.fromkeys([max(good), max(good, key=lambda S: tried[fam][S])]):
                i = Ss.index(best_S)
                if i + 1 < len(Ss) and Ss[i + 1] - best_S >= 4:
                    mid = int(round((best_S + Ss[i + 1]) / 2))
                    if mid not in tried[fam] and mid not in mids:
                        mids.append(mid)
            if not mids:
                break
            for mid in mids:
                say(f"Refining {FAMILY_NAMES[fam]} at {mid} mm", 0.05 + 0.85 * min(done, total - 1) / total)
                done += 1
                refined += 1
                tried[fam][mid] = explore(fam, mid)
    if not cands:
        why = ", ".join(f"{k} x{v}" for k, v in rejections.most_common()) or "no pockets fit"
        raise ValueError(f"No layout passes the hard rules ({why})")
    ok = sorted((c for c in cands if c["meets_target"]), key=lambda c: -c["mass_saved_pct"])
    styled = learner is not None and learner.pref.ok
    if ok:
        near = [c for c in ok if c["mass_saved_pct"] >= ok[0]["mass_saved_pct"] - (STYLE_TIE_PCT if styled else NEAR_TIE_PCT)]
        if styled:  # only designs that already pass everything compete on style
            for c in near:
                c["style_score"] = learner.style_score(c["_style"])
            near.sort(key=lambda c: (-(c["style_score"] if c["style_score"] is not None else -1e9),
                                     c["structure"]["worst_peak_stress_ratio"]))
        else:
            near.sort(key=lambda c: c["structure"]["worst_peak_stress_ratio"])
        ranked = near + [c for c in ok if c not in near]
    else:
        ranked = [max(cands, key=lambda c: c["structure"]["worst_stiffness_retained"])]
    best = ranked[0]
    if verify:
        # the pick has to hold on a ~3x finer mesh too; if not, fall back to the next one
        say("Checking the result on a finer mesh", 0.92)
        fine = [fea2.Analysis(p.profile, p.thickness, *FINE_CELLS, rib=base.rib, **rl)
                for p, rl in zip(plates, roles)]
        for c in ranked[:MAX_FINE_CHECKS]:
            c["convergence"] = mesh_check(plates, c, fine)
            if knowledge is not None and c.get("db_id"):
                knowledge.set_fine(c["db_id"], c["convergence"]["fine_stiffness"])
            if not c["meets_target"] or c["convergence"]["fine_stiffness"] >= target_stiffness:
                best = c
                break
    for c in cands:
        for k in ("_feat", "_style", "_pred"):
            c.pop(k, None)
    variants = _front(cands)
    if best not in variants:
        variants.append(best)
    variants.sort(key=lambda c: c["mass_saved_pct"])
    best_i = variants.index(best)
    diag = {"candidates_evaluated": len(cands), "rejections": dict(rejections), "pattern": pattern,
            "feasible": len(ok), "families": list(families), "eso_steps": eso_steps,
            "clearances": [cl.to_dict() for cl in clearances],
            "custom_clearances": sum(cl.custom for cl in clearances),
            "load_model": load_model(analyses, roles, loads), "refined_spacings": refined,
            "run_id": run_id, "learning": learner.summary() if learner else None}
    if knowledge is not None:
        knowledge.finish_run(run_id, best.get("db_id"), time.time() - t_start, diag["learning"])
    return plates, variants, best_i, diag


def _roles(plate, ld):
    holes = list(plate.profile.interiors)

    def pick(ids):
        return [Polygon(holes[i]) for i in sorted({int(i) for i in ids or []}) if 0 <= i < len(holes)]
    dirs = [(d.get("label", "Applied"), d["v"]) for d in (ld.get("dirs") or []) if d.get("v")]
    return {"mounts": pick(ld.get("mounts")), "bearings": pick(ld.get("bearings")), "dirs": dirs or None}


def load_model(analyses, roles, loads):
    """What the structural check assumed, and where each input came from."""
    eng = any(a.engineering for a in analyses)
    force = next((float(ld["force_n"]) for ld in loads if ld.get("force_n")), None)
    if not eng:
        return {"mode": "generic",
                "summary": "Generic screening loads: plate clamped at either end of its long side, bent both ways "
                           "and twisted. Mark bolted mounts and loaded bearings for an engineering check.",
                "inputs": {"supports": "assumed (end clamp)", "loads": "assumed (unit loads at the far end)"}}
    dirs = next((r["dirs"] for r in roles if r.get("dirs")), None)
    purpose = next((ld.get("purpose") for ld in loads if ld.get("purpose")), None)
    where = ", ".join(lbl for lbl, _ in dirs) if dirs else None
    return {"mode": "engineering", "purpose": purpose, "directions": where,
            "mounts": sum(len(r["mounts"]) for r in roles), "bearings": sum(len(r["bearings"]) for r in roles),
            "force_n": force,
            "summary": (f"{purpose.capitalize() + ': h' if purpose else 'H'}eld at the support holes; "
                        + (f"load applied {where} through the load holes, shared between them."
                           if dirs else "each load hole pushed in 4 in-plane directions and out of plane.")),
            "inputs": {"supports": f"user-specified holes, held fixed over a {fea2.WASHER_MM:g} mm washer ring (assumed)",
                       "load location": "user-specified load holes",
                       "load direction": f"user-specified: {where}" if dirs else "every direction checked (assumed envelope)",
                       "load size": (f"user-specified, {force:g} N" + (" in total, shared by the load holes" if dirs
                                                                       else " on each load hole"))
                       if force else "not given: relative results only"}}


def screening(variant, material, force_n):
    """Absolute stress / deflection for the user's bearing load (worst plate, worst case)."""
    if not force_n:
        return None
    m = MATERIALS[material]
    E = m["E"] * 1000.0  # MPa
    cs = variant["structure"]["cases"]
    worst = max(cs, key=lambda c: c["compliance"])
    hot = max(cs, key=lambda c: c["p99"])
    stress = hot["p99"] * force_n
    return {"force_n": force_n,
            "max_deflection_mm": worst["compliance"] * force_n / E,
            "max_deflection_blank_mm": worst["compliance_blank"] * force_n / E,
            "deflection_case": worst["case"],
            "peak_stress_mpa": stress, "peak_stress_blank_mpa": hot["p99_blank"] * force_n,
            "stress_case": hot["case"],
            "safety_factor": m["strength"] / stress if stress > 0 else None,
            "note": "Screening estimate from a coarse raster FEA (99th-percentile stress away from the supports "
                    "and loaded bores, idealised fixed mounts). Not a certified analysis."}


def edit_design(plates, variant, lines, clearances=None, loads=None, target=0.33, mirror=True):
    """A design rebuilt from the user's own rib lines (the Edit view).

    `lines`: per plate, a list of rib centre lines [[x, y], [x, y], ...] in the plate frame.
    With `mirror`, every line is mirrored onto the plate's symmetry axes too. Pockets are cut
    from the lines exactly as for generated designs (tool radius, blunt tips, clearances);
    the hard rules are checked and reported but don't reject the design, so the user can
    see what an edit breaks. Returns a candidate like plan()'s variants."""
    import numpy as np
    from shapely.geometry import LineString
    from .layout import Layout
    r = PlateRules(**variant["rules"])
    clearances = list(clearances or []) + [Clearances.from_rules(r)] * len(plates)
    loads = list(loads or []) + [{}] * len(plates)
    lays, analyses = [], []
    for p, ls, cl, ld in zip(plates, lines, clearances, loads):
        dom = Domain(p.profile, r, cl)
        segs = [LineString(seg) for seg in ls if len(seg) >= 2 and LineString(seg).length > 1.0]
        lay = Layout(dom, r, segs, np.zeros((0, 2)), SpacingField(r.spacing))
        if mirror and dom.axes:
            lay.lines = lay.mirrored(lay.lines)
            lay.rebuild()
        lays.append(lay)
        analyses.append(fea2.Analysis(p.profile, p.thickness, rib=r.rib, **_roles(p, ld)))
    c, _ = _evaluate(plates, analyses, lays, r, "Your edit", Counter(), strict=False)
    if c is None:
        raise ValueError("No pockets fit between those lines")
    for k in ("_lays", "_energy", "_feat", "_style", "_pred"):
        c.pop(k, None)
    density = MATERIALS["Aluminum 6061-T6"]["density"]
    c.update(meets_target=c["structure"]["worst_stiffness_retained"] >= target, target=target, eso_step=0,
             family="edit", mass_g=[c["volume"][0] * density / 1000, c["volume"][1] * density / 1000],
             failed=sorted({f for v in c["validation"] for f in v["failed"]}))
    return c, lays


def simulate(plates, variant, loads=None):
    """Per plate: high-resolution results of the original and the pocketed plate under the
    run's load cases (simview), plus where it is held and loaded, for drawing."""
    from . import simview
    r = PlateRules(**variant["rules"])
    loads = list(loads or []) + [{}] * len(plates)
    out = []
    for p, outlines, ld in zip(plates, variant["layouts"], loads):
        rl = _roles(p, ld)
        a = fea2.Analysis(p.profile, p.thickness, *simview.SIM_CELLS, rib=r.rib, **rl)
        pocketed = _pocketed_profile(p.profile, outlines, r)
        out.append({"engineering": a.engineering, "thickness": p.thickness, "rib": r.rib,
                    "profiles": {"original": p.profile, "pocketed": pocketed},
                    "original": simview.results(a, p.profile), "pocketed": simview.results(a, pocketed),
                    "supports": [list(h.centroid.coords[0]) for h in rl["mounts"]] if a.engineering else [],
                    "loads": [list(h.centroid.coords[0]) for h in rl["bearings"]] if a.engineering else [],
                    "dirs": [[lbl, list(v)] for lbl, v in (rl["dirs"] or [])] if a.engineering else []})
    return out


def cut_order(plates, variant, tol=0.15):
    """Per plate: the rounded pocket outlines in a machining order (nearest pocket next)."""
    import numpy as np
    r = PlateRules(**variant["rules"])
    out = []
    for p, outlines in zip(plates, variant["layouts"]):
        pockets = [q.simplify(tol) for q in validate.rounded(outlines, r) if not q.is_empty]
        pockets = [q for q in pockets if q.geom_type == "Polygon"]
        x0, y0 = p.profile.bounds[:2]
        here, order = np.array([x0, y0]), []
        left = list(range(len(pockets)))
        while left:
            k = min(left, key=lambda i: np.linalg.norm(np.array(pockets[i].exterior.coords[0]) - here))
            left.remove(k)
            order.append(k)
            here = np.array(pockets[k].exterior.coords[0])
        out.append([[[round(x, 3), round(y, 3)] for x, y in pockets[k].exterior.coords] for k in order])
    return out


def mesh_check(plates, variant, analyses):
    """Re-run a design on a ~3x finer FE mesh (a mesh-convergence spot check)."""
    r = PlateRules(**variant["rules"])
    worst = None
    for p, a, outlines in zip(plates, analyses, variant["layouts"]):
        s = a.evaluate(_pocketed_profile(p.profile, outlines, r))
        if worst is None or s["worst_stiffness_retained"] < worst["worst_stiffness_retained"]:
            worst = s
    coarse = variant["structure"]["worst_stiffness_retained"]
    fine = worst["worst_stiffness_retained"]
    return {"coarse_stiffness": coarse, "fine_stiffness": fine, "fine_cells": worst["cells"],
            "difference_pct": 100 * (fine - coarse) / max(coarse, 1e-9)}


def build(plates, variant):
    """Cut the variant's pockets (v1's CAD code) and check the solid. Returns (shape, n, cad_check)."""
    shape, n = v1runner.build(plates, variant)
    r = PlateRules(**variant["rules"])
    want = sum(_pocketed_profile(p.profile, o, r).area * p.thickness for p, o in zip(plates, variant["layouts"]))
    got = cadio.volume(shape)
    uniform = not any(p.warnings and "uniform" in " ".join(p.warnings) for p in plates)
    expected_n = sum(len(o) for o in variant["layouts"])
    ok = n == expected_n and (not uniform or abs(got - want) <= 0.01 * want)
    return shape, n, {"ok": ok, "pockets_cut": n, "pockets_planned": expected_n,
                      "volume_mm3": got, "volume_expected_mm3": want, "checked_volume": uniform}


def status(variant, cad=None):
    """Furthest evidence level reached; each needs the previous one."""
    if not all(v["ok"] for v in variant["validation"]):
        return "PREVIEW_ONLY"
    s = "DFM_PASS"
    if cad is not None:
        if not cad["ok"]:
            return "PREVIEW_ONLY"
        s = "CAD_VALID + DFM_PASS"
    cv = variant.get("convergence")
    if variant["meets_target"]:
        # with a finer-mesh check on record, it has to hold there too
        if cv and cv["fine_stiffness"] < variant["target"]:
            return s + " (stiffness target missed on the finer mesh)"
        s += " + ANALYSIS_PASS"
    return s


def report(plates, variants, chosen, material, target_stiffness, shape_out, t0, diag=None, cad=None):
    density = MATERIALS[material]["density"]
    v0 = sum(cadio.volume(p.solid) for p in plates)
    v1 = cadio.volume(shape_out)
    v = variants[chosen]
    lm = (diag or {}).get("load_model") or {}
    return {
        "version": VERSION,
        "material": material,
        "material_props": MATERIALS[material],
        "thickness_mm": [round(p.thickness, 3) for p in plates],
        "volume_mm3": [v0, v1],
        "mass_g": [v0 * density / 1000, v1 * density / 1000],
        "mass_saved_g": (v0 - v1) * density / 1000,
        "mass_saved_pct": 100 * (1 - v1 / v0),
        "pockets": v["pockets"],
        "spacing": v["label"],
        "holes": v["holes"],
        "holes_supported": v["holes_supported"],
        "structure": v["structure"],
        "target_stiffness": target_stiffness,
        "meets_target": v["meets_target"],
        "rules": v["rules"],
        "chosen": chosen,
        "status": status(v, cad),
        "failed_rules": sorted({f for x in v["validation"] for f in x["failed"]}),
        "validation": v["validation"],
        "cad_check": cad,
        "convergence": v.get("convergence"),
        "diagnostics": diag,
        "load_model": lm,
        "learning": (diag or {}).get("learning"),
        "screening": screening(v, material, lm.get("force_n")) if lm.get("mode") == "engineering" else None,
        "variants": [{k: x[k] for k in ("spacing", "label", "pockets", "mass_saved_pct", "meets_target", "eso_step")}
                     | {"stiffness": x["structure"]["worst_stiffness_retained"],
                        "stress": x["structure"]["worst_peak_stress_ratio"]} for x in variants],
        "warnings": sorted({w for p in plates for w in p.warnings}),
        "seconds": time.time() - t0,
    }


def run(shape, material="Aluminum 6061-T6", target_stiffness=0.33, progress=None, variant=None,
        rules: PlateRules | None = None, clearances=None, loads=None, knowledge=None, source="api", name=None,
        pattern="auto"):
    """Plan, pick the best (or the requested) variant, cut it. Returns dict(shape, report, ...)."""
    t0 = time.time()
    plates, variants, best, diag = plan(shape, material, target_stiffness, rules, progress=progress,
                                        clearances=clearances, loads=loads, knowledge=knowledge,
                                        source=source, name=name, pattern=pattern)
    chosen = best if variant is None else variant
    if progress:
        progress("Cutting pockets", 0.97)
    out, _, cad = build(plates, variants[chosen])
    return {"shape": out, "plates": plates, "variants": variants, "best": best, "diagnostics": diag,
            "cad_check": cad,
            "report": report(plates, variants, chosen, material, target_stiffness, out, t0, diag, cad)}
