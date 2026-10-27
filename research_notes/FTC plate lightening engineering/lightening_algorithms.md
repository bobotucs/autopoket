# Algorithms for automatic plate lightening: topology/shape/size optimisation vs rule-based and load-path (truss) methods

Scope: 2D flat plates, one material, mostly through-cuts, protected holes. This compares the candidate algorithms for an FTC plate-lightening tool, AutoPocket v2. v2 already has keep-out bands, a constrained-Delaunay truss whose spacing follows the blank plate's strain energy, an isogrid option, greedy ESO-style rib pruning, and FEA-checked selection.

Each section below separates three kinds of statement:
- **Cited Findings**: established, published results, each with a source.
- **Inferences**: my own engineering reasoning and proposals, marked as such.
- **Gaps**: things I could not verify.

Context taken from the local code, so the recommendations fit what already exists:
- v2's FEA ([autopocket2/fea2.py](C:\Users\abdul\Documents\autopoket\autopocket2\fea2.py), on top of v1's `autopocket/fea.py`) rasterises the plate onto a regular grid with a fill fraction `rho` per cell. It extrudes this into one layer of hex8 elements and scales element stiffness linearly by `rho`.
- It solves 3 load cases (out-of-plane bending, in-plane bending, torsion), each with the left end clamped and then the right: 6 cases in total. It returns per-element strain energy `rho * u_e^T K_e u_e`.
- Structurally this is already a density-method (SIMP with p = 1) analysis grid.
- I measured it in this session on a synthetic 300 x 120 x 6.35 mm plate with 6 holes, using the project venv. One full "analysis pass" (2 LU factorisations plus 6 solves) took:
  - **1.07 s** at 6,027 cells (37k DOF)
  - **4.38 s** at 16,000 cells (97k DOF)
  - **9.83 s** at 30,140 cells (182k DOF)

  Source: local timing script, scratchpad `time_fea.py`, calling `Analysis._solve`.

---

## 1. SIMP: formulation, sensitivities, filtering/projection, OC vs MMA, convergence, multiple load cases, passive regions, runtime, and available code

### Takeaway
SIMP is mature, well documented and cheap in 2D. A 30k-element compliance problem takes about 0.23 s per iteration in top99neo (MATLAB). The recipe is fixed:
- density filter plus volume-preserving Heaviside projection
- OC update for one volume constraint, or MMA for anything more
- passive solid/void element sets for bores, holes and edge bands
- a weighted-sum or bound (min-max) formulation for several load cases

The educational codes (99-line, 88-line, top99neo, and the DTU Python ports) carry no explicit licence. Licensed Python options exist: topoptlab (GPL-3.0) and mmapy (GPL).

### Cited Findings
**Formulation**
- The modified SIMP interpolation is E(x̂_e) = E_min + x̂_e^p (E_0 − E_min). top99neo uses E_min = 1e-9 (with E_0 = 1) and p = 3 in its tests, and its 2D listing can apply continuation on the penalty. — [Ferrari & Sigmund 2020, top99neo (arXiv HTML)](https://arxiv.org/html/2005.05436v2)
- The standard problem is: minimise compliance c = Fᵀu subject to K(x)u = F, a volume fraction constraint V(x̂) ≤ f·|Ω|, and 0 ≤ x ≤ 1. The element sensitivity is ∂c/∂x̂_e = −p x̂_e^(p−1) (E_0 − E_min) u_eᵀ k_0 u_e.
  - This adjoint result follows because compliance is self-adjoint.
  - The filtered and projected sensitivities are then obtained by the chain rule through the filter and projection.
  - Sources: [Andreassen et al. 2011, 88-line paper (DOI)](http://dx.doi.org/10.1007/s00158-010-0594-7); [Ferrari & Sigmund 2020](https://arxiv.org/html/2005.05436v2)

**Filtering and projection**
- Density filter: x̃_e = Σ h_ei x_i / Σ h_ei, with the linear hat weight h_ei = max(0, r_min − dist(i, e)). top99neo's default MBB case uses r_min = 8.75 elements; its benchmarks use r_min = 4, 8 and 16 on the 300x100, 600x200 and 1200x400 meshes. — [Ferrari & Sigmund 2020](https://arxiv.org/html/2005.05436v2)
- The 99-line code (Sigmund 2001) has 36 lines of main program, 12 lines of OC optimiser, 16 lines of "mesh-independency filter" (a sensitivity filter) and 35 lines of FE code. Three extra lines give multiple load cases. — [DTU TopOpt: 99-line code page](https://www.topopt.mek.dtu.dk/apps-and-software/a-99-line-topology-optimization-code-written-in-matlab); [DTU TopOpt: top99neo page](https://www.topopt.mek.dtu.dk/apps-and-software/new-99-line-topology-optimization-code-written-in-matlab)
- The 88-line code extends the 99-line code with a density filter. Its speed-up comes mainly from preallocation and vectorisation, about a factor of 100 on a 7,500-element benchmark. Variants:
  - top110.m: Heaviside projection
  - top82.m: PDE filter
  - top71.m: conv2 filtering

  Source: [DTU TopOpt: 88-line page](https://www.topopt.mek.dtu.dk/apps-and-software/efficient-topology-optimization-in-matlab)
- Relaxed Heaviside projection: x̂ = [tanh(βη) + tanh(β(x̃ − η))] / [tanh(βη) + tanh(β(1 − η))].
  - It is not volume-preserving for a fixed η. top99neo finds η* each iteration by Newton's method, usually in 1–2 Newton steps, with typical η* between 0.4 and 0.52, so the volume is preserved.
  - With a fixed η < 0.5 and the constraint applied to x, the physical volume overshoots.
  - Continuation on β is used, e.g. betaCnt = {250, 16, 25, 2}: start at iteration 250, β_max = 16, raise every 25 iterations, factor 2.

  Source: [Ferrari & Sigmund 2020](https://arxiv.org/html/2005.05436v2)

**Optimiser update**
- OC update: x_new = x·(−∂c / (λ ∂V))^(1/2), clamped to move limits [max(0, x − μ), min(1, x + μ)], with λ found by bisection.
  - Starting the bisection from an estimated bracket [0, λ#] instead of [0, 1e9] halves the number of bisection steps.
  - The bisection tolerance is (l₂ − l₁)/(l₂ + l₁) > 1e-4.

  Source: [Ferrari & Sigmund 2020](https://arxiv.org/html/2005.05436v2)
- MMA (Svanberg 1987) is available in Python as `mmapy` (GCMMA-MMA-Python by Arjen Deetman), ported from Svanberg's MATLAB code. It is GNU GPL; the exact version was not confirmed in the snippet. Users are asked to cite Svanberg 1987 and tell him about their application. — [mmapy on PyPI](https://pypi.org/project/mmapy/); [GCMMA-MMA-Python GitHub](https://github.com/arjendeetman/GCMMA-MMA-Python)

**Passive regions and stopping**
- Passive solid (x = 1) and passive void (x = 0) sets are built into top99neo (`pasS`, `pasV`), and the filtered field is overwritten on those sets. Its frame-reinforcement example uses a passive solid frame of thickness L/50 plus a void opening. This is exactly the mechanism needed for keep-out bands around bores and plate edges. — [Ferrari & Sigmund 2020](https://arxiv.org/html/2005.05436v2)
- Convergence criteria:
  - top99neo stops when ‖r_k‖₂/√m < 1e-6, with the residual measured on the physical variables.
  - top88 uses the maximum absolute change in the design variables instead.

  Source: [Ferrari & Sigmund 2020](https://arxiv.org/html/2005.05436v2)

**Iteration counts and runtimes**
- With tight tolerances, standard OC ran to the 2,500-iteration cap on all four test problems.
- Periodic Anderson extrapolation cut this to 828, 352, 752 and 818 iterations, with compliance changes of +2.5%, +3.2%, −1.0% and +0.2% (e.g. T1: 252.7 → 258.9).
- Settings: applied every 4 steps, 4 stored residuals, starting at iteration 20 or 500.
- Source: [Ferrari & Sigmund 2020](https://arxiv.org/html/2005.05436v2)
- Per-iteration MATLAB times, from 100-iteration MBB runs:

  | Mesh | Elements | top88 | top88U | top99neo | Speed-up vs top88 |
  |---|---|---|---|---|---|
  | 300x100 | 30k | 0.615 s | 0.358 s | 0.231 s | 2.66× |
  | 600x200 | 120k | 4.57 s | 1.87 s | 1.19 s | 3.85× |
  | 1200x400 | 480k | 31.3 s | 10.1 s | 5.69 s | 5.5× |

  Source: [Ferrari & Sigmund 2020](https://arxiv.org/html/2005.05436v2); [arXiv abstract](https://arxiv.org/abs/2005.05436)

**Multiple load cases**
- The weighted sum of compliances is the common formulation. Its weights can be read as load probabilities, but the result can be very sensitive to them: small changes in the weight ratios can give very different designs.
- The min-max (worst-case compliance) formulation is usually written as a bound problem: minimise t subject to c_k ≤ t for every case k.
- Both formulations need one linear solve per load case per iteration.
- Sources: [Zhang, de Sturler & Paulino 2017 (CMAME)](https://personal.math.vt.edu/sturler/Publications/CMAME_Zhang-deSturler-Paulino_2017_final.pdf); [Advances in Mech. Eng. 2020](https://doaj.org/article/a7f815648ad84c78a41c63fa1b4320ae); [CILAMCE 2021, many-load-case compliance TO](https://publicacoes.softaliza.com.br/cilamce2021/article/view/5973)

**Python code and licences**

| Code | What it is | Licence |
|---|---|---|
| DTU `topopt.py` | Python port of the 88-line code; needs numpy, scipy, matplotlib | None stated; intended for education and courses |
| DTU `topopt_cholmod.py` | Faster variant using CVXOPT's sparse Cholesky | None stated; intended for education and courses |
| topoptlab (stefanhiemer) | Grew from the Aage et al. Python code and the 88-line code; 2D MBB SIMP example | GPL-3.0 (per metadata) |
| ToPy | 2D/3D compliance, heat and mechanism problems | Not confirmed |
| topo-fenics | 55-line FEniCS/PETSc SIMP code | Not confirmed |
| PyHexTop | 2D, hexagonal elements | Not confirmed |
| PyTopo3D (Kim & Kang 2025) | **3D only**; SIMP + OC, STL obstacle import, STL export | Software licence not stated (arXiv paper is CC BY 4.0) |

Sources: [DTU TopOpt: Python codes](https://www.topopt.mek.dtu.dk/apps-and-software/topology-optimization-codes-written-in-python); [topoptlab metadata](https://science.ecosyste.ms/projects/806149); [topoptlab docs](https://topoptlab.readthedocs.io/en/stable/getting_started.html); [ToPy](https://github.com/milmillin/topy); [55-line FEniCS code](https://cs.paperswithcode.com/paper/a-55-line-code-for-large-scale-parallel); [PyTopo3D arXiv](https://arxiv.org/abs/2504.05604v1)

### Inferences
- **v2's blank-plate strain-energy field is SIMP's first sensitivity.** At the all-solid start (x = 1), the SIMP sensitivity is −p·u_eᵀk_0u_e, which is proportional to v2's element strain energy. So v2's "load-guided spacing" is iteration 0 of SIMP/BESO.
  - It ignores how load paths move once material is removed. That redistribution is the same effect Zhou & Rozvany identified as ESO's weakness (section 4).
  - A few dozen SIMP iterations give the converged version of the same field. *(Derived from the formula above; this is my inference, not a published claim about AutoPocket.)*
- **Adding SIMP to v2 is cheap in code.** v2 already rasterises onto a regular grid and scales stiffness by `rho`. Turning `rho` into a design variable means:
  - interpolation E = E_min + ρ^p
  - sensitivity −pρ^(p−1)·u_eᵀK_eu_e, summed over load cases
  - a density filter via `scipy.ndimage`, which v2 already imports
  - an OC update
  - passive solid on hole keep-out and edge bands, passive void outside the profile

  That is roughly 60–100 lines.
- **Runtime estimate for v2's 3D-hex, 6-case model** (my measurements and estimates):

  | Cells | Measured cost per pass | 50–150 iterations |
  |---|---|---|
  | 6k | ≈1.1 s | ~1–3 min |
  | 16k | ≈4.4 s | ~4–11 min |

  Ways to make it faster:
  - run SIMP only as guidance on a coarser grid (3–6k cells)
  - use 2D plane-stress Q4 elements (2 DOF/node) for the in-plane cases
  - reuse the factorisation for all cases with the same clamp (v2 already does this per end)

  The ~5–10× gap to top99neo comes from the 3-DOF hex single-layer model, the 6 cases, and the full LU each iteration. Iterative solvers with warm starts could narrow it.
- **Which formulation fits FTC plates.** FTC loads are uncertain and enveloped over generic cases. A normalised min-max is more defensible than a weighted sum: c_k / c_k,blank ≤ t (bound form with MMA), or a smooth p-norm/soft-max of the normalised compliances with OC. It matches v2's existing "worst case of 6" verdict and avoids having to choose weights.
- **Recommended SIMP defaults for this use** (my proposal):
  - p = 3
  - density filter with r_min ≈ 0.5–0.75 × the rib width in cells; v2 uses 8 mm ribs and h ≈ 1.5–2.5 mm, so r_min ≈ 2.5–4 cells
  - volume-preserving Heaviside with β continuation up to 8–16
  - OC with move limit 0.2
  - stop at max change < 0.01 or after 100–200 iterations, since the result is only guidance

### Gaps
- No published Python-SIMP runtimes at 5k–50k elements were found. The numbers here are MATLAB top99neo plus my local measurement of v2's FEA.
- Licences of ToPy, PyHexTop, topo-fenics, PyTopo3D and the PyPI `topopt` package could not be confirmed; the PyPI page did not load.
- The weighted-sum vs min-max comparison found in the sources is qualitative. No head-to-head benchmark numbers were retrieved.
- Primary sources for the classic checkerboard and mesh-dependence analysis (Sigmund & Petersson 1998) and for the original density filter (Bruns & Tortorelli 2001, Bourdin 2001) were not fetched in this session. The 99-line "mesh-independency filter" and top99neo's density filter are the cited proxies.

---

## 2. Stress-constrained topology optimisation; minimum and maximum length-scale control

### Takeaway
Stress-constrained TO is a known hard problem. Its constraints are local (as many as there are elements). It has the "singularity" phenomenon, which needs ε- or qp-relaxation with continuation. And p-norm aggregation only approximates the peak stress.

Reported costs run up to about 10× a compliance run, and convergence to the global optimum is not guaranteed. For a small FTC tool, stress is better handled as a post-check: FEA validation plus corner-radius and fillet rules.

A minimum rib width can be enforced in density TO with the robust eroded/intermediate/dilated formulation, at about 3× the analysis cost. A plain filter plus thresholding does not guarantee it.

### Cited Findings
**Why stress constraints are hard**
- Stress constraints should hold at every material point, so their number is comparable to the number of design variables. Solution times are therefore expected to be much longer, and local minima are more likely. — [Amir 2016, arXiv:1608.06654](https://arxiv.org/pdf/1608.06654)
- Active-set approach: Duysinx & Bendsøe (1998) kept about one third of the local constraints in the sensitivity analysis. At the end, 180 constraints (15% of the design variables) were active. — [Amir 2016](https://arxiv.org/pdf/1608.06654)
- Augmented-Lagrangian approach: Pereira et al. (2004) treated all constraints this way and reported run times up to 10× those of minimum-compliance problems. — [Amir 2016](https://arxiv.org/pdf/1608.06654)

**Aggregation**
- Duysinx & Sigmund (1998) bound the maximum stress from above with the p-norm and from below with the p-mean. Ill-conditioning limited them to p ≈ 4, which is too low to capture the real peak. — [Amir 2016](https://arxiv.org/pdf/1608.06654)
- Le et al. (2010) proposed regional p-norm measures, normalised by the actual maximum stress, and reproduced the L-bracket design that avoids the re-entrant corner. Drawbacks:
  - the normalisation is non-differentiable between iterations
  - regions are re-sorted each iteration, which adds inconsistency
  - more regions do not always give a better design

  Source: [Amir 2016](https://arxiv.org/pdf/1608.06654)
- p-norms need very high exponents when several close peaks exist. That is the typical case for stress, because good designs are nearly fully stressed. — [Search summary of stress-TO literature: e.g. Holmberg et al., Politecnico di Milano repository](https://re.public.polimi.it/bitstream/11311/994782/1/SMOCBD.pdf)

**The singularity problem and relaxation**
- The optimum can lie at a degenerate point of the design space; this was shown first for trusses (Sved & Ginos 1968; Kirsch 1990).
- Remedies:
  - ε-relaxation (Cheng & Guo 1997), with ε reduced by continuation
  - qp-relaxation (Bruggi 2008), which uses a lower penalty q for stress than p for stiffness

  The two give similar results, both depend strongly on the continuation, and a sequence of relaxed solutions may not converge to the global optimum (Stolpe & Svanberg 2001).
- Source: [Amir 2016](https://arxiv.org/pdf/1608.06654)

**Other approaches**
- Level-set/topological-derivative methods give smooth re-entrant corners: Allaire & Jouve 2008 used a stress-penalty integral; Amstutz & Novotny 2010 used an exterior penalty, ending only 1–2% above the target stress. — [Amir 2016](https://arxiv.org/pdf/1608.06654)
- Amir (2016) proposes a single global constraint on accumulated plastic strain, using an elasto-plastic analysis, in place of local or aggregated stress constraints. — [Amir 2016](https://arxiv.org/pdf/1608.06654)

**Minimum length scale**
- The robust formulation (Wang, Lazarov & Sigmund 2011) optimises the worst of three designs. These are projected from the same filtered field at thresholds η₋ (eroded), η (intermediate) and η₊ = 1 − η₋ (dilated).
  - Erosion only thins members, so a minimum solid size is guaranteed by the erosion distance; dilation does the same for voids.
  - It converges stably to nearly 0/1 designs.
  - The link between length scale and the filter radius/thresholds was found numerically (Wang et al. 2011) and analytically (Qian & Sigmund 2013). Setting these parameters is called cumbersome.
  - The filter needs special treatment at domain boundaries.
  - Sources: [Analytical relationships for minimum length scale in robust TO (arXiv:2101.08605)](https://arxiv.org/pdf/2101.08605); [Wang, Lazarov & Sigmund 2011 (DOI)](https://www.doi.org/10.1007/S00158-010-0602-Y)
- Morphology-based filters (Sigmund 2007) use dilation, erosion, open and close to give black-and-white designs with a minimum size for holes, members, or both. Sigmund found open-close and close-open too costly in sensitivity analysis. Schevenels & Sigmund (2016) cut that cost but found each open or close undoes the previous one, so only one phase gets the length scale. — [Sigmund 2007 (DTU Orbit)](https://orbit.dtu.dk/en/publications/morphology-based-black-and-white-filters-for-topology-optimizatio/); [Schevenels & Sigmund 2016 (DTU Orbit)](https://orbit.dtu.dk/en/publications/on-the-implementation-and-effectiveness-of-morphological-close-op/)

### Inferences
- The robust formulation needs three FE analyses per iteration (eroded, intermediate, dilated). In practice that is ~3× the cost of plain SIMP; often only the eroded design is analysed for compliance. *(Inference from the three-design formulation.)*
- For AutoPocket, minimum rib width is better enforced **geometrically after the fact**: morphological opening of the solid region by the rib half-width, then v2's existing `validate.py` rule check. The density result is only guidance (section 5).
- **Do not use stress-constrained TO** in an FTC tool. FTC loads are uncertain, and v2's peak-stress metric is a p99 von Mises relative to the blank plate, so precise stress constraints would be false precision. A peak-stress-ratio screen plus corner rules (section 3) captures most of the practical benefit. *(Engineering judgement.)*

### Gaps
- Maximum length-scale control (limiting pocket or rib size, e.g. Guest's local volume constraints) was not researched with sources in this session. Wu et al.'s local-volume "porous infill" appears only as a comparison in [Wang, Westermann & Wu 2022](https://arxiv.org/pdf/2207.09172).
- No quantitative cost ratio between robust-formulation and plain SIMP was retrieved.

---

## 3. Level-set / shape optimisation for smooth pocket boundaries, and size optimisation of rib widths

### Takeaway
Level-set and shape-gradient methods produce smooth boundaries and handle topology changes, but they depend on the starting design. Their real value for AutoPocket is local: reshaping pocket corners and fillets to cut stress concentrations, not finding the layout.

Cheap, validated alternatives exist:
- Mattheck's CAO and Method of Tensile Triangles for corners
- after the rib topology is fixed, a sizing step on rib widths (as in published rib-network and PSL-stiffener work)

### Cited Findings
**Level-set methods**
- Allaire, Jouve & Toader (2004) combine the adjoint shape derivative with level-set front propagation, with the shape derivative as the normal velocity in a Hamilton–Jacobi equation, in 2D and 3D. The method handles topology changes but depends strongly on the initial guess. — [Allaire, Jouve & Toader 2004 (IP Paris portal)](https://researchportal.ip-paris.fr/en/publications/structural-optimization-using-sensitivity-analysis-and-a-level-se/); [Allaire et al. 2002, C. R. Math.](https://www.numdam.org/item/CRMATH_2002__334_12_1125_0)
- Educational code: Challis (2010) wrote a 129-line MATLAB discrete level-set code in the spirit of the 99-line code. — [Liu & Tovar 2014/2015, citing Challis 2010](https://scholarworks.iupui.edu/bitstream/1805/6603/1/Tovar_2015_an_efficient.pdf)
- Level-set stress methods smooth re-entrant corners: Allaire & Jouve 2008; Amstutz & Novotny 2010 ended within 1–2% of the target stress. — [Amir 2016](https://arxiv.org/pdf/1608.06654)

**Rule-based corner shaping (Mattheck)**
- CAO (computer-aided optimisation) adds material at overloaded points, like tree growth. SKO (soft-kill option) removes underloaded material, like bone remodelling. Both are FEM-based and need several iterations.
- The Method of Tensile Triangles is a graphical shortcut inspired by buttress roots. A corner notch is bridged by a chain of tensile triangles, and the shape can be scaled to the available space.
- It works for multi-axial loading and for removing unloaded material, and it was checked against FE results and fatigue tests.
- Sources: [Mattheck et al. 2007, Int. J. Design & Nature](https://www.iieta.org/journals/ijdne/paper/10.2495/D%26N-V2-N4-301-309); [WIT Press 2006, A Graphic Way for Notch Shape Optimization](https://witpress.com/elibrary/wit-transactions-on-ecology-and-the-environment/87/16131); [KIT publication](https://publikationen.bibliothek.kit.edu/1000008473/317782)

**Sizing after topology is fixed**
- Rib-reinforced shells (Li et al. 2016): FEA, a quad mesh aligned to the principal-stress cross field, extraction of an initial rib network, **pruning of low-contribution ribs**, rib relocation, then **rib cross-section optimisation** for stiffness at minimum material. — [Li et al., Computer Graphics Forum (Eurographics DL)](https://diglib.eg.org/handle/10.1111/cgf13268)
- Vergara & Zegard (2024): principal stress lines reconstructed from FEA for Nervi-type shells, with members then sized by a gradient-based optimiser. They report beating structured and orthogonal reinforcement layouts. — [Vergara & Zegard 2024 (PUC Chile)](https://researching.investigacion.ing.uc.cl/publication/3069)
- He & Gilbert (2015) developed geometry-optimisation-based "rationalization" of layout-optimised trusses, cited as a way to make layout optimisation practical. — [He, Gilbert & Song 2019 (White Rose preprint)](https://eprints.whiterose.ac.uk/142746/1/trussPython.pdf)

### Inferences
- **Rib-width sizing would likely beat greedy deletion** for v2. v2 removes whole low-energy ribs at the fixed 8 mm width. A better next step, in the spirit of Li et al., is an OC/fully-stressed resizing loop: w_i ← w_i·(U_i/Ū)^η, clamped to [w_min = 8 mm, w_max]. This would:
  - widen ribs that carry most of the energy
  - leave lightly loaded ribs at the minimum
  - remove a rib only when the merged pocket stays valid

  This is size optimisation on a fixed topology. It is convex-ish and cheap: one FEA per iteration, 5–10 iterations. *(Proposal.)*
- **Corner rule (Mattheck-style):** at pocket corners where the FEA stress is above, say, the 95th percentile, enlarge the corner radius or apply a 2–3-step tensile-triangle blend instead of the uniform 2 mm tool radius. This needs no gradient and fits v2's polygon/shapely pipeline. *(Proposal.)*
- A full level-set optimiser is unlikely to pay off for FTC plates. Its benefit is boundary smoothness, which morphological rounding and fillet rules deliver more cheaply (section 5).

### Gaps
- No quantitative stress-concentration reduction for the Method of Tensile Triangles in plate pockets was retrieved; the papers were found but not read in full.
- No source compared rib sizing against rib deletion for flat through-cut plates.

---

## 4. ESO/BESO, ground-structure layout optimisation, Michell trusses, principal-stress-line methods, and isogrid

### Takeaway
- **ESO/BESO** is simple and gives 0/1 designs. It is also heuristic: hard-kill ESO can remove load-carrying material with no way back, while BESO's re-admission, filtering and history averaging fix most of that.
- **Ground-structure (layout) optimisation** is the rigorous load-path method. In plastic form it is a linear programme, solved in seconds for problems the size of an FTC plate by a 98-line Python script, and it handles holes, multiple load cases and unequal tension/compression limits.
- **Michell theory**: optimal members follow principal strain directions. Truss and lattice microstructures are optimal only as the volume fraction tends to zero.
- **Isogrid** (NASA CR-124075) is a robust, quasi-isotropic regular fallback.

### Cited Findings
**ESO/BESO**
- Zhou & Rozvany (2001) gave a tie-beam example where ESO's element removal raised total compliance by about **10×**, because the removal changed how load was transmitted. — [Finite-variation sensitivity paper, arXiv:2104.04571 (summarising Zhou & Rozvany 2001)](https://arxiv.org/pdf/2104.04571)
- Rebuttals and fixes:
  - With accurate sensitivities, ESO is not prone to this failure, though its one-way nature can still trap it in inefficient local optima, which BESO avoids ([The ESO method revisited (2014)](https://research.usq.edu.au/item/q2w53/the-eso-method-revisited)).
  - Fine meshes and suitable parameters let ESO reach good solutions (Edwards et al. 2007; Huang & Xie 2008) ([arXiv:2104.04571](https://arxiv.org/pdf/2104.04571)).
  - In Edwards, Kim & Budd, both ESO and SIMP first did worse than an "intuitive" design until the initial domain and mesh size were tuned ([Edwards, Kim & Budd, Univ. of Bath](https://researchportal.bath.ac.uk/en/publications/an-evaluative-study-on-eso-and-simp-for-optimising-a-cantilever-t/)).
- BESO (Huang & Xie 2007) adds three things:
  - a nodal sensitivity filter that averages element sensitivities to nodes, then maps them back, including onto void elements, to suppress checkerboards and mesh dependence
  - averaging of sensitivities over past iterations, for stability
  - removal and re-admission of material

  Sources: [Topology optimization via ML/DL review, arXiv:2210.10782](https://arxiv.org/pdf/2210.10782); [WCSMO 2015 paper 1154](https://web.aeromech.usyd.edu.au:443/WCSMO2015/papers/1154_paper.pdf)
- Soft-kill BESO sets void elements to x_min = 0.001 instead of deleting them, and uses a penalised (SIMP-like) sensitivity. As p → ∞ this reduces to hard-kill. Huang & Xie (2010) published a soft-kill BESO MATLAB code based on the 99-line code. — [CILAMCE 2021 BESO paper](https://publicacoes.softaliza.com.br/cilamce2021/article/download/5984/5041/2375); [Huang & Xie 2010 (DOI)](https://www.doi.org/10.1007/S00158-010-0487-9)
- A compact Python BESO code exists (Zuo & Xie 2015, Advances in Engineering Software), found only through a document-sharing listing, so availability and licence are unverified. — [Scribd listing](https://www.scribd.com/document/307004618/Zuo-Xie-2015-Python-Code-Published-pdf)
- Rozvany's critical review (2008) evaluated SIMP and ESO/SERA as the methods that reached industrial software, noting ESO saw only isolated industrial use. SERA (Rozvany & Querin) puts optimality-criteria foundations under ESO. — [Rozvany 2008 PDF (ulaval)](https://giref.ulaval.ca/~deteix/bois/documents_references/rozvany2007.pdf); [MaRDI record](https://portal.mardi4nfdi.de/entity/Q381242)

**Ground-structure layout optimisation (Gilbert & Tyas lineage)**
- Plastic layout formulation for a single load case: minimise V = lᵀa over member areas a and forces q, subject to Bq = f, q ≥ −σ⁻a, q ≤ σ⁺a, a ≥ 0. For several load cases, equilibrium and stress limits hold per case with shared areas.
  - Short members can be penalised with a joint cost s, using l + s in the objective, which simplifies the layout.
  - Overlapping members are removed with a gcd check, and members crossing the domain boundary with shapely `contains`. This is how holes and non-convex domains are handled.
  - Source: [He, Gilbert & Song 2019, A Python script for adaptive layout optimization of trusses (preprint)](https://eprints.whiterose.ac.uk/142746/1/trussPython.pdf); [SMO article](https://link.springer.com/article/10.1007/s00158-019-02226-6)
- Adaptive member adding (Gilbert & Tyas 2003):
  - Start with short connections only.
  - Solve the LP.
  - Use the dual (virtual displacement) field to find potential members that violate the optimality condition.
  - Add the most violating ones and repeat until there are none.

  This lets problems above 1,000,000,000 potential members be solved. Members with area above about 1e-3 × the maximum are kept for plotting. — [He et al. 2019](https://eprints.whiterose.ac.uk/142746/1/trussPython.pdf); [TU Delft interactive textbook, layout optimisation](https://interactivetextbooks.citg.tudelft.nl/computational-modelling/advanced_topics/layopt/key_concepts.html)
- The script is 98 lines. It uses numpy/scipy, cvxpy and shapely, with MOSEK optional. Runtimes on an Intel i7-7700HQ laptop, Windows 10:

  | Grid | Nodes | Potential members | Solve time | Notes |
  |---|---|---|---|---|
  | 20×10 | 231 | 16,290 | 0.8 s total (cvxpy default solver, with member adding) | |
  | 40×20 | 861 | 225,848 | 6.7 s with adding vs 47.7 s without | |
  | 60×30 | 1,891 | 1,086,938 | 71 s with adding vs 579 s without | Table gives 8.2× speed-up; text says 7.5× |
  | 20×10 | 231 | 16,290 | 0.95 s with MOSEK | 0.71% from the analytical Michell volume |
  | 80×40 | 3,321 | 3,352,500 | 45.5 s with MOSEK | 0.13% |
  | 160×80 | 13,041 | 51.7 M | 2,164 s with MOSEK | 0.053% |

  Source: [He et al. 2019](https://eprints.whiterose.ac.uk/142746/1/trussPython.pdf)

**Michell-type truss vs continuum optima (quantitative)**
- Sigmund, Aage & Andreassen (2016) solved a 1×2 cantilever, normalised compliance C/(f·a). Chan's analytical Michell value is 49.35:

  | Method | f = 0.125 | f = 0.25 | f = 0.5 | f = 0.75 |
  |---|---|---|---|---|
  | Variable-thickness sheet (p = 1) | 42.11 | 44.95 | 51.88 | 61.52 |
  | Rank-2 homogenisation | 50.88 | 52.40 | 56.73 | 63.56 |
  | SIMP p = 4 (0/1) | 54.71 | 54.55 | 58.14 | 64.28 |

  An optimised truss scores **52.04 (8 bars), 50.31 (18 bars) and 49.39 (392 bars)**, independent of f in that idealisation.
  - Every method except p = 1 solves the 0/1 problem.
  - The variable-thickness sheet is up to 20% better than Chan.
  - Square, triangular and hexagonal truss microstructures are optimal only in the small-volume-fraction limit.
  - Removing the frame restriction gave more than 30% better compliance in their 3D and variable-thickness cases.
  - Source: [Sigmund, Aage & Andreassen 2016, On the (non-)optimality of Michell structures (DTU Orbit postprint)](https://backend.orbit.dtu.dk/ws/files/140300672/Michell_plain.pdf)
- Michell's classical result: the least-weight arrangement of truss members or plate stiffeners follows the principal strain trajectories. Pyrrait (1973) reported about 40% weight reduction in one stiffened-plate case by grading thickness and stiffeners to local stress. — [TRID record 4794, "Optimizing the arrangement of truss members or the stiffeners of plated plane panels under inplane loads"](https://trid.trb.org/View/4794); [TRID record 11214, "Toward the optimum configuration of stiffeners and plating in simple beam structures"](https://trid.trb.org/View/11214) (attribution of each claim to one of the two records comes from a search summary and was not checked against the abstracts)

**Principal-stress-line (PSL) methods**
- Kwok et al.'s PSL method grows lattice members along PSLs iteratively. It works for concentrated loads and is harder with distributed loads. — [Wang, Westermann & Wu 2022, arXiv:2207.09172](https://arxiv.org/pdf/2207.09172) (related-work summary as returned by search)
- Stress-driven stiffened-plate layout (Zheng 2019 thesis) needed the input mesh updated iteratively so stiffeners align with mesh edges. — [Zheng PhD thesis, Bournemouth 2019](https://eprints.bournemouth.ac.uk/34112/1/ZHENG%2C%20Anzong_Ph.D._2019.pdf)

**Isogrid**
- The Isogrid Design Handbook (NASA-CR-124075, Meyer, Harwood & Orlando, McDonnell Douglas, February 1973) covers:
  - unflanged and flanged triangular integrally-stiffened structure
  - basic analysis theory and typical design situations
  - weight-optimisation methods where they exist, and worked examples

  A PDF is listed on NTRS. — [NTRS record 19730011184](https://ntrs.nasa.gov/citations/19730011184); [Shellbuckling.com page citing CR-124075](https://shellbuckling.com/presentations/stiffenedCylinders/pages/page_38.html)
- Isogrid behaves like an isotropic material. The equilateral-triangle pattern was used partly because it simplified analysis. Orthogrid is easier to make but not isotropic. Stiffeners are typically CNC-milled from plate. — [Wikipedia: Isogrid](https://en.wikipedia.org/wiki/Isogrid)

### Inferences
- **v2's greedy pruning is ESO-style and inherits its known risks.** It deletes the lowest-energy ribs a few per round, never re-admits, and always uses blank-plate-like energies. Two cheap upgrades:
  - recompute energies after every round (v2 already re-analyses)
  - allow BESO-style re-admission of previously removed ribs that become highly loaded, and average energies over the last two rounds (Huang & Xie's stabilisation)

  *(Proposal based on the cited BESO features.)*
- **Layout-LP on v2's own candidate graph.** He et al.'s LP could run on the CDT nodes plus a richer set of connections: all node pairs within 2–3 spacings, trimmed to the keep-in region with shapely as in the script.
  - At FTC scale (≈100–400 nodes, 10⁴–10⁵ candidate members) it solves in about a second.
  - It returns an optimal in-plane load-path topology for all in-plane cases at once, via shared areas across cases.
  - Member areas would then be mapped to rib presence and width, with w ≥ 8 mm and members below a threshold dropped.
  - Limitations: plastic, in-plane only; it ignores out-of-plane bending and torsion, which v2 also evaluates; and it ignores rib-overlap mass at nodes. So it should seed or score candidates, not replace the FEA check. *(Proposal.)*
- The Michell numbers matter for through-cut plates. For 0/1 (through-cut) designs at f = 0.25, an 18-bar optimised truss (50.31) beat 0/1 SIMP p = 4 (54.55) by about 8%, and sat about 2% above Michell.
  - So a well-laid-out truss is not inherently worse than SIMP for single-load-case through-cut plates.
  - Caveat: the truss result is a line-element idealisation that ignores node overlap at finite volume fractions, which flatters it at f ≥ 0.4.
  - The 20–30% "sheet beats truss" advantage applies only when thickness can vary, i.e. partial-depth pockets with floors. That is an argument for offering floored pockets in highly loaded zones.

### Gaps
- Exact isogrid design formulas (equivalent stiffness parameters α = bd/(th), node and cutout design rules) could not be read: the NTRS tech-brief PDF is a scanned image, and the full handbook was not parsed.
- I could not verify a source for the stiffness of a triangular through-cut (unskinned) lattice. The standard result for stretch-dominated triangular lattices, E*/E ≈ ρ̄/3 (Gibson–Ashby; Wang & McDowell 2004), is background knowledge only.
- Huang & Xie's exact BESO parameters (evolution rate ER, maximum admission ratio AR_max) were not retrieved from the primary paper.

---

## 5. From a density field to manufacturable 2D CAD

### Takeaway
The standard pipeline is:
1. threshold (volume-preserving)
2. extract iso-contours (marching squares)
3. simplify and smooth (Douglas–Peucker, B-spline)
4. rebuild B-rep geometry
5. optionally shape-optimise the spline control points to recover performance

The literature notes that no commercial tool yet produces parametric, feature-based CAD automatically. For 2D through-cuts the problem is much easier than in 3D: shapely buffering does the morphological opening and closing, and protected geometry is restored exactly by Boolean union with the keep-out bands.

### Cited Findings
- Survey of post-processing (Subedi, Verma & Suresh 2020, JCISE):
  - raw TO output is dense, poor-quality faceted geometry with no feature or parametric control
  - commercial tools mostly rebuild surfaces: NURBS in Rhino/Evolve, subdivision in Creo, T-splines in Fusion 360 Generative Design
  - none efficiently produce a parametric feature-based CAD model

  Source: [Subedi, Verma & Suresh 2020 (PDF)](https://ersl.wisc.edu/publications/2020/JCISE-TOSurvey.pdf); [ERSL page](https://ersl.me.wisc.edu/?p=324)
- Published reconstruction pipelines:
  - Amroune, Cuillière & François 2022: skeletonisation, then cubic B-spline cross-sections, then lofting, then FEA validation (3D beam-like results) ([UQTR record](https://depot-e.uqtr.ca/id/eprint/10116/))
  - NWPU: density-field isolines, B-spline fit, then shape optimisation of control points to recover lost performance, with compliance deviations of 0.5%–2.6% ([NWPU publication](https://pure.nwpu.edu.cn/en/publications/explicit-reconstruction-and-shape-optimization-of-topology-optimi/))
- scikit-image tools for this pipeline:

  | Function | Algorithm | Notes |
  |---|---|---|
  | `skimage.measure.find_contours` | Marching squares, with linear sub-pixel interpolation | Contours touching the array edge or a masked region stay open; others are closed. `fully_connected` resolves the ambiguous saddle case. Values are sampled at cell centres. |
  | `approximate_polygon` | Douglas–Peucker, with a tolerance | |
  | `subdivide_polygon` | B-spline subdivision, degree 1–7 | Keeps closed polygons closed |

  Source: [scikit-image measure API](https://scikit-image.org/docs/stable/api/skimage.measure.html)
- Morphological open/close is the standard tool for minimum feature size on density fields (Sigmund 2007), though one operator in the optimisation loop controls only one phase (Schevenels & Sigmund 2016). — [Sigmund 2007](https://orbit.dtu.dk/en/publications/morphology-based-black-and-white-filters-for-topology-optimizatio/); [Schevenels & Sigmund 2016](https://orbit.dtu.dk/en/publications/on-the-implementation-and-effectiveness-of-morphological-close-op/)
- Threshold choice: with a volume-preserving Heaviside, η* ≈ 0.4–0.52, so the 0.5 iso-contour of the projected field roughly preserves volume. — [Ferrari & Sigmund 2020](https://arxiv.org/html/2005.05436v2)

### Inferences
Proposed 2D pipeline for AutoPocket (uses only shapely, scikit-image and numpy):
1. Take the projected field x̂ on the analysis grid. Upsample it bicubically 2–4× before contouring to reduce staircase artefacts.
2. Run `find_contours(x̂, 0.5)` with a mask covering the plate profile. Build polygons with shapely from the **void** contours (pocket candidates) in plate coordinates.
3. Intersect pockets with the "pocketable region": the plate minus the edge offset band minus hole keep-out bands, which v2 already computes. This **restores protected geometry exactly**, because holes and edges come from CAD, not from the density field.
4. Enforce **minimum rib width w** by opening the solid region. Equivalently, apply to each pocket P: P' = P.buffer(+w/2).buffer(−w/2) (closing of voids merges pockets separated by ribs thinner than w), or drop or merge the offending pockets.
5. Enforce **minimum pocket corner radius r_t** (tool radius) by opening the voids: P'' = P'.buffer(−r_t).buffer(+r_t). This also removes slivers narrower than 2·r_t.
6. Simplify with Douglas–Peucker (tolerance ≈ 0.25·h). Optionally fit periodic cubic B-splines (`scipy.interpolate.splprep(per=1)`) or keep shapely's arc-approximated buffers, which are already G1 at convex corners.
7. Run v2's `validate.py` rules and FEA re-check. Add the result as one more candidate family in v2's archive.

Notes on this pipeline:
- Steps 4–5 are exact Minkowski operations for polygons. They guarantee the CNC constraints that a density filter only encourages.
- SIMP-derived pockets are usually not triangles. They come out as organic slots, so they may conflict with the user's stated aesthetic and shape rules (no acute wedge tips, symmetric pockets). Mirror-symmetrise the density field before contouring, as v2 already does for its energy field, and reject acute tips in `validate.py`.

### Gaps
- No published pipeline aimed specifically at 2D CNC through-cut plates from SIMP was found. The cited pipelines are 3D or general. The shapely-buffer approach is standard computational geometry, not taken from a TO paper.
- No source quantified the compliance lost by marching-squares thresholding plus opening on coarse (5–15k element) grids. The NWPU 0.5–2.6% figure is after shape re-optimisation.

---

## 6. Using a SIMP density or principal-stress field to guide a truss/rib layout (hybrids, de-homogenisation, stress-aligned ribs)

### Takeaway
Published hybrid methods fall into three groups:
1. **De-homogenisation**: optimise orientations and densities on a coarse grid, then project to a fine rib pattern (Pantz–Trabelsi; Groen & Sigmund 2018; streamline-based versions).
2. **PSL-guided rib layouts**: ribs along principal stress lines from an FEA of the solid domain, then pruning and sizing.
3. **PSL- or truss-initialised density TO.**

The streamline de-homogenisation work reports regular, grid-like ribs within about 5% of the homogenised optimum, often stiffer than plain density TO at the same mesh, in under a minute of post-processing. That is the published analogue of what AutoPocket is attempting.

### Cited Findings
**De-homogenisation**
- Homogenisation-based TO on a coarse grid produces per-element laminate orientations and densities. De-homogenisation maps these to a fine solid/void design.
  - Pantz & Trabelsi (2008) introduced it; Groen & Sigmund (2018) revised it and Allaire et al. extended it.
  - Groen & Sigmund solve a global least-squares problem for a conformal mapping field. This becomes expensive as the problem grows, can be unstable near orientation singularities, and can give disconnections in thin members.
  - Woldseth, Bærentzen & Sigmund (2023) proposed phasor noise instead, reaching "within a few percentages" of the homogenised optimum.
  - Sources: [Woldseth, Bærentzen & Sigmund 2023, arXiv:2310.04881](https://arxiv.org/pdf/2310.04881); [Groen et al. 3D de-homogenisation, arXiv:1910.13002](https://arxiv.org/abs/1910.13002)
- Streamline-guided de-homogenisation (Wang, Westermann & Wu; ASME IDETC-CIE 2022; J. Mech. Des. 2023):
  - Evenly spaced streamlines are traced in the two orthogonal orientation fields.
  - These are turned into a graph, then a quad-dominant mesh whose edges follow the directions, with edge widths set from cell density and anisotropy.
  - Singularities are degenerate points of the stress field, treated topologically (e.g. trisectors give a triangle/quad mix).
  - Parametrisation plus de-homogenisation took under a minute, about 40 s, against more than 2 minutes for Groen & Sigmund's step on the same example.
  - Results:
    - de-homogenised compliance ≈ 1.5 c₀ vs 1.447 c₀ homogenised
    - about 5% above homogenised for the L-shape and double-clamped beams
    - less than 10% deviation for distributed loads
    - lower compliance than density TO with a global volume constraint at the same element count
  - Their earlier "stress trajectory-guided" design (material along PSLs of the *solid* domain, thickness from accumulated strain energy) was "considerably" less stiff than de-homogenisation.
  - Evenly spaced, space-filling structures are expected to hold up better under changed loads or damage.
  - Seeding does not enforce symmetry unless adapted.
  - Sources: [Wang, Westermann & Wu, arXiv:2207.09172](https://arxiv.org/pdf/2207.09172); [TUM project page: Stress trajectory guided structural design and TO](https://cs.cit.tum.de/cg/research/publications/2022/stress-trajectory-guided-structural-design-and-topology-optimization)
- Using a PSL-based layout as the initial density field noticeably eases convergence problems in density TO, at comparable stiffness. — [TUM project page](https://cs.cit.tum.de/cg/research/publications/2022/stress-trajectory-guided-structural-design-and-topology-optimization)

**Stress-aligned ribs**
- Li et al. (2016) build ribs from a principal-stress-aligned quad mesh, then prune and size them. — [Li et al., CGF](https://diglib.eg.org/handle/10.1111/cgf13268)
- Vergara & Zegard (2024): PSL reconstruction plus gradient sizing beat structured and orthogonal layouts. Choosing directions is non-trivial, since there are several principal directions per node. — [Vergara & Zegard 2024](https://researching.investigacion.ing.uc.cl/publication/3069)

### Inferences
- **v2 is a scalar-field version of stress-trajectory design.** Its strain energy sets triangle *size* but not *orientation*. The literature suggests two upgrades, cheapest first:
  - **(a) Orientation.** Align the CDT with the principal-stress directions of the governing in-plane case. Use an anisotropic metric (Riemannian Delaunay), or seed points along a few PSLs traced from holes and load points, so that one edge family follows σ₁. Triangles then put ribs along load paths, as Michell's result says they should.
  - **(b) Density source.** Replace the blank-plate energy with a coarse SIMP density field (section 1), or with homogenisation orientations if anyone ever implements rank-2 laminates. Set local spacing from local density and drop candidate ribs crossing regions with x̂ < 0.2.

  The streamline results (de-homogenised ≈ within 5–10% of the homogenised optimum, and stiffer than plain SIMP at equal mesh) suggest this kind of hybrid can match or beat raw SIMP, while keeping v2's manufacturable truss and isogrid vocabulary. *(Proposal; not benchmarked on FTC plates.)*
- Full homogenisation-based TO plus de-homogenisation is over-engineered for 100–400 mm FTC plates with 8 mm ribs. At that scale there are only about 10–40 ribs across the plate, so "fine-scale microstructure" barely applies.

### Gaps
- The original Groen & Sigmund 2018 paper (IJNME) was not fetched, so its coarse-vs-fine mesh sizes and cost figures are not reported here.
- No published method was found that turns a SIMP density field directly into a *triangulated* rib network for flat CNC plates. That remains a proposal.

---

## 7. Honest assessment: is full SIMP worth it for small FTC plates with uncertain loads, versus load-path truss + ESO? Plus the comparison table

### Takeaway
For FTC plates, full SIMP as the *final geometry generator* is probably not worth it:
- loads are uncertain and enveloped over generic cantilever cases
- outputs must be CNC-friendly, symmetric and wedge-free
- the published stiffness advantage of 0/1 SIMP over a good truss layout is small or negative for through-cut designs (Michell numbers above)

SIMP is worth adding as a cheap *guidance field and candidate generator* inside v2's existing archive-and-verify loop. The biggest expected gains are:
- converged load-path guidance instead of blank-plate energy
- rib sizing and BESO-style re-admission instead of one-way greedy deletion
- stress-aligned triangle orientation

### Cited Findings
- For 0/1 designs (the through-cut analogue), optimised truss layouts approached Michell (50.31 with 18 bars vs 49.35), and 0/1 SIMP p = 4 reached 54.55–58.14 for f = 0.25–0.5. Variable-thickness sheets (partial-depth pockets) did up to 20% better than Michell. — [Sigmund, Aage & Andreassen 2016](https://backend.orbit.dtu.dk/ws/files/140300672/Michell_plain.pdf)
- Weighted-sum multi-load SIMP can be very sensitive to the chosen weights. — [Zhang, de Sturler & Paulino 2017](https://personal.math.vt.edu/sturler/Publications/CMAME_Zhang-deSturler-Paulino_2017_final.pdf); [AME 2020](https://doaj.org/article/a7f815648ad84c78a41c63fa1b4320ae)
- Regular, evenly spaced rib structures are expected to be more robust to load changes and damage than free-form density-TO designs, at similar compliance. — [Wang, Westermann & Wu 2022](https://arxiv.org/pdf/2207.09172)
- Untuned SIMP and ESO did worse than an intuitive design until the initial domain and mesh were tuned. — [Edwards, Kim & Budd](https://researchportal.bath.ac.uk/en/publications/an-evaluative-study-on-eso-and-simp-for-optimising-a-cantilever-t/)
- ESO's one-way removal can be badly non-optimal when removal changes the load path (about 10× compliance in Zhou & Rozvany's example). BESO's re-admission mitigates this. — [arXiv:2104.04571](https://arxiv.org/pdf/2104.04571); [ESO revisited](https://research.usq.edu.au/item/q2w53/the-eso-method-revisited)
- Ground-structure LP for ~231–861 nodes solves in about 1–7 s in Python (cvxpy), or about 1–4 s with MOSEK. — [He et al. 2019](https://eprints.whiterose.ac.uk/142746/1/trussPython.pdf)
- 2D SIMP at 30k elements costs about 0.23–0.62 s per iteration in MATLAB. — [Ferrari & Sigmund 2020](https://arxiv.org/html/2005.05436v2)
- v2's FEA costs 1.07 s, 4.38 s and 9.83 s per 6-case pass at 6k, 16k and 30k cells. — local measurement this session ([autopocket2/fea2.py](C:\Users\abdul\Documents\autopoket\autopocket2\fea2.py))

### Inferences
**Implementation-level comparison** (my synthesis of the cited material; runtimes are for FTC-scale 2D problems):

| Method | Formulation / inputs → outputs | Runtime at FTC scale | Complexity to add to v2 | Python code (licence) | Manufacturability of raw output | Handles uncertain / multiple loads |
|---|---|---|---|---|---|---|
| **Rule-based keep-outs + regular isogrid** (have) | Geometry rules → triangle pockets | ms | Done | own | Excellent (designed for CNC) | Robust: quasi-isotropic, load-agnostic |
| **CDT truss with energy-steered spacing** (have) | Blank-plate SED → local spacing → CDT edges = ribs | 1 FEA (~1–5 s) + meshing | Done | own | Excellent | Moderate (envelope of 6 cases) |
| **Greedy ESO rib pruning** (have) | Rib energy → delete lowest, re-analyse | ~1–5 s per round | Done | own | Excellent (merged pockets validated) | Moderate. Risk: one-way, path-changing removal |
| **BESO on ribs** (upgrade) | Rib energy with history averaging → delete *and re-add* | same | Small | own; Zuo & Xie Python BESO (unverified licence) | Excellent | Better (recovers from bad deletions) |
| **Rib-width sizing (OC / fully stressed)** | Fixed rib graph, widths w_i ≥ w_min → resized widths | 5–10 FEA (~10–50 s) | Small–medium | own | Excellent (variable-width ribs and fillets) | Good with min-max envelope |
| **Ground-structure plastic LP** | Nodes + candidate members + in-plane loads → member areas | ~0.1–7 s (cvxpy/HiGHS/MOSEK) | Medium | He et al. 98-line script (licence not stated) | Needs mapping areas → ribs; in-plane only | Native multi-load (shared areas) |
| **SIMP (density filter + Heaviside, OC)** | Grid, passive sets, loads, volume fraction → density field | 50–150 iterations × (0.2–4 s) ≈ 0.5–10 min | Medium (~100 lines on v2's grid) | DTU topopt.py (no licence stated), topoptlab (GPL-3), mmapy (GPL) | Poor until post-processed (organic slots, grey edges) | Weighted sum (weight-sensitive) or min-max with MMA |
| **SIMP + robust min length** | Plus eroded/dilated projections | ~3× SIMP | Medium–high | same | Better (guaranteed min member) | same |
| **Stress-constrained TO** | Plus relaxed and aggregated stress constraints | Up to ~10× compliance TO, fragile | High | none turnkey | Poor until post-processed | Hard |
| **Level-set shape opt.** | Boundary velocity from shape derivative | 10²+ FEA | High | Challis-style codes | Smooth boundaries | Depends on start; local |
| **Mattheck CAO/MTT corners** | Stress at corners → grown radii / tensile-triangle blends | 1–3 FEA | Small | own | Excellent | Local fix, load-agnostic shape |
| **PSL / de-homogenisation hybrid** | FEA stress tensor (or homogenisation orientations) → aligned rib mesh | ~1 FEA + <1 min geometry | Medium–high | none turnkey | Good (grid-like ribs) | Single governing case; symmetry needs care |

**Why full SIMP is not the right end-to-end engine for FTC plates:**
1. The governing loads are unknown: bearing loads, impacts, and how the plate is bolted into a channel. SIMP is an exact optimiser of an inexact problem, and it will tailor material to v2's assumed cantilever clamps. Truss and isogrid layouts are less tailored and therefore more forgiving, as the robustness remark in [Wang, Westermann & Wu 2022](https://arxiv.org/pdf/2207.09172) also suggests.
2. For through-cuts (0/1), published data show no inherent stiffness advantage of SIMP over a well-laid-out truss.
3. SIMP output needs a full post-processing chain (section 5) to become CNC- and rule-compliant, and its organic slots conflict with the project's symmetric, no-acute-wedge pocket conventions.
4. Runtime on v2's 3D-hex, 6-case model is minutes, not seconds, unless the grid is coarsened or reduced to 2D in-plane.

**Where SIMP or optimisation clearly helps:**
1. As a **guidance field**: converged, multi-case, with passive keep-outs. It replaces iteration-0 blank-plate energy.
2. As **one more candidate family** in v2's archive (SIMP→contour→opening→validate). Let the FEA-checked selection decide.
3. As a **sanity benchmark**: in bench/compare.py, compare each truss candidate's stiffness against a SIMP design at the same mass. If the truss is within ~5–10%, the layout is near-optimal for the assumed loads.

### Gaps
- No published FTC-specific or small-robot-plate comparison of SIMP vs truss lightening exists that I could find.
- No published quantitative comparison of ESO-on-ribs vs SIMP for perforated plates was found.
- The robustness advantage of regular rib patterns under load uncertainty is asserted in the cited work, but not quantified there.

---

## 8. What would most improve AutoPocket v2 (ranked, practical hybrid)

### Takeaway
Recommended hybrid, in order of value per effort. All of it stays inside v2's existing generate → validate → FEA → rank loop.
1. Re-energise and make pruning bi-directional (BESO-style).
2. Add rib-width sizing.
3. Replace blank-plate energy with a short multi-case SIMP run (passive keep-outs, min-max over the 6 cases) as the guidance field.
4. Orient the triangulation with principal-stress directions.
5. Add stress-driven corner radii (Mattheck-style).
6. Optionally add a SIMP-contour candidate family and an in-plane layout-LP candidate family.

### Cited Findings
- BESO's re-admission and history averaging address ESO's path-change failure. — [arXiv:2104.04571](https://arxiv.org/pdf/2104.04571); [arXiv:2210.10782](https://arxiv.org/pdf/2210.10782)
- Pruning followed by cross-section sizing of a stress-aligned rib network is an established pipeline. — [Li et al. 2016](https://diglib.eg.org/handle/10.1111/cgf13268); [Vergara & Zegard 2024](https://researching.investigacion.ing.uc.cl/publication/3069)
- Passive solid/void sets and volume-preserving projection are standard in top99neo, and are directly suited to bore keep-outs and edge bands. — [Ferrari & Sigmund 2020](https://arxiv.org/html/2005.05436v2)
- Michell: optimal stiffeners follow principal strain trajectories. — [TRID 4794](https://trid.trb.org/View/4794); [Sigmund et al. 2016](https://backend.orbit.dtu.dk/ws/files/140300672/Michell_plain.pdf)
- Mattheck's CAO and Method of Tensile Triangles reduce notch stresses by local shape growth, validated by FE and fatigue tests. — [Mattheck et al. 2007](https://www.iieta.org/journals/ijdne/paper/10.2495/D%26N-V2-N4-301-309)
- An in-plane plastic layout LP with holes and multiple load cases is about 98 lines of Python with cvxpy and shapely. — [He et al. 2019](https://eprints.whiterose.ac.uk/142746/1/trussPython.pdf)

### Inferences
All items below are my proposals, ranked by expected benefit per effort:

1. **BESO-ise `layout.prune_ribs` (small effort, high value).**
   - Recompute rib energies from the *current* design every round; v2 already re-analyses.
   - Average with the previous round's energies.
   - Keep a list of removed ribs and re-add any whose "virtual" energy is high. A removed rib's virtual energy is the strain energy of the merged pocket's interior along the removed rib's path, read from the soft-kill raster: v2's raster already gives near-void cells a small fill.
   - Allow 1-for-1 swaps when the stiffness target is binding.
2. **Rib-width sizing after topology (small–medium effort, high value).**
   - Per rib, w_i ← clip(w_i·(Ū_i/Ū_target)^0.5, 8 mm, w_max), with Ū_i the rib's mean strain-energy density across the governing cases.
   - Re-offset pockets with per-rib half-widths; shapely can do this by buffering the rib skeleton per edge.
   - Validate, then re-run FEA, 3–6 iterations.
   - This turns rigid 8 mm ribs into graded ribs and typically recovers stiffness at the same mass, or saves mass at the same stiffness. Published grading of stiffeners to local stress reported about 40% weight savings in one plate case ([TRID 4794](https://trid.trb.org/View/4794) / [TRID 11214](https://trid.trb.org/View/11214)), though that included thickness grading.
3. **Short SIMP guidance run (medium effort, high value for odd-shaped plates).**
   - Reuse `fea.Model` with ρ as the design variable: p = 3, density filter r_min ≈ 3 cells, OC, 30–60 iterations.
   - Passive solid = hole keep-out bands plus edge band. Passive void = outside the profile.
   - Objective: soft-max or bound of c_k/c_k,blank over the 6 cases.
   - Mirror-symmetrise the field each iteration for symmetric plates.
   - Use x̂ as the input to `SpacingField`, and as a rib-keep score: mean x̂ along each candidate edge.
   - Cost is about 1–3 min at 6k cells. A 2D plane-stress-only in-plane variant would be several times faster.
4. **Stress-direction-aligned triangulation (medium effort, medium–high value).**
   - Compute the principal-stress direction field from the governing in-plane case.
   - Seed CDT points along a few principal stress lines from each loaded hole, or warp the triangulation metric, so one edge family follows σ₁.
   - Keep isogrid as the load-agnostic fallback.
5. **Stress-driven corner radii (small effort, medium value for fatigue and peak stress).**
   - At pocket corners whose local von Mises exceeds the 95th percentile, increase the corner radius above the 2 mm tool radius, or apply a 2–3-step tensile-triangle blend, within the 8 mm rib and offset rules.
   - v2 already tracks the p99 peak-stress ratio, so this directly targets its secondary ranking metric.
6. **Optional new candidate families (medium effort, value depends on plate).**
   - **(a) SIMP-contour pockets**: the section 5 pipeline with shapely opening by rib/2 and tool radius, then `validate.py`.
   - **(b) Layout-LP truss**: He et al.'s LP on CDT nodes plus 2-ring candidate members, in-plane cases only. Member areas map to rib presence and width.

   Both go into the archive. Let the existing FEA-checked, rule-validated ranking choose, so no rule is ever relaxed.

**Not recommended for an FTC tool:**
- stress-constrained TO
- full level-set optimisation
- homogenisation + de-homogenisation
- robust-formulation SIMP as the final geometry generator (min-width is better guaranteed geometrically)

**Benchmarking:** add the SIMP same-mass reference to `bench/compare.py`, so each truss and isogrid design reports "% of SIMP stiffness at equal mass". This turns the honest-assessment question above into a measured answer on the project's own sample plates (`samples/*.step`).

### Gaps
- None of these proposals has been benchmarked on the project's sample plates. Expected gains are qualitative, from the cited literature.
- Out-of-plane bending and torsion, which v2 evaluates, are not handled by the plastic layout LP. How much SIMP guidance helps for out-of-plane-dominated FTC plates is untested.
