# Manufacturability, CAD Formats and Student-Facing Input Design for an FTC Plate-Lightening Tool (0.125 in 6061-T6)

Scope: what geometry a web lightening tool must output so FTC teams can laser cut, CNC route or CNC mill flat 1/8 in 6061-T6 plates; which file formats and libraries to use; how existing CAD lightening tools expose their controls; and how a novice-friendly UI should collect inputs and keep geometry-only results separate from engineering-analysed ones. Researched 2026-10-22. Where a vendor publishes a number it is quoted as published. Anything derived, such as "50% of 0.125 in = 0.0625 in", is marked as derived or put under Inferences.

---

## Q1. Manufacturing rules for 1/8 in aluminium: CNC routing/milling on hobby/school machines, laser/waterjet, and send-out service guidelines

### Takeaway
For 1/8 in 6061, the binding constraints come from the process. A 1/8 in end mill can't make an internal corner tighter than about 0.063 in radius, and vendors advise adding 0.02–0.05 in more so the tool doesn't stall in the corner. Send-out laser services publish small minimum features, but their recommended webs and hole-to-edge distances are roughly 1–2x material thickness (about 0.125–0.25 in). Vendors disagree on the exact minimums, so the tool should expose per-process presets rather than one hard-coded rule.

### Cited Findings

**SendCutSend (SCS): general sheet-cutting rules**
- Minimum hole/cutout size by process: laser "at least 50% of material thickness"; waterjet ".070"" for most materials; CNC routing ".125"" (bit diameter) for all holes. — [SCS Sheet Cutting Guidelines](https://sendcutsend.com/guidelines/sheet-cutting/)
- Internal corner radius by process: laser about the kerf width (no number given); waterjet ".032"" (stream diameter); CNC routing ".063"" (radius of a 0.125" bit). Routed dogbone corners are 0.063" radius. — [SCS Sheet Cutting Guidelines](https://sendcutsend.com/guidelines/sheet-cutting/)
- SCS routes with a 0.125" bit, "so allow for a radius of .063" on all internal geometry and minimum hole size of .125"". Outside corners can stay sharp. — [SCS CNC routing guidelines (search summary)](https://sendcutsend.com/CNC-guidelines); [SCS FAQ: smaller router bit](https://sendcutsend.com/faq/can-you-use-a-smaller-cnc-router-bit-size-for-my-parts/)
- SCS's CNC *machining* (milling) guide gives a minimum internal radius of ".0625" or 1.587mm" and a smallest drill of ".0629"". — [SCS CNC machining guidelines (search summary)](https://sendcutsend.com/guidelines/cnc-machining/)
- CNC routing tabs are "about 0.1875" wide", with depth equal to half the material thickness. Tab placement needs at least 0.400" between nodes on the part edge, and material removal must stay under 50%. The routing max-size list names only Delrin, ABS, ACM, HDPE, MDF, plywood and UHMW, so routing there appears to be for non-metals. — [SCS Sheet Cutting Guidelines](https://sendcutsend.com/guidelines/sheet-cutting/)
- Bridges and holes: the minimum is "no less than 50% of the material thickness", and the recommended width for strength is "closer to 1X – 1.5X the material thickness". Keep holes "at least 1X their diameter from an edge" and slots at least 1.5x their width from edges or other cuts. Laser tolerance is "+/- .005″" for most materials. — [SCS: Basic Tolerances and Cut Feature Relationships](https://sendcutsend.com/?p=89747)
- "No geometry should ever be smaller than .015”", and holes or cuts should be "50% of your material thickness or greater". — [SCS FAQ: minimum geometry](https://sendcutsend.com/faq/what-are-best-practices-for-minimum-geometry/)
- **SCS 6061-specific page** (conflicts with the 50% rule above): "Design holes no smaller than material thickness" (derived: 0.125" minimum hole for 1/8" stock) and "Keep holes and cutouts 1.5–2× material thickness away from edges to prevent warping or distortion" (derived: 0.1875–0.25" for 1/8"). SCS laser cuts 6061 to "±.005” tolerance". Instant-pricing part size runs from ".25" x .375" min" to 30" x 44" max. The page is internally inconsistent on custom-quote maximum size. — [SCS 6061 aluminum material page](https://sendcutsend.com/materials/6061-aluminum/)
- Worked example in an SCS blog (0.375" 5052, not 1/8" 6061): min bridge 0.143" and min hole-to-edge 0.113". To check a DXF, offset each path by the minimum value in QCAD and look for crossings. — [SCS blog: measuring cut geometry in QCAD](https://sendcutsend.com/blog/how-to-measure-cut-geometry-specifications-using-qcad/)
- Tapping example: 0.125" 5052 shows a tapping minimum hole-to-edge of 0.063" (5052, not 6061). — [SCS blog: hole distance specifications (search summary)](https://sendcutsend.com/blog/how-to-apply-hole-distance-specifications/)
- I could not retrieve SCS's 0.125" 6061 "View Specs" table, which gives exact tested min hole and min bridge values. — [SCS search results](https://sendcutsend.com/services/laser-cutting/examples/)

**Fabworks (named by gm0 as an FTC-used service)**
- 6061-T6 at 0.125": thickness tolerance "+/- 0.007"", min part size "0.25" x 0.25"", max part size "96" x 48"", **min feature size "0.04"**". 5052-H32 has identical values. The table also has a "Bending" column showing 0.04". The page doesn't define it, and it may be a mis-parse. — [Fabworks aluminum materials page](https://www.fabworks.com/resources/materials/sheet/aluminum)
- Sheet laser tolerance is "+/-0.005"" across the whole part (most parts come out around ±0.002"). No kerf compensation is needed in files. Hardware holes should be modelled at callout size, and Fabworks resizes them to press-fit size. — [Fabworks Sheet Laser Cutting Guidelines](https://www.fabworks.com/resources/guidelines/laser-cutting/sheet)
- Fabworks publishes no sheet hole-to-edge or web rule on these pages. — [Fabworks Sheet Laser Cutting Guidelines](https://www.fabworks.com/resources/guidelines/laser-cutting/sheet)

**Protocase**
- "We cannot cut dense vent or cutout patterns on our laser without causing the metal to warp. If a part requires such a pattern, we can mill it out of Aluminum on our Router table." This bears directly on heavy lightening patterns. — [Protocase FAQ: cutouts (search summary)](https://www.protocase.com/resources/faq/cutouts)
- CNC wall rule of thumb: "a minimum width of 60 thou" (0.06 in). A 0.06 in wall "1/8 in high and 1 in long 'probably won't be a problem'", but the same wall 1.5 in high and 5 in long may cause trouble. Thin walls raise vibration risk and can move during machining, leaving the part outside the ±0.005 in tolerance. — [Protocase blog: Wall thickness for CNC machined parts](https://www.protocase.com/blog/2024/03/06/wall-thickness-for-cnc-machined-parts/)
- I could not extract Protocase's published laser min-hole or edge-distance numbers. The URC design tips PDF was unreadable to the fetch tool. — [Protocase URC design tips PDF](https://www.protocase.com/pdf/urc/URC-DESIGN-TIPS-2018.pdf)

**Other shops (general rules of thumb, not FTC-specific)**
- Xometry sheet cutting: minimum hole-to-edge "2X MT or 0.125", whichever is smaller"; minimum hole-to-hole "6X MT or 0.125", whichever is smaller"; minimum corner fillets "0.5X MT or 0.125", whichever is smaller". — [Xometry laser/sheet cutting design guide (search summary)](https://www.xometry.com/resources/design-guides/design-guide-laser-and-sheet-cutting/)
- LaserBoost: for aluminium, minimum hole diameter equals sheet thickness, and minimum spacing between cut shapes is half the thickness. — [LaserBoost guide (search summary)](https://www.laserboost.com/wp-content/uploads/2022/02/Guia-EN_.pdf)
- Fabcon: hole-to-edge at least 1x thickness, 1.5x preferred to reduce distortion. — [Fabcon DFM guidelines (search summary)](https://fabcon.com/articles/?p=311)

**CNC milling/routing corner and wall guidance**
- Xometry recommends modelling internal corner radii "with at least 0.02″ – 0.05″ added" to the tool radius (for example 0.27–0.30″ for a 0.25″ tool radius). A radius equal to the tool's forces a stop-and-pivot, which "slows down machining speed (adding costs)" and "causes vibration, which creates chatter marks". — [Xometry: Optimizing internal corner radii](https://www.xometry.com/resources/machining/cnc-machining-optimizing-internal-corner-radii/)
- An alternative rule: internal radius at least 30% larger than the tool radius. Where the corner is still tight, reduce feed 30–50% depending on the tool-radius-to-part-radius ratio. — [MachineMFG: internal corner radii (search summary)](https://shop.machinemfg.com/optimizing-internal-corner-radii-in-cnc-machining). This conflicts slightly with Xometry's fixed +0.02–0.05″ allowance.
- Metal CNC minimum wall figures: RichConn gives 0.8 mm (0.5 mm possible in aluminium with good process control). Protolabs (turning) says walls under 0.020 in (0.5 mm) "typically do not survive". — [RichConn (search summary)](https://richconn.com/cnc-machining-wall-thickness/); [Protolabs turning guidelines (search summary)](https://www.protolabs.com/services/cnc-machining/cnc-turning/design-guidelines/)

**Hobby-router feeds for 1/8 in end mills in aluminium (forum data only, not manufacturer data)**
- Shapeoko users report a Carbide Create default of 0.015" depth per pass at 48 IPM for 1/8" sheet. Another user advised 0.010" if the sheet isn't 6061, with WD-40 or an air blast ready. — [Carbide 3D community: Cutting 1/8" aluminum](https://community.carbide3d.com/t/cutting-1-8-aluminum/33837)
- One Shapeoko data point: 500 mm/min, 0.3 mm per pass, 1-flute 1/8" carbide, DW611 router at speed 3. A ribbon-style single flute meant for plastics broke easily, and forum responders recommended a sturdier, shorter-flute single flute (Carbide 3D #274Z). — [Carbide 3D community (search summary)](https://community.carbide3d.com/t/yet-another-help-request-with-aluminum/86151)
- Onsrud tech support (relayed on a forum) advised about 8,000 RPM at 0.003–0.005" chip load per flute, saying many router owners run aluminium at too high an RPM. — [Signs101 forum (search summary)](https://www.signs101.com/threads/speeds-and-feeds-for-alum.83724)
- On an Onefinity forum, users favoured a single-flute upcut for aluminium. — [Onefinity forum (search summary)](https://forum.onefinitycnc.com/t/which-end-mills-are-best-for-aluminum/6608)

**Laser and waterjet in the FTC context**
- gm0: CO2 lasers, the type commonly available to FTC teams, "can only mark metal". Fiber lasers "can cut metal", but "These are very expensive and few FTC teams have access to them." gm0 recommends services such as Fabworks or SendCutSend. — [gm0 Laser Cutting](https://gm0.org/en/latest/docs/custom-manufacturing/laser-cutting.html)
- gm0: "Most laser cutting software does not account for the width of the laser beam". Teams needing precise hole sizes must offset paths manually or check with their service: "Check with the service you are using before you make these adjustments!" — [gm0 Laser Cutting](https://gm0.org/en/latest/docs/custom-manufacturing/laser-cutting.html)
- Fiber laser cutting of 2 mm AA6061 (peer-reviewed): roughness about 3 μm, dross under 0.1 mm, minimum heat-affected zone width about 10 μm. — [Chinese Journal of Lasers 41(6) 603004 (2014)](https://www.researching.cn/articles/OJ5cee517ea40c42a1)

### Inferences
- **Suggested per-process presets for 1/8 in 6061.** These are derived from the citations above; vendor-confirmed numbers are noted in brackets.
  - *Send-out fiber laser (SCS/Fabworks)*: min hole 0.125 in [SCS 6061 page; Fabworks would allow 0.04 in features]. Min rib/bridge 0.125 in (1x t) as the default, 0.0625 in absolute floor [SCS 50% rule]. Hole/pocket-to-edge 0.1875–0.25 in [SCS 6061 page: 1.5–2x t]. Internal corner fillet: anything above about 0.02 in is cuttable. For the user's "no acute wedge tips" aesthetic, a fillet of 0.0625 in or more still makes sense.
  - *School CNC router with a 1/8 in end mill*: min internal corner radius 0.0625 in (tool radius) as the hard floor, 0.08–0.11 in recommended [tool radius + 0.02–0.05 in, Xometry]. Min pocket/slot width must exceed the tool diameter (0.125 in). In practice it should be noticeably wider so the tool isn't slotting in a 1:1 channel; this point is an inference, not sourced. Min rib about 0.06 in is machinable at 1/8 in height [Protocase], but 0.125 in or more is safer for strength and hand finishing. Leave room for tabs or screws: SCS-style tabs are 0.1875 in wide and need 0.4 in of straight edge [SCS, routed non-metals].
  - *Waterjet*: internal radius about 0.032 in and min hole about 0.070 in [SCS].
- The tool should derive the pocket fillet radius from `max(process_min_radius, tool_radius + margin)` rather than ask novices for a fillet number directly.
- Dense lightening patterns can warp thin aluminium on a laser [Protocase]. This argues for a "max material removal" or "max pocket density" warning per process, mirroring SCS's "material removal must stay under 50%" rule for routed parts.
- Vendor rules conflict: hole-to-edge is 1x hole diameter (SCS blog), 1.5–2x t (SCS 6061 page), or 2x t / 0.125 in (Xometry). The UI should therefore label every preset with its source and let the user override it.

### Gaps
- SCS's exact tested min hole and min bridge for 0.125 in 6061 (its "View Specs" table) could not be retrieved; the SCS PDF found (5.2.pdf) was not text-extractable.
- No manufacturer feeds/speeds or DFM docs were found for Omio, Onefinity, Avid or Tormach, only community forum numbers for Shapeoko/Onefinity. End-mill-maker (Harvey, Onsrud) recommendations for minimum slot width or rib width in 1/8 in aluminium were not found in primary form.
- No published kerf width for 1/8 in 6061 at SCS/Fabworks. Fabworks says no compensation is needed, which implies the service handles kerf.
- No source found for laser heat effects on thin ribs specifically, such as ribs under 0.1 in in 1/8 in 6061.

---

## Q2. What FTC teams commonly use for rib width and edge offsets; goBILDA/REV patterns

### Takeaway
I found no FTC/FRC community source giving standard numeric rib widths or edge offsets. Teams size ribs "by feel" or "until it looks decent", using construction circles or offsets around holes and tangent lines between load points. gm0 recommends laser/waterjet for pocketing plates and adding rounds to every corner. goBILDA's 4 mm-on-8 mm hole grid is the main kit pattern a tool should recognise.

### Cited Findings
- gm0 Pocketing Guide method: construction circles around bearing and screw holes, joined by tangent lines and driven by one or two offset values. "The offset values determine the thickness of the remaining material." "Ideally all of the construction circles are one of less than 4 sizes to keep the pocketing consistent and simple." "The last step in pocketing is adding rounds to each and every corner, especially inner corners." "A very important tip to pocketing is to do it last when designing a part." — [gm0 CAD Tutorial Part 2: Pocketing Guide](https://gm0.org/en/latest/docs/design-skills/cad-tutorials.html#cad-tutorial-part-2-pocketing-guide)
- gm0: "CNC milling and routing excel at pocketing aluminum box tubing" while "water jet and laser cutting excel at pocketing plates". "routers and mills are able to make surface pockets" (more rigid but slower). The guide warns against removing too much because plates become less sturdy. — [gm0 CAD Tutorials](https://gm0.org/en/latest/docs/design-skills/cad-tutorials.html)
- gm0 materials guide suggests 1/8" or 3/16" sheet aluminium for drivetrain plates and warns that sheet "will bend if not supported correctly with standoffs or channel". — [gm0 Materials Guide (search summary)](https://gm0.org/en/latest/docs/custom-manufacturing/materials-guide.html)
- Pocketing is "removing unneeded material from a CAD-designed part" to lighten it, and can reduce stress concentrations at corners. — [gm0 Glossary (search summary)](https://gm0.org/en/stable/docs/appendix/glossary.html)
- FRC practice (Chief Delphi): "Pocketed plates are often done based on feel, as proper stress analysis on the plates is not worth the build-season time." "Struts typically get placed such that they are loading in pure tension and compression." Teams use 1/8" for large sheet components and 1/4" for gearbox plates; plates under bending "typically need to be much thicker, with .25 and 3/16ths being common". — [Chief Delphi: Aluminum Minimum Width Help](https://www.chiefdelphi.com/t/aluminum-minimum-width-help/458606)
- FRC workflow: "We start with the plate without any lightening, then draw lines where we need there to be aluminum to support everything", then apply a lightening FeatureScript. Another user: "I draw lines between all critical load areas and fuss with the widths until it looks decent". He also recommends direct load-bearing members between every gear/pulley/sprocket pair to hold center distance. Diminishing returns: "At a certain point you are better off going with a thinner plate (1/8" instead of 1/4")." — [Chief Delphi: CAD part weight reduction](https://www.chiefdelphi.com/t/cad-part-weight-reduction/441210)
- One poster says pocketing thin-wall material (0.09" and thinner) saves very little weight. — [Chief Delphi: FRC pocketing (search summary)](https://www.chiefdelphi.com/t/frc-pocketing/146081)
- goBILDA "is based on metric measurements using M4 hardware. The hole pattern has 4mm holes on 8mm grid." goBILDA "is able to interface with TETRIX channel because they share some holes" and is "quite compatible with REV's ecosystem". — [gm0 goBILDA](https://gm0.org/en/latest/docs/hardware-components/kit-and-hardware-guide/gobilda.html)

### Inferences
- "Offset around each hole + tangent struts between load points + fillet every corner" is the canonical community method (gm0, Chief Delphi). A tool that automates it, letting users override the per-hole offset ("halo") and strut width, matches how students already think.
- Since teams size ribs by eye, the tool's default rib width should be a manufacturability-driven number (for example 1x–1.5x t, 0.125–0.1875 in per SCS's strength recommendation) labelled as an assumption, not as an engineering result.
- The 8 mm goBILDA grid means a plate full of goBILDA-pattern holes leaves little room for pockets. Default per-hole protection should keep 4 mm holes on an 8 mm pitch from being isolated. Detecting a goBILDA grid and treating it as a protected region is a useful preset (inference).

### Gaps
- No published numeric rib or edge-offset standard from gm0, goBILDA, REV or specific FTC teams was found. goBILDA/REV plates' own lightening-pattern dimensions were not retrieved.
- I didn't search frcdesign.org directly; its pocketing guidance did not show up in results.

---

## Q3. How Onshape Lighten and community pocketing FeatureScripts work, plus Fusion/SolidWorks/Inspire equivalents and the controls users value

### Takeaway
Onshape's Lighten FeatureScript is region-based. The user draws a helper sketch dividing the plate into closed loops, picks each face, and the script offsets inward and fillets. Users find the helper sketch tedious and generation slow. Newer scripts (Enlighten, CheeseIt!, Engineering Grid) add per-hole halo selection, separate wall thicknesses (outer wall, inner walls, ribs, hole walls), auto-correction that skips unfilletable regions, and better error visualisation. Fusion and SolidWorks generative/topology tools expose preserve/obstacle regions, minimum wall thickness, minimum tool diameter and symmetry, which are the engineering-mode analogues.

### Cited Findings
**Onshape Lighten (FRC/FTC standard)**
- "The Lighten featurescript is based on selecting faces to remove the center from", so the helper sketch "needs to divide the part you're lightening into a number of closed loops". Making it takes "a good amount of copying geometry from other sketches" and "you need to individually select each loop". The proposed improvement would "hollow out everything except for a certain distance from every interior and exterior edge". Mounting holes don't need connecting to the outside edge. — [Chief Delphi: Some Helpful Featurescripts #139 (AriMB, 2020)](https://www.chiefdelphi.com/t/some-helpful-featurescripts/361652/139)
- Suggested workaround: project the plate's details into the sketch, draw webs hole to hole, and extend them to the outer profile. The "trim faces with parts" option controls how material around holes and the outer profile is thinned. In one troubleshooting reply, "filet radius looks kinda high". — [Chief Delphi search summary of lightening threads](https://www.chiefdelphi.com/t/some-helpful-featurescripts/361652?page=7)
- Lighten has been credited to Onshape developer ilya_baran (the community also calls it "Julia's Lighten FS"). He reportedly said it "works by doing a number of offsets (on the entire extruded face) among other operations", which is why text can make it fail. A known error is "Could not compute offset". These are search snippets from Onshape forum pages that require login, so I couldn't verify them directly. — [Onshape forum (search result, not fetched)](https://forum.onshape.com/discussion/comment/52964)
- An Onshape employee said a related hex-infill failure stems from being unable to shell the part at the chosen wall thickness, and suggested testing with Shell → hollow. Another user's Lighten failed on a 0.25-thick part even after changing hexagon size, wall thickness, ribs and tool diameter. — [Onshape forum (search summary)](https://forum.onshape.com/discussion/comment/18604)
- "lightening features take forever to generate." — [Chief Delphi: Onshape Performance Tips (search summary)](https://www.chiefdelphi.com/t/onshape-performance-tips/467490)

**Enlighten (2026, joshtargo), inspired by Lighten and Part Lighten**
- Offers "more options for creating internal walls around existing voids and holes", including selecting holes individually so you can "only create halos around a few screw holes instead of all or nothing". Rib sketches "can just be lines as needed" (no closed regions). Separate thicknesses exist for outer wall, inner walls, ribs and hole walls. Fillets are "the hard part". "Fillet processing" is "how much it shrinks regions to try and effectively delete small faces that wouldn't be filletable". Two optional auto-correction levels skip regions that might not cut or fillet correctly. Error checking and visualisation show why a feature failed. Supports "Flat plate parts and full-depth cuts only". — [Chief Delphi: Enlighten, a new lightening FeatureScript](https://www.chiefdelphi.com/t/enlighten-a-new-lightening-featurescript/522481)

**CheeseIt! / PatchIt! (TLamp) and isogrid scripts**
- CheeseIt! "automatically applies a isogrid/hexagon/circle weight reduction pattern" and works around features like bearing holes. Automatic grid generation is "inefficient but works", and it's "usually faster to define your own grid in the advanced tab". PatchIt! fixes cases where CheeseIt! "will generate pockets that aren't ideal or will cause some intended holes/part features to separate/float from the actual part". — [Chief Delphi: TLamp's Onshape FeatureScripts](https://www.chiefdelphi.com/t/tlamps-onshape-featurescripts/420133)
- Onshape forum comparison of isogrid scripts: one is "fast but rudimentary", Evan Reese's is "immensely powerful but slightly slower". A user-published "Engineering Grid" adds border control, removal of small border pockets, and fillets on internal pocket corners. — [Onshape forum: favorite featurescript for pocket holes (search summary)](https://forum.onshape.com/discussion/24327/favorite-featurescript-for-making-pocket-holes)

**Fusion generative design**
- 2-axis cutting has two parameters. **Cutting Direction** "Sets a tool orientation for a cutting operation with reference to the Global Coordinate System" (X, Y or Z, one only). **Minimum Wall Thickness** "Attempts to enforce the minimum thickness of a wall or rib after cutting"; wall thickness is "the thickness of features in the cutting plane, that are perpendicular to the Cutting Direction". — [Autodesk Fusion: 2-axis cutting parameters](https://help.autodesk.com/cloudhelp/ENU/Fusion-GenerativeDesign/files/GD-TWO-AXIS-CUTTING-REF.htm)
- 2.5-axis milling adds a minimum tool diameter ("the diameter of the smallest cutting tool that you plan to use"). Corner radii may come out larger than the specified tool when the tool would be too long. — [Autodesk Fusion: 2.5-axis milling parameters (search summary)](https://help.autodesk.com/cloudhelp/ENU/Fusion-GenerativeDesign/files/GD-TWO-HALF-MILLING-REF.htm)
- Preserve regions mark geometry the result must keep, and obstacles mark regions to avoid. Obstacles need enough space between them for the minimum thickness. Symmetry planes for 2-axis cutting must be mutually orthogonal and orthogonal or parallel to the cutting direction. — [Autodesk Fusion help (search summaries)](https://help.autodesk.com/cloudhelp/ENU/Fusion-GenerativeDesign/files/GENERATE-SYMMETRY-PLANE-CMD.htm); [GD 2.5-axis tips](https://help.autodesk.com/cloudhelp/ENU/Fusion-GenerativeDesign/files/GD-TWO-HALF-AXIS-TIPS.htm)

**SOLIDWORKS Topology Study**
- Manufacturing controls: **Preserved Region**. Faces with loads or fixtures are kept by default, and extra faces can be added with a depth that keeps a wall of material behind them. **Thickness control** sets member size limits. **De-mold direction** offers mid-plane, pull-direction-only and stamping options; stamping can create through-holes. — [SOLIDWORKS 2018 What's New: Topology Study](https://help.solidworks.com/2018/english/WhatsNew/c_generative_design_study.htm); [SOLIDWORKS blog: manufacturing controls](https://blogs.solidworks.com/tech/2018/12/best-setups-for-manufacturing-controls-in-topology-study.html); [CATI blog](https://www.cati.com/blog/simulation-topology-study-driving-your-results/)

**Altair Inspire**
- "it is best not to apply loads and supports directly to design spaces, as this often leads to incorrect results. Instead, you should split the part into design and non-design spaces." Partition and Boolean tools help create non-design spaces. "use the simplest design space possible." — [Altair Inspire help: Design Spaces (search summary)](https://help.altair.com/inspire/en_us/topics/inspire/structure/optimization_design_space_c.htm)
- One user report: a minimum-thickness constraint changed the shape near a non-design region; it was round at 12 mm, hexagonal in a failing case, and fixed at 8 mm but not at 6.5 mm. This is anecdotal. — [Altair community thread](https://community.altair.com/discussion/66443/why-does-the-optimization-not-work-properly-around-non-design-regions)

### Inferences
- **Controls users value**, judging by what newer scripts added and what complaints targeted:
  1. No helper sketch: automatic "everything except an offset from every edge".
  2. Per-hole halo on/off and size.
  3. Separate outer-border, rib and hole-wall widths.
  4. Automatic fillets with fallback (shrink or skip unfilletable regions rather than fail).
  5. Removal of tiny pockets.
  6. Clear failure explanations.
  7. Speed.
  8. A manual-grid override when automatic layout is poor.
- **Algorithm the tool should mirror** (the offset/shell approach from Lighten/Enlighten). Take the plate outline offset inward by border width, subtract each protected hole offset outward by its halo, subtract rib strips, then round internal corners. Rounding by morphological opening/closing (offset −r then +r) makes every remaining pocket corner at least r, and dropping pockets smaller than a minimum area is the "fillet processing / remove small pockets" step. This is consistent with Enlighten's "shrinks regions" description, but the exact Lighten internals were not verified.
- Fusion's 2-axis-cutting parameters are exactly the minimum that geometry mode needs: cut direction, implicit for a flat plate, and minimum wall thickness. SOLIDWORKS's "preserved region + depth" maps directly to "per-hole protection distance".

### Gaps
- The official Lighten source, its parameter names and defaults could not be read: Onshape forum pages redirect to SSO, and onshape4frc.com did not resolve.
- CheeseIt! parameter names and defaults are not published in the Chief Delphi post; they'd need opening the Onshape document.
- I didn't find Inspire's extrusion-control parameters for planar parts in an official page.

---

## Q4. File formats and libraries: DXF (ezdxf), SVG, STEP (OCCT/CadQuery), 3MF/STL; what services and CAD tools accept; keeping true arcs

### Takeaway
DXF in inches with `$INSUNITS = 1`, true LINE/ARC/CIRCLE entities (or LWPOLYLINE with bulges), closed contours on one layer, at 1:1 scale, is what services want and what CAD tools import. STEP is the second deliverable for re-importing into Onshape/Fusion/SolidWorks. STL is rejected by SCS. ezdxf (MIT) writes R12–R2018 DXF and handles units. CadQuery/OCCT can generate both DXF and STEP, but its DXF export must use `approx="arc"` to avoid splines that some cutting software drops.

### Cited Findings
- SCS file rules: 2D ".DXF (preferred), .DWG, .EPS, .AI"; 3D ".STEP, .STP" (single solid sheet-metal body). STL and raster formats are not accepted. Build at 1:1 scale; written dimensions are ignored. Units: inch preferred, mm fine if consistent with the quote; "cm and meters are not supported". Every cut path must be closed, with no intersecting or shared lines, all cut geometry on one layer, no stray points or duplicate lines, and text converted to outlines. — [SCS Sheet Cutting Guidelines](https://sendcutsend.com/guidelines/sheet-cutting/); [SCS guidelines landing](https://sendcutsend.com/guidelines/)
- Fabworks: DXF for flat 2D parts; its preflight "checks units, layers, scale, closed profiles, and material thickness". STEP/STP for bent or 3D parts. — [Fabworks Sheet Laser Cutting Guidelines](https://www.fabworks.com/resources/guidelines/laser-cutting/sheet)
- ezdxf on units: "Any length or coordinate value in DXF is unitless in the first place". `$INSUNITS` is "the most important setting": 1 = inches, 4 = mm. `doc.units = ...` is a validated shortcut. `$MEASUREMENT` (0 English, 1 Metric) "is independent from $INSUNITS". There is no implicit unit conversion for blocks. — [ezdxf: DXF Units](https://ezdxf.readthedocs.io/en/stable/concepts/units.html)
- ezdxf supports DXF R12 (AC1009) through R2018 (AC1032). "Ezdxf also reads older DXF versions but saves it as DXF R12." It is MIT licensed and needs Python 3.11+ plus pyparsing, numpy, fontTools and typing_extensions. — [ezdxf Introduction](https://ezdxf.readthedocs.io/en/stable/introduction.html)
- LWPOLYLINE requires DXF R2000 (AC1015). "The bulge value is used to create arc shaped line segments"; "a bulge value of 1 defines a semicircle"; positive bulge is CCW. The closed flag is 1. — [ezdxf: LWPolyline](https://ezdxf.readthedocs.io/en/stable/dxfentities/lwpolyline.html)
- CadQuery: "DXF exporting works only with 2D sections on the current workplane or sketches." "By default, the DXF exporter will output splines exactly as they are represented by the OpenCascade kernel." "Unfortunately some software cannot handle higher-order splines resulting in missing curves after DXF import." `approx="arc"` means "all curves approximated with arcs and line segments", with tolerance "Defaults to 0.001". Default DXF units are mm (`doc_units = 4`). CadQuery exports DXF, SVG, STEP, STL, AMF, TJS, VRML, VTP, 3MF, glTF (assemblies only) and XBF, and imports STEP and DXF. STL tolerance defaults to 1e-3 and angularTolerance to 0.1. — [CadQuery Import/Export](https://cadquery.readthedocs.io/en/latest/importexport.html)
- Onshape drawing export to DWG/DXF lets you "choose to use the drawing units or specify another unit", offers "Export splines as polylines" (all formats except PDF), and has "Set z-height to zero and normals to positive". The help page doesn't list version numbers. — [Onshape Help: Exporting a Drawing](https://cad.onshape.com/help/Content/drawings-exporting.htm)
- Laser software and splines: a laser operator reported that LaserCut "can't handle these and needs them converted to polylines before import". A later post in that thread found the failure wasn't purely spline-related. — [Onshape forum thread (search summary)](https://forum.onshape.com/discussion/comment/11915). Splines exported as many tiny segments can make the laser head "rattle". — [Autodesk forum: DXF has too many line segments](https://forums.autodesk.com/t5/autocad-lt-forum/dxf-for-laser-cutting-has-too-many-line-segments-laser-head/td-p/11066258)

### Inferences
- **Recommended export set.**
  1. **DXF**: R2000 or later via ezdxf; `doc.units = units.IN` ($INSUNITS = 1) when the user works in inches, mm (4) otherwise. Write holes as CIRCLE, pocket boundaries as LINE + ARC (or closed LWPOLYLINE with bulges), one cut layer, no splines, no text, no duplicate or overlapping entities, all contours closed. Optionally add an R12 export for very old laser software, using POLYLINE instead of LWPOLYLINE (inference).
  2. **STEP** of the plate solid (CadQuery/OCCT), so teams can re-import into Onshape/Fusion/SolidWorks/Inventor.
  3. **SVG** for preview and printing a 1:1 template only, not for metal services, since SCS accepts AI/EPS but not SVG.
  4. Skip STL/3MF for fabrication. They are mesh formats, and SCS explicitly rejects STL; they may be useful only for 3D-printed jigs or visualisation.
- If geometry is computed with an arc-preserving 2D kernel (for example shapely buffers produce polylines; OCCT and Clipper with arc reconstruction do better), arcs survive into DXF. If arcs are discretised, export with a tight tolerance and merge collinear segments to avoid "rattle". This is an inference from the sources above.
- Write a units-and-scale sanity check into the export (for example the plate's bounding box in the chosen unit printed in the UI and as a DXF comment) to catch the classic mm/inch 25.4x error that SCS and Fabworks preflight for.

### Gaps
- No source found on which DXF version each service prefers. Neither SCS nor Fabworks states R12 vs R2000+.
- No official statement found on SVG unit/DPI pitfalls (Inkscape 96 dpi vs Illustrator 72 dpi) for laser services.
- Import-format lists for Inventor and SOLIDWORKS were not retrieved. STEP and DXF are universally supported, but that's general knowledge, not cited here.

---

## Q5. Web architecture: server-side Python (FastAPI) vs browser WASM OCCT; three.js 3D; 2D editors; job queues; click-to-edit holes

### Takeaway
A pragmatic split: run the geometry kernel server-side in Python (FastAPI + ezdxf/CadQuery or OCCT) with a real job queue for heavier engineering-mode runs, and do 2D/3D display and hole picking in the browser (SVG/canvas for 2D, three.js Raycaster for 3D). Browser-side WASM OCCT (opencascade.js, replicad) is a viable alternative for instant previews, but no bundle-size or maintenance figures were found to support committing to it.

### Cited Findings
- FastAPI `BackgroundTasks` caveat: "If you need to perform heavy background computation and you don't necessarily need it to be run by the same process ... you might benefit from using other bigger tools like Celery." Those tools "require more complex configurations, a message/job queue manager, like RabbitMQ or Redis, but they allow you to run background tasks in multiple processes, and especially, in multiple servers." — [FastAPI: Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- opencascade.js is a "Port of the OpenCascade CAD library to JavaScript and WebAssembly via Emscripten". "Ship only the code that your application needs using custom builds of the library." "the CAD Kernel runs at near-native speeds and even supports multi-threading on all modern browsers." The homepage footer says "Copyright © 2023". — [opencascade.js homepage](https://ocjs.org/)
- replicad: "a library to build browser based 3D models with code", "an abstraction over opencascade" that "gives developers the power to integrate it in their web application". MIT licence. — [replicad docs](https://replicad.xyz/docs/intro); [replicad GitHub](https://github.com/sgenoud/replicad)
- three.js Raycaster: "Raycasting is used for mouse picking (working out what objects in the 3d space the mouse is over)". `setFromCamera(coords, camera)` takes coords "in normalized device coordinates (NDC). X and Y components should be between -1 and 1". Intersections are "sorted by distance, closest first", with fields distance, point, face, faceIndex, object, uv, normal and instanceId. `params` defaults: `Line: { threshold: 1 }`, `Points: { threshold: 1 }`, where threshold is "the precision of the raycaster when intersecting objects, in world units". — [three.js docs: Raycaster](https://threejs.org/docs/pages/Raycaster.html)
- CadQuery (server-side OCCT in Python) covers both STEP and DXF export with arc approximation. — [CadQuery Import/Export](https://cadquery.readthedocs.io/en/latest/importexport.html)

### Inferences
- **Hole picking.** In 3D, render each hole as its own mesh (or record face-to-hole IDs) so `intersectObjects` returns a hole ID directly. Because Line threshold defaults to 1 world unit, set it relative to the plate scale (inches vs mm) or hit-testing on hole outlines will be far too loose or tight. In 2D, SVG `<circle data-hole-id>` elements with native pointer events, or a canvas with point-in-circle tests against a spatial index, are simpler and more precise for a flat plate. That's an inference; no source was retrieved. A 2D top view is the natural primary editor for a flat plate, with 3D as preview.
- **Kernel placement.** Geometry-only lightening is fast 2D offsetting/booleans and can run synchronously, or in a web worker if done in-browser. Engineering-mode optimisation (FEA or topology loops) should go through a queue (Celery/RQ + Redis), per the FastAPI caveat, returning a job ID that the UI polls.
- Keep one canonical geometry model, holes as circles with IDs and per-hole protection values, so the 2D editor, 3D preview, DXF and STEP exporters all read the same data.

### Gaps
- No current figures found on opencascade.js bundle size, maintenance status or licence (the homepage omits them). replicad's export formats and worker guidance were not on the fetched pages.
- No sources retrieved for 2D SVG/canvas hit-testing best practice or for alternative queue systems (RQ, Dramatiq, Arq).

---

## Q6. Student UX: essential vs optional vs derived inputs; presets; geometry-only vs engineering modes; provenance labels; uncertainty and avoiding implied certification

### Takeaway
The few inputs that truly need a student are plate outline and holes (from DXF/STEP), manufacturing method, which sets tool radius and minimums, and which holes to protect. Everything else (fillet radius, minimum pocket size, border width, rib width) can come from a process preset and be shown with a provenance tag. Engineering mode must be clearly separate and labelled as screening analysis. NASA's input-pedigree concept and vendor disclaimers give language for this.

### Cited Findings
- Students and FRC mentors generally don't do stress analysis on pocketed plates; they size by feel. — [Chief Delphi: Aluminum Minimum Width Help](https://www.chiefdelphi.com/t/aluminum-minimum-width-help/458606); [Chief Delphi: CAD part weight reduction](https://www.chiefdelphi.com/t/cad-part-weight-reduction/441210)
- gm0 suggests inexperienced teams favour 3D printing over machining for custom parts for now, and notes "many teams do not have access to equipment such as lathes, routers, waterjet cutters, or CNC machines". — [gm0 Machining](https://gm0.org/en/latest/docs/custom-manufacturing/machining.html)
- gm0 pocketing advice is "do it last". Keep construction circles to under 4 sizes for consistency. — [gm0 Pocketing Guide](https://gm0.org/en/latest/docs/design-skills/cad-tutorials.html#cad-tutorial-part-2-pocketing-guide)
- Lighten's main usability pain is the helper sketch and per-loop selection. Enlighten added per-hole halo selection, auto-correction levels and failure visualisation "to show why a feature failed and how to fix it". — [Chief Delphi #139](https://www.chiefdelphi.com/t/some-helpful-featurescripts/361652/139); [Chief Delphi: Enlighten](https://www.chiefdelphi.com/t/enlighten-a-new-lightening-featurescript/522481)
- NASA-STD-7009 credibility assessment scores "Input Pedigree" as one of eight factors on a 0–4 scale. In 7009A usage, 0 means insufficient evidence and 4 means all data are known, used appropriately and traceable to the real-world system. The standard requires "that the lowest input data quality be used to represent the entire set of input data" when scoring input pedigree. Revision 7009B was approved 5 March 2024. — [Validas: NASA-STD-7009B](https://www.validas.de/resources/glossary/nasa-std-7009b); [NASA NTRS presentation 20150021308](https://ntrs.nasa.gov/api/citations/20150021308/downloads/20150021308.pdf); [NTRS 20230000585](https://ntrs.nasa.gov/citations/20230000585) (search summaries; I didn't read the standard's full level wording)
- Vendor disclaimer model (Siemens Solid Edge Simulation): results "should not be used to solely judge a design idea's suitability to a given set of environmental conditions"; "this does not replace good engineering judgment, which is always the responsibility of our users"; results should be evaluated "in conjunction with the practical experience of design engineers and analysts, and ultimately experimental test data". — [Siemens Solid Edge Simulation: Important Information (search summary)](https://soliddna.com/SEHelp/ST5/EN/a_h/feamapexpress_important_information.htm)
- SOLIDWORKS SimulationXpress is described as an entry-level first pass: "Limited to single parts only, static studies only, and a single 'fixed' fixture type". — [Javelin: SimulationXpress (search summary)](https://www.javelin-tech.com/3d/solidworks-simulationxpress/)
- Altair: putting loads or supports directly on design space "often leads to incorrect results". Users should define non-design regions for load and support points. — [Altair Inspire help (search summary)](https://help.altair.com/inspire/en_us/topics/inspire/structure/optimization_design_space_c.htm)

### Inferences
- **Input tiers for geometry mode:**
  - *Essential (user)*: plate geometry (upload DXF/STEP or draw it); manufacturing method (send-out laser / waterjet / school router / school mill), which sets min hole, min rib, edge distance and tool radius; and material thickness, defaulted to 0.125 in.
  - *Essential but defaulted (user can confirm)*: which holes are protected (default all) and protection distance per hole (default from hole size, for example a halo of max(1x t, 0.5x hole diameter); that formula is an inference). Bearing and shaft holes are flagged for larger halos.
  - *Optional (advanced)*: rib width, border width, pocket style (truss/triangle, isogrid, hex, circles), fillet radius, minimum pocket area, symmetry, keep-out regions (for example around wires and other components), manual struts between chosen holes (matching the CD habit of "lines between critical load areas").
  - *Derived (calculated, shown read-only)*: fillet radius = tool radius + margin (Xometry +0.02–0.05 in); minimum pocket width = 2x fillet radius (or tool diameter + clearance); mass and percent removed; warnings when rib width falls below the process minimum.
- **Two modes.**
  - *Geometry-only lightening*: manufacturability rules only. Label it plainly: "No strength analysis performed. Rib widths come from manufacturing minimums and your settings."
  - *Engineering-optimised*: needs load cases, meaning which holes carry load, direction and magnitude, and which holes are fixed. This mirrors Altair's and SOLIDWORKS's "loads on preserved/non-design regions" pattern. Results show safety factor or stress as a screening estimate.
- **Provenance labels per value**: `user-specified`, `calculated` (derived from other inputs by a formula shown on hover), `assumed` (a preset default with the vendor source, for example "SCS 6061: 1.5–2x t edge distance"), and `screening` (from a simplified analysis, not validated). Following NASA-STD-7009's lowest-pedigree rule, the overall result badge should take the weakest provenance of its inputs. If any load is "assumed", the strength result is "screening".
- **Avoiding implied certification**: use the Solid Edge-style statements (not a substitute for engineering judgment; verify by test). Never use "safe", "approved" or "certified". Show ranges or "estimated" instead of single-precision numbers. Attach the vendor rule set and date to every export, since vendor numbers conflict and change.
- **Presets** named by process and vendor ("SendCutSend laser – 0.125 in 6061", "Fabworks laser – 0.125 in 6061", "School router – 1/8 in end mill", "School router – 3 mm end mill"). Each preset shows its source link. This lets novices pick by "where are you getting it made?" rather than by numbers.
- Error UX should copy Enlighten: when a pocket can't be filleted or a hole would float, highlight it and say why ("rib narrower than 0.125 in minimum for router preset"). Don't fail silently.

### Gaps
- No usability studies found on novice CAD tools, input provenance tagging or uncertainty display for high-school users specifically. The UX recommendations above are inferences from tool-feature evolution and engineering-credibility standards.
- The full NASA-STD-7009B level definitions and exact SOLIDWORKS SimulationXpress disclaimer wording were not retrieved.
- No FTC-specific guidance found on what load magnitudes to assume for side plates, which an engineering mode would need; that likely falls under another researcher's scope.
