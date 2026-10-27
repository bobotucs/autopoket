# Protect the bores, then prune the ribs

A web tool can lighten an 18 x 18 in, 0.125 in (3.175 mm) 6061-T6 FTC plate well only if it treats the job as limited by stiffness and rules rather than by strength. A braced FTC plate carries mostly in-plane loads at a few MPa, and strength alone would let the ligaments around even a 500 N bearing bore shrink below 1 mm. What actually binds is the protected ring around each bearing bore and fastener face, in-plane load paths stiff enough to hold gear and belt centre distances and bore alignment, the slenderness of long ribs under impact, and the cutting process's tool radius and minimum web. ChatGPT's hybrid pipeline (feature classification, protected non-design regions, load cases, screening FEA, optimisation, boundary reconstruction, manufacturing checks, verification FEA) fits this, with four amendments from the research. First, hole rings should be computed per hole class; for a bearing bore a Lamé fit-retention rule gives a ring outer diameter of about 1.8 x the bore. Second, loads should come from motor stall torque through the gear train, applied through spring supports and a cosine pressure on the bore, never "all holes fixed". Third, SIMP should steer and benchmark a manufacturable truss/isogrid vocabulary rather than draw the pockets, because optimised through-cut trusses come within 2% of the Michell bound and beat 0/1 SIMP. Fourth, stress should be a post-check on body-fitted geometry, never an in-loop constraint on a raster. AutoPocket v2 already has the right skeleton (rules first, a hard validator, a candidate archive, symmetric blunt-tipped triangle pockets), but it judges designs against generic cantilevers clamped at each end, it samples stress at the plate mid-plane (a probe for this report found out-of-plane bending stress under-reported 16-18x), its hole protection is one user-set number rather than a class- and load-dependent ring, and its rib pruning is one-way ESO. The highest-value fixes, in order, are correcting stress recovery and adding regression benchmarks, adding hole classes with computed rings and process presets, replacing the cantilevers with FTC load templates and bore-alignment KPIs, upgrading pruning to BESO plus rib-width sizing guided by a short multi-case SIMP field, and adding a body-fitted verification tier with convergence checks and arc-true DXF/STEP export labelled by input provenance.

## A braced 1/8 in plate works in plane at a few megapascals

The material basis is simple. The tool should design to the specification minimums for 6061-T6, **F_tu = 290 MPa and F_ty = 240 MPa**, not the typical values that run 7-15% higher, with **E = 68.9 GPa, ν = 0.33** and density 2,700 kg/m³ ([Wikipedia: 6061 aluminium alloy](https://en.wikipedia.org/wiki/6061_aluminium_alloy)). The guaranteed MMPDS bearing and shear allowables sit in a licensed handbook, and bearing values exist only as typical data, 386 MPa yield and 607 MPa ultimate at e/D = 2 ([Quickparts 6061 datasheet](https://quickparts.com/wp-content/uploads/2024/05/Aluminum-6061.pdf)). The tool should therefore store separate "design" and "typical" columns, flag any placeholder it uses (such as F_su ≈ 0.6 F_tu), and let teams override the material for 5052 or 7075 plates.

Plate geometry shows where material actually matters. The flexural rigidity D = Et³/12(1−ν²) works out to **206 N·m** for this sheet ([Wikipedia: Bending of plates](https://en.wikipedia.org/wiki/Bending_of_plates)). Treat a 350 x 120 mm side plate as a simply supported beam carrying 300 N at mid-span:

| Loaded | Bending stress | Deflection |
|---|---|---|
| In its own plane | 3.44 MPa | 0.0085 mm |
| Out of plane | 130 MPa (54% of minimum yield) | 12.2 mm |

The section is **1,428x stiffer in plane than out of plane**, so FTC plates only work when standoffs or channel brace them out of plane; gm0 warns that sheet "will bend if not supported correctly" ([gm0 materials guide](https://gm0.org/en/latest/docs/custom-manufacturing/materials-guide.html)). Inside a braced box the plate is a deep in-plane beam, and a pocket's cost depends on where it sits. A 14 mm hole on the in-plane neutral axis removes 0.16% of the second moment of area, while the same hole 45 mm off the axis removes 19.8%. That is the quantitative case for keeping continuous top and bottom rims and keeping pockets out of the outer 15-20% of depth near load points. The in-plane bending stress concentration at a central hole is Kt = 2 at the hole edge ([AMES, after Pilkey](https://amesweb.info/stress-concentration-factor-calculator/central-circular-hole-in-plate.aspx)).

Pocketing turns the plate into a frame. Ribs 6-10 mm wide in 3.175 mm stock (width/thickness 1.9-3.1) are beams, not plates, and their governing instability is out-of-plane column buckling. The radius of gyration is **r = t/√12 = 0.917 mm whatever the rib width**, so elastic Euler buckling below minimum yield sets in once the effective length passes about **49 mm** (KL/r = 53.2) ([Wikipedia: Euler's critical load](https://en.wikipedia.org/wiki/Euler%27s_critical_load)). A pin-ended 80 mm rib buckles at about 89 MPa, or 2.3 kN for an 8 mm rib, while a 50 mm rib holds about 177 MPa on the Johnson curve. A typical chord force in a trussed side plate is about 240 N (9.4 MPa), which leaves a static margin near 9.5 on the 80 mm rib; an impact factor of 5 cuts that to about 1.9. The tool should therefore **limit unsupported rib length to about 15 t (≈ 49 mm at K = 1)** or check σ·DLF·SF against σ_cr explicitly. It should fix slender ribs by adding nodes, not width, because widening a rib raises its force capacity but leaves its slenderness unchanged. A narrow rim along a free compression edge behaves the same way: an outstand plate with k = 0.425 buckles at only about 19 MPa for b = 120 mm ([NPTEL: local buckling](https://archive.nptel.ac.in/content/storage2/courses/105106113/5_cold_form_steel/3_local_buckling.pdf); [Air Force Stress Manual](https://engineeringlibrary.org/reference/analysis-of-plates-axial-compression-air-force-stress-manual)).

Stress raisers matter mostly through ligament width and pocket shape. The finite-width hole factor in tension is Kt_n = 3.000 − 3.140x + 3.667x² − 1.527x³ with x = d/W ([AMES, after Pilkey 2005](https://amesweb.info/stress-concentration-factor-calculator/central-circular-hole-in-plate.aspx)). Relative to gross stress it climbs from **3.03 at d/W = 0.1 to 4.25 at 0.5 and 6.76 at 0.7**, so the ligament between a hole and a pocket matters more than the hole itself. Orientation matters just as much: a 30 x 8 mm slot has Kt ≈ 4.87 with its long axis across the stress and ≈ 1.53 along it ([Wikipedia: Stress concentration](https://en.wikipedia.org/wiki/Stress_concentration)). That is the mechanical argument for triangular pockets whose edges follow rib force lines. Kt also grows as √(a/ρ) as corner radius shrinks, so corner radii should be at least the cutter radius, and preferably at least t on primary load paths, which agrees with the project's existing "no acute wedge tips" rule.

Fatigue and impact refine this but rarely govern. 6061-T6 has about **97 MPa fatigue strength at 5 x 10⁸ cycles** with no true endurance limit ([Wikipedia: 6061](https://en.wikipedia.org/wiki/6061_aluminium_alloy)). With Peterson notch sensitivity (α ≈ 0.51 mm for aluminium; [SNU lecture notes](https://ocw.snu.ac.kr/sites/default/files/NOTE/MSBS_ch10.pdf)), a 1/8 in cutter corner gives Kf ≈ 2.1-2.5. Local rib amplitudes of about 24 MPa sit below a derated 50-65 MPa long-life value, so fatigue matters only for ligaments under about 2 mm, or for Kt above about 4 near bearing and motor mounts. Impact is the bigger amplifier. A suddenly applied load doubles stress, and a drop gives DLF = 1 + √(1 + 2h/δ_st): **15.2 for a 50 mm drop onto a structure that deflects 0.5 mm statically** ([Poznan University of Technology lecture](https://pawel.jasion.pracownik.put.poznan.pl/wp-content/uploads/2025/05/SOMC_lecture_04.pdf)). Because 6061 is ductile, a single overload tends to ovalise a bore rather than fracture the plate. Ovalisation is a functional failure, which argues for stiffness criteria around bores. Partial-depth pockets, a mill-only option, pay off asymmetrically: a 1.5 mm floor keeps 47% of the mass and 47% of the membrane stiffness but only 10.5% of the bending stiffness, because bending scales with t³.

## Bearing bores need fit-retaining rings, not strength rings

Classical lug analysis gives the strength terms in closed form: bearing σ_br = P/(dt), shear-out e_req = d/2 + P/(2tF_su), and net tension w = Kt·P/(2tF_ty) ([MechaniCalc: Lug Analysis](https://mechanicalc.com/reference/lug-analysis)). At FTC loads they are tiny. For a 14 mm bearing seat carrying an assumed 500 N design load, bearing stress is 11.2 MPa, the shear-out ligament needed is **0.38-0.42 mm**, and net tension needs about 0.66 mm in total.

Rule-based floors are far larger. MMPDS tabulates bearing allowables at e/D = 1.5 and 2.0 ([Eng-Tips](https://www.eng-tips.com/viewthread.cfm?qid=450377)). Eurocode 3 requires an end distance of at least 1.2 d₀ and a pitch of at least 2.2 d₀ ([Eurocode Applied](https://eurocodeapplied.com/design/en1993/bolt-design-properties)). AISC allows smaller edge distances when the bearing and tear-out equations are satisfied ([Eng-Tips](https://www.eng-tips.com/viewthread.cfm?qid=151072)). Read literally, e/D = 1.5 puts a 14 mm bore's centre 21 mm from any free edge, and pocket edges count as free edges. That is very conservative at FTC loads, and it applies only in the load direction.

What actually limits a bearing bore is fit and ovalisation. SKF says thin-walled and light-alloy housings need tighter fits and should avoid uneven wall thickness that distorts rings ([SKF: Selecting fits](https://www.skf.com/us/products/rolling-bearings/principles-of-rolling-bearing-selection/bearing-selection-process/bearing-interfaces/selecting-fits)). Lamé thick-cylinder theory ([Roymech](https://roymech.org/Useful_Tables/Mechanics/Cylinders)) turns that into a usable rule. A fully encircled ring keeps a fraction η = (1+ν)/(C+ν) of the solid-plate fit stiffness, where C = (b²+a²)/(b²−a²). Holding η = 0.6 needs **b/a ≈ 1.8**: a ring 5.6 mm wide around a 14 mm bore, or 8.9 mm around a 22 mm bore. For a light 0.010 mm diametral interference, contact pressure is 37 MPa in solid plate but only 15.1 MPa inside a 20 mm OD ring, so 59% of the fit is lost while hoop stress stays near 44 MPa, far below yield. The failure mode is compliance (lost fit, outer-ring creep, rattle), not rupture. No bearing maker publishes an η target, so 0.6 is an engineering choice the tool should expose.

That gives an implementable rule. For each hole and each direction the load can act, the keep-out radius is R_keep = d/2 + max(w_rule, w_shear, w_net, w_stiffness, w_contact, w_mfg). The ring is a circle when the load direction is unknown and a teardrop when it is known (for example chain pull). Ring boundaries are then treated as free edges for Kt and ligament checks against neighbouring pockets. The analytic strength terms act as a safety net for multi-kN pivots; at ordinary FTC loads the rule, stiffness, contact and manufacturing terms dominate. The classes below synthesise the cited theory. Their default values are engineering judgement and need test validation.

| Class | Typical FTC example | Ring is the max of | Default when no loads are given |
|---|---|---|---|
| A. Loaded bearing bore | 14 mm goBILDA 1611 seat; REV 9 mm and 12 mm seats | η fit retention, flange seat, e/D toward free edges, shear-out/net with P_d | ring ≥ 0.4 d (η ≈ 0.6) and ≥ flange OD/2 + 1 mm; e/D ≥ 2 toward free edges |
| B. Fastener / standoff | M3 (3.4 mm) and M4 (4.5 mm) clearance holes | solid under head/standoff face, e/D, pitch ≥ 2.2-2.5 d₀, bearing | max(contact radius − d₀/2, 1.0 d₀); e/D ≥ 1.5 |
| C. Mechanism interface | motor face pattern, servo, gear centre-distance pair | no pockets inside the group | convex hull of the group plus the class-B ring |
| D. Clearance hole | wire or shaft pass-through, unused pattern hole | Kt x local stress, manufacturing web | max(w_mfg, 0.5 d) |
| E. Existing void | prior lightening | rib width, length and buckling rules | treated as void |
| F. User-protected | drawn polygon or offset | hard keep-out | never overridden |

Automatic recognition is realistic because FTC kits are standardised. goBILDA uses **4 mm holes on an 8 mm grid with a 14 mm bearing hole**, with four holes clocked at 45° around it ([goBILDA pattern](https://gobilda.com/pattern)), and its 1611 bearing is 14 mm OD x 5 mm thick ([goBILDA 1611](https://www.gobilda.com/1611-series-flanged-ball-bearing-8mm-rex-id-x-14mm-od-5mm-thickness-2-pack/)). REV seats plastic bearings in 9 mm holes and its 8 x 12 mm flanged bearing in 12 mm holes ([REV docs: Bearings](https://docs.revrobotics.com/duo-build/motion/intro/bearings.md)), and its HD Hex planetary mounts on a 14 mm bolt circle ([REV docs: HD Hex](https://docs.revrobotics.com/duo-build/actuators/motors/hd-hex-motor)). Diameter plus local pattern can therefore propose a class, and unknown diameters should default to "free hole, ask the user". The UI must also ask which holes actually carry screws, because most goBILDA pattern holes on a student plate are unused. Fastener ligaments come out small:

| Rule (hole edge to free edge) | M3 | M4 |
|---|---|---|
| Eurocode 3 minimum | 2.4 mm | 3.2 mm |
| e/D = 1.5 | 3.4 mm | 4.5 mm |
| e/D = 2.0 | 5.1 mm | 6.8 mm |

An M4 hole's typical bearing capacity of about 4.9 kN is far above any FTC screw load.

## Stall torque and two-plate couples set the real load cases

The rules give no load envelope. R104 states "There is no ROBOT weight limit", R102 caps the starting size at an 18 in cube, R105 caps the expanded robot at 18 x 24 x 29 in, and R503 allows at most 8 motors ([FTC 2026-2027 Competition Manual](https://ftc-resources.firstinspires.org/ftc/game/manual)). Robot mass must therefore be a student input; the only sourced reference mass is goBILDA's 4.14 kg Strafer chassis ([goBILDA Strafer V5](https://www.gobilda.com/strafer-chassis-kit-v5/)).

Motors are a more reliable load source than mass. Every legal FTC gearmotor is a roughly 15-20 W device whose stall torque scales almost linearly with gear ratio:

| Motor and gearing | Stall torque | Source |
|---|---|---|
| goBILDA 5203, 1620 RPM | 0.53 N·m | [Core Electronics](https://core-electronics.com.au/5203-series-yellow-jacket-planetary-gear-motor-371-ratio-24mm-length-8mm-rex-shaft-1620-rpm-33-5v-encoder.html.plain.md) |
| goBILDA 5203, 312 RPM | 2.38 N·m | [goBILDA](https://www.gobilda.com/5203-series-yellow-jacket-planetary-gear-motor-19-2-1-ratio-24mm-length-8mm-rex-shaft-312-rpm-3-3-5v-encoder/) |
| goBILDA 5203, 30 RPM | 24.5 N·m | [RobotShop](https://www.robotshop.com/products/5203-series-yellow-jacket-planetary-gear-motor-1881-30-rpm-33-5v-encoder) |
| REV HD Hex, bare / 20:1 | 0.105 / 2.1 N·m | [REV docs](https://docs.revrobotics.com/duo-build/actuators/motors/hd-hex-motor) |
| REV Core Hex | 3.2 N·m | [REV docs](https://docs.revrobotics.com/duo-build/actuators/motors/core-hex-motor) |

Turning torque into plate loads uses textbook relations. Spur gears carry F_t = T/r and F_r = F_t tan 20° ([Engineers Edge](https://ns1.engineersedge.com/gears/force_analysis_spur_gears_13977.htm)). A belt's shaft load is √(T₁² + T₂² − 2T₁T₂cos θ), which equals T₁ + T₂ at 180° wrap, with slack-side T₂ ≈ 0.1-0.3 of the effective tension ([Gates timing belt theory](https://gates.com/content/dam/documents-library/whitepapers/timing-belt-theory-white-paper.pdf)). Equilibrium of a shaft on two bearings makes the near bearing of an overhung load carry (L + a)/L of it, more than the load itself.

Applied to typical builds, the numbers fall into clear tiers. A 15 kg robot (assumed) on four 96 mm wheels puts 36.8 N static on each wheel. Traction limits drive force to 18.8 N at the vendor-quoted μ = 0.51 ([AndyMark, via search](https://www.andymark.com:443/am-2626)). An overhung wheel puts about 60 N on its near bearing, and 120 N under a sudden-load factor of 2. A 117 RPM goBILDA motor driving a 20T/60T module-1 stage produces **671 N tangential mesh force and 535 N on the nearer bore** when the gear sits 10 mm from one plate. An arm stalled against a hard stop sees 20.1 N·m, against only 1.77 N·m of gravity torque at horizontal, and a 10 N side bump at the tip becomes a ±100 N couple across bearings 40 mm apart. A belt-driven roller at stall loads its shaft with 150-200 N, and a lift spool at stall pulls 233 N of string tension.

**Stall dominates powered mechanisms by more than 10x.** Drivetrain plates are the exception: traction governs sustained running and impact governs peaks. Impact numbers depend on drop height and compliance the student cannot know, so they must be labelled "conservative screening".

| Plate type | Governing loads (example magnitude) | Response that limits lightening |
|---|---|---|
| Drive wheel plate | weight share, traction, drop (37 N static; 60 N near bearing; 120 N sudden) | bore misalignment between paired plates; chain/belt centre distance |
| Gearbox plate pair | mesh F_t and F_r at stall (300-700 N per bore) | centre-distance change; bore alignment; ligaments at bores |
| Arm pivot plate | stall into a stop, tip side bumps (20 N·m; ±100 N couple) | out-of-plane stiffness for single plates; pivot fatigue |
| Lift plate | spool tension, pulley wrap, hang (233 N; 466 N on a 180° redirect axle) | pulley-hole stress; bending from offset slides |
| Intake plate | belt pull at stall, wall collisions (50-65 N belt load) | roller centre distance; leading-edge robustness |
| Chassis sandwich | racking, collisions (900-3,700 N whole robot, assumption-heavy) | standoff-hole stress; racking through standoff bending |

Boundary conditions matter as much as magnitudes, and "fix every mounting hole" is the classic error. Fixed hole edges create stress singularities exactly where students look ([Design World](https://www.designworldonline.com/avoiding-singularities-in-fea-boundary-conditions/)). They also over-stiffen the plate and route load to the nearest hole instead of through the standoffs. Spring supports remove the singular fields but need an estimate of the stiffness of the structure they stand in for ([COMSOL bracket example](https://doc.comsol.com/6.4/doc/com.comsol.help.models.sme.bracket_spring/bracket_spring.html)). That estimate is easy for FTC hardware. An 8 mm OD aluminium standoff 48 mm long is about **54,000 N/mm stiff axially but only 350-1,400 N/mm laterally**, so rigid in-plane fixity is the least realistic part of an all-fixed model.

The tool should model fasteners as springs spread over the washer annulus, with the clamp zone sized by a 30° frustum ([RoyMech: joint stiffness](https://roymech.org/Useful_Tables/Screws/Joint_Stiffness.html)), plus a minimal 3-2-1 restraint or inertia relief for self-equilibrated gearbox plates. Bearing loads should be a cosine pressure over the loaded half of the bore, as Ansys and SOLIDWORKS model them ([Ansys Help: Bearing Load](https://ansyshelp.ansys.com/public/views/secured/corp/v261/en/wb_sim/ds_Bolt_Load.html); [Javelin](https://www.javelin-tech.com/blog/2019/04/solidworks-simulation-bearing-load/)). The peak is p₀ = 4F/(πdt), 1.27x the projected bearing stress, whereas a uniform full-bore load creates artificial tension on the far side ([PrePoMax forum](https://prepomax.discourse.group/t/bearing-load-distribution/2862)). Loads should go in through RBE3-style distributing couplings rather than rigid RBE2 spiders, which stiffen the bore ([Altair Community](https://community.altair.com/discussion/comment/71861)). Results should be bracketed between soft (3EI/L³) and stiff (12EI/L³) supports, and marked "support-sensitive" when key outputs differ by more than about 25-30%. Paired plates need either a model of both plates with standoffs and shaft as beams, or at least the overhang couple, which loads the near plate at about 1.6x and the far plate at about 0.6x in reverse.

## Screening FEA must split membrane from bending and distrust raster stresses

Element choice decides whether bending is captured at all. With one element through the depth of a cantilever, the Abaqus benchmark gives these normalised tip deflections ([Abaqus Benchmarks: linbending](https://abaqus-docs.mit.edu/2017/English/SIMACAEBMKRefMap/simabmk-c-linbending.htm)):

| Element group | Elements | Tip deflection (exact = 1) |
|---|---|---|
| Linear, fully integrated | CPS3 / CPS4 / C3D8 | 0.012 / 0.034 / 0.035 |
| Incompatible-mode | CPS4I / C3D8I | 0.985 |
| Quadratic | CPS6 / C3D20R | 0.986 / 1.001 |
| Reduced integration, one layer | C3D8R | singular, or reliant on artificial hourglass stiffness |

Stress concentrations are harsher still. On NAFEMS LE1, linear triangles miss the 92.7 MPa target by 23% even on the fine mesh, while quadratic CPS8 lands within 0.12% ([Abaqus LE1](https://abaqus-docs.mit.edu/2017/English/SIMACAEBMKRefMap/simabmk-c-le1.htm)).

For a flat, mid-plane-symmetric, linear plate, membrane and bending responses decouple. The efficient screening solver is therefore two cheap problems superposed: a 2-DOF/node plane-stress problem (quadratic triangles or incompatible-mode quads) for in-plane loads, and a 3-DOF/node DKT/MITC plate problem for out-of-plane loads. Narrow ribs add a wrinkle. For an 8 x 3.175 mm rib the strip torsion constant is only about 0.75 of bt³/3 ([Oasys GSA: rectangular sections](https://docs.oasys-software.com/structural/gsa/references-theory/rectangular-sections/)), so Kirchhoff plate elements over-predict rib torsional stiffness by about 33%, and torsion-dominated verdicts need a Mindlin shell or 3D check. One post-processing trap also matters: CalculiX expands shells into solids, and its default 2D output averaging "removes the bending stresses" ([CalculiX manual](https://web.mit.edu/calculix_v2.7/CalculiX/ccx_2.7/doc/ccx/node37.html)).

Fixed-grid (raster) FEA, which AutoPocket uses, is fine for stiffness and poor for stress. Fixed-grid errors concentrate in partially filled boundary elements ([Dunning, Kim & Mullineux, Bath](https://researchportal.bath.ac.uk/en/publications/error-analysis-of-fixed-grid-formulation-for-boundary-based-struc/)), and topology-optimisation researchers respond by sampling stresses from the interior ([Interior Value Extrapolation, SMO 2014](https://link.springer.com/article/10.1007/s00158-014-1171-2)). Every raster stair step is a 90° re-entrant corner. A singularity shows itself as a peak that keeps rising under mesh refinement, whereas a true concentration converges ([SOLIDWORKS: assessing hot spots](https://help.solidworks.com/2017/english/solidworks/cworks/r_assessing_stress_hot_spots.htm); [PADT: geometric singularities](https://www.padtinc.com/wp-content/uploads/2024/01/PADT-Geometric_Singularities_in_Finite_Element_Problems_2023_01_09.pdf)).

The defensible metrics are compliance, bore kinematics, an area-weighted 99th-99.5th percentile stress that excludes about 1-2 t around loads and supports, and peak stress at modelled fillets reported only after a convergence study. Bore metrics have no published standard. A least-squares rigid-body fit of each bore's edge displacements gives centre translation and tilt, from which paired bores yield centre-distance change, lateral offset and relative tilt (θ ≈ Δδ/L); a second-harmonic fit isolates ovalisation. These integral quantities converge like displacements, unlike peak stress.

| Tier | Purpose | Formulation | Outputs to trust |
|---|---|---|---|
| Screening | rank candidates in seconds | decoupled plane stress + plate, on a grid or coarse body-fitted mesh with at least 2 quadratic elements across the narrowest rib | compliance, bore KPIs, interior percentile stress |
| Optimisation loop | SIMP guidance, BESO, rib sizing | fixed grid with ersatz material; factor once, many load cases | compliance, bore KPIs |
| Verification | final verdict on the exported geometry | Gmsh body-fitted quadratic mesh with real fillets, 24-36 elements around bores; C3D20R/tet10 or Mindlin for rib torsion | GCI-qualified KPIs, filleted peaks |

Verification follows the NASA NPARC procedure ([NASA NPARC spatial convergence](https://www.grc.nasa.gov/www/wind/valid/tutorial/spatconv.html)). Run three systematically refined meshes with refinement ratio r ≥ 1.1. Compute the observed order p = ln[(f₃−f₂)/(f₂−f₁)]/ln r, the Richardson extrapolation and GCI₁₂ = 1.25|f₂−f₁|/(|f₁|(r^p−1)), and check that the asymptotic ratio is close to 1. ASME V&V 10 supplies the vocabulary ([ANSI: ASME V&V 10](https://webstore.ansi.org/standards/asme/ansiasme102006)): verification means solving the equations right, validation means solving the right equations.

| Regression benchmark | Reference answer | Source |
|---|---|---|
| NAFEMS LE1 elliptic membrane | σ_yy(D) = 92.7 MPa | [Abaqus LE1](https://abaqus-docs.mit.edu/2017/English/SIMACAEBMKRefMap/simabmk-c-le1.htm) |
| NAFEMS LE6 skew plate, 0.7 kPa (not the 7 kPa misprint) | 0.802 MPa | [Altair OS-V:0050](https://help.altair.com/hwsolvers/os/topics/solvers/os/nafems_test_problem_le6_r.htm); [PrePoMax forum](https://prepomax.discourse.group/t/le6-skew-plate-under-normal-pressure/2304) |
| Simply supported / clamped square plate | w = 0.00406 / 0.00126 qa⁴/D | [SOLIDWORKS SS plate](https://help.solidworks.com/2025/English/simconntutorial/Simply_Supported_Rectangular_Plate_Static.htm); [SOLIDWORKS clamped plate](https://help.solidworks.com/2025/English/simconntutorial/Clamped_Square_Plate_Under_Uniform_Loading.htm) |
| Plate-with-hole strip | Pilkey polynomial (≈2.42 at d/W = 0.25, 2.16 at 0.5, → 3 as d/W → 0) | [AMES](https://amesweb.info/stress-concentration-factor-calculator/central-circular-hole-in-plate.aspx) |
| Cantilever, incl. 0-45° skewed elements | PL³/3EI | [Abaqus linbending](https://abaqus-docs.mit.edu/2017/English/SIMACAEBMKRefMap/simabmk-c-linbending.htm) |
| Thin-strip torsion | J = (bt³/3)(1 − 0.63 t/b) | [Oasys GSA](https://docs.oasys-software.com/structural/gsa/references-theory/rectangular-sections/) |

The open-source stack works on Windows. **Gmsh 4.15.2** (March 2026, `pip install gmsh`, GPL with a linking exception) handles body-fitted meshing ([gmsh.info](https://gmsh.info/)). **scikit-fem** gives an in-process pure-Python solver ([scikit-fem examples](https://scikit-fem.readthedocs.io/en/latest/listofexamples.html)), with one caution: cheap Morley-type plate reconstructions fail to converge on unstructured meshes ([Larsson & Larson](https://arxiv.org/pdf/1503.06282)). **CalculiX**, through PrePoMax's ccx_static.exe, provides independent cross-checks ([PrePoMax forum](https://prepomax.discourse.group/t/using-standalone-calculix/846)). DOLFINx should not be a hard dependency, because its Windows packages are beta and lack PETSc ([DOLFINx GitHub](https://github.com/fenics/dolfinx)). For repeated analyses, factor the stiffness matrix once and solve every load case as a multi-column right-hand side; PyPardiso is "in many cases significantly faster" than SciPy's SuperLU ([PyPI: pypardiso](https://pypi.org/project/pypardiso/0.4.5)).

## Good trusses sit within 2% of Michell, so SIMP should steer, not draw

SIMP is mature and cheap in 2D. The standard recipe ([Ferrari & Sigmund 2020, top99neo](https://arxiv.org/html/2005.05436v2)) interpolates stiffness as E = E_min + x^p(E₀ − E_min) with p = 3 and E_min = 10⁻⁹. It applies a density filter, then a volume-preserving Heaviside projection (η* ≈ 0.4-0.52) with β continuation, updates with OC, and uses passive solid and void sets that map exactly onto bore keep-outs and edge bands. It runs at **0.231 s per iteration on 30,000 elements** in MATLAB, although plain OC hit the 2,500-iteration cap at tight tolerances until Anderson acceleration cut that to 352-828. Weighted-sum multi-load SIMP is sensitive to the chosen weights ([Zhang, de Sturler & Paulino 2017](https://personal.math.vt.edu/sturler/Publications/CMAME_Zhang-deSturler-Paulino_2017_final.pdf)), so a min-max bound on normalised compliances suits enveloped FTC loads better. On licensing, the educational codes carry no stated licence, while topoptlab (GPL-3) and mmapy (GPL) do ([DTU TopOpt Python codes](https://www.topopt.mek.dtu.dk/apps-and-software/topology-optimization-codes-written-in-python); [mmapy](https://pypi.org/project/mmapy/)).

The harder variants do not pay off at FTC scale. Stress-constrained TO has one constraint per element and a "singularity" phenomenon that needs relaxation with continuation. Its p-norm aggregation is limited to about p = 4, and run times are reported **up to 10x** a compliance run ([Amir 2016](https://arxiv.org/pdf/1608.06654)); with uncertain loads that is false precision. The robust minimum-length formulation optimises the worst of eroded, intermediate and dilated designs ([Qian & Sigmund analysis, arXiv 2101.08605](https://arxiv.org/pdf/2101.08605)), costing roughly three analyses per iteration, whereas 2D polygon offsets guarantee minimum rib width exactly. Level-set methods produce smooth boundaries but depend strongly on the initial guess ([Allaire, Jouve & Toader 2004](https://researchportal.ip-paris.fr/en/publications/structural-optimization-using-sensitivity-analysis-and-a-level-se/)). Mattheck's CAO and Method of Tensile Triangles deliver most of the corner benefit cheaply, and were checked against FE and fatigue tests ([Mattheck et al. 2007](https://www.iieta.org/journals/ijdne/paper/10.2495/D%26N-V2-N4-301-309)).

Evolutionary and layout methods map most directly onto AutoPocket. ESO's hard-kill removal can go badly wrong when removal re-routes load: Zhou and Rozvany showed a tie-beam whose compliance rose about **10x** ([arXiv 2104.04571](https://arxiv.org/pdf/2104.04571)). BESO fixes most of this with nodal sensitivity filtering, history averaging and re-admission of removed material ([review, arXiv 2210.10782](https://arxiv.org/pdf/2210.10782)). Ground-structure layout optimisation is the rigorous in-plane load-path method. Its plastic linear programme minimises lᵀa subject to equilibrium and stress limits, handles holes through shapely containment and multiple load cases through shared areas, and fits in **98 lines of Python**. It solved 231 nodes in 0.8 s, and 861 nodes in 6.7 s with adaptive member adding versus 47.7 s without ([He, Gilbert & Song 2019](https://eprints.whiterose.ac.uk/142746/1/trussPython.pdf)).

The decisive evidence comes from the Michell comparison ([Sigmund, Aage & Andreassen 2016](https://backend.orbit.dtu.dk/ws/files/140300672/Michell_plain.pdf)). On a 1 x 2 cantilever with Chan's analytical Michell value of 49.35:

| Design | Normalised compliance | Gap to Michell 49.35 |
|---|---|---|
| Optimised truss, 18 bars | 50.31 | about 2% above |
| 0/1 SIMP (p = 4), volume fraction 0.25 | 54.55 | about 11% above |
| Variable-thickness sheet, fractions 0.125-0.25 | 42.11-44.95 | below Michell (better) |

For through-cuts, a well-laid-out truss is therefore not inferior to SIMP; the continuum advantage appears only when thickness can vary, which is what floored mill pockets in highly loaded zones would offer. Hybrid de-homogenisation, which traces evenly spaced streamlines along optimised orientations, reaches **about 5% of the homogenised optimum in about 40 s of post-processing**, and its authors argue that regular, evenly spaced rib structures tolerate load changes better ([Wang, Westermann & Wu 2022](https://arxiv.org/pdf/2207.09172)). Isogrid, documented in NASA's handbook ([NTRS: CR-124075](https://ntrs.nasa.gov/citations/19730011184)), remains the quasi-isotropic, load-agnostic fallback. Pruning low-contribution ribs and then sizing their cross-sections is an established pipeline for stress-aligned rib networks ([Li et al., Computer Graphics Forum](https://diglib.eg.org/handle/10.1111/cgf13268)).

AutoPocket's existing guidance has a precise reading. At the all-solid start, the SIMP sensitivity −p·x^(p−1)·u_eᵀk₀u_e is proportional to element strain energy. v2's "load-guided" spacing field is therefore **SIMP iteration zero**, and it ignores how load paths move once material is removed.

| Method | Role for FTC plates | Runtime at FTC scale | Verdict |
|---|---|---|---|
| Rule-based keep-outs + isogrid | load-agnostic generator | milliseconds | keep (robust under uncertain loads) |
| Load-guided CDT truss | load-aware generator | 1 FEA + meshing | keep; add stress-direction alignment |
| ESO rib pruning | refinement | 1-5 s per round | upgrade to BESO (re-admission, averaging) |
| Rib-width sizing (OC) | refinement on fixed topology | 5-10 FEA | add |
| Short multi-case SIMP | guidance field and same-mass benchmark | ~1-3 min on 6k cells (v2's hex model) | add as guidance, not as geometry |
| Ground-structure LP | in-plane load-path seed or extra candidate family | ~0.1-7 s | optional |
| Stress-constrained TO, level set, homogenisation | none | minutes to hours, fragile | skip |
| Mattheck corner growth | local stress fix at hot corners | 1-3 FEA | add |

## Offsets and process presets make pockets cuttable; arcs make files usable

The cutting process sets the hard floors, and published numbers disagree enough that a tool needs source-labelled presets rather than one rule. Most FTC teams cannot cut metal in-house: gm0 notes that CO2 lasers "can only mark metal", that fiber lasers are rare, and points teams to send-out services ([gm0: Laser Cutting](https://gm0.org/en/latest/docs/custom-manufacturing/laser-cutting.html)).

SendCutSend's general rules give routed internal corners a 0.063 in radius with a 0.125 in minimum hole, and require laser holes of at least 50% of thickness ([SCS sheet cutting guidelines](https://sendcutsend.com/guidelines/sheet-cutting/)). Bridges must be at least 50% of thickness, ideally 1-1.5x ([SCS tolerances and features](https://sendcutsend.com/?p=89747)). Its 6061 page is stricter: holes at least material thickness, and holes and cutouts 1.5-2x thickness from edges ([SCS 6061 aluminum](https://sendcutsend.com/materials/6061-aluminum/)). Fabworks lists a 0.04 in minimum feature for 0.125 in 6061-T6 and needs no kerf compensation in files ([Fabworks aluminum](https://www.fabworks.com/resources/materials/sheet/aluminum); [Fabworks guidelines](https://www.fabworks.com/resources/guidelines/laser-cutting/sheet)). Protocase warns that dense cutout patterns warp metal on its laser and mills them on a router instead ([Protocase FAQ](https://www.protocase.com/resources/faq/cutouts)), which justifies a pocket-density warning on laser presets. Xometry recommends modelling internal corner radii 0.02-0.05 in larger than the tool radius to avoid stop-and-pivot chatter ([Xometry](https://www.xometry.com/resources/machining/cnc-machining-optimizing-internal-corner-radii/)).

| Preset (0.125 in 6061) | Min internal radius | Min hole | Min web/rib | Hole/pocket to edge |
|---|---|---|---|---|
| Send-out fiber laser | about kerf; ≥ 0.0625 in to honour the no-acute-tip rule | 0.125 in (= t) | 0.0625 in floor, 0.125-0.19 in recommended | 0.19-0.25 in (1.5-2 t) |
| School router, 1/8 in end mill | 0.0625 in floor, 0.08-0.11 in recommended | 0.125 in | ~0.06 in machinable, ≥ 0.125 in safer | user-set |
| Waterjet | 0.032 in | 0.070 in | ≥ 0.0625 in | ≥ 1.5 t |

v2's current defaults already sit on the conservative side of the router column. Its 2 mm tool radius is the 1.59 mm radius of a 1/8 in cutter plus 0.41 mm, inside Xometry's margin. Its 8 mm ribs are 2.5 t, above SendCutSend's 1-1.5 t recommendation, which also keeps rib stresses well clear of the Johnson buckling range.

In 2D, manufacturability is enforced exactly by construction rather than checked afterwards. The pocketable region is the plate offset inward by the border width, minus the hole keep-out rings, minus the rib strips. Each pocket is then opened by the tool radius (buffer −r, then +r), pockets separated by less than the minimum web are merged, and pockets below a minimum area are dropped. The community scripts work this way and show what students value. Students dislike Onshape Lighten for its hand-drawn helper sketch and per-loop selection ([Chief Delphi #139](https://www.chiefdelphi.com/t/some-helpful-featurescripts/361652/139)). The 2026 Enlighten script added per-hole halos; separate outer, inner, rib and hole-wall thicknesses; auto-correction that shrinks or skips regions that cannot be filleted; and failure visualisation ([Chief Delphi: Enlighten](https://www.chiefdelphi.com/t/enlighten-a-new-lightening-featurescript/522481)). CheeseIt applies isogrid, hex or circle patterns around bearing holes, and PatchIt repairs features left floating ([TLamp's FeatureScripts](https://www.chiefdelphi.com/t/tlamps-onshape-featurescripts/420133)). Commercial tools expose the engineering-mode analogues: Fusion's 2-axis cutting takes a cutting direction and a minimum wall thickness ([Autodesk Fusion help](https://help.autodesk.com/cloudhelp/ENU/Fusion-GenerativeDesign/files/GD-TWO-AXIS-CUTTING-REF.htm)), and Altair advises splitting parts into design and non-design spaces rather than loading the design space ([Altair Inspire help](https://help.altair.com/inspire/en_us/topics/inspire/structure/optimization_design_space_c.htm)).

Output format is where many student files fail. SendCutSend prefers DXF and refuses STL, and wants 1:1 scale, inch or mm units, closed paths, one cut layer and no duplicates ([SCS guidelines](https://sendcutsend.com/guidelines/sheet-cutting/)). Fabworks' preflight checks units, scale and closed profiles ([Fabworks guidelines](https://www.fabworks.com/resources/guidelines/laser-cutting/sheet)).

The exporter should use ezdxf (MIT licensed) and set `$INSUNITS` (1 = inches, 4 = mm), because DXF coordinates are otherwise unitless ([ezdxf: DXF Units](https://ezdxf.readthedocs.io/en/stable/concepts/units.html)). It should write CIRCLE for holes and LINE + ARC, or closed LWPOLYLINE with bulges (R2000+), for pockets ([ezdxf: LWPolyline](https://ezdxf.readthedocs.io/en/stable/dxfentities/lwpolyline.html)). If CadQuery/OCCT writes the DXF instead, it needs `approx="arc"`, because CadQuery otherwise emits splines "some software cannot handle" and defaults to mm ([CadQuery Import/Export](https://cadquery.readthedocs.io/en/latest/importexport.html)). Long chains of tiny segments make laser heads "rattle" ([Autodesk forum](https://forums.autodesk.com/t5/autocad-lt-forum/dxf-for-laser-cutting-has-too-many-line-segments-laser-head/td-p/11066258)). Since shapely buffers produce polylines, the exporter must rebuild true arcs at fillets, or the final pockets must be cut in OCP with real fillets. STEP is the second deliverable, for re-import into Onshape, Fusion or SOLIDWORKS, and SVG serves only for preview and 1:1 printing. A bounding-box readout in the chosen unit catches the classic 25.4x error.

## Two modes and a weakest-link provenance badge keep results honest

The audience sizes plates by eye. Chief Delphi mentors say pocketed plates "are often done based on feel" because proper analysis "is not worth the build-season time" ([Chief Delphi](https://www.chiefdelphi.com/t/aluminum-minimum-width-help/458606)), and many teams lack routers or waterjets entirely ([gm0: Machining](https://gm0.org/en/latest/docs/custom-manufacturing/machining.html)).

Geometry-only mode should therefore need just three inputs: plate geometry (STEP or DXF), the manufacturing route, and thickness. Hole protection is pre-filled from the class table for the student to confirm. Rib width, border, pattern style, symmetry, extra keep-outs and manual struts are advanced options. Fillet radius, minimum pocket width, mass and percent removed are derived, read-only values. The result should say plainly, "No strength analysis performed; rib widths come from manufacturing minimums and your settings", and may still show a relative stiffness indicator.

Engineering mode adds loads built from what students actually know: motor model and ratio give stall torque, teeth counts give mesh and belt forces, wheel size gives forces and speed, measured mass gives weight and traction, and bearing spacing and overhang give reactions and couples. Every value carries one of six provenance tags:

| Tag | Meaning |
|---|---|
| User-specified | entered by the student |
| Vendor datasheet | published spec, with a link |
| Calculated | derived by a formula shown on hover |
| Assumed default | tool default when the student doesn't know (μ = 0.51, T₂ = 0.2 Te, 15 kg) |
| Conservative screening | deliberate high-side value: stall into a stop, DLF 2, short collision stopping distance |
| Physically validated | confirmed by a team test, such as a pull or deflection test |

Only "physically validated" should ever lower a safety margin. The overall result badge should inherit the weakest input, following NASA-STD-7009's rule that "the lowest input data quality be used to represent the entire set of input data" when scoring input pedigree ([Validas: NASA-STD-7009B](https://www.validas.de/resources/glossary/nasa-std-7009b)). Results should show low, nominal and high values with a sensitivity bar, and keep stiffness criteria (bore misalignment, centre-distance change) separate from stress criteria. Disclaimer language should follow vendor practice, saying results do not replace "good engineering judgment" and should be confirmed by "experimental test data" ([Siemens Solid Edge Simulation notice](https://soliddna.com/SEHelp/ST5/EN/a_h/feamapexpress_important_information.htm)). The words "safe", "approved" and "certified" should never appear.

The architecture follows from the workloads. Geometry-only lightening is fast 2D offsetting and can run synchronously. Engineering runs belong on a job queue: FastAPI's own documentation points heavy computation to Celery with Redis or RabbitMQ rather than in-process background tasks ([FastAPI: Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)). A 2D top-view editor is the natural place to click holes and assign classes, with three.js as a 3D preview. The three.js Raycaster's line-picking threshold defaults to 1 world unit and must be scaled to the plate's units ([three.js Raycaster](https://threejs.org/docs/pages/Raycaster.html)). Browser-side OCCT exists (opencascade.js; replicad, MIT), but no bundle-size or maintenance figures were found to justify committing to it ([opencascade.js](https://ocjs.org/); [replicad](https://github.com/sgenoud/replicad)). One canonical geometry model (outline, holes with IDs, classes and rings, and pockets) should feed the editor, the solver and both exporters.

## ChatGPT's pipeline holds with four amendments

The research confirms ChatGPT's overall shape: a hybrid pipeline, two modes, and provenance labelling. It changes the role of SIMP, the order of manufacturing checks, the basis for protected regions, and the meaning of "validated".

| ChatGPT step | Research verdict | Amendment |
|---|---|---|
| Feature classification | confirmed | classify by diameter and pattern (goBILDA 4/8/14 mm, REV 9/12 mm, 14 mm bolt circle); ask which holes are fastened |
| Protected non-design regions | confirmed | ring per class = max(rule, strength, stiffness, contact, manufacturing); bearing rings governed by fit retention, not strength |
| Load cases | confirmed | FTC templates driven by stall torque; spring supports, cosine bearing pressure, two-plate couples; never "all holes fixed" |
| Screening FEA | confirmed with caveats | split membrane and bending; trust raster FEA for stiffness only; stress only at surfaces and interior percentiles |
| SIMP / load-path optimisation | amended | SIMP is a guidance field and same-mass benchmark; geometry comes from truss/isogrid + BESO + rib sizing; no stress-constrained TO |
| Boundary reconstruction | simplified | exact 2D Minkowski operations; protected geometry restored by Boolean with keep-outs |
| Manufacturing checks | moved earlier | build constraints into candidate generation, check again at export |
| Verification FEA | confirmed | body-fitted quadratic mesh, GCI, bore KPIs; physical test is the only validation |
| Two modes | confirmed | geometry-only states "no strength analysis" |
| Provenance labels | extended | add "vendor datasheet"; "validated" means physically tested; the result inherits the weakest label |

ChatGPT's list also omits three things the research adds: stiffness acceptance criteria based on bore alignment and centre distance, which usually limit FTC lightening; a rib slenderness rule; and bracketing of support stiffness with a "support-sensitive" flag.

## AutoPocket v2 has the right skeleton but grades against the wrong loads

v2's generate → validate → analyse → rank loop is sound, and several of its choices match the research directly. It measures every rule on the finished geometry and rejects violators before any FEA: clearance, web, tool radius, pocket width, a single connected piece, no pocket wrapping more than 120° around a hole, no corner sharper than 45°, and symmetry mismatch under 2% ([validate.py](C:\Users\abdul\Documents\autopoket\autopocket2\validate.py)). It keeps an archive of truss, guided-truss and isogrid candidates, mirrors pockets using phantom keep-outs, and re-checks its pick on a finer mesh ([runner.py](C:\Users\abdul\Documents\autopoket\autopocket2\runner.py)). The problems are in what it measures.

The solver itself is mostly sound. v2 reuses v1's single-layer hex8 raster, with selective reduced integration of the shear terms, E = 1 (relative units) and ν = 0.3, and stiffness scaled by each cell's fill fraction ([fea.py](C:\Users\abdul\Documents\autopoket\autopocket\fea.py)). A probe run for this report on a 300 x 24 x 3.175 mm cantilever strip ([fea_probe.py](C:\Users\abdul\AppData\Local\Temp\claude\C--Users-abdul-Documents-autopoket\ff6bb0af-88ab-4e62-bff3-e207d0e3f6f8\scratchpad\fea_probe.py)) gave **0.90 of the Euler-Bernoulli out-of-plane deflection and 1.00 in plane**. The element avoids the shear locking that wrecks plain C3D8, so v2's stiffness ratios are trustworthy as relative numbers.

Stress, however, is evaluated only at the element centroid, which in a one-layer model is the plate's mid-plane, exactly where bending and twisting stresses are zero. On the same strip, the reported out-of-plane 99th-percentile von Mises was **0.42-0.46 against an analytic surface bending stress of 7.44, an under-report of 16-18x**. The raw maximum also grew from 1.09 to 2.06 as cells shrank from 3 to 1 mm, the singularity signature at the clamp. The "peak stress ratio" v2 uses as a tie-breaker therefore measures transverse shear for two of its three load cases. The benchmark ratios of ×1.4-×9.6 ([bench/results.md](C:\Users\abdul\Documents\autopoket\bench\results.md)) also carry raster staircase effects.

The load cases are arbitrary in a way that matters. v2 picks the lightest design that keeps at least 33% of blank stiffness in the worst of three generic cantilever cases (out-of-plane bending, in-plane bending, torsion), each clamped at either end ([fea2.py](C:\Users\abdul\Documents\autopoket\autopocket2\fea2.py)). A second probe on a 300 x 120 mm plate with three 14 mm bores ([fea_probe2.py](C:\Users\abdul\AppData\Local\Temp\claude\C--Users-abdul-Documents-autopoket\ff6bb0af-88ab-4e62-bff3-e207d0e3f6f8\scratchpad\fea_probe2.py)) showed the governing case flipping with layout family:

| Layout (valid, from that probe) | Mass saved | Governing case | Stiffness retained |
|---|---|---|---|
| Isogrid | 41% | out-of-plane cantilever | 37% |
| Truss | 52% | in-plane cantilever | 18% |

The out-of-plane cantilever is the case the research says matters least for braced plates, and neither case resembles a gearbox plate whose bearing forces cancel internally. Nothing measures the bore centre-distance change or tilt that actually limits FTC plates.

Hole protection is a uniform 8 mm clearance with per-hole user overrides ([features.py](C:\Users\abdul\Documents\autopoket\autopocket2\features.py)), and the hole classifier labels holes ≤ 6.5 mm "fastener" and ≥ 9 mm "bearing" without using pattern, load or fit. By the analysis above, a uniform 8 mm is generous for M3/M4 fasteners and above the η = 0.6 ring for a 14 mm bore, but short of a literal e/D = 1.5-2 rule in a bearing's load direction. That is defensible at FTC loads, but only if the strength terms are checked rather than assumed.

Rib pruning removes the lowest-energy ribs a few at a time and never re-admits any ([layout.py](C:\Users\abdul\Documents\autopoket\autopocket2\layout.py)), which is the ESO pattern with its known path-change failures. The guidance field is SIMP iteration zero, and the validator has no rib-length or buckling rule. Export is STEP only, through OCP ([cadio.py](C:\Users\abdul\Documents\autopoket\autopocket\cadio.py)), with no DXF, and each job runs on a daemon thread inside the FastAPI server ([server.py](C:\Users\abdul\Documents\autopoket\autopocket2\server.py)). Runtime is a real problem: v2 took **21,810 s (about 6 hours) on blank_top.step against 9 s for v1** ([bench/results.md](C:\Users\abdul\Documents\autopoket\bench\results.md)), and one 6-case analysis pass costs 1.07 s at 6k cells and 9.83 s at 30k cells ([fea2.py](C:\Users\abdul\Documents\autopoket\autopocket2\fea2.py), measured during the research).

## A five-stage roadmap puts correct numbers before clever optimisers

The order matters. Every later stage ranks designs using the analysis, so a wrong stress or load model would quietly corrupt the optimiser. The runtime targets in the table are proposals, not sourced figures.

| Stage | Deliverable | Exit criterion |
|---|---|---|
| 0. Correct numbers | surface stress recovery; real material constants and units for engineering mode; regression benchmarks in CI | cantilever, plate, hole-Kt and torsion benchmarks pass |
| 1. Geometry-only mode | hole classes and computed rings; process presets; rib-length rule; arc-true DXF + STEP; "no strength analysis" badge | all samples export with units, closed contours and no splines; validator green |
| 2. Engineering screening | FTC load templates; spring supports; cosine bearing loads; decoupled plane-stress + plate solve; bore KPIs; envelope and support bracketing | Strafer-style worked example reproduced; support-sensitivity flag fires correctly |
| 3. Optimisation upgrades | BESO pruning; rib sizing; short min-max SIMP guidance and same-mass benchmark; stress-aligned seeding; Mattheck corners | bench shows equal or better stiffness at equal mass than v2.2 on every sample; "% of SIMP stiffness" reported |
| 4. Verification and validation | Gmsh body-fitted quadratic tier; three-mesh GCI; CalculiX cross-check; two-plate model; test-data entry that upgrades provenance | chosen designs carry GCI-qualified KPIs |
| 5. Web hardening | job queue; 2D hole editor; three.js preview; runtime caps | typical engineering run under ~60 s; no run over 10 min |

## Conclusion

For FTC plates, the question "which material contributes least" is answered mostly by geometry and stiffness rules, not by stress fields. Stresses are low almost everywhere. What FEA uniquely adds is knowing which bores are loaded, how stiff the load paths between them are, and whether paired bores stay aligned. A tool that gets hole classes, supports and bore KPIs right with a modest solver will beat one that runs a sophisticated optimiser against generic cantilevers. Under load uncertainty, regular rib vocabularies (triangle trusses and isogrid) are an asset rather than a compromise: the published data put them within a few percent of the optimum for through-cuts, and they forgive mis-specified loads, which shrinks the optimiser's job to steering, sizing and benchmarking.

The most consequential risk in the current tool is false confidence, not insufficient optimisation. A tie-breaking "peak stress ×1.4" that under-reports bending stress by an order of magnitude, judged against loads no FTC plate sees, reads like engineering without being it. The provenance badge, the two-mode split and the regression benchmarks are therefore not polish; they are what makes an engineering mode honest enough to ship. Physical tests (a spring-scale pull, a dial-gauge deflection) are the only thing that should ever relax a margin, so making those tests easy to log may matter more than any further algorithm.

## Implementation handoff for AutoPocket v2

**Constraint:** v1 (`autopocket/`) must stay untouched. New solver code goes in new `autopocket2/` modules (for example `autopocket2/fea3.py` and `autopocket2/loads.py`) that copy or wrap v1 functions rather than editing `autopocket/fea.py`. Re-run `bench/compare.py` after each step.

### Prioritised changes

| # | Change | Where | Basis | Effort |
|---|---|---|---|---|
| 1 | Recover stress at the top and bottom surfaces (Gauss points at z = ±t/2, or B evaluated at ζ = ±1), report max over both faces, keep excluding a 1-2 t zone around loads and supports; use interior-cell percentiles only | new v2 FEA module replacing `fea.Model.stresses` usage in `fea2.Analysis._solve` | centroid = mid-plane; probe shows 16-18x under-report | S |
| 2 | Regression test suite: out-of-plane and in-plane cantilever strips, SS and clamped square plates, strip torsion, mirror invariance; later LE1 and plate-with-hole Kt on the verification tier | `tests/` (new) | benchmark table above | S-M |
| 3 | Hole classes A-F with computed rings R_keep = d/2 + max(w_rule, w_shear, w_net, w_stiff, w_contact, w_mfg); diameter + pattern recognition (goBILDA 4 mm on 8 mm grid with 14 mm seats, REV 9/12 mm, 14 mm bolt circle); "fastened / bearing / unused" toggle in the UI; teardrop rings for known load directions; user overrides stay as hard floors | `features.py` (`classify_hole`, `Clearances`, `Domain`), `static/` UI | Lamé η rule, e/D floors, lug formulas | M |
| 4 | Process presets (send-out laser, router 1/8 in, waterjet, mill) setting tool radius, min web, min hole, edge distance, min pocket width and a pocket-density warning, each labelled with its source | `PlateRules` construction in `runner.py`/`server.py` | SCS, Fabworks, Xometry, Protocase | S |
| 5 | Rib slenderness rule: unsupported rib length ≤ 15.4 t/K (49 mm at K = 1) unless σ·DLF·SF < σ_cr passes; flag narrow free-edge rims in compression | `validate.py` | Euler/Johnson analysis | S |
| 6 | DXF export with ezdxf R2000+, `$INSUNITS`, CIRCLE/LINE/ARC or bulge LWPOLYLINE, one closed-contour layer, arcs rebuilt at fillets, bounding-box unit readout; keep STEP | new `autopocket2/export.py` | SCS/Fabworks file rules, ezdxf docs | S-M |
| 7 | FTC load templates (drive wheel, gearbox, arm, lift, intake) built from a motor table, ratio, teeth/pulley, wheel and mass, with DLF/SF and provenance tags; envelope of cases | new `autopocket2/loads.py` | stall-torque relations and examples | M |
| 8 | Supports as springs over washer annuli (standoff 3EI/L³ and 12EI/L³ brackets, axial EA/L), minimal 3-2-1 or inertia relief; cosine bearing pressure p₀ = 4F/(πdt) on the loaded half of each bore | new v2 FEA module | spring-support and bearing-load sources | M |
| 9 | Engineering-mode solver: decoupled 2D plane stress (Q4 incompatible-mode or Q8 on the existing grid) plus plate bending (DKT/MITC); factor once, multi-RHS; real E = 68.9 GPa, ν = 0.33, N and mm | new v2 FEA module | element benchmarks; decoupling | M-L |
| 10 | Bore KPIs: per-bore rigid fit, centre-distance change, lateral offset, tilt and ovalisation for bore pairs; in engineering mode these replace "worst cantilever stiffness retained" as the acceptance metric | v2 FEA module, `runner.py` ranking | bore-metric method | M |
| 11 | BESO-ise `prune_ribs`: re-energise every round, average with the previous round, re-admit removed ribs whose virtual energy is high, allow 1-for-1 swaps | `layout.py` | ESO failure, BESO fixes | S |
| 12 | Rib-width sizing: w_i ← clip(w_i·(Ū_i/Ū_target)^0.5, w_min, w_max), re-offset per rib, 3-6 iterations | `layout.py`, `shapes.cut_pockets` | rib pruning + sizing pipeline | M |
| 13 | Short SIMP guidance (p = 3, r_min ≈ 3 cells, OC, 30-60 iterations, min-max of c_k/c_k,blank, passive keep-outs, mirror-symmetrised) feeding `SpacingField` and a rib-keep score; same-mass SIMP reference in `bench/compare.py` | new `autopocket2/simp.py` | top99neo recipe; Michell data | M |
| 14 | Stress-direction-aligned CDT seeding; Mattheck-style radius growth at corners above the 95th-percentile stress | `layout.py`, `shapes.py` | Michell trajectories; CAO/MTT | M |
| 15 | Verification tier: Gmsh body-fitted quadratic mesh of the exported vector geometry, three-mesh GCI on the KPIs, optional CalculiX S8R/C3D20R cross-check | new module | NPARC GCI; LE1 accuracy | L |
| 16 | Runtime: coarse grid for search, reuse symbolic factorisation, cap candidates, move jobs to a queue | `runner.py`, `server.py` | 21,810 s benchmark outlier; FastAPI guidance | M |
| 17 | Two-mode UI with per-value provenance tags, a weakest-link result badge and disclaimer text | `static/`, `runner.report` | NASA-STD-7009 pedigree rule | S-M |

### Acceptance tests

| Test | Setup | Pass criterion |
|---|---|---|
| Out-of-plane stress recovery | 300 x 24 x 3.175 mm cantilever, unit tip load, h = 1-3 mm | surface σ two cells from the clamp within 10% of Mc/I; deflection within 12% of PL³/3EI (currently 0.90) |
| In-plane cantilever | same strip, in-plane load | deflection within 3% (currently 1.00); interior p99 within 15% of the analytic peak |
| Plate bending | 457 mm square, SS and clamped, uniform q | w_centre within 3% of 0.00406 and 0.00126 qa⁴/D |
| Strip torsion | 300 x 25 and 300 x 8 mm strips | twist within 5% of TL/GJ at b/t = 7.9; difference at b/t = 2.5 reported |
| Hole Kt (verification tier) | strip with hole, d/W = 0.25 and 0.5, L/W ≥ 3 | peak/net stress within 5% of 2.42 and 2.16 |
| Mirror invariance | any sample plate and its mirror image | identical pocket sets (≤ 0.1% area) and KPIs (≤ 1%) |
| Class-A ring | 14 mm bore, no loads | ring ≥ 5.6 mm and ≥ flange radius + 1 mm; e/D ≥ 2 toward free edges |
| Directional ring | 14 mm bore, 500 N in a known direction, e/D = 1.5 selected | 21 mm centre-to-edge only in the load direction; shear-out and net terms reported |
| Rib slenderness | layout with a 70 mm unsupported rib | rejected or flagged unless the explicit buckling check passes with DLF |
| DXF export | every sample, both unit choices | `$INSUNITS` matches the UI; only CIRCLE/LINE/ARC/LWPOLYLINE; all contours closed; no SPLINE; bounding box equals plate size; ezdxf round-trip passes |
| Process preset | router 1/8 in preset | every internal radius ≥ 1.59 mm + margin; every pocket width > 3.175 mm |
| Load template | 15 kg, 4 x 96 mm wheels, 5203 312 RPM, 30 mm overhang, 48 mm bearing spacing | 36.8 N static per wheel, 59.8 N near bearing, 1.568 m/s free speed |
| Support sensitivity | gearbox plate, soft vs stiff springs | "support-sensitive" flag when bore-KPI change > 25% |
| Bore KPI kinematics | imposed rigid translation, then rotation | centre-distance change = 0; tilt equals the imposed rotation |
| Provenance | any run using an "assumed default" load | result badge reads "screening"; "physically validated" is never auto-assigned |
| BESO regression | all samples | stiffness at equal mass ≥ the v2.2 ESO design |
| Runtime | all samples | geometry-only < 5 s per plate; engineering screening < 60 s typical; nothing > 10 min |

### Open decisions

| Decision | Options | Recommendation |
|---|---|---|
| Class-A defaults | η target 0.5/0.6/0.7; e/D 1.5 vs 2.0 toward free edges | η = 0.6 and e/D = 2.0 toward the outline, with the strength terms shown; validate with a press-fit and deflection test |
| Geometry-only FEA | keep the cantilever "relative stiffness" indicator, or drop FEA from this mode | keep it, labelled relative and non-engineering, with surface stresses fixed |
| Solver path | stay on the raster grid (cheap, SIMP-friendly) vs move to body-fitted tri6 now | grid for screening and optimisation, Gmsh body-fitted for verification only |
| Bore KPI limits | no published FTC allowable for centre-distance change or tilt | make them assumed defaults with visible provenance; collect team test data |
| Default mass and DLF | 15 kg; DLF 2 routine, 3-5 collision | ask for measured mass; label DLF "conservative screening" |
| Symmetry in engineering mode | keep the mirror-symmetry hard rule vs allow load-tailored asymmetry | keep symmetry by default (user rule); offer asymmetry as an explicit opt-in |
| Partial-depth pockets | mill-only floored pockets | defer; consider for highly loaded zones where variable thickness wins |
| Two-plate modelling | single plate + couple vs plate pair + standoffs + shaft beam | single plate with couple first; pair model in the verification tier |
| Licensing and deployment | Gmsh GPL linking; local Windows app vs Linux server | run Gmsh and CalculiX as separate processes; target a Linux server for multi-user |
