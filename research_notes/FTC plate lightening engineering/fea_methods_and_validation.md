# FEA Methods and Verification/Validation for Thin Flat Aluminium Plates with Holes and Lightening Pockets (3.175 mm 6061-T6, up to 457 x 457 mm)

Context for the report writer: the plate span-to-thickness ratio is about 457 / 3.175 = 144 (a very thin plate). A typical rib of 8 mm width has width/thickness = 8 / 3.175 = 2.5, so an individual rib is not "thin" relative to its own width. Several conclusions below follow from those two ratios. Material constants (E, nu, yield) for 6061-T6 were not researched here. Other notes should cover them, and any numbers below that use E = 68.9 GPa and nu = 0.33 are illustrative only.

Research budget note: about 20 web searches and fetches. Where a claim could not be tied to a fetched or searched source, it is listed under Inferences (reasoning) or Gaps (unverified), never under Cited Findings.

---

## 1. Which formulation (2D plane stress, shell/plate, or 3D solid) and what element size for screening, optimisation-in-the-loop and final verification?

### Takeaway
Linear, fully-integrated low-order elements (CST triangles, plain 4-node quads, plain hex8, linear tets) lock badly in bending: they give 0.1-3.5% of the correct cantilever deflection with one element through the depth. Quadratic elements, incompatible-mode elements (CPS4I/C3D8I) and shells give about 0.9-1.0 of the correct value. For a flat, linear-elastic plate, use (a) plane-stress quadratic triangles for in-plane loads plus (b) a thin-plate/shell bending element for out-of-plane loads. Use a 3D solid (C3D20R/tet10/C3D8I, with care) only as a final check, mainly for torsion of narrow ribs, where plate theory is marginal at b/t of about 2.5.

### Cited Findings
- **Abaqus benchmark "Performance of continuum and shell elements for linear analysis of bending problems".** A cantilever under end shear load (E = 689.5 GPa, nu = 0; Euler-Bernoulli reference tip deflection 2.74 mm) is meshed 1/2/4/8 elements through the depth x 4/16 along the length. Normalised tip deflection for the 1 x 4 mesh (one element through the depth): C3D4 0.001, CPS3 0.012, CPS4 0.034, C3D8 0.035; C3D8I 0.985, CPS4I 0.985; C3D8R and CPS4R give a **singular** stiffness matrix; C3D8R with enhanced hourglass control 0.985; C3D10 0.985; CPS6 0.986; C3D20 0.987; C3D20R 1.001; CPS8R 1.001; S4 0.899; S4R (enhanced hourglass) 0.985. — [Abaqus Benchmarks 2017, linbending](https://abaqus-docs.mit.edu/2017/English/SIMACAEBMKRefMap/simabmk-c-linbending.htm)
- The same benchmark concludes the following. Linear isoparametric elements (CPS3, CPS4, C3D4, C3D8) are far too stiff in bending (shear locking). Second-order elements are accurate with one layer. Incompatible-mode elements perform well only for roughly rectangular shapes and degrade with parallelogram/trapezoidal distortion (tested at 0, 15, 30 and 45 degrees). With reduced-integration elements and one layer, the bending response "depends entirely on artificial hourglass stiffness", so at least four layers are needed for reliable results. For thin structures it recommends shell or beam elements. — [Abaqus Benchmarks 2017, linbending](https://abaqus-docs.mit.edu/2017/English/SIMACAEBMKRefMap/simabmk-c-linbending.htm)
- **Incompatible modes.** Abaqus says C3D8I-type elements add internal incompatible deformation modes. These remove the parasitic shear stresses that regular first-order elements show in bending, and they remove artificial stiffening due to Poisson's effect. In bending they can match quadratic elements at significantly lower cost, but they are sensitive to element distortion. — [Abaqus "Incompatible mode elements"](https://abaqus.uclouvain.be/English/SIMACAEGSARefMap/simagsa-c-ctmincompat.htm)
- Bathe and co-workers' inf-sup study of 8-node hexahedra reports that a 3D-MITC8 element performs better than the incompatible-modes element in plate bending problems. — [Inf-sup testing of 3D low-order elements (MIT, K.J. Bathe)](https://web.mit.edu/kjb/www/Principal_Publications/Inf_sup_testing_of_some_three_dimensional_low_order_finite_elements_for_the_analysis_of_solids.pdf)
- **CalculiX shells are expanded into one layer of solids.** S4 becomes C3D8I, S4R becomes C3D8R, S8 becomes C3D20 and S8R becomes C3D20R. With OUTPUT=2D the expanded-element fields are averaged back onto the shell nodes, and "averaging removes the bending stresses in beams and shells". Bending stresses are only visible with 3D output. — [CalculiX ccx 2.7 manual, node37 (MIT mirror)](https://web.mit.edu/calculix_v2.7/CalculiX/ccx_2.7/doc/ccx/node37.html)
- CalculiX forum users quote the documentation describing S4 to C3D8I as having controlled hourglassing "still questionable for one layers only". They report that linear shells (e.g. S3) behave poorly in bending and suggest quadratic S8R/S6. This is anecdotal forum material, not a benchmark. — [CalculiX Discourse thread](https://calculix.discourse.group/t/elasto-plastic-bending-elements-accuracy/700/12)
- **Stress-concentration accuracy by element order (NAFEMS LE1, plane stress).** Target sigma_yy at point D is 92.7 MPa. Abaqus results: CPS3 gives 51.04 MPa (-45%) on the coarse mesh and 71.26 MPa (-23%) on the fine mesh; CPS8 gives 84.54 MPa (-9%) coarse and 92.81 MPa (+0.12%) fine. — [Abaqus LE1](https://abaqus-docs.mit.edu/2017/English/SIMACAEBMKRefMap/simabmk-c-le1.htm). OptiStruct solid models: Hex8 coarse 63.15 MPa, Hex8 fine 79.8 MPa, Hex20 coarse 87.46 MPa, Hex20 fine 91.01 MPa. — [Altair OptiStruct OS-V:0010](https://help.altair.com/hwsolvers/os/topics/solvers/os/nafems_test_problem_le1_r.htm). COMSOL notes that the coarse mesh cannot capture the stress concentration unless high-order elements are used. — [COMSOL elliptic membrane model](https://doc.comsol.com/6.4/doc/com.comsol.help.models.sme.elliptic_membrane/elliptic_membrane.html)
- **Shell bending stress on coarse meshes (NAFEMS LE6 skew plate).** Abaqus S8R5 overestimates the target centre principal stress by +44.1% on the 2x2 mesh and +7.5% on the 4x4 mesh. OptiStruct Quad8 gives 0.8294 MPa (coarse) and 0.7869 MPa (fine) against a 0.802 MPa target. — [Abaqus LE6](https://docs.software.vt.edu/abaqusv2024/English/SIMACAEBMKRefMap/simabmk-c-le6.htm); [Altair OS-V:0050](https://help.altair.com/hwsolvers/os/topics/solvers/os/nafems_test_problem_le6_r.htm)
- **Thin-strip torsion stiffness depends on b/t.** The St Venant torsion constant of a rectangle is J = K * b_max * t^3, with K = (1/3)[1 - 0.63 (t/b_max)(1 - t^4/(12 b_max^4))]. This reduces to K = (1/3)(1 - 0.63 t/b_max) when b_max > 2t. — [Oasys GSA theory: rectangular sections](https://docs.oasys-software.com/structural/gsa/references-theory/rectangular-sections/). The coefficient tends to 0.333 as the aspect ratio tends to infinity. — [Wikipedia: Torsion constant](https://en.wikipedia.org/wiki/Torsion_constant)

### Inferences
- **The span/thickness ratio of about 144 puts the plate firmly in the thin (Kirchhoff) regime for global behaviour.** Transverse-shear deformation is negligible at plate scale. Mindlin/MITC elements are still the safer *element* choice, because they are locking-free by construction and handle the local regions near holes and narrow ribs. A pure Mindlin element without MITC/selective integration would lock badly at L/t = 144.
- **Membrane and bending decouple for this plate.** For a flat, homogeneous, mid-plane-symmetric plate in *linear* analysis, membrane (in-plane) and bending responses are uncoupled. The screening and optimisation solver can therefore run (a) a 2-DOF/node plane-stress problem for in-plane load cases and (b) a 3-DOF/node plate-bending problem (w, theta_x, theta_y) for out-of-plane bending and torsion, then superpose. That is much cheaper than a 6-DOF shell or a 3D solid. This is standard plate theory (Cook/Malkus/Plesha; Zienkiewicz), not fetched this session.
- **Do not use linear triangles (CST) for ribs.** Ribs in a pocketed plate act as frame members carrying in-plane bending. CPS3 recovers 1.2% of the correct cantilever stiffness with one element through the depth and is -23% on the LE1 fine-mesh peak stress. Use quadratic triangles (tri6/CPS6, about 0.986) or incompatible-mode quads (CPS4I, about 0.985).
- **When is a single layer of hex8 through the 3.175 mm thickness acceptable?**
  - Plain fully-integrated hex8 (C3D8): never for bending; it is misleading (3.5% of correct deflection).
  - Reduced-integration hex8 (C3D8R) single layer: misleading. Bending stiffness then comes from the hourglass control, not from physics; Abaqus asks for at least 4 layers.
  - Incompatible-mode hex8 (C3D8I) single layer: acceptable for stiffness when the bricks are close to rectangular, e.g. a 2D quad mesh swept straight through the thickness, with modest in-plane distortion. It degrades with distortion. Paved quad meshes around holes and pocket fillets will contain distorted elements, so this needs a convergence check.
  - Quadratic bricks (C3D20/C3D20R) single layer: good (0.987-1.001).
  - Consequence for CalculiX: S8R (expanded to C3D20R) is the preferred shell. S4 (expanded to C3D8I) behaves like a single layer of incompatible-mode bricks.
- **Tet10 for a 3.175 mm plate.** C3D10 is accurate with one structured layer. Free tet meshers, however, need an in-plane size comparable to the thickness to keep element aspect ratios reasonable. That drives DOF counts to hundreds of thousands or millions for a 457 mm plate. Illustrative estimate: about 0.1 m^2 of remaining material at h of about 1.6 mm gives roughly 40k surface nodes per face and, with mid-side nodes and two or more layers, around 1M DOF. 3D solids are therefore a final-verification tool, not an in-the-loop one.
- **Plate theory overestimates the torsional stiffness of narrow ribs.** For an 8 mm x 3.175 mm rib, the strip torsion constant is about 0.75 x (b t^3 / 3), since 1 - 0.63/2.52 = 0.75. Kirchhoff plate theory gives exactly b t^3 / 3 for a strip in twist: integrating the twisting moment M_xy = D(1 - nu) w_xy plus the Kirchhoff edge forces gives T = G b t^3 theta'/3. So Kirchhoff/DKT shells **overpredict the St Venant torsional stiffness of individual 8 mm ribs by about 1/0.75, i.e. about 33%**. Mindlin/MITC shells capture part of the edge boundary layer, and 3D solids capture it fully. For load cases dominated by plate torsion, verify the final design with a 3D solid model or a Mindlin shell. Treat any Kirchhoff-only torsional stiffness as optimistic when ribs have b/t below about 5. (This derivation is reasoning; it has not been confirmed in a fetched source.)
- **Suggested tiers** (synthesis, not from a single source):
  1. *Screening* (milliseconds to seconds): decoupled plane-stress tri6 or CPS4I-like quads, plus a DKT/Morley/MITC plate, on a coarse body-fitted mesh (h of about 4 mm, at least 2 quadratic elements across the narrowest rib), or on a fixed grid (Section 2). Report compliance and displacement metrics only.
  2. *Optimisation in the loop*: fixed grid with ersatz material, or a reused body-fitted topology, driven by stiffness/compliance and bore-displacement metrics. Use stress only as an interior-sampled or percentile measure (Sections 2 and 3).
  3. *Final verification*: a Gmsh body-fitted mesh of the actual vector geometry (with fillets). Use quadratic elements (tri6 plane stress plus MITC plate, or CalculiX S8R, or C3D20R/tet10 with at least 2 layers for torsion checks), local refinement at bores and narrow webs, and a three-mesh GCI on each reported KPI (Section 4).
- **Element-size heuristic for an 8 mm rib (unsourced; confirm by a convergence study).** For stiffness: at least 2 quadratic or at least 4 linear-incompatible elements across the rib (h of about 2-4 mm). For rib stresses: at least 3-4 quadratic elements across (h of about 2-2.7 mm). Around bores: element size of about R/4 to R/6 on the edge, or 24-36 elements around the circumference, graded out with a Gmsh Distance+Threshold field. The LE1 data confirm that quadratic elements on a refined mesh reach the analytical concentration within about 0.1%.

### Gaps
- No primary DKT reference (Batoz, Bathe & Ho 1980) or MITC4 benchmark tables were fetched. Their accuracy statements rely on general knowledge and on the Bathe inf-sup paper above.
- No published rule of thumb was found for "elements across a rib". The heuristic above is unsourced.
- The Kirchhoff-overprediction-of-rib-torsion argument is derived, not quoted. It should be checked with a quick 3D vs shell comparison on an 8 mm x 3.175 mm strip.
- No NASA FEA modelling guideline document (e.g. a NASA-STD or handbook on FEA practice) was located in this session.

---

## 2. Voxel/raster (fixed-grid, ersatz-material) FEA vs body-fitted meshes: stiffness vs stress accuracy

### Takeaway
Fixed-grid FEA gives usable *stiffness* (compliance, displacements). Boundary *stresses* are unreliable, because errors concentrate in boundary and bi-material elements, and a staircase boundary is a chain of artificial re-entrant corners. The literature's fixes are: sample or extrapolate stresses from the interior (Interior Value Extrapolation), correct boundary-element stiffness, or represent the boundary explicitly (B-splines or level sets). For a final verdict, re-mesh the real geometry body-fitted.

### Cited Findings
- Dunning, Kim and Mullineux analyse the fixed-grid stiffness approximation analytically. Maximum errors occur on the boundary, due to homogenisation of bi-material (partially filled) elements. This matters because boundary sensitivities drive boundary-based optimisation. — [Error analysis of fixed grid formulation (Univ. of Bath)](https://researchportal.bath.ac.uk/en/publications/error-analysis-of-fixed-grid-formulation-for-boundary-based-struc/)
- A 2014 Structural and Multidisciplinary Optimization paper proposes Interior Value Extrapolation (IVE) for stresses in the jagged structures produced by fixed-mesh topology optimisation. It starts from the observation that FE stresses are more accurate in the interior than at the boundary, and combines IVE with a nonlinear density filter to improve stress accuracy. — [Springer, s00158-014-1171-2](https://link.springer.com/article/10.1007/s00158-014-1171-2)
- Kim, Querin, Steven and Xie report that a fixed-grid mesh in evolutionary structural optimisation eliminates jagged edges and checkerboards and improves solution time, for both stress-based and stiffness optimisation. — [Univ. of Bath research portal](https://researchportal.bath.ac.uk/en/publications/improving-efficiency-of-evolutionary-structural-optimization-by-i/)
- Heshmati, Daneshmand and Amini use a modified fixed-grid FEM with a new stiffness computation for boundary-intersecting elements, applied to boundary stress minimisation. They report good agreement with analytical and FE solutions. — [Scientia Iranica 2014](https://scientiairanica.sharif.edu/article_3477_140fe1a51edf2b55873c74336b63bcef.pdf)
- Edwards, Kim and Budd represent the boundary with B-spline curves in a fixed-grid setting, giving smooth boundaries with fewer design variables. — [Edwards/Kim/Budd draft (Bath)](https://people.bath.ac.uk/mascjb/draft6.pdf)

### Inferences
- **Why stiffness survives and stress does not.** Compliance and displacement are integral (energy) quantities, so local boundary errors average out and converge reasonably as the grid is refined. Stress is a derivative quantity, evaluated pointwise, and is largest exactly at the boundary, where the fixed grid is least accurate. On a binary (0/1) raster, every stair step is a 90-degree re-entrant corner (270-degree interior angle). Each step is therefore a local singularity (Section 3): the peak stress at jagged edges grows as the grid is refined instead of converging.
- **Recommended practice for the tool.**
  - Use the raster or ersatz-material FE only for compliance, mass and bore-displacement objectives, and for relative ranking of designs.
  - If a stress constraint is needed in the loop, evaluate stress at element centroids at least one or two cells inside the boundary (an IVE-like approach), or use an aggregated (p-norm/percentile) measure. Never use the raw max on the boundary.
  - For the verification step, build vector geometry (offset/smoothed pocket outlines with real fillet radii), mesh it body-fitted in Gmsh, and recompute stress there.
- **Grid alignment.** A 457 mm plate on a 1 mm grid is about 209k cells. On a 2-3 mm grid it is about 23k-52k cells, so 2 DOF/node plane stress lands in the 50k-100k DOF range. The rib width of 8 mm is then only 3-8 cells, which is marginal for bilinear-quad bending of ribs (Section 1: bilinear quads lock unless they use incompatible modes). Use Q4 with incompatible modes / enhanced assumed strain, or Q8/Q9, on the grid as well.

### Gaps
- The Andreassen et al. (2011) "88-line" topology-optimisation code and Sigmund/Bendsoe texts were not fetched. Typical ersatz Emin/E ratios (e.g. 1e-9) and penalisation details are therefore not cited here.
- No quantitative study was found comparing raster vs body-fitted stress errors specifically for thin plates with circular holes, so error magnitudes are not quantified.

---

## 3. Stress singularities (re-entrant corners, point loads/supports) and meaningful stress post-processing

### Takeaway
At a sharp re-entrant corner, a point load or a point support, the linear-elastic stress is theoretically infinite. The FE peak keeps climbing with refinement, so raw max von Mises is meaningless there. A genuine concentration (a hole edge or a filleted corner) converges to a finite value. Model real fillets, spread loads and supports over realistic areas, and judge designs with converged quantities: hole-edge stresses, stresses at a distance, or robust percentiles that exclude load/support zones.

### Cited Findings
- A singularity is diagnosed when the stress at a hot spot keeps increasing with mesh refinement. A true concentration such as a hole edge converges to a finite value. — [SOLIDWORKS "Assessing stress hot spots"](https://help.solidworks.com/2017/english/solidworks/cworks/r_assessing_stress_hot_spots.htm); [Javelin: mesh refinement for stress singularities](https://www.javelin-tech.com/blog/?p=31417); [AskDrQ: singularities](https://www.askdrq.com/en/academy/results/singularities)
- Typical causes are point loads, point supports and sharp re-entrant corners, e.g. 90-degree notches without a fillet. — [AskDrQ: singularities](https://www.askdrq.com/en/academy/results/singularities)
- Dlubal's test: if the stress result rises while the area over which it acts shrinks, the location is very likely a singularity. Real materials yield or crack, so singularities are not physical, but the FE answer is mathematically correct for the idealised model. — [Dlubal knowledge base 001503](https://www.dlubal.com/en/support-and-learning/support/knowledge-base/001503)
- PADT defines a geometric singularity as the cause of any mesh-refinement convergence plot whose quantity of interest fails to converge, and lists point nodal forces as one cause. Mitigations: add fillets, spread loads over areas, evaluate away from the singularity, or use submodelling. — [PADT: Geometric singularities in FE problems](https://www.padtinc.com/wp-content/uploads/2024/01/PADT-Geometric_Singularities_in_Finite_Element_Problems_2023_01_09.pdf)
- Post-processing pitfall in CalculiX: averaging the expanded shell fields back to 2D nodes removes the bending stresses, so read shell bending stresses from the 3D-expanded output. — [CalculiX manual node37](https://web.mit.edu/calculix_v2.7/CalculiX/ccx_2.7/doc/ccx/node37.html)

### Inferences
- **Sources of singularity in this application.**
  1. Pocket corners that are not filleted (and every raster stair step).
  2. Bolt and bearing loads applied as nodal point forces.
  3. Single-node or single-edge-node constraints.
  Fixes: always model the actual end-mill fillet radius in verification geometry. Apply bore loads as distributed bearing pressure (e.g. cosine distribution over 180 degrees) or through a distributing coupling (RBE3-type), not a rigid spider. Constrain over bolt-head/washer footprints, not single nodes.
- **Robust stress metrics to report.**
  - Peak von Mises at *filleted* features after convergence (GCI, Section 4).
  - The 99th or 99.5th area-weighted percentile of element von Mises, excluding a radius of about 1-2 t around load and support application points.
  - Stress "at a distance" or averaged over a small control area or volume, e.g. over a 1 mm radius.
  - Through-thickness linearisation for 3D solids: split into membrane and bending components along a line through the 3.175 mm thickness. For shells this split is native (membrane resultant N and bending moment M).
  These are design-comparison metrics. Use them consistently across candidate designs rather than as absolute allowables.
- **Use the convergence study as the arbiter.** A KPI whose GCI does not show monotone convergence with an observed order p > 0 is likely contaminated by a singularity (Section 4).

### Gaps
- The Williams (1952) corner-singularity exponent was not fetched. The stress at a 90-degree re-entrant corner scales as r^(lambda - 1), with the commonly quoted mode-I lambda of about 0.544, so stress ~ r^-0.46; this value is unverified here.
- No authoritative source was found that recommends a specific percentile for automated design screening. The 99-99.5% figure is a heuristic.
- The hot-spot structural-stress method (IIW/DNV, extrapolation from reference points at 0.4t/1.0t) and ASME BPVC Section VIII Div 2 stress linearisation were not fetched. Their applicability to machined (non-welded) plates is an inference.
- The theory of critical distances (Taylor) was not researched.

---

## 4. Mesh-convergence and V&V practice (Richardson extrapolation, GCI, local refinement; ASME V&V 10, NASA, NAFEMS)

### Takeaway
Use at least three systematically refined meshes (constant ratio r >= 1.1, ideally about 1.3-2). Compute the observed order p, the Richardson-extrapolated value and the GCI with Fs = 1.25 (Fs = 3.0 if only two meshes). Check the asymptotic range (GCI_23 / (r^p GCI_12) close to 1). Apply this per KPI: tip/bore displacement, compliance, fillet stress. ASME V&V 10 provides the terminology and framework: verification means solving the equations right, and validation means solving the right equations.

### Cited Findings
- The NASA NPARC procedure runs the simulation on two or more successively finer grids and applies Richardson extrapolation following Roache. It recommends a refinement ratio r >= 1.1 to separate discretisation error from iteration and round-off error. It notes that the observed order is usually lower than the theoretical order, because boundary conditions, models and grids degrade it. — [NASA NPARC V&V tutorial: spatial convergence](https://www.grc.nasa.gov/www/wind/valid/tutorial/spatconv.html)
- **NPARC worked formulas** (general forms consistent with these instances):
  - Observed order: p = ln[(f3 - f2)/(f2 - f1)] / ln r. Example: p = ln[(0.96178 - 0.96854)/(0.96854 - 0.97050)] / ln 2 = 1.786.
  - Richardson extrapolation: f_h=0 = f1 + (f1 - f2)/(r^p - 1). Example: 0.97130.
  - Fine-grid GCI: GCI_12 = Fs |(f2 - f1)/f1| / (r^p - 1).
  - Recommended Fs = 3.0 for two-grid comparisons and Fs = 1.25 for three or more grids.
  - Asymptotic check: GCI_23 = r^p GCI_12, giving a ratio of about 1 (example 1.002; the tool output on the same page shows 0.998).
  - Reporting format: result 0.97130 "with an error band of 0.103%".
  - The GCI is recommended whether or not the Richardson value is used.
  — [NASA NPARC V&V tutorial](https://www.grc.nasa.gov/www/wind/valid/tutorial/spatconv.html)
- Roache (1994, J. Fluids Eng.) introduced the GCI for uniform reporting of grid refinement studies. It is based on generalised Richardson extrapolation and relates any refinement to a grid doubling with a second-order method. — [Roache 1994 (abstract)](https://scholarhub.vn/publication/Perspective-A-Method-for-Uniform-Reporting-of-Grid-Refinement-Studies/247af627-5c87-4eb6-a231-d7018475d527). Checking the asymptotic range requires two GCIs from three grids. — [arXiv 1705.09062](https://arxiv.org/pdf/1705.09062). The procedure was standardised by Celik et al. (2008, ASME); a minimum of three systematically refined grids is commonly required. — [Volupe GCI calculator note](https://volupe.com/?p=28452)
- ASME V&V 10-2006 (PTC 60 committee) is a guide that gives the solid-mechanics community common terminology and general guidance, not a step-by-step procedure. — [ANSI webstore: ASME V&V 10-2006](https://webstore.ansi.org/standards/asme/ansiasme102006). A vendor listing names V&V 10-2019 as the current revision ("Standard for Verification and Validation in Computational Solid Mechanics"). It frames verification as checking that the mathematical model is solved correctly and validation as checking that the correct model is being solved (revision status not confirmed on asme.org). — [Nimonik listing](https://standards.nimonik.com/products/asme/v-v%2010/). V&V 10.1-2012 gives a worked example. — [ANSI webstore: V&V 10.1-2012](https://webstore.ansi.org/standards/asme/asmevv102012). A free overview by L.E. Schwer (PTC 60 chair) exists. — [Schwer overview (DYNAmore)](https://www.dynamore.de/de/download/papers/forum06/keynote/an-overview-of-the-asme-guide-for-verification-and/view)

### Inferences
- **Practical recipe for the tool (verification tier).**
  1. Define global size h0 and local sizes at bores and webs as h0 x factor, all scaled together (e.g. r = 1.5: h0 = 3, 2, 1.33 mm), so the refinement is systematic. Gmsh MeshSizeFactor or a scaled Threshold field does this.
  2. Run three meshes. For each KPI (compliance, bore relative displacement/tilt, peak *filleted* von Mises, 99th-percentile stress), compute p, f_extrap and GCI_12 (Fs = 1.25).
  3. Accept if GCI_12 is below a tolerance (e.g. 2-5% for displacements, 5-10% for fillet stresses; these thresholds are a judgement, not from a standard) and the asymptotic ratio is about 1.
  4. If p is negative or the KPI rises without bound, flag a singularity (Section 3).
- **Expected orders.** Displacement converges faster than stress, and quadratic elements faster than linear. For smooth problems the textbook a priori rates are O(h^2) displacement and O(h) stress for linear elements, and O(h^3)/O(h^2) for quadratic. Observed orders will be lower near re-entrant features. (Textbook statement, not fetched this session.)
- **Unstructured meshes.** Strict geometric similarity is impossible with unstructured meshes. Use the representative size h = (A / N_elements)^(1/2) to compute an effective r between meshes (Celik et al. approach, recalled rather than fetched).
- **Regression testing in CI.** Run the Section 5 benchmarks at a fixed mesh and assert against stored values, which guards against code changes. Separately assert that the same benchmark's GCI-extrapolated value lies within tolerance of the analytical value, which verifies the solver.

### Gaps
- The Celik et al. (2008) paper itself was not fetched, so its exact representative-size and oscillatory-convergence rules are recalled, not cited.
- No NAFEMS "How to" convergence guidance document or NASA solid-mechanics FEA guideline was fetched.
- No published acceptance thresholds (GCI %) specific to structural FEA were found.

---

## 5. Benchmark problems with published reference answers (for regression tests)

### Takeaway
Useful benchmarks with traceable answers:
- NAFEMS LE1 (plane-stress elliptic membrane, 92.7 MPa)
- NAFEMS LE6 (skew plate under pressure, 0.802 MPa; note the documented load-magnitude error in some Abaqus versions)
- Timoshenko square-plate deflections (0.00406 and 0.00126 q a^4/D)
- Finite-width plate-with-hole Kt (Peterson-type polynomial, tending to Kirsch Kt = 3)
- Cantilever tip deflection (PL^3/3EI)
- Thin-strip torsion (J = b t^3/3 (1 - 0.63 t/b))

### Cited Findings
- **NAFEMS LE1, elliptic membrane (plane stress).**
  - Load: 10 MPa outward normal on the outer elliptic boundary.
  - Material: E = 210 GPa, nu = 0.3; thickness does not influence the answer.
  - Target: tangential stress sigma_yy at point D (x = 2, y = 0) = **92.7 MPa** (analytical).
  - Source document: NAFEMS TNSB Rev. 3 (1990), "The Standard NAFEMS Benchmarks".
  - Element results are listed in Section 1.
  — [COMSOL LE1 model](https://doc.comsol.com/6.4/doc/com.comsol.help.models.sme.elliptic_membrane/elliptic_membrane.html); [Abaqus LE1](https://abaqus-docs.mit.edu/2017/English/SIMACAEBMKRefMap/simabmk-c-le1.htm); [Altair OS-V:0010](https://help.altair.com/hwsolvers/os/topics/solvers/os/nafems_test_problem_le1_r.htm)
- **NAFEMS LE6, skew plate under normal pressure (plate bending).**
  - Supports: simply supported on all four edges.
  - Material: E = 210 GPa, nu = 0.3; thickness 0.01 m (SOLIDWORKS example).
  - Meshes: coarse 2x2 and fine 4x4.
  - Target: **maximum principal stress 0.802 MPa on the lower surface at the centre, point E**.
  - **Load-magnitude caveat:** the Abaqus benchmark page lists -7.0 kPa pressure, while OptiStruct and SOLIDWORKS use 0.7 kPa. A PrePoMax forum user traced a 10x discrepancy to this and reported that Dassault corrected the Abaqus 2025 documentation. The 0.802 MPa target is consistent with 0.7 kPa.
  - Sources: NAFEMS TNSB Rev. 3 (1990); SOLIDWORKS cites NAFEMS P07 (1987) with the same target.
  — [Abaqus LE6](https://docs.software.vt.edu/abaqusv2024/English/SIMACAEBMKRefMap/simabmk-c-le6.htm); [Altair OS-V:0050](https://help.altair.com/hwsolvers/os/topics/solvers/os/nafems_test_problem_le6_r.htm); [SOLIDWORKS skew plate](https://help.solidworks.com/2025/English/simconntutorial/r_skew_plate_normal_pressure.htm); [PrePoMax forum LE6](https://prepomax.discourse.group/t/le6-skew-plate-under-normal-pressure/2304)
- **Square plate under uniform pressure q (Timoshenko & Woinowsky-Krieger, Theory of Plates and Shells),** with D = E h^3 / (12(1 - nu^2)):
  - Simply supported, centre deflection w_max = **0.00406 q a^4 / D**. — [SOLIDWORKS: simply supported plate](https://help.solidworks.com/2025/English/simconntutorial/Simply_Supported_Rectangular_Plate_Static.htm)
  - Clamped, centre deflection = **0.00126 q a^4 / D**. — [SOLIDWORKS: clamped square plate](https://help.solidworks.com/2025/English/simconntutorial/Clamped_Square_Plate_Under_Uniform_Loading.htm)
  - Both are secondary sources citing the book; the original table page was not seen.
- **Plate with central circular hole in tension, finite width.** A Peterson-style curve fit with nominal stress on the net section, valid for 0 <= d/W <= 1, is Kt = 3.000 - 3.140(d/W) + 3.667(d/W)^2 - 1.527(d/W)^3. The calculator does not state its attribution. — [AMES stress concentration calculator](https://amesweb.info/stress-concentration-factor-calculator/central-circular-hole-in-plate.aspx)
- A study comparing FE results against the Heywood and Howland formulations found them most valid for a plate length-to-width ratio of 2 (search snippet; paper not fetched). — [UPB Scientific Bulletin](https://www.scientificbulletin.upb.ro/static/pdfs/rezeef_601718.pdf)
- **Cantilever tip deflection.** The Abaqus bending benchmark uses the Euler-Bernoulli reference (2.74 mm for its data) and includes skewed-element variants (0-45 degrees), which make a good distortion-sensitivity regression test. — [Abaqus linbending](https://abaqus-docs.mit.edu/2017/English/SIMACAEBMKRefMap/simabmk-c-linbending.htm). scikit-fem Example 34 (Euler-Bernoulli beam, cubic Hermite) states an exact deflection of 1/8 at x = 1. — [scikit-fem list of examples](https://scikit-fem.readthedocs.io/en/latest/listofexamples.html)
- **Torsion of a thin strip.** J = (b t^3 / 3)(1 - 0.63 t/b) for b > 2t, with the exact coefficient tending to 1/3 as b/t tends to infinity; twist rate = T/(G J). — [Oasys GSA rectangular sections](https://docs.oasys-software.com/structural/gsa/references-theory/rectangular-sections/); [Wikipedia: Torsion constant](https://en.wikipedia.org/wiki/Torsion_constant)

### Inferences
- **Proposed regression suite for the tool.**
  1. **LE1** with plane-stress tri6: assert sigma_yy(D) within 1-2% of 92.7 MPa on the fine mesh.
  2. **Plate-with-hole strip**, d/W = 0.25 and 0.5, with length/width at least 2-4 so the far field is uniform: compare peak hoop stress / net-section stress with the polynomial Kt. The fit gives about 2.42 at d/W = 0.25 and about 2.16 at d/W = 0.5; these are computed from the fit and should be re-checked against Peterson's chart. Also check d/W tending to 0 gives Kt tending to 3 (Kirsch).
  3. **Timoshenko square plate**, simply supported and clamped, 457 x 457 x 3.175 mm: assert w_centre / (q a^4/D) = 0.00406 and 0.00126. With E = 68.9 GPa and nu = 0.33 (illustrative), D is about 206 N.m, so q = 1 kPa gives w_SS of about 0.86 mm. The FE is linear, so load magnitude does not matter for the ratio.
  4. **LE6** for shell/plate elements, using **0.7 kPa**.
  5. **Cantilever plate strip** (e.g. 300 x 50 x 3.175 mm) for in-plane bending (plane stress; tests rib-like locking) and out-of-plane bending (plate): assert PL^3/(3EI) using the appropriate I (t b^3/12 vs b t^3/12). Out-of-plane plate-strip stiffness is between beam and plate (anticlastic, factor up to 1/(1 - nu^2)), so use a narrow strip or accept a tolerance band.
  6. **Strip torsion** (e.g. 300 x 25 x 3.175 mm, b/t of about 7.9): compare twist with T L/(G J). Run at b/t of about 2.5 (8 mm rib) as well, to expose the Kirchhoff-vs-3D difference discussed in Section 1.
  7. **Distortion test**: the same cantilever with parallelogram/trapezoid elements (Abaqus linbending style), to catch elements that are sensitive to distortion.
- Store benchmark meshes and expected values in the repo and run them on every solver change.

### Gaps
- LE6 skew-plate geometry (side length, skew angle) and LE1 dimensions were not captured in the fetched summaries; take them from TNSB or the Abaqus pages before implementing.
- Other NAFEMS LE problems (e.g. LE5 Z-section cantilever torsion, LE2/LE3 shell problems) were not fetched, so their targets are not given.
- The original Peterson/Pilkey chart, Howland (1929-30, Phil. Trans. Roy. Soc. A229) and Heywood (Designing by Photoelasticity, 1952) were not consulted directly. The polynomial's attribution to Peterson is unconfirmed, although its d/W tending to 0 limit of 3 matches Kirsch.
- The Kirsch closed-form hoop stress (sigma_theta = sigma(1 - 2 cos 2 theta) at the hole edge) was not fetched.
- No Timoshenko moment/stress coefficients (dependent on nu) were captured; only the deflection coefficients are cited.

---

## 6. Bearing-bore metrics: relative bearing displacement and misalignment between two bores from FE results

### Takeaway
No published standard metric was found for this. A sound approach is a least-squares rigid-body fit of each bore's edge-node displacements, giving centre translation (u, v, w) and tilt (theta_x, theta_y) per bore. Then report the change in centre-to-centre distance, relative in-plane offset, and relative tilt between paired bores. Load the bores through distributing (RBE3-type) couplings or bearing pressure, not rigid spiders, so the measurement does not stiffen the bore.

### Cited Findings
- The only directly relevant fetched evidence concerns post-processing. Shell bending fields must be read from expanded/3D output in CalculiX, because 2D averaging removes bending stresses. Bore tilt derived from mid-surface rotations is fine, but surface stresses near bores need the 3D output. — [CalculiX manual node37](https://web.mit.edu/calculix_v2.7/CalculiX/ccx_2.7/doc/ccx/node37.html)
- No source specific to bearing-bore misalignment metrics in FE was found in this session.

### Inferences
- **Per-bore rigid-body fit.** For bore k with edge nodes i at positions x_i and displacements u_i:
  - Centre in-plane translation: c_k = mean(u_i, v_i) for uniformly spaced nodes; otherwise use an arc-length-weighted mean.
  - In-plane rotation: gamma_k = mean of the tangential displacement / R.
  - Out-of-plane: fit w_i = a + b x_i + c y_i by least squares. Then a is the bore centre deflection, and theta_y = b and theta_x = -c are the bore-axis tilts (small angles). For plate/shell models, the average nodal rotations theta_x, theta_y around the bore can also be used directly, as a cross-check.
  - For 3D solid models: fit both faces separately and take the mean. The face difference indicates bore ovalisation and twist through the thickness.
- **Pairwise metrics** for two bores on the same shaft or chain, A and B, with unit vector e_AB between their undeformed centres:
  - Centre-distance change: delta_L = (c_B - c_A) . e_AB. This is critical for chain/belt tension and gear mesh.
  - Lateral offset: (c_B - c_A) . e_perp.
  - Relative out-of-plane offset: w_B - w_A.
  - Relative tilt: |theta_B - theta_A|, in mrad or arcmin.
  - For a shaft supported in two parallel plates (typical FTC gearbox/drivetrain), use the misalignment between the bore in plate 1 and the bore in plate 2. This needs a two-plate model or an assumed rigid spacer.
- **Ovalisation:** fit u_r(theta) = a0 + a1 cos(theta) + b1 sin(theta) + a2 cos(2 theta) + b2 sin(2 theta). The first harmonic is rigid translation and a2/b2 is ovalisation. This keeps bearing fit/clearance effects separate from rigid misalignment.
- **Loading and measurement coupling.** Apply bearing loads as a cosine-distributed radial pressure over the loaded half of the bore, or through an RBE3/distributing coupling to a reference node at the bore centre. A rigid RBE2/kinematic coupling artificially stiffens the bore and suppresses ovalisation and local tilt. Measure kinematics on the bore edge nodes, not on the coupling's reference node.
- **Robustness.** These metrics are integral (averaged over many nodes), so they converge like displacements, unlike peak stresses. Include them in the GCI study (Section 4) as primary KPIs.

### Gaps
- No published allowable for FTC-type bearing misalignment was found. Typical deep-groove ball bearing misalignment tolerances (often a few arc-minutes) are from general knowledge and were not verified here.
- Specific RBE2/RBE3 equivalents in CalculiX (*DISTRIBUTING COUPLING vs *KINEMATIC/rigid body) were not looked up in the manual during this session.

---

## 7. Open-source meshers and solvers usable from Python (licences, maintenance, Windows, capabilities)

### Takeaway
- **Gmsh** (GPL with a linking exception; v4.15.2, March 2026; `pip install gmsh` on Windows/Linux/macOS) is the clear mesher choice. It offers OpenCASCADE booleans and Distance/Threshold size fields.
- For a self-contained Python solver, **scikit-fem** (pure Python, many element types including Morley/Argyris plate elements and Kirchhoff plate examples) works natively on Windows.
- **CalculiX** (GPL, Windows builds bundled with PrePoMax) is a robust external verification solver driven by `.inp` files.
- **DOLFINx** is powerful but awkward on Windows: the Windows conda build is beta and lacks PETSc, so WSL2 is recommended. It also has no official shell/plate demos.

### Cited Findings
- **Gmsh**
  - Licence: GNU GPL "version 2 or later, with an exception to allow for easier linking with external libraries"; closed-source integration requires a commercial licence.
  - Latest version 4.15.2, released 24 March 2026.
  - Install the Python API and SDK with `pip install --upgrade gmsh`.
  - Platforms: Windows 10+, Linux (glibc 2.28+) and macOS, on x86 and ARM.
  - Uses OpenCASCADE for constructive geometry.
  — [gmsh.info](https://gmsh.info/)
- Gmsh tutorial t10 shows mesh-size control with a "Distance" field from points/curves feeding a "Threshold" field. Field option names changed across versions (older NodesList/EdgesList vs PointsList/CurvesList with NumPointsPerCurve). — [Gmsh t10 tutorial (4.8.4)](https://gitlab.onelab.info/gmsh/gmsh/-/raw/gmsh_4_8_4/tutorial/c++/t10.cpp). A user feature request noted that size fields could not be evaluated from Python (gmsh.field eval) at the time; current status unverified. — [Gmsh issue 1375](https://gitlab.onelab.info/gmsh/gmsh/-/issues/1375). An early-version OCC point-size precedence issue was reported fixed by Gmsh 4.4. — [Gmsh mailing list 2019](https://onelab.info/pipermail/gmsh/2019/013047.html)
- **CalculiX**
  - Runs on *nix and Windows and is distributed under the GNU GPL. — [Wikipedia: CalculiX](https://en.wikipedia.org/wiki/Calculix); official downloads for ccx (solver) and cgx (GUI). — [dhondt.de](https://dhondt.de/)
  - A native Windows 64-bit build exists (GPL-2.0). — [Gitee CalculiX Windows build](https://gitee.com/nust_xdy/CalculiX)
  - PrePoMax bundles a Windows solver (ccx_static.exe) that can be run from the command line on exported `.inp` files. — [PrePoMax forum: using standalone CalculiX](https://prepomax.discourse.group/t/using-standalone-calculix/846)
  - Building from source needs SPOOLES and ARPACK; PARDISO-enabled Windows builds are discussed on the forum. — [CalculiX forum: Windows install](https://calculix.discourse.group/t/need-for-comprehensive-updated-calculix-2-20-windows-install-guide-and-windows-install-help/1415); [CalculiX forum: PARDISO on Windows](https://calculix.discourse.group/t/calculix-and-pardiso-windows/2011)
  - Shell elements S4/S4R/S8/S8R are expanded to C3D8I/C3D8R/C3D20/C3D20R. — [CalculiX manual node37](https://web.mit.edu/calculix_v2.7/CalculiX/ccx_2.7/doc/ccx/node37.html)
- **FEniCSx / DOLFINx**
  - The DOLFINx README lists a Windows conda install but marks Windows packages as beta, with PETSc/petsc4py unavailable on Windows. — [DOLFINx GitHub](https://github.com/fenics/dolfinx)
  - FESTIM docs state dolfinx cannot be installed natively on Windows and point users to WSL. — [FESTIM installation](https://festim.readthedocs.io/en/v2.1/installation.html)
  - A FEniCS moderator (2024) described the Windows build as beta and recommended WSL. — [FEniCS Discourse](https://fenicsproject.discourse.group/t/fenicsx-0-8-installation-issues/15828)
  - **Plates and shells in FEniCS:**
    - No official dolfinx shell demo was found.
    - The community project shell_analysis_fenicsx implements Reissner-Mindlin shell analysis in FEniCSx with a locking-free formulation (Campello et al.) extended to quads, validated on the shell obstacle course. — [shell_analysis_fenicsx](https://github.com/RuruX/shell_analysis_fenicsx)
    - Legacy FEniCS-Shells (dolfin, not dolfinx) supports Reissner-Mindlin plates with MITC reduction operators, DG and reduced integration. Its clamped-plate demo uses the Duran-Liberman (MITC) element. — [FEniCS-Shells docs](https://fenics-shells.readthedocs.io/en/stable/); [clamped RM demo](https://fenics-shells.readthedocs.io/en/stable/demo/reissner-mindlin-clamped/demo_reissner-mindlin-clamped.py.html)
    - The COMET tutorial gives a locking-free RM plate using P2 deflection and Crouzeix-Raviart rotations (legacy dolfin). — [COMET RM-CR demo](https://comet-fenics.readthedocs.io/en/latest/demo/reissner_mindlin_crouzeix_raviart/reissner_mindlin_CR.html)
- **scikit-fem**
  - A pure-Python (3.8+) FE assembly library supporting tri/quad/tet/hex and 1D meshes. — [scikit-fem docs](https://scikit-fem.readthedocs.io/)
  - Relevant examples:
    - Ex 2: Kirchhoff plate bending on a unit square with clamped/simply supported/free edges.
    - Ex 8: C1 fifth-degree Argyris elements for conforming biharmonic problems.
    - Ex 11: 3D linear elasticity with trilinear hexes.
    - Ex 34: Euler-Bernoulli beam with cubic Hermite elements and an exact value.
    - Ex 9/32 use PyAMG optionally; Ex 32 "scales to reasonably fine meshes (a million tetrahedra in a few minutes)".
    — [scikit-fem list of examples](https://scikit-fem.readthedocs.io/en/latest/listofexamples.html)
  - Larsson & Larson: a P1-continuous Kirchhoff plate method with Morley-type reconstruction (equivalent to the Basic Plate Triangle) does **not** converge on unstructured meshes, while a fully quadratic reconstruction converges optimally. This is a caution for cheap plate elements on unstructured meshes. — [arXiv 1503.06282](https://arxiv.org/pdf/1503.06282)
- **SfePy** provides linear-solver wrappers for scikit-sparse Cholesky, PyPardiso and PyAMG. — [SfePy solvers.ls](https://sfepy.org/doc/src/sfepy/solvers/ls.html)

### Inferences
- **Recommended stack on Windows.**
  - Gmsh (Python API, OCC booleans of plate minus bores/pockets, Distance+Threshold fields on bore and fillet curves, `Mesh.ElementOrder = 2`).
  - In-process solver: scikit-fem or a small custom NumPy/SciPy assembler, for plane-stress tri6 plus a plate element (Morley/DKT/MITC; scikit-fem ships ElementTriMorley and ElementTriArgyris, from general knowledge; the docs list only confirms Argyris and a Kirchhoff example).
  - Verification: CalculiX via subprocess (write `.inp` with S8R or C3D20R/C3D10, read `.frd`/`.dat`) for an independent cross-check.
  - Avoid making DOLFINx a hard dependency for a Windows web tool. If it is used, run it server-side on Linux or WSL2.
- **Licensing.**
  - Gmsh's GPL-with-linking-exception and CalculiX's GPL both allow running the tools as separate executables or a Python module on a server.
  - Distributing a closed-source product that links Gmsh needs care (commercial licence).
  - Calling CalculiX as an external process is generally treated as "aggregation", but that is a legal judgement, not verified here.
- **Typical runtimes** (order-of-magnitude expectation, not benchmarked here): a 2D plane-stress or plate problem of 10k-50k DOF assembles in well under a second with vectorised NumPy (scikit-fem). A sparse direct solve of a 2D problem of that size typically takes tens to hundreds of milliseconds. Gmsh 2D meshing of a 457 mm plate at h of about 2-3 mm with a few dozen holes takes around a second. CalculiX on a 2D-shell model of that size spends more time on I/O and process start-up than on the solve. Measure on the target server.

### Gaps
- FreeCAD FEM (a GUI/Python front end to CalculiX) was not researched.
- Exact licences of scikit-fem (believed BSD-3), DOLFINx (believed LGPL-3), SfePy (believed BSD) and pyamg (believed MIT) were not verified in this session.
- Which element the scikit-fem Example 2 Kirchhoff plate uses (believed Morley) was not confirmed from the fetched page.
- No measured runtimes for 10k-50k DOF problems in these specific tools were found; treat the figures above as expectations.
- The CalculiX current version, maintenance cadence and whether CalculiX supports a true DKT/thin-shell element (rather than expansion to solids) were not confirmed.

---

## 8. Fast linear solvers for repeated analyses and multiple load cases

### Takeaway
For 2D plane-stress and plate problems of 10k-100k DOF, a sparse direct factorisation with fill-reducing ordering is the right default. Factor once, then solve every load case by cheap triangular solves. Candidates: CHOLMOD via scikit-sparse (K is SPD once constrained), MKL PARDISO via pypardiso (multithreaded, a drop-in for spsolve), or SciPy SuperLU/`factorized`. AMG-preconditioned CG (pyamg) pays off mainly for large 3D models. No head-to-head benchmark of all three Python options was found.

### Cited Findings
- PyPardiso wraps Intel MKL PARDISO, a shared-memory parallel direct sparse solver. Its API mirrors `scipy.sparse.linalg.spsolve`, and it is "in many cases significantly faster" than SciPy's single-threaded SuperLU. It does not support complex numbers. — [PyPI: pypardiso](https://pypi.org/project/pypardiso/0.4.5)
- A 2021 FEA-speed blog found that newer SciPy permutation (ordering) options had substantially improved SciPy's direct-solver performance relative to earlier versions, and compared them with PyPardiso. — [Newton Excel Bach: FEA faster and PyPardiso](https://newtonexcelbach.com/2021/10/17/making-finite-element-analysis-go-faster-update-and-pypardiso/)
- SfePy wraps scikit-sparse Cholesky, PyPardiso and PyAMG. Its docs note that its PyPardiso pre-factorisation step just calls `pypardiso.spsolve()` on a zero right-hand side, so explicit pre-factorisation brings no extra performance there. — [SfePy solvers.ls](https://sfepy.org/doc/src/sfepy/solvers/ls.html)
- No published FEM benchmark comparing PyPardiso, scikit-sparse CHOLMOD and PyAMG head-to-head was found; CHOLMOD requires SPD matrices. — [search summary; SfePy docs](https://sfepy.org/doc/src/sfepy/solvers/ls.html)
- scikit-fem examples use PyAMG for large 3D problems (Ex 9) and report a million tetrahedra solved in minutes with AMG (Ex 32, a Stokes problem). — [scikit-fem examples](https://scikit-fem.readthedocs.io/en/latest/listofexamples.html)

### Inferences
- **Multiple load cases.** Assemble K once per geometry, factor once, and solve for all load cases (in-plane pulls, bearing loads, torsion, bending) as a multi-column right-hand side: `factor(B)` with B as an n x m matrix. The marginal cost per extra load case is a forward/back substitution, about the cost of 2 x nnz(L), typically 5-20% of the factorisation cost for 2D problems.
- **Optimisation in the loop on a fixed grid.** The sparsity pattern is identical every iteration, because ersatz material keeps all elements. The symbolic analysis (ordering and elimination tree) can therefore be computed once and only the numeric factorisation repeated. CHOLMOD supports this (analyze once, then refactor with new values); SciPy's `splu` does not expose it. Element stiffness matrices on a uniform grid are identical up to a density scale factor, so assembly reduces to a scaled scatter of one precomputed Ke (the 88-line-code approach).
- **Body-fitted re-meshing.** Each new geometry changes the sparsity, so a fresh symbolic analysis is needed. For 2D problems of 50k DOF this is still fast. Nested-dissection/AMD orderings give near-O(n^1.5) factorisation cost in 2D (textbook result, not fetched).
- **When to use AMG-CG.** 3D solid verification models above roughly 200k-500k DOF, or memory-limited servers. For elasticity, smoothed-aggregation AMG should be given the rigid-body near-nullspace (pyamg's `B` argument). Plate/shell systems with rotational DOFs and high L/t (144 here) are ill-conditioned, which favours direct solvers for 2D plate models.
- **Constraint handling.** Eliminate constrained DOFs (condense) rather than using huge penalty springs, to keep K well-conditioned and SPD for Cholesky. Lagrange multipliers make the system indefinite, which rules out Cholesky and needs LU/LDL^T (PARDISO handles symmetric-indefinite).
- **Windows.** pypardiso pulls MKL (large wheel, x86-only). scikit-sparse/CHOLMOD on Windows has historically needed conda (SuiteSparse); this was not verified here. SciPy SuperLU works everywhere and is a safe fallback.

### Gaps
- No measured timings were found for CHOLMOD vs PARDISO vs SuperLU vs pyamg on 2D elasticity or plate problems of 10k-50k DOF. The newtonexcelbach post's numbers were not extracted.
- Whether pypardiso caches the factorisation when called repeatedly with the same matrix (believed yes, via a matrix-hash check) was not confirmed from its docs.
- scikit-sparse Windows wheel availability and the current maintenance status of scikit-sparse were not verified.
