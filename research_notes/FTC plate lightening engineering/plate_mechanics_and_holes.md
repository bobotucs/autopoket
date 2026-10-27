# Plate Mechanics and Holes in 3.175 mm (0.125 in) 6061-T6 FTC Plates

Scope: equations, numbers and rules that an automated plate-lightening tool (it chooses where to cut through-pockets in flat 6061-T6 plates up to 18 x 18 in, robots 15-20 kg) can implement directly. Notation is consistent throughout:

```
t      plate thickness                      3.175 mm = 0.125 in
E      Young's modulus                      68.9 GPa = 10.0e6 psi  (68-69 GPa quoted; see Q1)
nu     Poisson's ratio                      0.33
G      shear modulus = E/(2(1+nu))          25.9 GPa = 3.76e6 psi (derived)
F_ty   tensile yield; F_tu tensile ultimate; F_su shear ultimate
F_bry  bearing yield;  F_bru bearing ultimate (depend on e/D)
d      hole diameter;  a = d/2 hole radius
e      edge distance: hole CENTRE to free edge, measured in the load direction
W      width of the strip/ligament region that contains the hole
P      load on a hole (N); P_d = design load = P * DLF * SF
Unit conversions: 1 ksi = 6.895 MPa; 1 in = 25.4 mm; 1 lbf = 4.448 N; 1 lbf*in = 0.1130 N*m
```

All worked examples below were computed by the researcher (Python, this session) from the cited formulas; inputs that are assumptions (not sourced) are labelled "assumed".

---

## Q1. 6061-T6 material properties: values, basis (minimum vs typical), temper variability

### Takeaway
For 3.175 mm 6061-T6 sheet use E = 68.9 GPa (10.0 Msi), nu = 0.33, and for strength design the specification minimums F_tu = 290 MPa (42 ksi), F_ty = 240 MPa (35 ksi); typical values (~310/270-276 MPa) are 7-15 % higher and must not be used as allowables. Typical bearing strengths (e/D = 2.0) are about 607 MPa ultimate / 386 MPa yield, i.e. bearing is rarely the limiting mode at FTC loads; the guaranteed MMPDS bearing allowables (e/D = 1.5 and 2.0) are in a licensed handbook and could not be retrieved.

### Cited Findings
- 6061-T6 tensile strength: minimum 290 MPa (42 ksi), typical 310 MPa (45 ksi); yield minimum 240 MPa (35 ksi), typical 270 MPa (39 ksi); elongation >= 8 % for thickness <= 6.35 mm (0.250 in), 10 % in thicker sections (Wikipedia attributes the T6 figures to makeitfrom.com, not explicitly to ASTM B209) — [Wikipedia: 6061 aluminium alloy](https://en.wikipedia.org/wiki/6061_aluminium_alloy)
- Young's modulus 68 GPa (9,900 ksi) in the infobox; text gives 69 GPa (10,000 ksi) "regardless of temper" citing Aluminum Standards and Data 2006 (Aluminum Association); Poisson's ratio 0.33; density 2.70 g/cm3; linear thermal expansion 2.32e-5 /K; specific heat 897 J/(kg K) — [Wikipedia: 6061 aluminium alloy](https://en.wikipedia.org/wiki/6061_aluminium_alloy)
- Fatigue: 97 MPa (14 ksi) at 5 x 10^8 completely reversed cycles, R.R. Moore rotating-beam machine and specimen (cites an archived ASM Material Data Sheet); aluminium has no well-defined knee in its S-N curve, and real fatigue limits are reduced by loading, gradient and surface-finish de-rating factors — [Wikipedia: 6061 aluminium alloy](https://en.wikipedia.org/wiki/6061_aluminium_alloy)
- Other tempers: 6061-O sheet/plate UTS max 150 MPa (22 ksi), yield max 83 MPa (12 ksi); 6061-T4 sheet/plate UTS min 210 MPa (30 ksi), yield min 110 MPa (16 ksi) (ASTM B209); T651 (stress-relieved plate) described as similar to T6 — [Wikipedia: 6061 aluminium alloy](https://en.wikipedia.org/wiki/6061_aluminium_alloy)
- Welding: heat-affected zone reverts to roughly T4 properties (~40 % strength loss); the Aluminum Design Manual recommends 165 MPa (24 ksi) design strength adjacent to an unheat-treated weld — [Wikipedia: 6061 aluminium alloy](https://en.wikipedia.org/wiki/6061_aluminium_alloy)
- Typical (not guaranteed) bearing strengths for 6061-T6 at edge distance / pin diameter = 2.0: bearing ultimate 607 MPa (88 ksi), bearing yield 386 MPa (56 ksi); the same datasheet lists typical tensile yield 276 MPa (40 ksi) and labels these "AA; Typical" — [Quickparts 6061 datasheet (ASM/MatWeb-derived)](https://quickparts.com/wp-content/uploads/2024/05/Aluminum-6061.pdf) (values from search-result extraction; the PDF body could not be parsed directly)
- MMPDS tabulates F_bru and F_bry at two edge-margin ratios, e/D = 1.5 and e/D = 2.0, and the difference between them is significant (forum statement) — [Eng-Tips forum](https://www.eng-tips.com/viewthread.cfm?qid=450377)
- MMPDS (Metallic Materials Properties Development and Standardization) is the successor of MIL-HDBK-5; a 6061 property page built on MMPDS-01 covers T6/T651/T4/T451 and defines A-basis and S-basis allowables — [AMES 6061 properties (MMPDS-01)](https://amesweb.info/Materials/Aluminum-6061-Rods-Bars-Shapes-Properties.aspx); [MMPDS.org](https://www.mmpds.org/?p=481)
- MMPDS allowables change between editions (example: 7075-T6 sheet F_bru went from 156 ksi in MMPDS-04 to 146 ksi in MMPDS-05), so the edition must be stated with any allowable — [Eng-Tips forum thread on bearing strength](https://www.eng-tips.com/threads/bearing-strength-vs-thickness.416439/latest)
- Welded 6061-T6 typical values (for contrast only): F_tu 24, F_ty 20, F_cy 20, F_su 15, F_sy 12, F_bru 50, F_bry 30 ksi — [AMES 6061 properties](https://amesweb.info/Materials/Aluminum-6061-Rods-Bars-Shapes-Properties.aspx)

### Inferences
- Recommended property set for the tool (store both columns; use "design" for checks):

```
Property             Design value (use)         Typical (info only)        Basis / source
E                    68.9 GPa (10.0e6 psi)      68-69 GPa                  AA, temper-independent
nu                   0.33                       0.33
G = E/(2(1+nu))      25.9 GPa (3.76e6 psi)      -                          derived
F_tu                 290 MPa (42 ksi)           310 MPa (45 ksi)           spec minimum vs typical
F_ty                 240 MPa (35 ksi)           270-276 MPa (39-40 ksi)    spec minimum vs typical
F_cy                 ~= F_ty (assumption)       -                          see Gaps
F_su                 see Gaps (use 0.6*F_tu = 174 MPa as a flagged placeholder)
F_bry (e/D=2.0)      see Gaps                   386 MPa (56 ksi)           typical
F_bru (e/D=2.0)      see Gaps                   607 MPa (88 ksi)           typical
S_f (5e8, R=-1)      97 MPa (14 ksi), polished rotating-beam; derate for real parts
rho                  2700 kg/m3 (0.0975 lb/in3)
alpha                23.2e-6 /K
```
- Basis vocabulary for the tool's documentation: S-basis = specification minimum; A-basis = value exceeded by 99 % of the population with 95 % confidence; B-basis = 90 % / 95 % (standard MMPDS definitions; the AMES page defines A and S; the B definition is the standard MMPDS convention, see Gaps). Treat ASTM B209 minimum (42/35 ksi) as the conservative design value when MMPDS is not available.
- Typical-to-minimum yield ratio is ~1.12-1.15, so a design that is "just OK" with typical values may be ~13 % overstressed for a minimum-property lot; at FTC load levels (Q5) this rarely matters for strength but matters for any check that is near its limit (e.g. rib buckling near the Johnson range, Q3).
- Bearing yield / tensile yield (typical, e/D = 2): 386/276 = 1.40; bearing ultimate / tensile ultimate: 607/310 = 1.96. MechaniCalc's simplified lug method uses S_bru ~= 1.5 S_tu (Q5), which is conservative relative to these e/D = 2 typical values.
- Product form: 0.125 in is "sheet" (< 0.250 in). Plates sold to FTC teams may be 6061-T6 or T651; for 3.175 mm sheet the mechanical properties are the same T6 values. A tool should let the user override the material record (e.g. 5052-H32 or 7075-T6 plates) rather than hard-code 6061.

### Gaps
- MMPDS 6061-T6 sheet design allowables (F_tu, F_ty, F_cy, F_su, F_bru and F_bry at e/D = 1.5 and 2.0, A/B/S basis, thickness range) could not be retrieved: MMPDS is licensed, and the AMES/MMPDS-01 page rendered its tables as blanks. Values often quoted from memory (e.g. F_su ~ 27 ksi, F_bru(1.5) ~ 67 ksi, F_bry(1.5) ~ 50 ksi) were searched for and NOT confirmed; do not hard-code them without the handbook.
- Typical shear strength (often quoted ~207 MPa / 30 ksi by ASM/MatWeb) and fracture toughness could not be verified: MatWeb/ASM pages returned 403/connection errors.
- The MMPDS definition of bearing yield (an offset-based criterion on hole elongation) and the D/t range over which tabulated bearing allowables apply were not verified.
- Minor conflict: typical yield 270 MPa (Wikipedia/makeitfrom) vs 276 MPa (ASM-derived datasheet). Immaterial for design (use 240 MPa minimum).

---

## Q2. Plate flexural rigidity, Kirchhoff vs Mindlin, analytic vs FEA, through-cuts vs partial-depth pockets

### Takeaway
D = E t^3 / (12(1 - nu^2)) = 206 N*m (1,826 lbf*in) for 3.175 mm 6061-T6. An FTC side plate is ~1,400x stiffer in its own plane than out of plane, so pockets should be judged mainly by their effect on in-plane load paths (a hole near the neutral axis of in-plane bending costs ~0 % stiffness; the same hole near an edge costs ~20 %). Thin-plate (Kirchhoff) theory is fine for panels (span/t ~ 10-140) but narrow ribs are beams, and the short, deep plate in in-plane bending needs shear deformation (Timoshenko) or FEA. Partial-depth pockets keep in-plane stiffness proportional to floor thickness (t) but bending stiffness proportional to t^3.

### Cited Findings
- Flexural rigidity D = E H^3 / (12(1 - nu^2)), H = plate thickness; small-deflection governing equation nabla^4 w = q / D; Kirchhoff kinematics u = -z dw/dx, v = -z dw/dy (normals stay normal); large deflections add membrane strains (1/2)(dw/dx)^2 — [Wikipedia: Bending of plates](https://en.wikipedia.org/wiki/Bending_of_plates)
- Navier solution, simply supported rectangular plate a x b, uniform pressure q0: w(x,y) = (16 q0 / (pi^6 D)) * sum_{m,n odd} sin(m pi x/a) sin(n pi y/b) / (m n (m^2/a^2 + n^2/b^2)^2); bending stresses sigma_x = -(12 D z / H^3)(w_xx + nu w_yy), sigma_y = -(12 D z / H^3)(nu w_xx + w_yy), tau_xy = -(12 D z / H^3)(1 - nu) w_xy — [Wikipedia: Bending of plates](https://en.wikipedia.org/wiki/Bending_of_plates)
- Thick plates require through-thickness shear deformation (Mindlin theory); the shear correction factor kappa usually = 5/6. The article gives no numeric thin/thick boundary — [Wikipedia: Bending of plates](https://en.wikipedia.org/wiki/Bending_of_plates)
- Out-of-plane (transverse) bending stress concentration at a hole is milder than in tension and depends on d/t: Kt = [1.793 + 0.131/(d/t) + 2.052/(d/t)^2 - 1.019/(d/t)^3] * [1 - 1.04(d/D) + 1.22(d/D)^2], sigma_nom = 6 M1 / ((D - d) t^2), valid 0 <= d/D <= 0.3 and 1 <= d/t <= 7 (D = plate width here) — [AMES, after Pilkey 2005](https://amesweb.info/stress-concentration-factor-calculator/central-circular-hole-in-plate.aspx)
- In-plane bending of a strip with a central hole: Kt at the hole edge = 2 with sigma_nom = 6 M d / ((D^3 - d^3) t); Kt at the plate edge = 2d/D with sigma_nom = 6 M D / ((D^3 - d^3) t) — [AMES, after Pilkey 2005](https://amesweb.info/stress-concentration-factor-calculator/central-circular-hole-in-plate.aspx)

### Inferences
Equations to implement (SI: N, mm, MPa; D in N*mm):

```
D        = E t^3 / (12 (1 - nu^2))
         = 68900 * 3.175^3 / (12 * 0.8911) = 2.062e5 N*mm = 206 N*m
Imperial = 10.0e6 * 0.125^3 / (12 * 0.8911) = 1,826 lbf*in  (1,808 with E = 9.9e6 psi)

In-plane membrane stiffness   A = E t / (1 - nu^2)       (scales with t)
Bending stiffness             D = E t^3 / (12(1 - nu^2)) (scales with t^3)

Partial-depth pocket with floor t_f (same plate t = 3.175 mm):
  t_f = 2.0 mm -> mass kept 63 %, membrane stiffness kept 63 %, bending stiffness kept 25.0 %
  t_f = 1.5 mm -> mass kept 47 %, membrane stiffness kept 47 %, bending stiffness kept 10.5 %
  t_f = 1.0 mm -> mass kept 31 %, membrane stiffness kept 31 %, bending stiffness kept  3.1 %
  through-cut   -> 0 % of everything locally, plus stress concentration at the pocket boundary
```
- Worked example A (in-plane vs out-of-plane; 350 x 120 x 3.175 mm side plate treated as a simply supported beam, span L = 350 mm, central load P = 300 N, assumed ~1.5x a 20 kg robot's weight on one plate including a dynamic factor):

```
In-plane (bending about the axis normal to the plate, depth h = 120 mm):
  I_in  = t h^3 / 12 = 3.175 * 120^3 / 12 = 457,200 mm^4
  M     = P L / 4 = 26,250 N*mm
  sigma = M (h/2) / I_in = 3.44 MPa
  delta_bending = P L^3 / (48 E I_in) = 0.0085 mm
  delta_shear   = P L / (4 kappa G A),  kappa = 5/6, A = h t  -> 0.0032 mm  (+38 %: deep beam, L/h = 2.9)
Out-of-plane (bending about the in-plane axis):
  I_out = h t^3 / 12 = 320 mm^4      (I_in / I_out = 1,428)
  sigma = M (t/2) / I_out = 130 MPa  (54 % of minimum yield)
  delta = P L^3 / (48 E I_out) = 12.2 mm
```
  Conclusion: FTC plates must be stabilised out of plane by standoffs/channels; inside a braced box the plate works in plane, where stresses are a few MPa and the governing issues are stiffness of load paths, hole rings and local stability, not gross strength.
- Worked example B (where a hole sits matters, in-plane bending of the same 120 mm deep plate, d = 14 mm bearing-size hole):

```
hole centred on the neutral axis : Delta_I = t d^3 / 12            =    726 mm^4  (0.16 % of I_in)
hole centred 45 mm off the axis  : Delta_I = t d^3/12 + t d (45)^2 = 90,737 mm^4  (19.8 % of I_in)
```
  Rule for the tool: for plates that act as in-plane beams, weight pocket "cost" by distance from the in-plane bending neutral axis (keep continuous top and bottom rims = "flanges"), and keep pockets out of the outer ~15-20 % of the depth near load points.
- Worked example C (validating D with Navier): simply supported 350 x 120 mm panel, q = 1 kPa: series gives w_max = alpha q b^4 / D with alpha = 0.01214 (b = 120 mm, a/b = 2.92), w_max = 0.0122 mm. This matches the classic Timoshenko table value (~0.0122 for a/b ~ 3). Pressure loads are not typical in FTC; this is only a sanity check of D.
- Kirchhoff applicability for FTC geometry: unpocketed panel spans 30-450 mm give span/t = 9-142; the commonly used thin-plate threshold is span/t > ~10-20 (see Gaps), so Kirchhoff is valid for panels and Mindlin corrections are negligible. Ribs 6-10 mm wide have width/t = 1.9-3.1, so they are not plates; model them as beams (Euler-Bernoulli when rib length / rib depth in the bending plane > ~10, otherwise Timoshenko).
- Analytic formulas suffice for: material ring checks around individual holes (Q5), rib column buckling (Q3), Kt estimates for isolated holes in strips (Q4), ranking pocket layouts by in-plane section properties (example B), partial-pocket t^3 scaling.
- FEA (2D plane-stress shell, ~1-2 mm elements near holes) is advisable when: hole-to-hole or hole-to-pocket ligaments are < ~2 d or < ~2 t (interaction makes single-hole Kt unreliable); load paths are unclear (multiple attachment points, statically indeterminate plate + standoffs); out-of-plane loads act on a pocketed plate (it becomes a grillage of ribs, where torsion of ribs matters); impact or vibration (modal) behaviour is needed. A practical automated approach is a fast 2D linear plane-stress FE solve of the candidate layout with point loads at bearing bores, followed by max-stress x Kt and stiffness-loss checks.
- Out-of-plane hole Kt example: d = 8 mm hole, t = 3.175 mm (d/t = 2.52), d/D = 0.1 -> Kt = 2.104 x 0.908 = 1.91.

### Gaps
- No fetched source gave a numeric thin/thick plate boundary; the span/t > ~10-20 rule is standard textbook practice (Timoshenko & Woinowsky-Krieger, Reddy) but was not verified in this session.
- No source located that gives closed-form equivalent stiffness of triangular (isogrid-style) through-pocket patterns in 3.175 mm plate; NASA's Isogrid Design Handbook would be the place to look.

---

## Q3. Elastic buckling of thin plates and of narrow ribs; relevance at 3.175 mm with 6-10 mm x 30-80 mm ribs

### Takeaway
A rib cut from 3.175 mm plate buckles out of plane with radius of gyration r = t/sqrt(12) = 0.917 mm regardless of rib width, so slenderness is L_eff/r = 3.78 L_eff/t. Elastic (Euler) buckling below minimum yield occurs only for L_eff > ~49 mm; an 80 mm pin-ended rib buckles at ~89 MPa (~2.3 kN for an 8 mm rib), a 50 mm rib at ~177 MPa (Johnson). FTC rib forces are typically ~0.1-0.5 kN (stress ~5-20 MPa), so buckling is a secondary but real check for long ribs under impact, and it is the reason to keep unsupported rib length below ~50-60 mm (or ~15-20 t).

### Cited Findings
- Euler critical load P_cr = pi^2 E I / (K L)^2; critical stress sigma_cr = pi^2 E / (L_e / r)^2 with L_e = K L and r = sqrt(I/A); pin-ended K = 1; practical design K values should be increased over theoretical; Euler applies only while sigma_cr < yield; Johnson's parabolic formula is used for low slenderness; assumptions: straight, homogeneous, axially loaded, elastic — [Wikipedia: Euler's critical load](https://en.wikipedia.org/wiki/Euler%27s_critical_load)
- Plate compressive buckling stress F_cr = eta * k * pi^2 E / (12(1 - nu^2)) * (t/b)^2 (eta = plasticity reduction, 1 for elastic) — [Engineering Library, Air Force Stress Manual: plates in axial compression](https://engineeringlibrary.org/reference/analysis-of-plates-axial-compression-air-force-stress-manual)
- k = 4.0 for a long plate with all edges simply supported (stiffened element); k = 0.425 with one unloaded edge free and the other simply supported (unstiffened element) — [NPTEL cold-formed steel: local buckling](https://archive.nptel.ac.in/content/storage2/courses/105106113/5_cold_form_steel/3_local_buckling.pdf)
- k = 0.425 assumes the buckle half-wavelength is free to equal the plate length; if the buckle is restricted to about twice the width, k rises to roughly 0.675 — [Steel Australia: Stiffened and unstiffened compression elements](https://www.steel.org.au/getattachment/46f21e2b-188d-433d-b838-d5e67788d51f/Stiffened-and-unstiffened-compression-elements-Local-buckling_bk150.pdf)
- The low k of an outstand is because the free edge lets transverse strips rotate with little bending resistance — [Steel-INSDAG Chapter 7](https://www.steel-insdag.org/assets/frontend/trmpdf/Chapter7.pdf)

### Inferences
Equations (6061-T6, t = 3.175 mm; values computed):

```
Plate coefficient   C_p = pi^2 E / (12 (1 - nu^2)) = 63,593 MPa
Plate buckling      sigma_cr = k * C_p * (t/b)^2
  b = 120 mm : k=4 -> 178 MPa ; k=0.425 -> 18.9 MPa
  b =  60 mm : k=4 -> 712 MPa ; k=0.425 -> 75.7 MPa
  b =  30 mm : k=0.425 -> 303 MPa (> yield, so no elastic buckling)
  b = 450 mm (18 in plate) : k=4 -> 12.7 MPa
Shear buckling (standard SS-plate form, not verified here, see Gaps):
  tau_cr = k_s C_p (t/b)^2, k_s = 5.35 + 4 (b/a)^2 ; 120 x 350 mm panel: k_s = 5.82 -> 259 MPa (> shear yield) -> no shear buckling

Rib column buckling (out of plane governs because t < rib width b_r):
  r_out = t / sqrt(12) = 0.9165 mm     (independent of rib width)
  r_in  = b_r / sqrt(12) = 2.31 mm for b_r = 8 mm (in-plane; never governs when b_r > t)
  Euler:   sigma_E = pi^2 E / (K L / r)^2
  Johnson (standard form): sigma_J = sigma_y - (sigma_y^2 / (4 pi^2 E)) (K L / r)^2, used when K L / r < pi sqrt(2E/sigma_y)
  Euler = yield at       K L / r = pi sqrt(E/sigma_y)   = 53.2 (sigma_y = 240) / 49.6 (sigma_y = 276)
  Johnson/Euler tangent  K L / r = pi sqrt(2E/sigma_y)  = 75.3 (240)           / 70.2 (276)
  -> elastic buckling governs for K L > 75.3 * 0.9165 = 69 mm (sigma_y = 240 MPa)
```

```
Rib buckling table (sigma_y = 240 MPa minimum; P_cr = sigma_cr * b_r * t)
L (mm)  K     KL/r   sigma_Euler  sigma_design   P_cr (b_r=6 / 8 / 10 mm)
30      1.0   32.7   635 MPa      217 MPa (J)    4.1 / 5.5 / 6.9 kN
50      1.0   54.6   228 MPa      177 MPa (J)    3.4 / 4.5 / 5.6 kN
50      0.7   38.2   466 MPa      209 MPa (J)    4.0 / 5.3 / 6.6 kN
80      1.0   87.3    89 MPa       89 MPa (E)    1.7 / 2.3 / 2.8 kN
80      0.7   61.1   182 MPa      161 MPa (J)    3.1 / 4.1 / 5.1 kN
80      0.5   43.6   357 MPa      200 MPa (J)    3.8 / 5.1 / 6.3 kN
```
- Effective length: ribs in a through-pocketed plate are joined at nodes that give partial rotational restraint out of plane; K = 1.0 (pinned) is a safe default; K ~ 0.7 is defensible for ribs framing into wide solid regions or bosses; K = 0.5 (fixed-fixed) should not be used without FEA (Wikipedia notes practical K should exceed theoretical).
- FTC relevance check (worked): the in-plane beam of Q2 example A, if converted to a truss with chords ~110 mm apart, has chord force M/h_eff = 26,250 / 110 = 239 N, i.e. 9.4 MPa in an 8 mm rib. Against 89 MPa (80 mm pinned rib) the buckling margin is ~9.5; against 177 MPa (50 mm rib) ~19. With an impact factor of 5 (Q6) the 80 mm pinned rib margin drops to ~1.9. Therefore: buckling is not critical for typical ribs at static FTC loads, but long unsupported compression ribs (> ~60-70 mm) become the weak link under impact. Rule for the tool: L_rib_max = min(user limit, ~15.4 t / K) for ribs whose Euler stress stays above minimum yield (L_eff < 53.2 r = 15.4 t, i.e. 49 mm at K = 1), or check sigma_rib * SF < sigma_cr explicitly.
- Rib width does not change the out-of-plane buckling stress; it changes only the force capacity (proportional to b_r) and in-plane bending stiffness (proportional to b_r^3). So a "wider rib" fixes strength and in-plane stiffness but not slenderness; shortening the rib (more nodes) fixes slenderness.
- Plate-panel buckling is irrelevant for the remaining solid regions at FTC stresses (178 MPa for a 120 mm SS panel vs a few MPa applied), but a long free edge in compression (e.g. the compression rim of an in-plane-loaded plate between supports, k = 0.425) buckles at only ~19 MPa for b = 120 mm. Pockets that leave a narrow rim along a free edge convert that rim into a rib, which is then governed by the rib column formula above.
- Local yielding/crippling at rib nodes (stress concentration at fillets) is addressed by Kt in Q4, not by buckling.

### Gaps
- Shear buckling coefficient k_s = 5.35 + 4(b/a)^2 and the in-plane-bending buckling coefficient (k ~ 23.9 for an SS plate in pure bending) are standard Timoshenko & Gere results but were not verified against a fetched source.
- The Johnson parabola formula itself was not reproduced on the fetched Wikipedia page (only named); the form given is the standard textbook form.
- No source found on effective-length factors for ribs inside isogrid/truss-pocketed thin plates (out-of-plane rotational restraint at nodes); FEA or test needed for K < 1.

---

## Q4. Stress concentration factors (Peterson/Pilkey): finite-width holes, interacting holes, slots, notches, corner radius

### Takeaway
For a hole of diameter d in a strip of width W under tension, the net-section factor is Kt_n = 3.000 - 3.140(d/W) + 3.667(d/W)^2 - 1.527(d/W)^3 (Pilkey; Heywood's simpler Kt_n = 2 + (1 - d/W)^3 agrees within 2 % for d/W <= 0.5); the peak stress relative to the GROSS stress is Kt_g = Kt_n / (1 - d/W), which grows rapidly as the ligament shrinks (3.03 at d/W = 0.1, 4.25 at 0.5, 6.76 at 0.7). Elongated cut-outs are benign when their long axis is parallel to the principal stress (Kt ~ 1 + 2b/a) and severe when perpendicular (Kt ~ 1 + 2 sqrt(a/rho)); sharp internal pocket corners are the main avoidable stress raiser.

### Cited Findings
- Central hole in finite-width plate, tension: Kt = 3.000 - 3.140(d/D) + 3.667(d/D)^2 - 1.527(d/D)^3, valid 0 <= d/D <= 1, sigma_nom = P / ((D - d) t) (net section), sigma_max = Kt sigma_nom — [AMES calculator, after Pilkey, Formulas for Stress, Strain and Structural Matrices, 2nd ed. 2005](https://amesweb.info/stress-concentration-factor-calculator/central-circular-hole-in-plate.aspx)
- Eccentric hole (centre at distance c from the near edge, plate width D): Kt = 3.000 - 3.140(d/2c) + 3.667(d/2c)^2 - 1.527(d/2c)^3 with sigma_nom = [P sqrt(1 - (d/2c)^2) / (D t (1 - d/2c))] * [(1 - c/D) / (1 - (c/D)(2 - sqrt(1 - (d/2c)^2)))], maximum at the edge of the hole nearest the plate edge — [AMES calculator, after Pilkey 2005 / Roark 7th ed.](https://amesweb.info/stress-concentration-factor-calculator/eccentric-circular-hole-in-plate.aspx)
- Heywood and Howland formulations for a central hole in a finite plate apply for d/W up to 0.9; both global (gross) and net SCFs are defined; FE comparison over d/W = 0.1-0.9 showed Heywood/Howland are most valid for plate length/width L/W = 2 (shorter plates deviate) — [Deghboudj, Satha, Boukhedena, U.P.B. Sci. Bull. Series D 78(4), 2016](https://www.scientificbulletin.upb.ro/static/pdfs/rezeef_601718.pdf)
- Kt is defined on the gross section in some references and depends only on shape, not size; circular hole in an infinite plate Kt = 3 (Kirsch); elliptical hole with semi-axis a perpendicular to the load and b parallel: sigma_max = sigma (1 + 2a/b) = sigma (1 + 2 sqrt(a/rho)), rho = radius of curvature at the end of the major axis; as rho -> 0 Kt -> infinity (use fracture mechanics); mitigation: relief holes, larger fillets at internal corners, shape changes, crack-tip blunting holes; ductile materials redistribute by local yielding while fatigue cracks almost always start at stress raisers — [Wikipedia: Stress concentration](https://en.wikipedia.org/wiki/Stress_concentration)

### Inferences
Equations to implement:

```
Strip with a hole, tension, d = hole diameter, W = strip (ligament region) width
  Kt_n(d/W) = 3.000 - 3.140 x + 3.667 x^2 - 1.527 x^3,  x = d/W     (Pilkey)
  Kt_n(d/W) ~= 2 + (1 - x)^3                                         (Heywood)
  Kt_g      = Kt_n / (1 - x)        sigma_peak = Kt_g * sigma_gross  = Kt_n * sigma_net

x = d/W   Kt_n Heywood   Kt_n Pilkey   Kt_g (Heywood)
0.1       2.729          2.721         3.03
0.2       2.512          2.506         3.14
0.3       2.343          2.347         3.35
0.4       2.216          2.233         3.69
0.5       2.125          2.156         4.25
0.6       2.064          2.106         5.16
0.7       2.027          2.075         6.76
```
- Implementation note (inverse design of the ligament w on each side of a hole in a strip that carries force F): W = d + 2w, sigma_peak = Kt_n(d/W) * F / (2 w t) <= sigma_allow. Because Kt_n lies between 2 and 3 for all d/W, a closed-form conservative minimum is w >= 3 F / (2 t sigma_allow); iterate with Kt_n(d/W) for a tighter value.
- Worked example (fastener hole between two pockets): M4 clearance hole d = 4.5 mm (assumed size), 3.0 mm ligaments each side -> W = 10.5 mm, d/W = 0.429 -> Kt_n = 2.19, Kt_g = 3.83. A rib force of 240 N (Q3 example) gives sigma_net = 240 / (6.0 x 3.175) = 12.6 MPa, peak 27.6 MPa: fine statically (SF ~ 8.7 on 240 MPa) and for fatigue (Q6).
- Interacting holes: a row of holes perpendicular to the load can be approximated as a strip of width W = pitch p containing one hole (symmetry lines between holes act like constrained, not free, edges, so this is believed to be conservative; see Gaps). Holes in line with the load shield each other (lower Kt). A hole next to a pocket: treat the pocket boundary as a free edge and use the eccentric-hole formula with c = distance from hole centre to pocket edge.
- Slots / obround pockets (equivalent-ellipse estimate, upper-bound-ish): slot 30 x 8 mm (a = 15, rho = 4) with its long axis perpendicular to the load: Kt ~ 1 + 2 sqrt(15/4) = 4.87; same slot parallel to the load: Kt ~ 1 + 2(4/15) = 1.53. Rule for the tool: orient elongated pockets with their long axis along the local principal stress / rib direction; this is the same logic behind triangular truss pockets whose edges run along rib force lines.
- Pocket corner radius: the Inglis form shows Kt grows as sqrt(a/rho); halving corner radius raises Kt by ~sqrt(2) in the sharp-corner limit. Practical rule: corner radius >= cutter radius (1/8 in cutter -> r = 1.59 mm), prefer r >= t (3.2 mm) at corners that sit on primary load paths, and avoid acute pocket tips (consistent with the project's existing "no acute wedge tips" shape rule). For FTC load levels the corner rule matters mainly for fatigue and impact crack initiation (Q6), not static strength.
- Ductility: 6061-T6 elongation >= 8 % means static overload redistributes at holes; static strength checks can use net-section stress (Kt ~ 1) with yield as the limit, while fatigue and "first yield / permanent hole ovalization" checks must use Kt (or Kf).

### Gaps
- Peterson's charts for interacting holes (two holes, infinite rows, staggered patterns), rectangular holes with rounded corners, and pin-loaded holes (lugs) were not accessible online; the row-of-holes approximation above is the researcher's inference, not a verified Peterson value.
- No verified closed-form Kt for triangular pockets with filleted corners; FEA recommended for calibration.
- The exact Heywood/Howland equations in the 2016 paper were garbled during PDF extraction; the Heywood net form quoted above was cross-checked numerically against Pilkey's polynomial (agreement within 2 % for d/W <= 0.5), not read directly from the paper.

---

## Q5. Bolted-joint and bearing-bore design; how much material must remain around loaded bores and fastener holes

### Takeaway
Classical pin/bolt failure modes (bearing, net-section tension, shear-out/tear-out, hoop/press-fit) can be computed analytically from load and geometry; at FTC loads (hundreds of N) the strength-required edge ligaments come out below 1 mm, so the remaining ring is in practice set by (a) edge-distance rules (e/D >= 1.5 minimum, 2.0 preferred, as used for MMPDS bearing allowables; Eurocode 3 minimum 1.2 d0), (b) the stiffness needed to hold a bearing fit and resist ovalization, which can be computed with the Lamé ring solution, and (c) manufacturing/impact robustness. A load-dependent ring = max(rule floor, strength demand, stiffness demand, manufacturing minimum) is implementable.

### Cited Findings
- Simplified lug/pin-hole method (after Bruhn), stated as not for critical structure: net tension A_t = (w - D_h) t, P_tu = S_tu A_t (uniform stress, Kt ignored); shear tear-out on two planes A_s = 2 L_sp t, conservative L_sp = a = e - 0.5 D_h (e = edge distance to centre), refined L_sp from a 40-degree line from the pin centre, P_su = S_su A_s; bearing A_br = D_p t, P_bru = S_bru A_br with S_bru ~= 1.5 S_tu (lesser of lug and pin) — [MechaniCalc: Lug Analysis](https://mechanicalc.com/reference/lug-analysis)
- Air Force (Melcon-Hoblit) lug method: bearing/shear-out capacity uses F_bru and F_bry switched at e/D < 1.5 vs >= 1.5, an allowable-load coefficient K read from curves for D/t <= 5 and D/t > 5, and net-section capacity P_nu = K_n min(S_tu, 1.304 S_ty)(w - D) t with K_n from material-dependent curves — [MechaniCalc: Lug Analysis](https://mechanicalc.com/reference/lug-analysis)
- Edge distance history and practice: 1.5 D was the standard metal edge distance in the 1950s; after the Comet accidents UK practice moved to a minimum of 2 D (forum statement); MIL-HDBK-5/MMPDS bearing allowables are given at e/D = 2.0 and 1.5 — [Eng-Tips forum](https://www.eng-tips.com/viewthread.cfm?qid=450377)
- Eurocode 3 (EN 1993-1-8 Table 3.3) minimums for normal holes: end distance e1 = 1.2 d0, spacing in the load direction p1 = 2.2 d0 (d0 = hole diameter); e.g. M20 (d0 = 22 mm) -> e1 = 27 mm, p1 = 49 mm (rounded up) — [Eurocode Applied: bolt design properties](https://eurocodeapplied.com/design/en1993/bolt-design-properties); software design-rule checks use the same 1.2 d0 / 2.2 d0 limits — [IDEA StatiCa knowledge base](https://www.ideastatica.com/de/schrauben-kantenabstand)
- AISC 360 Table J3.4 permits lesser edge distances if the bolt bearing and tear-out equations of Section J3.10 are satisfied (forum quotation of footnote [a]) — [Eng-Tips forum](https://www.eng-tips.com/viewthread.cfm?qid=151072); under the AISC Specification tear-out strength is proportional to the clear distance, in the load direction, from the hole edge to the edge of the adjacent hole or material — [AISC Engineering Journal](https://ej.aisc.org/index.php/engj/article/download/1180/1179/1179)
- SKF: thin-walled housings, light-alloy housings and hollow shafts require a tighter fit than thick-walled steel or cast-iron housings and must have sufficient strength; heavier-than-normal interference is advised because fits are less effective in thin-walled or light-alloy housings; for non-ferrous housings tighter fits may be needed; the heavier the load, the tighter the required interference (SKF gives an interference-vs-load formula); bearing rings usually run hotter than seats; avoid uneven wall thickness and seat discontinuities that can distort rings — [SKF: Selecting fits](https://www.skf.com/us/products/rolling-bearings/principles-of-rolling-bearing-selection/bearing-selection-process/bearing-interfaces/selecting-fits); [SKF bearing maintenance handbook](https://cdn.skfmediahub.skf.com/api/public/0901d1968013be94/pdf_preview_medium/0901d1968013be94_pdf_preview_medium.pdf) (as summarised from search results; the JS-rendered page could not be fetched directly)
- NSK: aluminium expands more than steel, so an outer-ring interference fit in an aluminium housing needs more interference than in steel; thin-wall housings need special conditions — [NSK technical note P_TI-0001](https://nsk.com/content/dam/nsk/eu/en_gb/documents/P_TI-0001_EN.pdf) (search-result summary; PDF text not extractable)
- Fit selection depends on shaft and housing material, wall thickness and surface accuracy; a ring under rotating load needs a tight fit, a ring under stationary load can be loose; tight fits give uniform support around thin rings — [Bearing fit handout (TTE)](https://tte-lisa.ac.uk/wp-content/uploads/vle_content/Phase2/mechanical/CME8/Resource/Bearing%20Fit%20Handout.pdf)
- Outer-ring creep in housings wears housings; it is a recognised failure mode for thin outer rings — [JTEKT Engineering Journal](https://www.jtekt.co.jp/e/engineering-journal/assets/1014/1014e_09.pdf)
- Contrary data point: THK recommends N7 housing tolerance for spherical plain bearings in light-alloy housings (vs H7 for steel) — [THK spherical plain bearing design](https://www.thk.com/eu/en/products/joints/spherical_plain_bearing/design/0001/); an Eng-Tips user reported noise problems after following a K7 catalogue tolerance in an aluminium (LM27) housing (anecdotal) — [Eng-Tips forum](https://www.eng-tips.com/viewthread.cfm?qid=17723)
- Press/shrink fits: Lamé thick-cylinder equations give radial and hoop stresses; radial interference = shaft compression + hole expansion — [Roymech: thick cylinders](https://roymech.org/Useful_Tables/Mechanics/Cylinders); Lamé assumes constant interface pressure along the axial length (not valid with shoulders/grooves) — [Press fit calculator (FIRGELLI)](https://www.firgelliauto.com/blogs/engineering-calculators/press-fit-calculator-interference-and-force), which also gives the simplified single-modulus form p = (delta/d_i) E (d_o^2 - d_i^2)/(d_o^2 + d_i^2)

### Inferences
Equations to implement for a loaded hole (diameter d, plate t, design load P_d acting in direction u; e measured from hole centre to the nearest free edge or pocket boundary along +u; w_side = ligament width to free edges/pockets perpendicular to u):

```
1. Bearing          sigma_br = P_d / (d t)             <= F_bry(e/D) / SF_y   (and <= F_bru / SF_u)
                    (independent of ring width: if it fails, the plate is too thin -> boss, doubler or bigger d)
2. Shear-out        P_d <= 2 (e - d/2) t F_su          -> e_req = d/2 + P_d / (2 t F_su)
3. Net tension      P_d <= 2 w_side t F_ty / Kt_pin    -> w_side_req = Kt_pin P_d / (2 t F_ty)
                    (Kt_pin for a pin-loaded hole is higher than the open-hole value; use 3 as a flagged placeholder)
4. Rule floor       e >= c_e d  with c_e = 1.5 (minimum, MMPDS lower tabulated ratio) or 2.0 (preferred);
                    hole-to-hole pitch >= 2.2-2.5 d (EC3 p1 = 2.2 d0)
5. Press-fit hoop   (bearing bores with interference)  see Lamé block below
6. Stiffness        (bearing bores)                     see eta block below
7. Manufacturing    w >= w_mfg (user: cutter diameter, minimum web the shop/router holds, e.g. >= t)
Ring/edge requirement = max(1..7), evaluated in every direction the load can act
(omnidirectional when the load direction is unknown, e.g. belt/chain tension that changes with tensioner position).
```

Lamé ring around a bore (plane stress, bore radius a, ring outer radius b, free outer boundary = fully encircling pocket; this is a lower bound on support because real rings connect to ribs):

```
C          = (b^2 + a^2) / (b^2 - a^2)
Interface pressure for a rigid insert with diametral interference delta:
   p       = delta * E / (d (C + nu))            (b -> infinity: C -> 1, p = delta E / (d (1 + nu)))
Hoop stress at the bore: sigma_theta = p * C    (radial stress = -p)
Retained fit pressure / radial stiffness vs solid plate:
   eta(b/a) = (1 + nu) / (C + nu)
   inverse:  C = (1 + nu)/eta - nu ;  b/a = sqrt((C + 1)/(C - 1))
b/a :  1.25   1.43   1.5    1.75   2.0    2.5    3.0
eta :  0.27   0.41   0.45   0.58   0.67   0.78   0.84
Target eta -> b/a -> ring width (b - a) for d = 14 mm / d = 22 mm bores:
eta 0.50 -> 1.58 -> 4.1 / 6.4 mm
eta 0.60 -> 1.80 -> 5.6 / 8.9 mm
eta 0.70 -> 2.12 -> 7.9 / 12.4 mm
eta 0.75 -> 2.35 -> 9.4 / 14.8 mm
```
- Worked example 1, bearing bore (assumed geometry: 14 mm OD flanged bearing seat, t = 3.175 mm; assumed design load P_d = 500 N, e.g. chain/belt tension plus a wheel reaction with dynamic factor):

```
bearing stress    = 500 / (14 x 3.175)            = 11.2 MPa   (typical F_bry(e/D=2) = 386 MPa -> margin ~34)
shear-out e - d/2 = 500 / (2 x 3.175 x 186..207)  = 0.38-0.42 mm
net tension       = 500 / (3.175 x 240)           = 0.66 mm total (x Kt_pin 3 -> ~1 mm per side)
rule e/D = 1.5    -> e = 21 mm   -> ligament 14 mm  (e/D = 2.0 -> 28 mm -> ligament 21 mm)
press fit, delta = 0.010 mm diametral (assumed light interference), rigid outer ring:
   solid plate      p = 37.0 MPa, sigma_theta = 37.0 MPa
   ring OD 30 mm    p = 26.1 MPa, sigma_theta = 40.6 MPa
   ring OD 20 mm    p = 15.1 MPa, sigma_theta = 44.2 MPa   (eta = 0.41: fit pressure lost by 59 %)
   ring OD 18 mm    p = 11.2 MPa, sigma_theta = 45.5 MPa
thermal: (23.2 - ~11.5) e-6/K x 20 K x 14 mm = 3.3 um of diametral loosening for a 20 K rise
```
  Interpretation: strength demands are tiny; the binding constraints are the e/D rule (if adopted literally it is very conservative at these loads) and fit retention / ovalization stiffness. A defensible, load-independent bearing rule derived analytically is eta >= ~0.6, i.e. ring outer diameter >= ~1.8 x bore diameter (ring width >= ~0.4 d) where the ring is fully encircled by pockets, plus a flange-seat floor (the ring must extend at least to the bearing flange OD so the flange bears on solid metal). The eta target itself is a design choice (no manufacturer number found).
  Hoop stresses from realistic press fits (~40-50 MPa) are well below 240 MPa yield, so press-fit rupture is not the issue; ring compliance (loss of fit, outer-ring creep, rattling) is.
- Worked example 2, fastener/standoff holes (assumed clearance holes d0 = 3.4 mm for M3 and 4.5 mm for M4):

```
                     e_min (centre)   ligament from hole edge
EC3 e1 = 1.2 d0      4.1 / 5.4 mm     2.4 / 3.2 mm
e/D = 1.5            5.1 / 6.8 mm     3.4 / 4.5 mm
e/D = 2.0            6.8 / 9.0 mm     5.1 / 6.8 mm
```
  Bearing capacity of an M4 hole at typical F_bry: 4 x 3.175 x 386 = 4.9 kN, far above FTC screw shear loads. For clamped joints (screw + standoff), the material under the screw head/washer/standoff face must stay solid: ring outer radius >= contact-face radius (standoff or washer OD / 2) plus a small margin, and check under-head bearing pressure p = F_clamp / ((pi/4)(d_w^2 - d0^2)) <= F_bry.
- Load estimation for FTC (formulas, inputs to be supplied by the tool user): static weight per support = m g / n_supports (20 kg -> 196 N total); chain/belt pull = motor stall torque x gear ratio / sprocket pitch radius (stall is the worst case); multiply by a dynamic load factor DLF (Q6) and a safety factor SF (suggest 1.5 on yield for static, 2 for fatigue-sensitive features; researcher's suggestion).
- Why "analytic instead of fixed clearance" works: every term in the ring rule is closed form in (P_d, d, t, material, fit, load direction). The fixed-clearance approach is still needed as a floor because FTC loads are poorly known (impacts, abuse) and because analytic minima (< 1 mm) are unmanufacturable and fragile in handling.

### Gaps
- No bearing-manufacturer (SKF/NSK/Timken/Schaeffler) rule of thumb for minimum housing wall thickness or allowable bore ovality was found in accessible pages; SKF's interference-from-load formula was referenced but its exact form and units were not retrieved (JS-rendered page). The eta-based ring rule above is the researcher's derivation from Lamé theory.
- AISC Table J3.4 numeric minimum edge distances were not retrieved (secondary sources only).
- No closed-form ovalization (out-of-roundness) solution was found for a radially loaded bore in a finite ring connected by ribs; FEA is required to quantify ovalization in mm.
- Stress concentration for pin-loaded holes (Peterson lug charts, where Kt_n typically exceeds the open-hole value) not retrieved; Kt_pin = 3 is a placeholder.
- Bearing steel thermal expansion (~11-12e-6 /K) used above is an assumed typical value, not sourced in this session.

---

## Q6. Fatigue and impact for 6061-T6 robot plates

### Takeaway
6061-T6 has a fatigue strength of ~97 MPa (5 x 10^8 cycles, polished rotating-beam) and no true endurance limit; with notch factor Kf ~ 2-2.5 at pocket corners/holes and realistic de-rating, allowable local alternating stress for long life is a few tens of MPa, still several times the ~5-30 MPa nominal stresses in FTC plates. Impact is the more important amplifier: sudden load doubles stress (DLF = 2) and drops/collisions give DLF = 1 + sqrt(1 + 2h/delta_st), which can reach 5-15 for stiff structures, so compliance (wheels, bumpers) and avoiding sharp notches matter more than raw static margins.

### Cited Findings
- Fatigue limit 97 MPa (14 ksi) at 5 x 10^8 cycles (R.R. Moore); no well-defined knee in the S-N curve; real limits reduced by loading, gradient and surface finish factors — [Wikipedia: 6061 aluminium alloy](https://en.wikipedia.org/wiki/6061_aluminium_alloy)
- Neuber constant for aluminium alloys about 0.02 in (0.51 mm) in Kuhn-Hardrath's evaluation, and Peterson-form lecture notes list alpha = 0.51 mm for aluminium alloys; Neuber's form q = 1/(1 + sqrt(a/r)) and Peterson's form q = 1/(1 + a/r) use different, non-interchangeable constants — [SNU lecture notes, MSBS ch.10](https://ocw.snu.ac.kr/sites/default/files/NOTE/MSBS_ch10.pdf) (summarised from search results)
- A 1952 Caltech thesis on 75S-T6 and 17S-T6 found a Neuber constant of ~0.05 in gave reasonable agreement (about 2.5x the Kuhn-Hardrath value) and called for more data on other alloys — [Caltech thesis: Fatigue stress concentration studies on aluminum alloys](https://thesis.library.caltech.edu/1082/)
- Fatigue cracks almost always start at stress raisers — [Wikipedia: Stress concentration](https://en.wikipedia.org/wiki/Stress_concentration)
- Impact dynamic factor K_D = 1 + sqrt(1 + 2h/delta_S) (h = drop height, delta_S = static deflection under the same weight); sigma_D = K_D sigma_S; h = 0 (suddenly applied load) gives K_D = 2 — [Poznan University of Technology, SOMC lecture 04](https://pawel.jasion.pracownik.put.poznan.pl/wp-content/uploads/2025/05/SOMC_lecture_04.pdf); [Skill-Lync impact loading](https://resources.skill-lync.com/branches/mechanical-engineering/questions/strength-of-materials/impact-loading-analysis)
- K_D = 2 is the theoretical maximum for an ideal undamped spring under sudden load; real damped structures give less (forum discussion) — [Metabunk thread](https://www.metabunk.org/threads/how-did-nist-calculate-that-the-dynamic-amplification-factor-for-a-suddenly-applied-load-was-2-faq-18.15033/post-374137)

### Inferences
Equations:

```
Fatigue notch factor    Kf = 1 + q (Kt - 1)
Peterson                q  = 1 / (1 + alpha / r),  alpha ~ 0.51 mm (aluminium; source spread up to ~1.3 mm)
Example values (alpha = 0.51 mm):
  r (mm)    q       Kf (Kt = 2.5)   Kf (Kt = 3.0)
  0.40      0.44    1.66            1.88
  0.80      0.61    1.92            2.22
  1.59      0.76    2.14            2.51     (1/8 in cutter corner)
  3.18      0.86    2.29            2.72     (r = t)
Long-life check (fully reversed):  Kf * sigma_a <= S_f_derated / SF_f
  S_f_derated = 97 MPa x (surface, size, load-type, reliability factors) -> assume ~0.5-0.7 x 97 for machined plate (researcher's estimate)

Impact
  Sudden load:                        DLF = 2
  Drop from height h:                 DLF = 1 + sqrt(1 + 2 h / delta_st)
     h = 50 mm, delta_st = 0.5 mm  -> 15.2
     h = 50 mm, delta_st = 5 mm    ->  5.6   (compliant wheels/suspension)
  Collision at speed v (energy: 1/2 m v^2 = 1/2 k delta^2):  F_peak = v sqrt(m k)
     m = 18 kg, v = 1.5 m/s, k = 1e5 N/m -> 2.0 kN ;  k = 1e6 N/m -> 6.4 kN
```
- Note on notch sensitivity: q < 1 means small radii are partly "forgiven" in fatigue, which is why notch factors at 1.6 mm cutter radii are ~2.1-2.5 rather than the elastic Kt. The constant alpha is uncertain by ~2.5x between sources, so use Kf = Kt (q = 1) when in doubt; it is conservative.
- Cycle counts: FTC plates see perhaps 10^4-10^6 significant load cycles per season (drive reversals, vibration from drivetrains, repeated impacts) (researcher's estimate). For a rib at 9.4 MPa nominal (Q3) with Kf = 2.5: local amplitude ~24 MPa, below a derated ~50-65 MPa long-life value. Fatigue becomes relevant only where pockets leave a ligament < ~2 mm or Kt > ~4 at a highly stressed bearing/motor mount.
- Impact governs peak loads: use DLF ~ 2 for routine sudden loads (stall, direction reversal) and 3-5 for collisions/drops when compliance is unknown (researcher's suggestion). Through-pocketing makes plates more compliant (larger delta_st), which slightly lowers impact force but raises stress per unit force in ribs; the ring rules in Q5 should use P_d = P_static x DLF x SF.
- Ductility (>= 8 % elongation) means single impacts tend to cause local yielding/permanent hole ovalization rather than fracture; this is a functional failure for bearing bores (misalignment, bearing rattle) and argues for the stiffness/fit criterion (eta) rather than strength criteria around bores.

### Gaps
- No 6061-T6-specific notched fatigue data (Kf vs radius) or S-N curve for machined (not polished) 3.175 mm sheet was retrieved; Marin-type derating factors for aluminium were not sourced.
- The Kuhn-Hardrath (NACA, 1952) Neuber constant was relayed via a search summary; the primary NACA report was not fetched.
- No measured FTC impact accelerations or load spectra were found (outside this researcher's scope; may be covered elsewhere).

---

## Q7. Hole classification framework and load-dependent minimum material rings

### Takeaway
Each hole should carry a class plus parameters (diameter, load magnitude/direction/type, fit, contact-face diameter, user overrides); the tool computes a keep-out ring radius R_keep = d/2 + max(w_rule, w_strength(P), w_stiffness, w_contact, w_mfg) for every direction the load can act, and treats ring boundaries as free edges for Kt/ligament checks between neighbouring holes and pockets. Bearing bores and mechanism interfaces are governed by stiffness/fit and flatness, fasteners by edge-distance and under-head contact rules, clearance and existing lightening holes by Kt and rib-width rules only.

### Cited Findings
- Edge distance floors: MMPDS bearing allowables at e/D = 1.5 and 2.0 (forum) — [Eng-Tips](https://www.eng-tips.com/viewthread.cfm?qid=450377); EC3 e1 >= 1.2 d0, p1 >= 2.2 d0 — [Eurocode Applied](https://eurocodeapplied.com/design/en1993/bolt-design-properties); AISC allows smaller edge distance when bearing/tear-out equations are satisfied (forum quote) — [Eng-Tips](https://www.eng-tips.com/viewthread.cfm?qid=151072)
- Analytic failure-mode formulas for loaded holes (bearing, net tension, shear-out) — [MechaniCalc: Lug Analysis](https://mechanicalc.com/reference/lug-analysis)
- Light-alloy/thin-wall housings need tighter fits and sufficient strength; avoid uneven wall thickness that distorts rings — [SKF: Selecting fits](https://www.skf.com/us/products/rolling-bearings/principles-of-rolling-bearing-selection/bearing-selection-process/bearing-interfaces/selecting-fits)
- Finite-width and edge-hole Kt formulas — [AMES central hole](https://amesweb.info/stress-concentration-factor-calculator/central-circular-hole-in-plate.aspx); [AMES eccentric hole](https://amesweb.info/stress-concentration-factor-calculator/eccentric-circular-hole-in-plate.aspx)

### Inferences
Proposed classes and parameters (researcher's synthesis of Q1-Q6):

```
Class                      Key params                                   Governing criteria (ring = max of)
A. Loaded bearing bore     d_bore, bearing OD, flange OD, fit           eta >= 0.6 (b >= 1.8 a) when encircled;
   (shaft support)         (press/slip), radial P (+dir or "omni"),     flange-seat floor (b >= flange OD/2 + margin);
                           axial P, DLF                                 shear-out/net/bearing with P_d; e/D >= 1.5-2
                                                                        toward free edges in load direction
B. Fastener / standoff     d0 (screw size), contact face OD             contact-face floor (solid under head/standoff);
                           (washer/standoff/nut), shear P, clamp F      e/D >= 1.5 (2.0 if load-bearing);
                                                                        pitch >= 2.2-2.5 d0; bearing check
C. Mechanism interface     group of holes (motor face, servo, gear     keep-out = convex hull of group offset by the
   (pattern)               centre-distance pair), flatness/position     class-B ring; no pockets inside the hull
                           sensitivity                                  (centre distance and face flatness need stiffness)
D. Clearance hole          d (wire/tool access), no load                Kt x local nominal stress <= allowable/SF;
                                                                        ring >= w_mfg (rib-width rule only)
E. Existing lightening     outline                                     treat as an existing void; ribs between it and
   hole / pocket                                                        new pockets obey rib width/length/buckling rules
F. User-protected          user offset or polygon                       hard keep-out, never overridden
```

Algorithm sketch (per hole, per load direction set U):

```
P_d = P * DLF * SF
w_rule      = (c_e - 0.5) * d                      # c_e = 1.5 (min) or 2.0 (preferred), toward edges along u in U
w_shear     = P_d / (2 t F_su)                     # e - d/2
w_net_side  = Kt_pin * P_d / (2 t F_ty)            # perpendicular to u
w_stiff     = (bA(eta_target) - 1) * d/2           # class A only, bA = sqrt((C+1)/(C-1)), C = (1+nu)/eta - nu
w_contact   = max(0, D_contact/2 - d/2) + margin   # classes A (flange) and B (head/standoff)
w_mfg       = user minimum web (>= cutter diameter, suggest >= t)
w_ring(u)   = max(w_rule, w_shear, w_net_side, w_stiff, w_contact, w_mfg)
check       sigma_br = P_d/(d t) <= F_bry/SF  else flag "plate too thin here"
check       neighbouring rings: if ligament between two keep-outs < w_mfg -> merge into one solid island
check       fatigue: Kf * sigma_a <= S_f_derated/SF_f at pocket corners near class A/C features
```
- Default parameter values when the user gives no loads (researcher's suggestion for FTC, 6061-T6, t = 3.175 mm): class A: eta_target 0.6 -> ring width >= 0.4 d_bore and >= flange OD/2 - d/2 + 1 mm, plus e/D >= 2 toward free edges; class B: ring = max(contact radius - d0/2, 1.0 d0) and e/D >= 1.5; class C: hull + class-B ring; class D: ring = max(w_mfg, 0.5 d); rib width >= max(w_mfg, ~2 t) and unsupported rib length <= ~50 mm (Q3).
- When load direction is known (e.g. chain pull direction), the e/D and shear-out requirements apply only in that direction (a "teardrop" or offset keep-out), which recovers material on the unloaded side; when unknown, use a circle.
- Because analytic strength rings at FTC loads are sub-millimetre (Q5 example), the dominant terms will be w_rule, w_stiff, w_contact and w_mfg; exposing c_e, eta_target and w_mfg as user-tunable parameters, with the analytic strength terms as a safety net for heavily loaded holes (e.g. arm pivots, lift pulleys with multi-kN loads), gives load-dependence without making the tool fragile.

### Gaps
- No published FTC-specific or manufacturer rule for eta_target, ring width around flanged bearings, or default DLF/SF was found; values above are engineering judgement derived from the cited theory and should be validated by FEA or physical testing on representative plates.
- No authoritative source was found for merged keep-out treatment of hole patterns (class C); it is a proposed practice.
