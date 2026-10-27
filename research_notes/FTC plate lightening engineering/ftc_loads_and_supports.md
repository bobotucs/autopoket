# FTC Plate Load Cases, Boundary Conditions, and Student-Input Load Estimation

Scope: FIRST Tech Challenge (FTC) robot plates only, for the "engineering mode" of an automated plate-lightening tool. Current season checked: 2026-2027 BIOBUZZ (Competition Manual version TU06, downloaded 2026-10-22). Convention below: anything not backed by a URL is labelled **[ASSUMED]**, **[DERIVED]** (my arithmetic from cited inputs), or **[TEXTBOOK]** (standard statics/mechanics I did not re-verify online this session).

Unit note used in all conversions: 1 kg·cm = 0.0980665 N·m; g = 9.81 m/s².

---

## 1. Common FTC motors, gear ratios, and robot size/mass rules

### Takeaway
FTC gearmotors all deliver roughly 15-20 W peak, so the stall torque at the output shaft scales almost linearly with gear ratio: goBILDA 5203 motors run from about 0.53 N·m (1620 RPM) to 24.5 N·m (30 RPM), REV HD Hex from 0.55 to 5.75 N·m on common UltraPlanetary builds, and REV Core Hex gives 3.2 N·m at 125 RPM. The 2026-2027 manual has **no robot weight limit**: an 18 in starting cube, a fully expanded volume of 18 x 24 x 29 in, and at most 8 motors and 8 servos. Robot mass therefore has to come from the student, not the rules.

### Cited Findings

**goBILDA 5203 Series Yellow Jacket (12 V; 9.2 A stall and 0.25 A no-load current listed for every ratio)**

| Ratio | Free speed (RPM) | Stall torque (vendor) | Stall torque (N·m, [DERIVED] conversion) | Source |
|---|---|---|---|---|
| 3.7:1 | 1620 | 5.4 kg·cm (75.8 oz-in) | 0.53 | [Core Electronics listing](https://core-electronics.com.au/5203-series-yellow-jacket-planetary-gear-motor-371-ratio-24mm-length-8mm-rex-shaft-1620-rpm-33-5v-encoder.html.plain.md) |
| 5.2:1 | 1150 | 7.9 kg·cm (109 oz-in) | 0.77 | [RobotShop listing](https://www.robotshop.com/products/5203-series-yellow-jacket-planetary-gear-motor-521-1150-rpm-33-5v-encoder) |
| 13.7:1 | 435 | 18.7 kg·cm (260 oz-in) | 1.83 | [goBILDA product page](https://www.gobilda.com/5203-series-yellow-jacket-planetary-gear-motor-13-7-1-ratio-24mm-length-8mm-rex-shaft-435-rpm-3-3-5v-encoder/) |
| 19.2:1 | 312 | 24.3 kg·cm (338 oz-in) | 2.38 | [goBILDA product page](https://www.gobilda.com/5203-series-yellow-jacket-planetary-gear-motor-19-2-1-ratio-24mm-length-8mm-rex-shaft-312-rpm-3-3-5v-encoder/) |
| 26.9:1 | 223 | 38.0 kg·cm (530 oz-in) | 3.73 | [Core Electronics listing](https://core-electronics.com.au/5203-series-yellow-jacket-planetary-gear-motor-2691-ratio-24mm-length-8mm-rex-shaft-223-rpm-33-5v-encoder.html.plain.md) |
| 50.9:1 | 117 | 68.4 kg·cm (950 oz-in) | 6.71 | [Core Electronics listing](https://core-electronics.com.au/5203-series-yellow-jacket-planetary-gear-motor-5091-ratio-24mm-length-8mm-rex-shaft-117-rpm-33-5v-encoder.html.plain.md) |
| 71.2:1 | 84 | 93.6 kg·cm (1310 oz-in) | 9.18 | [Core Electronics listing](https://core-electronics.com.au/5203-series-yellow-jacket-planetary-gear-motor-7121-ratio-24mm-length-8mm-rex-shaft-84-rpm-33-5v-encoder.html.plain.md) |
| 99.5:1 | 60 | 133.2 kg·cm (1850 oz-in) | 13.06 | [Core Electronics listing](https://core-electronics.com.au/5203-series-yellow-jacket-planetary-gear-motor-9951-ratio-24mm-length-8mm-rex-shaft-60-rpm-33-5v-encoder.html.plain.md) |
| 139:1 | 43 | 185 kg·cm (2570 oz-in) | 18.14 | [RobotShop EU listing](https://eu.robotshop.com/products/5203-series-yellow-jacket-planetary-gear-motor-1391-43-rpm-33-5v-encoder) |
| 188:1 | 30 | 250 kg·cm (3470 oz-in) | 24.52 | [RobotShop listing](https://www.robotshop.com/products/5203-series-yellow-jacket-planetary-gear-motor-1881-30-rpm-33-5v-encoder) |

- Every 5203 ratio above has an 8 mm REX output shaft, 24 mm long. The 312 RPM motor weighs 437 g and has a 537.7 PPR encoder at the output. The 435 RPM motor weighs 438 g with 384.5 PPR. — [goBILDA 312 RPM](https://www.gobilda.com/5203-series-yellow-jacket-planetary-gear-motor-19-2-1-ratio-24mm-length-8mm-rex-shaft-312-rpm-3-3-5v-encoder/), [goBILDA 435 RPM](https://www.gobilda.com/5203-series-yellow-jacket-planetary-gear-motor-13-7-1-ratio-24mm-length-8mm-rex-shaft-435-rpm-3-3-5v-encoder/)
- Neither goBILDA page lists a maximum radial or axial load for the output shaft, or the face-mount thread pattern. — same pages

**REV Robotics HD Hex Motor (REV-41-1291), 12 V**
- Bare motor: 6000 rpm free speed, 0.105 N·m stall torque, 8.5 A stall current, 0.4 A free current, 15 W maximum output power, 234 g, 37 mm body diameter, 28 counts/rev encoder at the motor. — [REV docs: HD Hex Motor](https://docs.revrobotics.com/duo-build/actuators/motors/hd-hex-motor)
- 20:1 planetary or 20:1 spur: 300 rpm, 2.1 N·m stall. 40:1 spur: 150 rpm, 4.2 N·m stall. Output is a 5 mm hex shaft 40 mm long. The planetary has mounting holes on a 14 mm bolt circle. The spur gearboxes have 10x M3 tapped holes. — [REV docs: HD Hex Motor](https://docs.revrobotics.com/duo-build/actuators/motors/hd-hex-motor)
- UltraPlanetary nominal (actual) ratios: 5:1 (5.23:1) gives 1147 rpm and 0.55 N·m. 20:1 (18.9:1) gives 317 rpm and 1.98 N·m. 60:1 (54.8:1) gives 109.5 rpm and 5.75 N·m. Ratios multiply when you stack up to three cartridges. — [REV docs: HD Hex Motor](https://docs.revrobotics.com/duo-build/actuators/motors/hd-hex-motor)

**REV Core Hex Motor (REV-41-1300)**
- 125 RPM free speed, 3.2 N·m stall torque, 4.4 A stall current, 72:1 internal ratio, 5 mm female hex output (a hex shaft can pass through), about 7 oz, 288 counts/rev at the output. REV recommends supporting it with two or more plastic brackets. — [REV docs: Core Hex Motor](https://docs.revrobotics.com/duo-build/actuators/motors/core-hex-motor)

**Rules (2026-2027 FTC Competition Manual, BIOBUZZ, version TU06)** — [FIRST: 2026-2027 Competition Manual (PDF)](https://ftc-resources.firstinspires.org/ftc/game/manual)
- R102: the starting configuration must fit within 18 in x 18 in x 18 in (45.70 cm per side).
- R104: "There is no ROBOT weight limit." The manual still asks teams to consider field tile damage, battery consumption, transport, and performance.
- R105: after the match starts, the robot must stay within an 18 in x 24 in x 29 in (45.70 x 61.0 x 73.65 cm) volume, with 29 in vertical. It must be constrained physically, not by software, and must not deliberately detach components.
- R501 legal motors include: goBILDA Yellow Jacket 520x (5201, 5202, 5203, 5204 series), goBILDA 5000 Series, REV HD Hex (REV-41-1291), REV Core Hex (REV-41-1300), AndyMark NeveRest, Studica Maverick, TETRIX MAX TorqueNADO, NFR Yuksel, SWYFT Spike, and WATTOS Stingray. A gearmotor may be used with or without its gearbox, or with any other compatible gearbox.
- R503: at most 8 motors and 8 servos across all mechanisms and configurations.
- R601: exactly one approved 12 V NiMH main battery.
- Older third-party pages quote a 42 lb weight limit, but they describe the 2018-2019 era and are superseded by R104. — [Game Manual 0 (archived readthedocs)](https://game-manual-0.readthedocs.io/en/stable/docs/getting-started-in-ftc/index.html); superseded by [current manual R104](https://ftc-resources.firstinspires.org/ftc/game/manual)

**Reference drivetrain mass and gearing**
- goBILDA Strafer Chassis Kit V5: 4140 g (9.13 lb) assembled. It uses four 312 RPM 5203 motors (19.2:1) driving 96 mm mecanum wheels directly (207 g each), with goBILDA's stated theoretical speed of "over 5.14 ft/sec". The frame is 1120 Series U-channel. Wheel hub-shafts ride on 1611 Series flanged ball bearings (6 mm and 8 mm ID, 14 mm OD, 5 mm thick). V5 is discontinued; V6 also uses 96 mm wheels. — [goBILDA Strafer Chassis Kit V5](https://www.gobilda.com/strafer-chassis-kit-v5/)

### Inferences
- **[DERIVED] Torque can be scaled from the bare motor with a small loss.** Dividing each 5203 stall torque by its ratio gives 0.124-0.149 N·m at the motor for all ten ratios. For REV, 0.105 N·m x 20 = 2.1 N·m exactly, so REV's geared figures look like ideal ratio x bare torque with no gearbox loss. A tool can estimate a missing ratio as about 0.13 N·m x ratio (5203) or 0.105 N·m x ratio (HD Hex). Label that "calculated (scaled from vendor data)", not vendor data.
- **[DERIVED] Peak mechanical power is about T_stall x ω_free / 4** (linear DC motor). 5203 312 RPM: 2.383 x 32.67 / 4 = 19.5 W. 5203 117 RPM: 20.5 W. HD Hex bare: 16.5 W (REV lists 15 W). Core Hex: 10.5 W. Any 5203 is therefore about a 20 W source no matter its ratio.
- **[DERIVED] Free-speed check:** v = (RPM x 2π / 60) x r_wheel. For 312 RPM on a 96 mm wheel this gives 1.568 m/s = 5.14 ft/s, matching goBILDA's figure. That confirms the direct-drive assumption for Strafer.
- **Typical ratios by use [ASSUMED from FTC practice, not verified this session]:** drivetrain 312-435 RPM direct to 96-104 mm wheels; intakes and rollers 1150-1620 RPM; slides and lifts 223-435 RPM on spools; arms 60-117 RPM, often with another external reduction.
- **Robot mass default:** no rule bounds it (R104). The only sourced number is the 4.14 kg Strafer chassis. A tool should ask the student to weigh the robot (provenance "measured"). If they can't, use a placeholder **[ASSUMED] 15 kg (range 10-20 kg)** and flag every derived load as depending on it.

### Gaps
- I found no official stall torque for the bare 6000 RPM 5203 (1:1), and no published radial/axial load rating for goBILDA or REV output shafts.
- I couldn't verify the current goBILDA 5203 face-mount screw pattern (thread size, bolt circle) from goBILDA's pages.
- I found no source for typical whole-robot FTC mass. Forum results were about VEX or FRC.
- I didn't find whether the REV Control/Expansion Hub applies a motor current limit below stall. That would cap the real torque below the vendor stall values.

---

## 2. Load equations: torque through gear trains, gear tooth forces, belt/chain pull, shaft and bearing reactions, cantilever arms, impact factors, load combinations

### Takeaway
Every FTC plate load can be built from a few relations. Torque times ratio goes through the gear train. Gear tooth force is F_t = T/r with F_r = F_t·tan 20°. Belts carry effective tension T_e = T1 − T2 = T/r, and the shaft load is the vector sum of the two belt tensions (T1 + T2 at 180° wrap). Shaft reactions come from two-bearing statics, which amplify overhung loads by (L + a)/L. Impact factors are 2 for a suddenly applied load and 1 + √(1 + 2h/δ_st) for a drop. The impact numbers and friction coefficients carry the most uncertainty and must be labelled as such.

### Cited Findings
- **Gear tooth forces:** compute the tangential force from torque as W_t = T/(D/2), where D is the pitch diameter. The radial force is W_r = W_t·tan φ, with φ typically 14.5°, 20°, or 25°. Spur gears have no axial force. — [Engineers Edge: force analysis of spur gears](https://ns1.engineersedge.com/gears/force_analysis_spur_gears_13977.htm); [Khalil lecture, gear force analysis (Tikrit Univ.)](https://ceng.tu.edu.iq/images/Lectures/mech/Lec03-Gears-Force%20Analysis%20-%20dr%20hazim%20khalil%203.pdf); [KHK Gears: gear forces](https://khkgears.net/new/gear_knowledge/gear_technical_reference/gear_forces.html) (spur gears: "no axial force acts on teeth")
- **Idler gears** transmit no torque to their shaft but still carry the tangential and radial reactions of both meshes. The shaft reaction is the vector sum and depends on where the idler sits. — [Khalil lecture](https://ceng.tu.edu.iq/images/Lectures/mech/Lec03-Gears-Force%20Analysis%20-%20dr%20hazim%20khalil%203.pdf); [Engineers Edge](https://ns1.engineersedge.com/gears/force_analysis_spur_gears_13977.htm)
- **Bearing reactions** come from static equilibrium (sum of forces and moments in each plane), with the gear-force directions set correctly first. — [Khalil lecture](https://ceng.tu.edu.iq/images/Lectures/mech/Lec03-Gears-Force%20Analysis%20-%20dr%20hazim%20khalil%203.pdf)
- **Belt effective tension:** Te = T1 − T2 (Gates Eq. 11), with torque = Te x d/2 at the driver. — [Gates: Timing Belt Theory white paper](https://gates.com/content/dam/documents-library/whitepapers/timing-belt-theory-white-paper.pdf); torque = (T1 − T2)·r — [Engineers Edge: one pulley, two bearings](https://engineersedge.com/mechanics_machines/one-pulley-two-bearings.htm)
- **Belt shaft load:** Fs = √(T1² + T2² − 2·T1·T2·cos θ), where θ is the wrap angle (Gates Eq. 34). This reduces to Fs = T1 + T2 at 180° wrap (Eq. 36). — [Gates white paper](https://gates.com/content/dam/documents-library/whitepapers/timing-belt-theory-white-paper.pdf)
- **Timing belt slack side:** T2 ≈ (0.1 to 0.3)·Te for best performance (Gates Eq. 46). Pretension keeps the slack side from sagging and keeps the teeth meshed. — [Gates white paper](https://gates.com/content/dam/documents-library/whitepapers/timing-belt-theory-white-paper.pdf)
- **Pulley centered between two bearings:** each bearing carries (T1 + T2)/2, and the maximum moment is at the pulley. — [Engineers Edge: one pulley, two bearings](https://engineersedge.com/mechanics_machines/one-pulley-two-bearings.htm)
- **Impact (falling weight):** dynamic load factor n = 1 + √(1 + 2h/δ_st), where h is drop height and δ_st is static deflection. A sudden load (h = 0) gives n = 2, and impact stress = n x static stress. — [Skill-Lync: impact loading analysis](https://resources.skill-lync.com/branches/mechanical-engineering/questions/strength-of-materials/impact-loading-analysis); [Engineers Edge: mass impact loading](https://ns2.engineersedge.com/material_science/mass-impact-loading.htm) (about 2 treated as a floor)
- **Elastic dynamic amplification** for a suddenly removed or applied member peaks at 2 and falls with damping or longer load-application time. — [Engineering Mechanics (CN) journal article](https://www.engineeringmechanics.cn/cn/article/id/2366)
- **Wheel friction on FTC tiles:** AndyMark lists its 4" mecanum wheel at about 0.51 forward/reverse and 0.67 sideways on FTC soft tile. This is a vendor figure with no stated test method, and I saw it in search results but couldn't load the page (HTTP 429). — [AndyMark am-2626 (via search result)](https://www.andymark.com:443/am-2626)
- **No published FRC/FTC shock or collision factor for drivetrains turned up.** Practitioners point to tooth bending as the usual gear failure, and to Lewis/AGMA methods. — [Chief Delphi thread](https://www.chiefdelphi.com/forums/showthread.php?p=1391426)

### Inferences
**Core formulas the tool should implement:**

1. **Torque through a gear train [TEXTBOOK]:** T_out = T_in x (N_driven / N_driver) x η per stage. Use η = 1 for conservative force estimates, because a higher torque gives higher downstream loads. The design torque at any shaft is T_motor_stall x (cumulative ratio up to that shaft) x (number of motors driving it).
2. **Spur mesh:** F_t = T / (d/2), F_r = F_t·tan 20° = 0.364·F_t, F_n = F_t / cos 20° = 1.064·F_t. Equal and opposite forces act on the mating gear's shaft. Pitch diameter d = m·z (module x teeth) **[TEXTBOOK]**.
3. **Timing belt:** pitch diameter d = z·p/π **[TEXTBOOK]**. Te = T/(d/2). T2 = 0.1-0.3·Te, T1 = Te + T2. Shaft load Fs comes from the Gates vector formula, which is Te + 2·T2 at 180° wrap. Chain [ASSUMED]: same as belt with T2 ≈ 0 (slack side carries little load), so Fs ≈ Te.
4. **Shaft on two bearings, A and B, spacing L [TEXTBOOK statics]:**
   - Load W between the bearings, distance a from A (b = L − a): R_A = W·b/L, R_B = W·a/L, M_max = W·a·b/L.
   - Load W overhung, distance a outboard of A: R_A = W·(L + a)/L, R_B = −W·a/L (opposite direction), M_max = W·a at bearing A. **The near bearing always carries more than the applied load.** For a = 0.6·L it carries 1.6·W.
   - Moment M about an axis perpendicular to the shaft (for example a side hit on an arm): the bearings react a couple of ±M/L, opposite in direction in the two plates.
   - Solve the vertical and horizontal planes separately and combine vectorially: R = √(R_v² + R_h²).
5. **Cantilever arm or mechanism [TEXTBOOK]:** root moment M = F·L, tip deflection δ = F·L³/(3EI). For a plate holding a cantilevered pivot, the root moment loads the plate out of plane unless it is resolved into a couple across two plates.
6. **Traction-limited wheel force:** F_trac = μ·N per wheel, compared with the motor-limited F_motor = T_wheel_stall / r_wheel. The smaller one is the sustained drive load. The larger one, stall torque, is the conservative shaft-torque load for a jammed wheel.
7. **Collision [DERIVED from work-energy]:** with stopping distance d, the average force is F_avg = m·v²/(2d). For a linear-spring contact the peak is about 2·F_avg. The answer depends entirely on d, which the student almost never knows. Label it "conservative screening".
8. **Load combinations [ASSUMED engineering practice]:** run separate cases and take the envelope. Combine only loads that physically happen together: weight + traction at the same wheel, or gravity + motor holding torque on an arm. Never add stall torque and collision together unless the user asks.

**Worked example A: drivetrain wheel loads (Strafer-like) [DERIVED, inputs marked]**
- Inputs: robot mass 15 kg [ASSUMED]; 4x 96 mm mecanum wheels, r = 0.048 m [cited Strafer]; 5203 312 RPM direct drive, T_stall = 2.383 N·m [cited]; μ = 0.51 forward [vendor, unverified].
- Static normal load per wheel (even split): N = 15 x 9.81 / 4 = **36.8 N**.
- Traction limit: F_trac = 0.51 x 36.8 = **18.8 N** per wheel, so wheel torque at slip = 18.8 x 0.048 = 0.90 N·m.
- Motor limit: F_motor = 2.383 / 0.048 = **49.6 N**. Since this is more than F_trac, the drivetrain is traction-limited, with acceleration at most about μ·g = 5.0 m/s².
- Free speed 1.568 m/s (matches goBILDA's 5.14 ft/s). For comparison, 435 RPM gives 2.19 m/s and 38.2 N, and 223 RPM gives 1.12 m/s and 77.6 N.
- Overhung wheel: a = 30 mm outboard of bearing A, bearing spacing L = 48 mm (both [ASSUMED]; 48 mm is the 1120 U-channel width per [gm0 goBILDA guide](https://game-manual-0.readthedocs.io/en/latest/docs/hardware-basics/kit-and-hardware-guide/gobilda.html)).
  - Vertical: R_A = 36.8 x (48 + 30)/48 = **59.8 N**, R_B = 36.8 x 30/48 = **23.0 N** (opposite direction). Shaft moment at A = 36.8 x 0.030 = 1.10 N·m.
  - Horizontal, traction: R_A = 18.8 x 1.625 = 30.6 N, R_B = 11.8 N.
  - Sudden-load factor 2: R_A = 120 N vertical.
- Drop of h = 25 mm [ASSUMED]: n = 1 + √(1 + 50/δ_st). δ_st = 1 mm gives n = 8.1, and δ_st = 3 mm gives n = 5.2. **This is very sensitive to tile and wheel compliance, which the student does not know.** Treat it as screening only.
- Pushing match against another robot or a wall: whole-robot sustained force ≈ μ·m·g = 0.51 x 15 x 9.81 = **75 N**.
- Wall collision at 1.568 m/s: KE = 18.4 J. d = 10 mm gives F_avg = 1844 N (peak about 3700 N), and d = 20 mm gives 922 N. This lands on bumpers and frame, not on individual bearing bores.

**Worked example B: gearbox plate with 3:1 external reduction [DERIVED]**
- Inputs: 5203 117 RPM, T_stall = 6.708 N·m [cited]; 20T pinion and 60T gear, module 1 [ASSUMED], so d1 = 20 mm and d2 = 60 mm.
- F_t = 6.708 / 0.010 = **670.8 N**; F_r = 670.8 x 0.364 = **244.1 N**; F_n = **713.8 N**. Output torque about 20.1 N·m (ideal).
- 60T gear shaft between two plates with L = 40 mm [ASSUMED]:
  - Gear centered: 357 N per bearing.
  - Gear 10 mm from plate A: R_A = 713.8 x 30/40 = **535 N**, R_B = **178 N**.
- The pinion's equal and opposite 714 N goes into the motor shaft and the motor's mounting face or plate. That is a plate load at the motor-mount holes, not at a bearing bore.

**Worked example C: belt-driven roller or shaft [DERIVED]**
- 24T HTD 5 mm pulley [ASSUMED]: d = 24 x 5/π = 38.2 mm.
- With 5203 312 RPM at stall: Te = 2.383 / 0.0191 = **124.8 N**. T2 = 12.5-37.4 N, T1 = 137-162 N. Shaft load at 180° wrap: **150-200 N**.
- With 5203 1150 RPM (intake) at stall: Te = 40.6 N, Fs = 48.7-64.9 N.

**Worked example D: arm on a pivot [DERIVED]**
- Inputs [ASSUMED]: arm 0.40 m long, 0.5 kg with its CG at 0.20 m, 0.2 kg payload at the tip.
- Gravity torque when horizontal: 0.5 x 9.81 x 0.2 + 0.2 x 9.81 x 0.4 = **1.77 N·m**, which gives F_t = 58.9 N at the 60T gear.
- Stall against a hard stop through the 3:1 stage of example B: 20.1 N·m and F_t = 671 N. **Motor stall dominates gravity by more than 10x.** The arm support plate should be designed to the stall case, because arms do get driven into stops and field elements.
- A 10 N side bump at the arm tip, with bearings 40 mm apart, gives a ±100 N couple (M = 4 N·m; 4/0.04 = 100 N), opposite in direction in the two plates. Small side loads at long arms produce large bearing reactions.

**Worked example E: lift / slide spool [DERIVED]**
- 5203 223 RPM (3.727 N·m) on a spool of radius 16 mm [ASSUMED]: string tension at stall = **233 N**. A redirect pulley with 180° wrap sees about 466 N on its axle.
- Robot hanging on the lift (if the game has an endgame hang; not checked for BIOBUZZ): 15 x 9.81 = 147 N, or 294 N with factor 2.

### Gaps
- I found no FTC-specific, test-based impact or collision factor, and no measured stopping distance for FTC bumper-less collisions. Any value is an assumption.
- I couldn't load the vendor friction coefficient (AndyMark 0.51/0.67) directly, and found no independent FTC-tile measurement. A 2012 paper measured μ_s = 0.51 on a lab floor, not foam ([arXiv 1211.2323](https://arxiv.org/pdf/1211.2323)), so the agreement is coincidental, not a confirmation.
- I couldn't verify goBILDA gear module or tooth counts or HTD pulley tooth counts. Example geometry is assumed.
- I didn't find mecanum-specific load vectors (45° roller force components). The examples treat the wheel as a conventional wheel.

---

## 3. Typical FTC plate scenarios: loads, directions, magnitudes, supports, responses of interest

### Takeaway
Most loads on FTC side plates and gearbox plates act **in the plate's own plane**: bearing radial loads, gear mesh forces, belt pull, and wheel weight and traction. When a shaft spans two plates, an overhung load becomes opposite in-plane forces on each plate, carried in shear by the standoffs between them. Out-of-plane bending appears mainly with single-plate cantilevered shafts and mechanisms mounted at an offset. In both cases, bearing-bore misalignment between paired plates is often the response that matters, more than stress.

### Cited Findings
- Strafer construction: wheels on hub-shafts supported by 1611 flanged ball bearings in 1120 U-channel, with 1201 quad block pattern mounts joining the channels. — [goBILDA Strafer V5](https://www.gobilda.com/strafer-chassis-kit-v5/)
- goBILDA motors can face-mount directly into channel. The system uses 6 mm D and 8 mm REX shafts with clamping hubs, 8 mm pitch chain, and HTD 3/HTD 5 belts sized to land center-to-center on the goBILDA pattern. — [gm0 goBILDA guide](https://game-manual-0.readthedocs.io/en/latest/docs/hardware-basics/kit-and-hardware-guide/gobilda.html)
- REV advises supporting a Core Hex motor with two or more plastic brackets. — [REV docs: Core Hex](https://docs.revrobotics.com/duo-build/actuators/motors/core-hex-motor)
- R105 caps the expanded robot at 18 x 24 x 29 in, which sets the maximum lever arm for cantilevered arms and slides (roughly ≤ 0.6-0.7 m horizontal reach from the chassis). — [2026-2027 manual](https://ftc-resources.firstinspires.org/ftc/game/manual)
- A ChiefDelphi discussion separates drivetrain load cases into accelerating the robot, maintaining speed against drag, and pushing at constant speed, and notes sustained pushing is limited by current and heat. — [Chief Delphi thread](https://www.chiefdelphi.com/forums/showthread.php?p=1391426)

### Inferences
The table below is the proposed template set for the tool. Magnitudes come from the formulas and worked examples in section 2; everything here is **[DERIVED/ASSUMED]**.

| Plate type | Force sources | Directions on plate | Typical magnitude (example inputs) | How the plate is supported | Responses of interest |
|---|---|---|---|---|---|
| **Drivetrain side plate (wheel between two plates, or wheel overhung from a channel)** | Robot weight share; traction (μN); sudden/drop factor; wheel-jam stall torque (reacted at the motor mount); side scrub on mecanum/omni | Vertical in-plane (weight); horizontal in-plane (traction); out-of-plane only if the shaft is cantilevered from one plate | 37 N static per wheel at 15 kg; 60 N at the near bearing for an overhung wheel; 120 N with factor 2; drop up to 5-8x (very uncertain) | Bolted to cross-members or standoffs; the other side plate takes part of the couple | Bearing-bore stress; in-plane stiffness between the wheel bores (chain/belt center distance); bore misalignment between paired plates |
| **Gearbox plate pair (2+ bearings, plates joined by standoffs)** | Gear mesh F_t and F_r at each shaft; motor-face reaction; idler vector sums | All in-plane at the bores; equal and opposite pairs within the gearbox; net load leaves through the mounting bolts | 300-700 N per bore at stall for a 117 RPM motor with a small pinion (example B) | Self-equilibrated internally; attached to the chassis at a few bolts | Center-distance change under load (mesh separation); bore misalignment; stress at thin ligaments between pockets and bores |
| **Arm / pivot support plate** | Motor stall through gearing (hard-stop case); gravity on the arm and payload; side bumps at the arm tip; arm inertia | In-plane mesh forces; in-plane bearing couple from side loads (two-plate) or out-of-plane plate bending (single plate) | 1.8 N·m gravity versus 20 N·m stall (example D); a 10 N tip side load gives a ±100 N bearing couple | Bolted to the chassis or a tower through standoffs/channel | Out-of-plane stiffness (arm droop and wobble); bore misalignment; fatigue at the pivot (many cycles) |
| **Lift / slide mounting plate** | String or belt tension at pulleys and spool; slide carriage moments; robot weight when hanging | In-plane at pulley axles (2T for 180° wrap); out-of-plane moments from slides offset from the plate | 233 N string tension at stall (example E); hang 147-294 N | Bolted to the drivetrain frame | Stress at pulley-axle holes; plate bending from offset slides |
| **Intake plate (roller support)** | Belt pull from the roller drive; roller-game piece compression; jam at stall; robot driving into field walls with the intake leading | In-plane at roller axles; collision loads at the leading edge | 50-65 N belt shaft load at stall (1150 RPM, example C); compression unknown (user input) | Cantilevered from the chassis, or on a pivoting four-bar | Deflection of the roller center distance (belt tension loss); collision robustness |
| **Chassis plates joined by standoffs (sandwich)** | Combined drivetrain loads; frame racking from mecanum side forces; collision | In-plane on each plate; racking puts the standoffs in shear and bending | Frame collision loads of 900-3700 N whole-robot (very assumption-dependent) | Mutual: plate + standoffs + plate act as a frame | Racking stiffness (standoff bending dominates); stress at standoff holes |
| **Cantilevered mechanism plate (e.g. a sensor or servo bracket)** | Self-weight x acceleration; servo stall torque; impacts | Out-of-plane bending at the root bolts | Usually small; driven by servo stall torque (not researched here) | Root bolts, usually in one row (behaves like a hinge) | Out-of-plane deflection and vibration; root bolt-hole stress |

- **Key modelling consequence [INFERENCE]:** for plate pairs, the two-plate system decides the load split. An overhung wheel or gear makes the near plate carry about 1.6x the load and the far plate about 0.6x in the reverse direction. Standoffs between the plates carry the couple in shear. A single-plate FEA model that applies only "its share" without the couple misses this.
- **Stall is the governing case for most powered-mechanism plates [INFERENCE]:** examples B and D show stall loads 10x larger than gravity or holding loads. Drivetrain wheel plates are the exception, where traction-limited loads govern sustained running and drop or impact governs peaks.
- **Responses that matter more than stress [INFERENCE]:** typical FTC plate stresses near bores are low. Example B gives about 10-12 MPa projected bearing stress on a 4 mm plate, far below aluminum yield. Lightening limits usually come from (a) in-plane stiffness that keeps gear and belt center distances, (b) relative bore misalignment between paired plates, (c) thin ligaments next to pockets, and (d) out-of-plane stiffness for single-plate cantilevers.
- Misalignment angle between paired bores [TEXTBOOK]: θ ≈ (δ_A − δ_B)/L_shaft, where δ_A and δ_B are the radial displacements of the two bores in the same direction.

### Gaps
- I couldn't find quantified FTC-specific failure data (which plates crack or bend in practice) or engineering notebooks with measured loads.
- I found no allowable bearing-misalignment or gear center-distance tolerance for goBILDA/REV bearings and gears. Generic bearing-maker limits weren't retrieved this session.
- I didn't research servo stall torques. Servo-driven plate loads need that data.
- I didn't verify whether BIOBUZZ includes an endgame hang or climb, which would add a whole-robot-weight case.

---

## 4. Typical FTC hardware: hole patterns, bearing sizes, standoffs, channel, and classifying holes by diameter

### Takeaway
Hole diameter is a strong feature-classification signal. goBILDA uses 4 mm holes on an 8 mm grid for M4 screws, with 14 mm bearing bores for 1611 bearings (14 mm OD), spaced every 24 mm along structure. REV uses M3 hardware on 15 mm extrusion, 9 mm holes for plastic through-bore bearings, 12 mm holes for 8x12 mm metal flanged bearings, and a 14 mm bolt circle on HD Hex planetaries. A small table of diameters ±tolerance can label holes as fastener, bearing bore, or shaft clearance. Unrecognised diameters should be kept and flagged for the user.

### Cited Findings
- goBILDA pattern: "4mm holes on an 8mm grid", plus a 14 mm hole "to easily seat a bearing". The four holes nearest the bearing hole are clocked for 45° mounting, and joined holes form slots. — [goBILDA: The goBILDA Pattern](https://gobilda.com/pattern)
- On much of goBILDA's structure, a 14 mm hole appears every 24 mm. — [gm0 (Spanish edition source), goBILDA page](https://gm0-es.readthedocs.io/es/latest/_sources/docs/hardware-components/kit-and-hardware-guide/gobilda.rst.txt)
- goBILDA uses M4 hardware. U-channel is 48 x 48 mm and low-side channel is 12 x 48 mm. Shafts are 6 mm D and 8 mm REX, with a 12 mm REX large-bore option. — [gm0 goBILDA guide](https://game-manual-0.readthedocs.io/en/latest/docs/hardware-basics/kit-and-hardware-guide/gobilda.html)
- goBILDA 1611 flanged ball bearing: 8 mm REX ID, 14 mm OD, 5 mm thick, high-carbon steel, 3.5 g. Flange OD and load ratings aren't listed. — [goBILDA 1611 bearing page](https://www.gobilda.com/1611-series-flanged-ball-bearing-8mm-rex-id-x-14mm-od-5mm-thickness-2-pack/). A 6 mm ID version (same 14 mm OD x 5 mm) is used in Strafer. — [goBILDA Strafer V5](https://www.gobilda.com/strafer-chassis-kit-v5/)
- REV bearings: plastic End Cap (REV-41-1322), Short Through-Bore (REV-41-1326), and Long Through-Bore (REV-41-1329) bearings have a maximum 9 mm OD and fit 9 mm holes in motion brackets or the Extended Motion Pattern bearing seat. The 8 mm x 12 mm Flanged Bearing (REV-49-1559) press-fits a 12 mm hole in the 15 mm Metal Ball Bearing Mount V2 (REV-41-1452). The 5 mm Hex Bearing Block (REV-41-1683) matches the Extended Motion Pattern. — [REV docs: Bearings](https://docs.revrobotics.com/duo-build/motion/intro/bearings.md)
- 15 mm extrusion (REV, Misumi) takes M3 bolts and nuts. — [gm0 kit glossary (Spanish edition source)](https://gm0-es.readthedocs.io/es/latest/_sources/docs/hardware-components/kit-and-hardware-guide/kit-glossary.rst.txt)
- REV HD Hex outputs a 5 mm hex shaft. Planetary mounting holes sit on a 14 mm bolt circle. Spur gearboxes use the REV Motion Pattern and have 10x M3 tapped holes. — [REV docs: HD Hex](https://docs.revrobotics.com/duo-build/actuators/motors/hd-hex-motor)
- goBILDA's 8 mm metric chain isn't interchangeable with #25 chain. — [gm0 goBILDA guide](https://game-manual-0.readthedocs.io/en/latest/docs/hardware-basics/kit-and-hardware-guide/gobilda.html)

### Inferences
**Proposed hole-classification table** (nominal diameters from the citations above; tolerance bands and clearance sizes are **[ASSUMED]**, so let the user override):

| Measured hole Ø (mm) | Likely feature | System | Load role in FEA |
|---|---|---|---|
| 3.0-3.6 | M3 clearance hole | REV / 15 mm extrusion | Fastener: elastic support or load transfer (see section 5) |
| ≈ 2.5 (tapped M3) | M3 tapped | REV gearbox faces | Fastener |
| 4.0-4.6 | M4 clearance (pattern hole) | goBILDA | Fastener if a screw is present; otherwise an unused pattern hole (free, no BC) |
| ≈ 5.0-5.8 / hex 5 mm | 5 mm hex shaft pass-through (no bearing) | REV | Usually free; flag it |
| ≈ 8-8.5 | 8 mm shaft clearance, or REX pass-through | goBILDA | Usually free; flag it |
| 9.0 | Plastic through-bore bearing seat | REV | **Bearing bore**: apply load |
| 12.0 | 8x12 flanged ball bearing seat | REV | **Bearing bore** |
| 14.0 | 1611 bearing seat (6 or 8 mm ID) | goBILDA | **Bearing bore** |
| other | Unknown | — | Ask the user; default to "free hole, no BC" |

- **The pattern matters as much as the diameter [INFERENCE]:** a 14 mm hole surrounded by 4 mm holes on 8 mm spacing (with the four clocked holes) is almost certainly a goBILDA bearing seat. A 14 mm bolt circle of small holes around a central hole suggests a REV HD Hex planetary face mount. Both can be detected geometrically.
- **Most 4 mm pattern holes on a student plate are not fastened [INFERENCE].** The tool should never assume every hole carries a screw. The user should tick which holes have screws, standoffs, or channel attached. This is the main defence against the "every hole fixed" error in section 5.
- **Contact patch for fastener supports [ASSUMED]:** use a washer/head annulus of about 1.5 x nominal screw diameter (about 6 mm for M4, about 4.5 mm for M3, the classic Shigley washer-face proxy). Standard ISO 4762 M4 socket head is about 7 mm in diameter (from memory; verify).

### Gaps
- I couldn't confirm goBILDA's exact clearance diameter for 4 mm pattern holes (4.0 nominal vs actual drill size), standoff hex size and outer diameter, or plate thicknesses from primary pages.
- I didn't retrieve REV Extended Motion Pattern dimensions or REV channel and plate hole diameters.
- I didn't find the flange OD of goBILDA 1611 bearings (useful for the bearing contact annulus on the plate face) or any bearing load ratings.
- I didn't research AndyMark/TETRIX/Actobotics (0.770 in pattern) hole sizes. They may appear on mixed-system robots.

---

## 5. Modelling supports and bearing loads realistically in FEA

### Takeaway
Don't fix every mounting hole. Fixing hole edges creates stress singularities exactly where students will look, over-stiffens the plate, and hides the real load path. Model fasteners as elastic supports (springs with stiffness estimated from the standoff or channel they connect to), spread over the bolt-head contact annulus, with just enough rigid restraint to stop rigid-body motion. Apply bearing loads as a cosine (sinusoidal) pressure over the loaded 180° of the bore, or through an RBE3-type distributing coupling. Use pin-in-bore contact only when local bore stress is critical. Report results as a range across support assumptions.

### Cited Findings
- **Singularities at fixtures:** stress singularities occur where fixtures end, like a stiff part digging into a soft part. They can mask a real nearby stress concentration. — [Design World: avoiding singularities in FEA boundary conditions](https://www.designworldonline.com/avoiding-singularities-in-fea-boundary-conditions/)
- **Spring supports as the fix:** replace fixed constraints with spring elements at each node of the constrained surface. If the stiffness is too low, displacements become excessive and the solver may fail. If it is too high, spurious stress concentrations remain. — [Design World](https://www.designworldonline.com/avoiding-singularities-in-fea-boundary-conditions/)
- **COMSOL bracket example:** using springs instead of fixed bolt holes removes the singular stress fields around the holes, but requires an estimate of the supporting structure's stiffness. — [COMSOL Application Gallery: bracket with spring supports](https://doc.comsol.com/6.4/doc/com.comsol.help.models.sme.bracket_spring/bracket_spring.html)
- **Elastic support limits:** an Ansys staff answer notes that an elastic (spring) foundation only constrains the surface-normal direction, so lateral constraints are still needed. For loads carried at bolt holes, it suggests a remote displacement at each hole centre. — [Ansys Innovation Space forum](https://innovationspace.ansys.com/forum/forums/reply/398340/)
- **Hand-calculate bolt-hole bearing stress:** a practitioner view holds that fastener holes in large FEMs are better replaced by springs or beams. Extract the fastener loads and hand-calculate the bearing stress. — [Eng-Tips thread](https://www.eng-tips.com/viewthread.cfm?qid=477487)
- **Bearing load (Ansys):** Ansys Mechanical's Bearing Load applies a nonuniform pressure over part of the cylindrical surface, varying sinusoidally (cosine) and peaking in the load direction. — [Ansys Help: Bearing Load](https://ansyshelp.ansys.com/public/views/secured/corp/v261/en/wb_sim/ds_Bolt_Load.html)
- **Bearing load (SOLIDWORKS):** "Applying a force to a hole in Simulation will give a uniform load to all locations on the hole", whereas real loads act on part of the hole. The SOLIDWORKS bearing load applies to the half of the hole on the load side, with sinusoidal or parabolic distribution, and needs a coordinate system with Z along the hole axis. — [Javelin: SOLIDWORKS Simulation Bearing Load](https://www.javelin-tech.com/blog/2019/04/solidworks-simulation-bearing-load/)
- **Uniform full-bore loading creates artificial tension** on the opposite side of the hole. Elastic pin-in-bore theory gives a sinusoidal contact pressure. Pin-plus-contact modelling is more accurate than a bearing load. The cosine approach is a good, quick approximation for a close-fitting pin, and the right choice depends on the clearance between the pin or bearing and the hole. — [PrePoMax forum: bearing load distribution](https://prepomax.discourse.group/t/bearing-load-distribution/2862); [Ansys Innovation Space forum](https://innovationspace.ansys.com/forum/?p=229719)
- **RBE2 vs RBE3:** RBE2 is a rigid, kinematic link where attached nodes move together. It effectively stiffens the region and can give inaccurate results in flexible areas. RBE3 is an interpolation element that spreads a reference-point force or moment to nodes by weight factors without adding stiffness. Use RBE2 for rigid connections and RBE3 for applying loads. — [Altair Community](https://community.altair.com/discussion/comment/71861); [Eng-Tips: RBE2 versus RBE3](https://www.eng-tips.com/viewthread.cfm?qid=149522); [Ansys Innovation Space forum](https://innovationspace.ansys.com/forum/?p=47631)
- **Bolt clamp zone:** frustum (pressure-cone) half-angles of 25°-35° suit steel, cast iron, and aluminum with a washer face, and 30° is a good general value. — [RoyMech: joint stiffness](https://roymech.org/Useful_Tables/Screws/Joint_Stiffness.html). A 3D FEA of a 14-bolt flange found a 32.8° half-angle frustum predicted stiffness within a few percent. — [OSTI 122652](https://www.osti.gov/biblio/122652)

### Inferences
**Why "all holes fixed" is wrong for FTC plates [INFERENCE, consistent with the cited sources]:**
1. It makes the plate artificially stiff, so deflection and misalignment are under-predicted. Those are often the real lightening constraints.
2. Load takes the shortest path to the nearest fixed hole instead of the real path through standoffs. That understates stress in the pocket ligaments that actually carry load.
3. It creates singular stress at every fixed hole edge, which the optimiser may "fix" by adding unnecessary material there (Design World).
4. It ignores load sharing in two-plate systems: the couple that loads standoffs in shear (section 3).

**Standoff stiffness shows why in-plane fixity is the worst assumption [DERIVED; dimensions ASSUMED]:**
- Aluminum standoff, OD 8 mm, ID 4 mm, L = 48 mm, E = 69 GPa: A = 37.7 mm², I = 188.5 mm⁴.
- Axial stiffness EA/L ≈ **54,000 N/mm**.
- Lateral stiffness (in the plate's plane) is 12EI/L³ ≈ **1,400 N/mm** if both ends are clamped and guided, or 3EI/L³ ≈ **350 N/mm** if one end is free to rotate.
- In-plane support stiffness is therefore 40-150x lower than out-of-plane stiffness. A fixed in-plane BC at a standoff hole is the least realistic part of an "all fixed" model, and most FTC plate loads are in-plane (section 3).

**Recommended recipe for the tool [INFERENCE / ASSUMED best practice]:**
1. **Ask which holes are connected and to what:** screw into a standoff (and its length), into channel, a bearing seat, or unused. Unused holes get no BC.
2. **Fastener supports:** spring BCs spread over a washer annulus (OD ≈ 1.5-1.75 x screw diameter), not hole-edge nodes.
   - Normal stiffness ≈ standoff EA/L, or clamped-joint stiffness via the 30° frustum (RoyMech).
   - In-plane stiffness ≈ standoff bending stiffness (12EI/L³ as an upper bound, 3EI/L³ as a lower bound), or a very stiff value for screws clamped directly to channel.
   - Use RBE3-style distribution for loads. If the tool wants a "rigid washer" option, use RBE2 only over the head-contact annulus, and know that it adds stiffness.
3. **Prevent rigid-body motion minimally:** if springs give enough restraint in all directions, nothing else is needed. Otherwise add a statically determinate 3-2-1 set of point restraints far from the region of interest. For self-equilibrated gearbox plates, where bearing forces cancel, use inertia relief or a determinate support. **[ASSUMED: inertia relief is a standard solver feature; not verified this session.]**
4. **Bearing loads:** cosine pressure on the loaded half of the bore, p(θ) = p₀·cos θ for |θ| ≤ 90°, with p₀ = 4F/(π·d·t) **[DERIVED by integrating the pressure resultant]**. Peak pressure = 1.27 x the projected bearing stress F/(d·t).
   - Example B's 535 N on a 14 mm bore in a 4 mm plate [ASSUMED thickness]: projected stress 9.6 MPa, cosine peak 12.2 MPa.
   - Alternative: an RBE3 spider from the bearing centre to the bore face, which also carries the moment when the bearing is offset axially.
   - Avoid uniform force on the full bore (SOLIDWORKS/Ansys sources).
   - For flanged bearings, also apply the axial and flange component on the flange annulus if axial loads exist.
5. **Two-plate systems (gearbox, wheel pair):** if possible, model both plates, the standoffs as beams, and the shaft as a beam on spring bearings. This captures the load split and the bore misalignment directly. A single-plate model must at least apply the overhang couple (section 2, formula 4).
6. **Bracketing and uncertainty:** run at least two support variants, for example soft springs (cantilever standoff 3EI/L³) and stiff springs (12EI/L³ or pinned). If key outputs (peak ligament stress, bore misalignment) differ by more than about 25-30% [ASSUMED threshold], label the result "support-sensitive" and show both.
7. **Reading results:** ignore peak stress at the edge of any remaining point constraint, and check whether it converges with mesh refinement (Design World). Report fastener loads and hand-calculate bolt-hole bearing stress (Eng-Tips approach).

### Gaps
- I didn't retrieve NAFEMS or NASA FEA boundary-condition guidance documents directly. The cited guidance comes from vendor documentation, application notes, and practitioner forums.
- I found no FTC- or small-robot-specific study validating spring-support stiffness values against tests.
- I didn't verify the Shigley frustum stiffness equation against a primary text this session. It's recalled as k = 0.5774πEd / ln[(1.155t + D − d)(D + d) / ((1.155t + D + d)(D − d))] per frustum at 30°. **Verify before implementing.**
- Bearing outer-race fit (press vs slip) changes the bore pressure distribution (PrePoMax/Ansys forum), but I found no data on actual goBILDA/REV bore tolerances.

---

## 6. Load templates for a student UI, provenance labels, uncertainty communication, and what can be derived from motor + ratio + wheel + mass

### Takeaway
From motor model, gear ratio(s), wheel or pulley size, and robot mass, the tool can calculate stall torque at every shaft, mesh and belt forces, traction-limited wheel loads, free speed, and screening impact loads. It can't know friction, impact stiffness, which holes are fastened, or the game-specific cases. Each load should carry a provenance tag (user-specified, vendor datasheet, calculated, assumed default, conservative screening, physically validated) and a low/nominal/high range. Results should be framed as screening, not certification.

### Cited Findings
- Vendor stall torque and free speed per motor and ratio are published (section 1 table). — [goBILDA](https://www.gobilda.com/5203-series-yellow-jacket-planetary-gear-motor-19-2-1-ratio-24mm-length-8mm-rex-shaft-312-rpm-3-3-5v-encoder/); [REV HD Hex](https://docs.revrobotics.com/duo-build/actuators/motors/hd-hex-motor); [REV Core Hex](https://docs.revrobotics.com/duo-build/actuators/motors/core-hex-motor)
- The motor-plus-wheel speed calculation checks out against vendor data: goBILDA states over 5.14 ft/s for 312 RPM motors on 96 mm wheels, exactly what v = ω·r gives. — [goBILDA Strafer V5](https://www.gobilda.com/strafer-chassis-kit-v5/)
- The rules give no mass bound (R104), so mass must be a user input. — [2026-2027 manual](https://ftc-resources.firstinspires.org/ftc/game/manual)
- Friction coefficients are vendor-published without a method (AndyMark), and impact factors depend on unknown stiffness (n = 1 + √(1 + 2h/δ_st)), so both need explicit uncertainty labels. — [AndyMark am-2626 (via search)](https://www.andymark.com:443/am-2626); [Skill-Lync impact loading](https://resources.skill-lync.com/branches/mechanical-engineering/questions/strength-of-materials/impact-loading-analysis)
- Spring-support results depend on the estimated support stiffness, which is itself uncertain. — [COMSOL bracket example](https://doc.comsol.com/6.4/doc/com.comsol.help.models.sme.bracket_spring/bracket_spring.html); [Design World](https://www.designworldonline.com/avoiding-singularities-in-fea-boundary-conditions/)

### Inferences
**Inputs a student knows, and what each one unlocks [DERIVED design]:**

| Student input | Derived quantity | Formula | Provenance tag |
|---|---|---|---|
| Motor model + gearbox ratio | Stall torque, free speed at the motor output | Vendor table; else 0.13 N·m x ratio (5203) or 0.105 N·m x ratio (HD Hex) | "Vendor datasheet" or "Calculated (scaled)" |
| + external gear teeth / pulley teeth | Torque at each shaft; mesh F_t, F_r; belt Te, T1, T2, shaft load | Section 2, formulas 1-3 | "Calculated" (T2 split = "Assumed default 0.1-0.3 Te") |
| + wheel diameter | Wheel force at stall; free speed | F = T/r; v = ω·r | "Calculated" |
| + robot mass | Static wheel load; traction limit; pushing force; collision energy | N = mg/n_wheels; μN; ½mv² | "User-specified" mass; μ = "Assumed (vendor 0.51)" |
| + geometry (bearing spacing, overhang, arm length, payload) | Bearing reactions, couples, gravity torque | Section 2, formula 4; arm statics | "Calculated" from "User-specified" geometry |
| Unknown: drop height, stopping distance, game-piece compression | Impact and collision loads | Section 2, formulas 7 and impact factor | "Conservative screening" |
| Test (spring scale pull test, measured deflection, observed failure) | μ, stiffness, real load | — | "Physically validated" |

**Provenance labels (proposed definitions):**
- **User-specified:** typed by the student (mass, geometry, which holes are fastened). Show it as entered.
- **Vendor datasheet:** a published spec with its link (stall torque, free speed, bearing dimensions).
- **Calculated:** derived by a stated formula from the inputs above. Show the formula and the inputs on hover.
- **Assumed default:** the tool's value when the student doesn't know (μ = 0.51, T2 = 0.2·Te, 15 kg). Visually distinct, for example italic or amber, with a one-click override.
- **Conservative screening:** a deliberately high-side value for unknowable events (stall against a hard stop, sudden-load factor 2, collision with a short stopping distance). Tells the student it's an envelope, not an expected value.
- **Physically validated:** confirmed by a team test, such as a pull test for traction or a measured deflection. The only label that should lower safety margins.

**Communicating uncertainty [INFERENCE]:**
- Show low, nominal, and high values for each load. For example drivetrain per-wheel vertical: static 37 N, sudden 74 N, screening drop 190-300 N.
- Propagate the extremes through the FEA as separate cases. The output then reads as "max ligament stress 12-48 MPa depending on drop assumption", not one number.
- Show a sensitivity bar: which input changes the result most. For drops this is usually δ_st or h. For gearbox plates it's motor stall versus current limit. For two-plate systems it's support stiffness.
- Default to envelope-based design checks, and state plainly that results are a screening estimate and that physical testing is the validation step.
- Keep stiffness criteria (bore misalignment, center-distance change) separate from stress criteria. Lightening is often limited by stiffness.

**Suggested UI load templates (one per plate type, pre-filled from motor, ratio, mass, and wheel) [DESIGN PROPOSAL]:**
1. *Drive wheel plate:* static (mg/4), drive (μN horizontal), sudden (x2 vertical), wheel jam (stall torque at the motor mount), optional drop (h, δ_st).
2. *Gearbox plate:* motor stall through the train (each mesh), with an optional efficiency of 1.0 (conservative) or user-set.
3. *Arm plate:* gravity at horizontal (arm + payload), stall against a stop, tip side bump (user N; default 10-20 N [ASSUMED]).
4. *Lift plate:* spool stall tension, pulley wrap multiplier, optional hang (mg x 2).
5. *Intake plate:* belt shaft load at stall, user compression, leading-edge collision (screening).
6. Every template exposes its support model: which holes are fastened, standoff length, and channel or standoff type. It defaults to springs, never "all holes fixed".

### Gaps
- I didn't research formal frameworks for simulation credibility and uncertainty labelling (for example NASA-STD-7009 or ASME V&V 10). The provenance scheme above is a design proposal, not a cited standard.
- I found no validated FTC-specific defaults for drop height, collision stopping distance, or side-bump force. They have to stay "conservative screening" or user-supplied until teams test them.
- The effect of motor controller current limits on achievable torque is unverified (section 1 gap). Stall-based loads may be conservative by an unknown margin.
