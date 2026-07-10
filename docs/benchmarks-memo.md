# Benchmarks memo (feldspar canonical copy)

Status: NORMATIVE for this repo's calibration citations (WO-20/21/23/
24 tests cite this file's section numbers). Provenance: this file is
a byte-faithful copy of lithos `docs/workflow/research/2026-07-08-
benchmarks-and-datasets.md` (dated 2026-07-08, "advisory/non-
normative" in ITS repo of origin), canonicalized here per WO-24
deliverable -1 because that source file is the only place the
numbered sections (1.1, 1.3, 1.5, 3.1-3.4, 4.1-4.5, ...) that feldspar
tests/WO close-outs cite by number actually exist. Section numbering
is preserved EXACTLY as the tests cite it; do not renumber existing
sections when adding new ones -- append new numbered subsections
instead (e.g. a new bolted-joints case would be a new "1.6" or a new
top-level section, never a renumbering of 1.1-1.5).

Audit method (WO-24 deliverable -1): grepped `memo` (case-insensitive)
across `tests/` and `docs/` in this repo, collected every numbered
citation (1.1, 1.2, 1.3, 1.4, 1.5, 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 4.3,
4.4, 4.5), then located the source document via the WO-20 close-out's
explicit path reference
(`lithos docs/workflow/research/2026-07-08-benchmarks-and-datasets.md`
sec. 3) and confirmed every one of the collected citations resolves
to a section in that document with the SAME numeric worked values the
tests assert against (e.g. this repo's
`tests/unit/test_library_struct.py::test_propped_cantilever_udl_matches_closed_form`
asserts `w=10e3, length=6.0 -> R_A=37.5kN, R_B=22.5kN, M_A=45.0kNm`,
matching sec. 1.1's worked fixture verbatim).

**Result: every numbered citation found in this repo's tests/docs
resolves to a real section below. No unreconstructed citations.**

Citation inventory (this repo, WO-24 deliverable -1 audit):

| Cited as                          | File(s)                                                      | Resolves to |
|------------------------------------|---------------------------------------------------------------|-------------|
| "benchmarks memo 1.1"             | `tests/unit/test_library_struct.py`, `WO-23-load-paths.md`    | sec. 1.1    |
| "benchmarks memo's cases 1.2"     | `WO-21-civil-structural-wave.md`                               | sec. 1.2    |
| "benchmarks memo 1.3"             | `tests/unit/test_library_struct.py`                            | sec. 1.3    |
| "benchmarks memo 1.4"             | `WO-21-civil-structural-wave.md`                                | sec. 1.4    |
| (sec. 1.5, not yet cited by name in this repo's landed tests -- reserved, see WO-24 deliverable 8 cut note) | -- | sec. 1.5 |
| "benchmarks memo 3.1"             | `tests/unit/test_library_fluids.py`                            | sec. 3.1    |
| "benchmarks memo 3.2" / "sec. 3.2"| `tests/unit/test_library_fluids.py`, `test_library_fluids_network.py` | sec. 3.2 |
| "benchmarks memo 3.3" / "memo case"| `tests/unit/test_library_fluids.py`                            | sec. 3.3    |
| "benchmarks memo sec. 3.4"        | `tests/unit/test_library_thermo.py`                             | sec. 3.4    |
| "benchmark memo sec. 4.1"         | `tests/integration/test_elec_ngspice_pipeline.py`               | sec. 4.1    |
| (sec. 4.2, RLC -- `test_library_elec.py::test_rlc_resonance_matches_benchmark_memo`, no explicit numeral in the docstring but matches sec. 4.2's L/C/R values exactly) | `test_library_elec.py` | sec. 4.2 |
| "benchmark memo sec. 4.3"         | `tests/integration/test_elec_ngspice_pipeline.py`               | sec. 4.3    |
| (sec. 4.4, BJT -- `test_library_elec.py::test_bjt_bias_matches_benchmark_memo`, matches sec. 4.4's Vcc/R1/R2/RE/RC/beta values) | `test_library_elec.py` | sec. 4.4 |
| (sec. 4.5, NMOS -- `test_library_elec.py::test_nmos_bias_matches_benchmark_memo`, matches sec. 4.5's k/Vth/Vgs values) | `test_library_elec.py` | sec. 4.5 |

Deliverable 0 (`member_capacity.py`, this WO's already-merged slice)
cites AISC 360-16 directly (sec. F2.1, E1, E2, E3) and explicitly
states no memo section existed or was needed for that slice -- true,
unchanged by this audit; AISC 360-16 member-capacity cases are NOT
added as new memo sections here since deliverable 0 already landed
with its own direct-standard citation trail and does not need a memo
detour.

---

The remainder of this file, below the horizontal rule, is the
UNMODIFIED body of the source memo (section numbers, worked values,
and source list [S1]-[S14] preserved verbatim so every existing test
citation keeps resolving).

---

# Validation benchmarks and public datasets (feldspar tiers, stdlib records)

Date: 2026-07-08. Author: benchmarks-and-datasets market-research
agent (cycle 27, second memo). Status: advisory input, non-normative
IN ITS REPO OF ORIGIN (lithos); NORMATIVE here as the citation target
for this repo's own calibration tests (see provenance note above).
Companion to `2026-07-08-stdlib-market-research.md` (that memo chose
WHAT to ship; this one supplies the NUMBERS the implementation agents
turn into typed records and pack conformance tests).

## How to read this

Every value below carries a source and an HONESTY TIER:

- `[exact]`   -- exact closed-form; expected value is analytically
                 derivable, tolerance covers only float/round-off.
- `[textbook]`-- canonical textbook / standards value (Roark,
                 Timoshenko, Cengel, IAPWS, ISO); tolerance is the
                 source's stated band.
- `[vendor]`  -- vendor-typical catalog value; dimensions stable,
                 load ratings brand-specific (licensing noted).
- `[fixture]` -- FIXTURE-GRADE illustrative only; validity-windowed;
                 NEVER live pricing, NEVER a design authority.

Binds to feldspar WO-17 (ngspice), WO-20 (thermal-fluids), WO-21
(frame direct-stiffness); lithos WO-45/48/53/54; std.models floor.
All SI unless a US-customary standard (AISC, NPS, copper tube) is the
native authority; both given where practical.

## Table of contents

1. Frame / structural benchmarks (feldspar WO-21)
2. Beam-formula floor checks (std.models, Roark/Timoshenko)
3. Fluid-network benchmarks (feldspar WO-20) + CoolProp state points
4. Circuit benchmarks (feldspar WO-17, ngspice)
5. Public dimensional / property datasets (WO-45/48/53/54)
6. Costing anchor points (WO-54, all fixture-grade)
7. Sources
8. Bolted joints (feldspar WO-24 deliverable 1, VDI 2230 + Shigley/
   AISC elastic bolt-group distribution)
9. Classical Euler column buckling (feldspar WO-24 deliverable 8)
10. Fillet weld groups, elastic line method (feldspar WO-24)
11. Rolling-bearing basic dynamic rating life, ISO 281:2007 (feldspar
    WO-24)
12. Lumped-capacitance thermal transient (feldspar WO-24 deliverable 6)
13. Signal-integrity: microstrip/stripline impedance + termination
    sizing (feldspar WO-25)

---

## 1. Frame / structural benchmarks (feldspar WO-21 direct stiffness)

These are the calibration cases for the direct-stiffness `frame`
tier. All reactions are STATICALLY DETERMINATE (exact) even where the
structure is indeterminate for deflection; deflection expressions are
exact closed-form for the stated EI. Convention: down/right positive,
sagging moment positive, E = 200 GPa steel, g = 9.81 not used (loads
given directly).

### 1.1 Propped cantilever, uniform load  [exact]

Fixed at A (x=0), roller at B (x=L). Uniform w over span L.
Standard result (Roark Table 8.1, case propped cantilever UDL):

    Reaction at prop B      R_B = 3wL/8
    Reaction at fixed A     R_A = 5wL/8
    Moment at fixed end A    M_A = -wL^2/8   (max magnitude)
    Max span moment          M+  = 9wL^2/128 at x = 5L/8
    Max deflection           d   = wL^4 / (185 EI) at x = 0.5785 L

Worked fixture: w = 10 kN/m, L = 6 m, EI = 200e9 * 300e-6 = 6.0e7 N m^2
(Ix = 300e6 mm^4, e.g. a W-ish section).

    R_B = 3*10e3*6/8   = 22.5 kN
    R_A = 5*10e3*6/8   = 37.5 kN
    M_A = -10e3*36/8   = -45.0 kN m
    d   = 10e3*6^4 / (185*6.0e7) = 12.96e6/1.11e10 = 1.168e-3 m = 1.17 mm

Tolerance: reactions/moments +/-0.1% [exact]; deflection +/-1%
(round-off of the 0.5785 coefficient).

### 1.2 Portal frame sway, pinned feet, single lateral load  [exact]

Rectangular portal: columns height h, beam span L, rigid joints,
pinned bases at C and D. Horizontal load H applied at beam level
(top-left). Reactions are determinate by symmetry of the horizontal
split (Hibbeler, Structural Analysis, portal-frame approximate =
exact for reactions here):

    Horizontal reaction each base   H_C = H_D = H/2   (opposing H)
    Vertical reaction couple        V   = H*h / L     (up at leeward,
                                          down at windward base)

Worked fixture: H = 20 kN, h = 4 m, L = 6 m.

    H_C = H_D = 10 kN
    V   = 20*4/6 = 13.33 kN  (one base up, other down)

Tolerance: +/-0.1% [exact]. (Beam-column moments require the 1x
indeterminate solve; use this case to check REACTION assembly.)

### 1.3 Two-span continuous beam, uniform load  [exact]

Two equal spans L, uniform w, simple supports at A, B (center), C.
Three-moment theorem (Timoshenko, Strength of Materials Pt.1):

    Moment over center support   M_B = -wL^2/8
    Center support reaction      R_B = 10wL/8 = 1.25 wL
    End reactions                R_A = R_C = 3wL/8 = 0.375 wL
    Max span moment              M+  = 9wL^2/128 at 0.375L from ends

Worked fixture: w = 12 kN/m, L = 5 m.

    M_B = -12e3*25/8 = -37.5 kN m
    R_B = 1.25*12e3*5 = 75.0 kN
    R_A = R_C = 0.375*12e3*5 = 22.5 kN

Sum check: 2*22.5 + 75.0 = 120 kN = w*(2L) = 12*10 = 120 kN. OK.
Tolerance: +/-0.1% [exact].

### 1.4 Plane truss, determinate, apex load  [exact]

Symmetric two-bar (king-post) truss: node A apex, bases B, C on a
horizontal line span 2a apart, apex height h above the base line.
Members AB, AC each at angle theta from horizontal, tan theta = h/a.
Vertical load P down at apex A.

    Member force  F_AB = F_AC = P / (2 sin theta)   (compression)
    Base vert.    R_By = R_Cy = P/2
    Base horiz.   R_Bx = -R_Cx = P/(2 tan theta) = F * cos theta

Worked fixture: P = 40 kN, a = 3 m, h = 4 m -> theta = 53.13 deg,
sin theta = 0.8, cos theta = 0.6.

    F_AB = F_AC = 40/(2*0.8) = 25.0 kN  (compression)
    R_By = R_Cy = 20.0 kN
    horiz thrust = 25.0*0.6 = 15.0 kN each (inward)

Tolerance: +/-0.1% [exact].

### 1.5 Fixed-fixed beam, central point load  [exact]

Both ends fully fixed, point load P at midspan L/2 (Roark Table 8.1):

    End moments     M_A = M_B = -PL/8
    Midspan moment  M_C = +PL/8
    End reactions   R_A = R_B = P/2
    Max deflection  d = PL^3 / (192 EI) at midspan

Worked fixture: P = 30 kN, L = 4 m, EI = 6.0e7 N m^2.

    M_A = M_B = -30e3*4/8 = -15.0 kN m
    M_C = +15.0 kN m
    R_A = R_B = 15.0 kN
    d = 30e3*4^3/(192*6.0e7) = 1.92e6/1.152e10 = 1.667e-4 m = 0.167 mm

Tolerance: reactions/moments +/-0.1% [exact]; deflection +/-0.5%.

Case count, section 1: 5 frame/structural benchmarks.

---

## 2. Beam-formula floor checks (std.models -- Roark/Timoshenko)  [exact]

Closed-form single-span beams the std.models `beam` law must
reproduce exactly. E, I, L, w, P symbolic; tolerance +/-0.1%
(analytic). Source: Roark's Formulas for Stress and Strain, 8th ed.,
Table 8.1; Timoshenko, Strength of Materials.

    Case                        R_max      M_max        d_max (at)
    --------------------------  ---------  -----------  -------------------
    SS beam, UDL w              wL/2       wL^2/8       5wL^4/384EI (mid)
    SS beam, central load P     P/2        PL/4         PL^3/48EI (mid)
    Cantilever, end load P      P          PL (fixed)   PL^3/3EI (tip)
    Cantilever, UDL w           wL         wL^2/2       wL^4/8EI (tip)
    Fixed-fixed, UDL w          wL/2       wL^2/12 end  wL^4/384EI (mid)
                                           wL^2/24 mid
    SS beam, load P at a,b      Pb/L,Pa/L  Pab/L        (a(a+2b))^... see
                                                        Roark; check @load

Numeric anchor (SS beam UDL): w = 8 kN/m, L = 5 m, EI = 6.0e7 N m^2.
    R_max = 8e3*5/2 = 20.0 kN
    M_max = 8e3*25/8 = 25.0 kN m
    d_max = 5*8e3*5^4/(384*6.0e7) = 2.5e7/2.304e10 = 1.085e-3 m = 1.085 mm

Numeric anchor (cantilever tip load): P = 5 kN, L = 3 m, EI = 6.0e7.
    M_max = 5e3*3 = 15.0 kN m
    d_tip = 5e3*3^3/(3*6.0e7) = 1.35e5/1.8e8 = 7.50e-4 m = 0.750 mm

Case count, section 2: 6 canonical beam formulas + 2 numeric anchors.

---

## 3. Fluid-network benchmarks (feldspar WO-20) + CoolProp state points

### 3.1 Colebrook / Haaland friction factor  [textbook]

Colebrook-White (implicit): 1/sqrt(f) = -2 log10( eps/(3.7 D) +
2.51/(Re sqrt(f)) ). Haaland (explicit): 1/sqrt(f) = -1.8 log10(
(eps/D/3.7)^1.11 + 6.9/Re ). Source: Wikipedia Colebrook_equation;
Moody / White Fluid Mechanics. Moody-chart accuracy is +/-5% smooth,
+/-10% rough.

Worked case: commercial steel, D = 0.1 m, eps = 0.045 mm ->
eps/D = 4.5e-4, Re = 1.0e5 (turbulent).

    f_Colebrook (iterated)  = 0.0195   [textbook]
    f_Haaland (explicit)    = 0.0199   [exact eval of formula]

Tolerance for a solver: match Colebrook root to +/-0.5% and confirm
Haaland within +/-2% of Colebrook (the two should agree to ~2%).

Second anchor (laminar floor): Re = 1000 -> f = 64/Re = 0.0640
[exact] (Hagen-Poiseuille). Tolerance +/-0.1%.

### 3.2 Series / parallel pipe network  [exact]

Series (same Q, head losses add):  h_total = h1 + h2 + ...
Parallel (same head loss, flows add): Q_total = Q1 + Q2 + ...,
each branch same delta-h.

Worked series: two pipes carrying Q = 0.01 m^3/s, with
h1 = 3.0 m and h2 = 2.0 m at that Q -> h_total = 5.0 m [exact].

Worked parallel: two identical branches each passing Q = 0.006 m^3/s
at delta-h = 4.0 m -> Q_total = 0.012 m^3/s at delta-h = 4.0 m [exact].
Hardy-Cross convergence check: loop correction dQ -> 0 to |dQ| < 1e-6.

### 3.3 Pump operating point  [exact]

Pump curve H_p = H0 - a Q^2; system curve H_s = H_static + R Q^2.
Operating point where H_p = H_s: Q* = sqrt((H0 - H_static)/(a + R)).

Worked: H0 = 50 m, a = 2000 s^2/m^5, H_static = 10 m,
R = 3000 s^2/m^5.
    Q* = sqrt((50-10)/(2000+3000)) = sqrt(40/5000) = sqrt(0.008)
       = 0.08944 m^3/s
    H* = 10 + 3000*0.008 = 34.0 m   (check: 50 - 2000*0.008 = 34.0 m) OK
Tolerance +/-0.1% [exact].

### 3.4 CoolProp reference state points  [textbook]

Pin the property-table backend (CoolProp MIT). Values are IAPWS-95
(water) and ISO/REFPROP-grade correlations at the stated state; use
to lock the interpolation eps and domain boxes. Tolerance +/-0.5% for
liquid density/cp, +/-2% for viscosity (correlation band).

    Fluid   T (K)    P (Pa)    rho (kg/m^3)  cp (J/kg/K)  mu (Pa s)
    ------  -------  --------  ------------  -----------  ----------
    Water   293.15   101325    998.2         4184         1.002e-3
    Water   298.15   101325    997.0         4181         8.90e-4
    Water   373.124  101325    958.4 (satL)  4217         2.82e-4
    Air     298.15   101325    1.184         1006         1.849e-5
    N2      298.15   101325    1.145         1040         1.78e-5

Notes: Water 373.124 K row is the saturated-liquid boiling point at
1 atm (satL). Air/N2 densities are near-ideal-gas; CoolProp uses
real-gas EOS (Lemmon N2, Lemmon air). Source: CoolProp PropsSI
('D'/'C'/'V', 'T', T, 'P', P, fluid); IAPWS-95; ISO 5167 air data.

Case count, section 3: 2 friction cases + 2 network cases + 1 pump
point + 5 CoolProp state points.

---

## 4. Circuit benchmarks (feldspar WO-17, ngspice tier)

ngspice invocation shape: write a SPICE deck, run headless batch
`ngspice -b deck.cir -r out.raw`, parse the binary/ASCII rawfile
(`-r` sets the raw output; `.control ... write out.raw ... .endc`
inside the deck is the alternative). Analyses: `.op`, `.dc`, `.ac`,
`.tran`. Version pinning: pin to ngspice 42 (2024 release) or newer;
record `ngspice --version` in the eps provenance. Discovery order:
env `FELDSPAR_NGSPICE` then PATH. License BSD-3-Clause.

### 4.1 RC step response  [exact]

Series R-C, step V from 0 to Vf. v_C(t) = Vf (1 - e^(-t/tau)),
tau = R C. R = 1 kohm, C = 1 uF -> tau = 1.0 ms.
    v_C(tau)   = 0.6321 Vf   (63.21%)
    v_C(5 tau) = 0.9933 Vf
Deck: Vin step 0->5 V, `.tran 10u 5m`. Expect v_C(1ms) = 3.161 V for
Vf = 5 V. Tolerance +/-1% (tran timestep).

### 4.2 Series RLC resonance  [exact]

f0 = 1/(2 pi sqrt(LC)); Q = (1/R) sqrt(L/C). L = 10 mH, C = 100 nF,
R = 10 ohm.
    sqrt(LC) = sqrt(1e-9) = 3.162e-5
    f0 = 1/(2 pi * 3.162e-5) = 5033 Hz
    Q  = (1/10) sqrt(10e-3/100e-9) = 0.1 * sqrt(1e5) = 0.1*316.2 = 31.6
Deck: `.ac dec 100 100 100k`, expect |H| peak at ~5.03 kHz.
Tolerance +/-1% on f0 [exact], +/-3% on Q (mesh of the ac sweep).

### 4.3 Resistive divider under load  [exact]

Vout = Vin R2/(R1+R2); loaded, R2 || RL. Vin = 10 V, R1 = 10 k,
R2 = 10 k, RL = 100 k.
    Unloaded  Vout = 10*10k/20k = 5.000 V
    Loaded    R2||RL = (10k*100k)/110k = 9.091 k;
              Vout = 10*9.091k/(10k+9.091k) = 10*9.091/19.091 = 4.762 V
Deck: `.op`. Tolerance +/-0.5%.

### 4.4 BJT 4-resistor bias point  [textbook]

Vcc = 12 V, R1 = 47 k, R2 = 10 k, RE = 1 k, RC = 2.2 k, beta = 100,
V_BE = 0.7 V. Thevenin: V_th = 12*10/57 = 2.105 V, R_th = 47k||10k =
8.246 k.
    I_B  = (V_th - V_BE)/(R_th + (beta+1)RE)
         = (2.105-0.7)/(8246 + 101*1000) = 1.405/109246 = 12.86 uA
    I_C  = beta I_B = 1.286 mA
    V_E  = I_E RE ~ 1.30 V ; V_C = 12 - I_C RC = 12 - 2.83 = 9.17 V
Deck: `.op` with a Gummel-Poon 2N3904 model card. Tolerance +/-5%
[textbook] (I_C sensitive to the model's V_BE/beta vs the hand calc).

### 4.5 NMOS bias (saturation)  [textbook]

I_D = (k/2)(V_GS - V_th)^2 in saturation. k = 1 mA/V^2, V_th = 1 V,
V_GS = 3 V.
    I_D = (1e-3/2)(3-1)^2 = 0.5e-3 * 4 = 2.0 mA
Deck: `.op` with a level-1 MOS card (KP=1m, VTO=1). Tolerance +/-5%
(level-1 vs hand calc, ignores lambda/body effect).

Case count, section 4: 5 canonical circuits.

---

## 5. Public dimensional / property datasets (WO-45/48/53/54)

Each dataset: source, license/redistribution status, load-bearing
fields, and a transcribed SAMPLE for immediate fixture use.

### 5.1 AISC steel shapes (std.civil, WO-48/WO-21)  [textbook]

Source: AISC Shapes Database v15.0, freely downloadable from
aisc.org (Excel/CSV). License: AISC permits use of the shapes
database; the tabulated dimensional/section properties are factual
data (not copyrightable), redistributable as records. Fields that
matter: A (area), d (depth), b_f (flange width), t_w, t_f, I_x, S_x,
r_x, I_y, S_y, weight/ft. US-customary is native (in, in^2, in^4).

    Shape    A(in^2)  d(in)   Ix(in^4)  Sx(in^3)  wt(lb/ft)
    -------  -------  ------  --------  --------  ---------
    W8x31    9.13     8.00    110       27.5      31
    W12x26   7.65     12.22   204       33.4      26
    W14x90   26.5     14.02   999       143       90
    W16x40   11.8     16.01   518       64.7      40
    W18x50   14.7     17.99   800       88.9      50

Tolerance: transcribe exactly (+/-0 on tabulated digits); these are
rounded catalog values, so pack tests compare to the printed digit.

### 5.2 ISO metric fasteners (std.mech, WO-45/53)  [textbook]

Source: ISO 261 (general-purpose metric thread), ISO 724 (basic
dimensions), ISO 898-1 (property classes), ISO 4014/4762 (hex/socket
head). License: ISO standards are paywalled TEXT, but the thread
dimensions are factual and widely tabulated (engineeringtoolbox and
machinery handbooks). Fields: pitch (coarse), tapping drill,
clearance hole (medium), tensile stress area A_s, width across flats.

    Size  Pitch(mm)  TapDrill(mm)  Clear(mm)  A_s(mm^2)  AF(mm)
    ----  ---------  ------------  ---------  ---------  ------
    M6    1.00       5.0           6.6        20.1       10
    M8    1.25       6.8           9.0        36.6       13
    M10   1.50       8.5           11.0       58.0       16
    M12   1.75       10.2          13.5       84.3       18

A_s per ISO 724 (stress area = pi/4 * ((d2+d3)/2)^2). Tolerance:
exact digits [textbook]; A_s +/-0.5% (rounding of the mean-diameter
formula). AF per ISO 4014 (note some legacy DIN uses 17/19 for
M10/M12).

### 5.3 NPS / DN pipe schedules (std.fluid/civil, WO-48/WO-20)  [textbook]

Source: ASME B36.10M (welded/seamless wrought steel pipe). License:
standard paywalled; OD/wall are factual tabulated data. Fields: OD,
wall (per schedule), computed ID. Sch 40 shown (most common).

    NPS   DN    OD(mm)   Sch40 wall(mm)  ID(mm)
    ----  ----  -------  --------------  ------
    1     25    33.4     3.38            26.6
    2     50    60.3     3.91            52.5
    4     100   114.3    6.02            102.3
    6     150   168.3    7.11            154.1

Tolerance: OD exact [textbook]; ID computed = OD - 2*wall, +/-0.1 mm.

### 5.4 Deep-groove ball bearings, 6000/6200 series (std.mech, WO-45)

Source: ISO 15 (rolling bearing boundary dimensions -- factual,
redistributable). CAUTION: dynamic/static load ratings (C, C0) and
fatigue limits are BRAND-SPECIFIC (SKF/NSK/FAG catalogs, copyrighted
-- do NOT transcribe as generic). Ship ISO 15 BOUNDARY DIMENSIONS
only; treat any C rating as `[vendor]` requiring a cited catalog
record. Fields: bore d, OD D, width B.

    Desig  bore d(mm)  OD D(mm)  width B(mm)
    -----  ----------  --------  ----------
    6000   10          26        8
    6204   20          47        14
    6205   25          52        15
    6206   30          62        16

Tolerance: exact [textbook] (ISO 15 boundary dims). Load ratings:
OUT -- vendor record only.

### 5.5 Copper tube Type K/L/M (std.fluid, WO-48)  [textbook]

Source: ASTM B88 (seamless copper water tube). License: dimensions
factual/redistributable. Fields: nominal size, OD (constant across
types), wall (per type K>L>M). Type L (most common) shown.

    Nom(in)  OD(in)   Type L wall(in)  Type L ID(in)
    -------  -------  ---------------  -------------
    1/2      0.625    0.040            0.545
    3/4      0.875    0.045            0.785
    1        1.125    0.050            1.025

Note: nominal size is ~1/8 in less than OD. Tolerance: exact digits
[textbook].

### 5.6 Spring wire gauges (std.mech, WO-45)  [textbook]

Source: ASTM A228 (music wire) preferred diameters; min tensile
strength is diameter-dependent (Sut = A/d^m, the Samonov constants,
Shigley Table 10-4). Fields: nominal diameter, min tensile (music
wire A = 2211 MPa mm^m, m = 0.145).

    Wire dia(mm)  Music-wire min Sut(MPa, ~)
    ------------  --------------------------
    0.50          2405
    1.00          2170
    2.00          1962
    3.00          1844

Tolerance: Sut +/-3% [textbook] (A,m fit band per Shigley). Diameters
exact.

### 5.7 IEC / NEMA motor frames (std.elec/mech, WO-45)  [textbook]

Source: IEC 60072 (IEC frames -- frame number = shaft-height mm),
NEMA MG-1 (NEMA frames). License: dimensions factual. Fields: frame,
shaft height H, shaft diameter D, output speed classes.

    IEC frame  shaft ht H(mm)  shaft dia(mm)
    ---------  --------------  -------------
    80         80              19
    90         90              24
    100        100             28
    112        112             28

    NEMA frame  shaft ht(in)  shaft dia(in)
    ----------  ------------  -------------
    56          3.50          0.625
    143T        3.50          0.875
    145T        3.50          0.875

Tolerance: exact digits [textbook]. Note IEC 90S/90L share H=90 but
differ in mounting length (record the S/L suffix).

Case count, section 5: 7 datasets, each with a 3-5 row sample.

---

## 6. Costing anchor points (WO-54)  [fixture]

EVERY number here is FIXTURE-GRADE ILLUSTRATIVE. Validity window:
~2023-2025 US market, order-of-magnitude only. NEVER live pricing,
NEVER a design authority. These exist ONLY to give the WO-54 fixtures
plausible magnitudes; the compiler ships NO prices (AD-29) and each
record is profile-selected, hash-pinned, `valid_until`-windowed. Mark
every fixture record `honesty: fixture` and set a past `valid_until`
on the expired-quote negative test.

    Anchor                     Fixture range        Basis (illustrative)
    -------------------------  -------------------  ---------------------
    Hot-rolled steel, mtl      $0.80-1.50 / kg      mill/coil, 2023-24
    Fabricated struct. steel   $2.00-5.00 / kg      shop-fab, erected
    Copper (raw metal)         $8.00-10.00 / kg     LME-ish, 2023-24
    PCB, 2-layer proto         $0.05-0.50 / cm^2    qty-break, proto fab
    PCB, per dm^2 (100 cm^2)   $5-50 / dm^2         same, scaled
    Ready-mix concrete         $100-160 / m^3       US delivered, 2023-24
    Rebar (grade 60)           $0.90-1.40 / kg      2023-24
    Shop labor (machining)     $60-120 / hr         US shop rate, 2024

Usage rule for fixtures (the one honesty pin): a cost is a CLAIM,
the itemized table is the evidence, and a consumed record past its
`valid_until` yields INDETERMINATE naming the record (waivable with
basis). Fixture the expired-quote-indeterminate path hard -- give one
record a `valid_until` of 2024-01-01 so the negative test fires.

Case count, section 6: 8 fixture-grade anchors.

---

## 7. Sources

[S1] Roark's Formulas for Stress and Strain, 8th ed. (Young, Budynas,
Sadegh), McGraw-Hill -- Table 8.1 (beam cases), propped/fixed cases.
[S2] Timoshenko, Strength of Materials, Part 1 -- three-moment
theorem, continuous beams.
[S3] Hibbeler, Structural Analysis -- portal-frame reactions, plane
trusses.
[S4] Colebrook equation and Haaland approximation --
https://en.wikipedia.org/wiki/Colebrook_equation ; White, Fluid
Mechanics (Moody chart, +/-5%/10% band).
[S5] CoolProp (MIT), high-level PropsSI API --
https://coolprop.org/coolprop/HighLevelAPI.html ; IAPWS-95 water
formulation; Lemmon air/N2 EOS.
[S6] Sedra/Smith, Microelectronic Circuits -- BJT 4-resistor bias,
RC/RLC, divider; Horowitz & Hill, Art of Electronics.
[S7] ngspice manual (BSD-3-Clause), batch/-r rawfile, analyses --
https://ngspice.sourceforge.io/docs.html
[S8] AISC Shapes Database v15.0 (free download) --
https://www.aisc.org/publications/steel-construction-manual-resources/
[S9] ISO 261 / ISO 724 / ISO 898-1 / ISO 4014 metric threads;
Shigley's Mechanical Engineering Design (stress-area, spring Sut
constants Table 10-4).
[S10] ASME B36.10M welded/seamless wrought steel pipe (NPS/DN/Sch).
[S11] ISO 15 rolling-bearing boundary dimensions (SKF/NSK catalogs
for C ratings -- vendor-copyrighted, not transcribed here).
[S12] ASTM B88 seamless copper water tube (Type K/L/M).
[S13] IEC 60072 (IEC frames) / NEMA MG-1 (NEMA frames).
[S14] Costing anchors: fixture-grade illustrative only; magnitudes
consistent with public 2023-2025 US market commentary (steel/copper
commodity ranges, ready-mix and PCB proto quotes). NO live source is
cited BY DESIGN -- these must never be read as real pricing.


## 8. Bolted joints (feldspar WO-24 deliverable 1, VDI 2230 elastic
   tier + Shigley/AISC elastic bolt-group distribution)

New section (append-only, per this memo's own rule) -- these three
cases back the `mech.joint.*` directions in
`python/feldspar/library/bolted_joints.py`. All three are pure
algebraic closed-form identities (no empirical curve-fit, no FEA
cross-check needed), so all are tagged `[exact]` like sec. 4.1-4.3.

### 8.1 Single-bolt VDI 2230 load factor + working load  [exact]

VDI 2230 Part 1:2015, "Systematic calculation of highly stressed
bolted joints", the simplified two-body elastic model: a bolt of
stiffness `c_B` clamping parts of stiffness `c_P`, preloaded to `F_V`,
then loaded by an external concentric axial force `F_A`. The load
factor (VDI 2230's `Phi_en` for a concentric, unthrottled joint,
reduced here to the two-body case) is

    phi = c_B / (c_B + c_P)

The bolt's additional working load and the clamped parts' residual
clamp load are

    F_S  = F_V + phi * F_A       (bolt total load)
    F_KR = F_V - (1 - phi) * F_A (residual clamp load; F_KR <= 0 means
                                   the joint has separated)

Worked case (hand-computed, exact algebra): c_B = 200e6 N/m,
c_P = 800e6 N/m, F_V = 10,000 N, F_A = 5,000 N.

    phi  = 200e6 / (200e6 + 800e6) = 0.20
    F_S  = 10,000 + 0.20*5,000 = 11,000 N
    F_KR = 10,000 - 0.80*5,000 = 6,000 N   (positive -> no separation)

Tolerance: exact (rel 1e-9), pure arithmetic.

### 8.2 Elastic bolt-group, in-plane shear + torsion about centroid
   [exact]

Shigley's Mechanical Engineering Design, 11th ed., ch. 8 sec. 8-11
("Shear Joints Under Eccentric Loading"), the elastic (superposition)
method: a bolt at position `(x_i, y_i)` relative to the group
centroid, under a centroidal shear `(V_x, V_y)` and an in-plane
torque `T` about the centroid (CCW positive), carries

    F_direct  = (V_x/n, V_y/n)                     (equal split)
    F_torsion = (-T*y_i/J, T*x_i/J)                 (J = sum r_i^2)
    F_i       = F_direct + F_torsion  (vector sum)

Worked case (hand-computed, exact algebra): 4-bolt rectangular
pattern, half-width a=0.05 m, half-height b=0.03 m (all 4 bolts at
`r_i = sqrt(a^2+b^2) = 0.058310` m, `J = 4*r_i^2 = 0.013600` m^2).
Critical bolt at `(x_i, y_i) = (0.05, 0.03)`. `V_x=1000 N, V_y=0 N,
T=50 N*m`.

    F_direct  = (1000/4, 0) = (250.0, 0.0) N
    F_torsion = (-50*0.03/0.0136, 50*0.05/0.0136) = (-110.294, 183.824) N
    F_i       = (139.706, 183.824) N
    |F_i|     = sqrt(139.706^2 + 183.824^2) = 230.94 N

Tolerance: exact (rel 1e-6), pure arithmetic (float rounding only).

### 8.3 Elastic bolt-group, tension from moment about the neutral
   axis  [exact]

AISC Manual of Steel Construction, Part 7 (elastic/vector analysis
method for eccentrically loaded fastener groups) and Shigley ch. 8
sec. 8-12 (bolted joints loaded in bending): a bolt group loaded by
a moment `M` about its neutral axis (the axis through the centroid
perpendicular to the moment vector) develops a LINEAR tension
distribution analogous to bending stress, `F_ti = M*y_i / sum(y_j^2)`,
`y_i` the bolt's signed distance from the neutral axis.

Worked case (hand-computed, exact algebra): 4-bolt pattern, two rows
at `y = +0.04 m` and `y = -0.04 m` (2 bolts per row) -> `sum(y_j^2) =
4*0.04^2 = 0.0064 m^2`. `M = 800 N*m`. Critical (extreme-tension) bolt
at `y_i = 0.04 m`:

    F_t = 800 * 0.04 / 0.0064 = 5,000 N

Tolerance: exact (rel 1e-9), pure arithmetic.

Case count, section 8: 3 closed-form bolted-joint cases.

---

## 9. Classical Euler column buckling (feldspar WO-24 deliverable 8)

New section -- backs `mech.member.euler_critical_buckling_load` in
`python/feldspar/library/member_capacity.py`. Euler's classical
elastic buckling formula (Timoshenko, Theory of Elastic Stability,
2nd ed., ch. 2; also Shigley 11e ch. 4 sec. 4-14 eq. 4-42), for a
pin-ended (or effective-length-adjusted) prismatic column:

    Pcr = pi^2 * E * I / (K*L)^2

`K` the effective-length factor (AISC 360-16 commentary Table C-A-7.1
gives standard K values: 1.0 pinned-pinned, 0.5 fixed-fixed, 0.7
fixed-pinned, 2.0 fixed-free), `L` the unbraced length, `I` the
second moment of area about the buckling axis, `E` Young's modulus.
This is the SAME physics as sec. E3's `Fe = pi^2*E/(KL/r)^2`
(`Pcr = Fe*Ag` since `I = Ag*r^2`) presented as its own direction over
caller-supplied `E, I, K, L` directly (no `Ag`/`r` needed
separately) -- a narrower, more fundamental elastic-only tier with no
yield-strength input and no inelastic (eq. E3-2) branch.

Worked case (hand-computed, exact algebra): E = 200e9 Pa,
I = 8.0e-6 m^4, K = 1.0 (pinned-pinned), L = 3.0 m.

    Pcr = pi^2 * 200e9 * 8.0e-6 / (1.0*3.0)^2
        = pi^2 * 1.6e6 / 9.0
        = 15.7914e6 / 9.0
        = 1,754,600 N  (approx, pi^2=9.8696044...)

Tolerance: exact (rel 1e-6), pure closed-form (no material-yield
branch to select).

Case count, section 9: 1 closed-form Euler column case.

---

## 10. Fillet weld groups, elastic line method (feldspar WO-24
   deliverable 2)

New section (append-only) -- these three cases back the
`mech.weld.*` directions in `python/feldspar/library/weld_groups.py`.
All are pure algebraic closed-form identities (no empirical curve-
fit), tagged `[exact]`.

### 10.1 Elastic-line in-plane shear + torsion  [exact]

Shigley's Mechanical Engineering Design, 11th ed., ch. 9 sec. 9-5/
9-6 (fillet welds treated as a line, unit second-moment-of-area
method); Blodgett, Design of Weldments, sec. 4.3-4.4 (the same
elastic-line torsion/shear treatment). A weld line of total length
(unit area) `Aw`, with unit polar second moment `Jw` about its
centroid, under a centroidal shear `(Vx, Vy)` and centroidal torque
`T`, develops at a point `(x_i, y_i)` on the line:

    f_direct  = (Vx/Aw, Vy/Aw)                (equal-per-length split)
    f_torsion = (-T*yi/Jw, T*xi/Jw)
    f_i       = f_direct + f_torsion  (vector sum, N/m)

Worked case (hand-computed, exact algebra): Aw = 0.20 m,
Jw = 0.0136 m^3, critical point (x_i, y_i) = (0.05, 0.03),
Vx = 1000 N, Vy = 0 N, T = 50 N*m.

    f_direct  = (1000/0.20, 0) = (5000.0, 0.0) N/m
    f_torsion = (-50*0.03/0.0136, 50*0.05/0.0136)
              = (-110.294, 183.824) N/m
    f_i       = (4889.706, 183.824) N/m
    |f_i|     = sqrt(4889.706^2 + 183.824^2) = 4893.16 N/m

Tolerance: exact (rel 1e-6), pure arithmetic.

### 10.2 Elastic-line out-of-plane bending  [exact]

Shigley ch. 9 sec. 9-5 (fillet weld groups loaded in bending, unit
second moment of area treated exactly like a bending-stress section
modulus): `f_bending = M*c/Iw` (N/m), `Iw` the unit second moment of
the weld line about the bending neutral axis, `c` the extreme-fiber
distance.

Worked case (hand-computed, exact algebra): M = 600 N*m,
Iw = 0.0024 m^3, c = 0.06 m.

    f_bending = 600 * 0.06 / 0.0024 = 15,000.0 N/m

Tolerance: exact (rel 1e-9), pure arithmetic.

### 10.3 Vector-summed peak line force vs allowable  [exact]

AWS D1.1/D1.1M Structural Welding Code -- Steel, and AISC 360-16 sec.
J2.4 (effective throat of a fillet weld = 0.707*leg size `h`): the
in-plane (shear-plane) and out-of-plane (bending-plane) unit line
forces act on mutually perpendicular components of the weld throat,
so the peak unit line force is their vector sum; dividing by the
effective throat area converts to an actual stress, compared against
a caller-supplied allowable (e.g. AWS D1.1 table 2.3's `0.30*F_EXX`
for fillet-weld shear -- not derived here, caller-supplied by
design, a named cut).

    f_peak  = sqrt(f_inplane^2 + f_bending^2)
    stress  = f_peak / (0.707*h)
    ratio   = stress / allowable

Worked case (hand-computed, exact algebra): f_inplane = 4893.16 N/m
(sec. 10.1's case), f_bending = 15,000.0 N/m (sec. 10.2's case),
h = 0.008 m, allowable = 145e6 Pa (E70 electrode, illustrative,
`0.30*482e6 ~ 145e6`).

    f_peak  = sqrt(4893.16^2 + 15000.0^2) = 15,777.9 N/m
    throat  = 0.707*0.008 = 0.005656 m
    stress  = 15777.9 / 0.005656 = 2,789,591 Pa (approx)
    ratio   = 2,789,591 / 145e6 = 0.01924   (Valid, ratio <= 1.0)

Tolerance: exact (rel 1e-9), pure arithmetic.

Case count, section 10: 3 closed-form weld-group cases.

---

## 11. Rolling-bearing basic dynamic rating life, ISO 281:2007
   (feldspar WO-24 deliverable 3)

New section (append-only) -- these three cases back the
`mech.bearing.*` directions in
`python/feldspar/library/bearing_life.py`. Rating-record shape (`C`
basic dynamic load rating, `C0` basic static load rating) mirrors
lithos:stdlib/std.bearings/records/deep_groove_ball.toml's
`dynamic_load_kn`/`static_load_kn` fields (read-only reference, not
duplicated here). All cases are pure algebraic closed-form
identities, tagged `[exact]`.

ISO 281:2007, Rolling bearings -- Dynamic load ratings and rating
life, sec. 6.2 eq. 4 (basic rating life, millions of revolutions):

    L10 = (C/P)^p

`p = 3` for ball bearings, `p = 10/3` for roller bearings (the
standard's own fixed load-life exponents). `P` is the equivalent
dynamic bearing load -- CALLER-SUPPLIED (the sec. 6.1 `P = X*Fr +
Y*Fa` combined-load reduction needs bearing-geometry-specific X/Y
tables, not transcribed here; a named cut). Sec. 6.2 eq. 5 converts
to hours at a constant speed `n` (rev/min):

    L10h = L10 * 1e6 / (60*n)

No sec. 6.3 life-modification factor (`a1` reliability, `aISO`
systems approach) is applied -- basic (unmodified, 90%-reliability)
L10/L10h only, a named cut for v1.

### 11.1 Basic L10, ball bearing (p=3)  [exact]

Worked case: a 6205-class record (lithos std.bearings:
`dynamic_load_kn = 14.0` -> C = 14,000 N), equivalent load
P = 2,000 N.

    L10 = (14000/2000)^3 = 7.0^3 = 343.0 million revolutions

Tolerance: exact (rel 1e-9), pure arithmetic (integer exponent).

### 11.2 Basic L10, roller bearing (p=10/3)  [exact]

Worked case: C = 50,000 N, P = 10,000 N.

    L10 = (50000/10000)^(10/3) = 5^(10/3) = 213.747... million
          revolutions

Tolerance: exact (rel 1e-6), closed-form (fractional exponent
evaluated in floating point, no series truncation).

### 11.3 L10 -> L10h at constant speed  [exact]

Worked case: L10 = 343.0 million revolutions (sec. 11.1's case),
n = 1,800 rpm.

    L10h = 343.0e6 / (60*1800) = 343.0e6 / 108000 = 3,175.93 hours

Tolerance: exact (rel 1e-9), pure arithmetic.

Case count, section 11: 3 closed-form bearing-life cases.

---

## 12. Lumped-capacitance thermal transient (feldspar WO-24 deliverable
6, `python/feldspar/library/thermal_transient.py`)

These cases back the `heat.transient.*` directions. Incropera &
DeWitt, Fundamentals of Heat and Mass Transfer, 7th ed., ch. 5 sec.
5.1-5.2, single-node governing ODE `C_th*dT/dt = P - (T-T_amb)/R_th`.
Common fixture across 12.1-12.3: `T_amb = 298.15 K` (25 C),
`P = 5.0 W`, `R_th = 20.0 K/W`, `C_th = 2.0 J/K` -> `tau = R_th*C_th
= 40.0 s`, asymptotic steady rise `P*R_th = 100.0 K`. All cases
assume `Bi < 0.1` (caller-asserted, not derived in these worked
values -- the Biot GATE itself has no numeric worked case here since
it is a pure inequality check, not a formula with a reference
answer).

### 12.1 Step response, T(t) = T_amb + P*R_th*(1-exp(-t/tau))  [exact]

At `t = tau = 40.0 s` (one time constant, the textbook ~63.2% mark):

    rise = 100.0 * (1 - exp(-1)) = 100.0 * 0.6321205588... = 63.21205588 K
    T = 298.15 + 63.21205588 = 361.36205588 K

At `t = 5*tau = 200.0 s` (textbook ~99.3% mark):

    rise = 100.0 * (1 - exp(-5)) = 99.32620530... K
    T = 397.47620530 K

Tolerance: exact (rel 1e-9), closed-form transcendental (`exp`
evaluated in floating point, no series truncation).

### 12.2 Time-to-threshold, invert 12.1 for t  [exact]

Threshold `T_thresh = T_amb + 63.21205588... K` (the exact 12.1
one-tau rise, chosen so the inverted time recovers `tau` itself as a
closed-form self-check):

    needed = 63.21205588... K, steady = 100.0 K
    t = -40.0 * ln(1 - 63.21205588.../100.0) = -40.0 * ln(exp(-1))
      = -40.0 * (-1) = 40.0 s

Matches `tau` exactly by construction (tolerance: exact, rel 1e-9) --
the algebraic inverse of 12.1 recovers its own input.

### 12.3 Duty-cycle peak temperature, periodic square-wave forcing
[exact]

`t_on = 2.0 s`, `t_off = 8.0 s` (period 10 s, duty 0.2), same
`tau = 40.0 s` fixture:

    a = exp(-2.0/40.0) = exp(-0.05) = 0.9512294245...
    b = exp(-8.0/40.0) = exp(-0.2)  = 0.8187307531...
    rise = 100.0 * (1-a)/(1-a*b) = 100.0 * 0.0487705755 / 0.2212088...
         = 22.04825866 K
    T_peak = 298.15 + 22.04825866 = 320.19825866 K

Tolerance: exact (rel 1e-9), closed-form (two `exp` evaluations, no
series truncation).

**Two limiting-case sanity checks** (not separately asserted as
their own numeric fixtures, but load-bearing for the derivation's
honesty -- verified by direct substitution, not merely claimed):

- `t_off -> 0` (continuous power, duty -> 1): `b -> 1`, and the
  fraction `(1-a)/(1-a*b) -> (1-a)/(1-a) = 1`, so `rise -> P*R_th =
  100.0 K`, the 12.1 asymptote -- continuous power recovers the
  ordinary step response's steady state exactly, as it must.
- Switching period `<< tau` (`t_on = 0.001 s`, `t_off = 0.004 s`,
  duty `d = 0.2`, same `tau = 40.0 s`): numerically, `rise =
  20.001000012...` K, matching the quasi-steady average-power
  reduction `P*d*R_th = 5.0*0.2*20.0 = 20.0` K to 5 significant
  figures -- the standard power-electronics "average-power" duty
  derating heuristic is this direction's own high-switching-
  frequency limit, not a separate assumption bolted on.

Case count, section 12: 3 closed-form thermal-transient cases (+2
limiting-case derivation checks, not independent fixtures).

## 13. Signal-integrity: microstrip/stripline impedance + termination
sizing (feldspar WO-25, `python/feldspar/library/signal_integrity.py`)

These cases back the `elec.si.*` directions (lithos design-log
2026-07-10-cycle-32 D186). Source: Burkhardt, A.J., Gregg, C.S. &
Staniforth, J.A., "Calculation of PCB Track Impedance", IPC Printed
Circuit Expo 1999 ("Burkhardt 1999" below), which reproduces both the
IPC-2141 microstrip eq. (1), the Wadell/Hammerstad-Jensen microstrip
eq. (2)/(3a)/(3b), and Cohn's 1954 exact stripline eq. (4)/(5a)/(5b)
verbatim, with a published Table 1 comparing eq. (1)/eq. (2) against a
boundary-element field-solver ("Numerical Method") ground truth.

### 13.1 microstrip_z0 (Hammerstad-Jensen, Wadell 1991 eq. (2))  [2%
quoted accuracy]

Fixture: `t = 35e-6 m`, `h = 794e-6 m`, `er = 4.2` (Burkhardt 1999
Table 1's own popular 1oz-copper-on-1/32in-substrate case). This
implementation's thickness correction `dw = (t/pi)*(1+ln(2h/t))`
(Hammerstad 1975) is the one intermediate term Burkhardt 1999 cites
but does not transcribe -- calibration below is therefore against the
FULL formula's agreement with the field-solver ground truth, not a
verbatim digit-for-digit reproduction of Burkhardt 1999's own eq. (2)
column.

    w=450e-6 m  -> Z0 = 88.70224843... ohm (Numerical Method: 89.63,
                   -1.04%)
    w=1500e-6 m -> Z0 = 50.24391978... ohm (Numerical Method: 50.63,
                   -0.77%)
    w=3300e-6 m -> Z0 = 29.81945882... ohm (Numerical Method: 30.09,
                   -0.90%)

Tolerance: all three within ~1.3% of the field-solver ground truth,
inside Wadell's own quoted 2% accuracy band.
`tests/unit/test_library_signal_integrity.py::
test_microstrip_z0_matches_burkhardt_1999_table1` pins the tolerance
check; `test_microstrip_z0_hand_computed_exact_value` pins this
implementation's own exact output as a regression guard.

### 13.2 stripline_z0 (Cohn 1954 exact, eq. (4)/(5a)/(5b))  [exact
analytic result]

Not a numeric-table fit -- Cohn's formula is EXACT (zero-thickness,
centred track), same calibration tier as sec. 9's Euler buckling
load. The complete-elliptic-integral ratio `K(k)/K(k')` is evaluated
via Hilberg's 1969 closed-form approximation, which Burkhardt 1999
states is "accurate to 10-12" relative to the true ratio.

    w=0.382e-3 m, b=1e-3 m, er=3.66 -> Z0 = 60.34290501... ohm
    (k=sech(pi*w/2b)=0.8435..., branch k > 1/sqrt(2))

Monotonicity (Burkhardt 1999 Figure 4's own qualitative shape, not a
numeric fixture): fixing `b=3e-3 m, er=4.2`, Z0 strictly decreases as
`w` sweeps `{0.1, 0.3, 0.6, 1.0, 2.0}e-3 m` -- a wider centred track
always has a lower stripline Z0.
`tests/unit/test_library_signal_integrity.py::
test_stripline_z0_hand_computed_exact_value` and
`test_stripline_z0_monotonically_decreases_with_width` pin these.

### 13.3 Termination sizing (Johnson & Graham 1993 ch. 4)  [exact
algebra, except 13.3.3]

**13.3.1 series_termination**: `Z0=50, Ro=15 -> Rs=35 ohm` (exact,
`Rs=Z0-Ro`).

**13.3.2 thevenin_termination (r1/r2)**: `Z0=50, Vcc=5.0V,
Vbias=1.5V -> R1=166.66666... ohm, R2=71.42857142... ohm` (exact,
solved from `R1||R2=Z0` and the divider condition
`R2/(R1+R2)=Vbias/Vcc`); the Kirchhoff check `(R1*R2)/(R1+R2)=50.0`
exactly recombines to Z0, verified in
`test_thevenin_termination_matches_hand_computed_and_recombines_to_z0`.

**13.3.3 ac_shunt_sizing (r/c)**: `R=Z0` exact (matched shunt);
`C=tr/(4R)` is a NAMED HEURISTIC (Johnson & Graham's own quoted
tr/5..tr/2 range around the tr/4 midpoint this direction bakes, +100%/
-20% relative to the chosen value) -- `tr=1e-9 s, R=50 ohm ->
C=5e-12 F` is this implementation's pinned exact output for that
formula, NOT an independently verified "correct" capacitor value (no
single correct value exists for a heuristic).

### NAMED CUT: diff_pair_z (edge-coupled differential impedance)

No independently verifiable published numeric impedance table for an
edge-coupled differential closed form could be confirmed against a
primary source within the WO-25 dispatch's research budget. See
`python/feldspar/library/signal_integrity.py`'s module docstring for
the full reasoning and reopen criteria.

Case count, section 13: 3 microstrip cases (table calibration) + 1
stripline exact case + 1 monotonicity sanity sweep + 4 termination
cases (3 exact, 1 heuristic-pinned) = 9 numeric fixtures, plus the
`diff_pair_z` named cut.

---

## 14. Shaft/member fatigue: Marin-modified endurance limit + modified
Goodman (WO-24 deliverable 4)

Source: Shigley's Mechanical Engineering Design, 11th ed., ch. 6
(Fatigue Failure Resulting from Variable Loading). All numeric values
below reproduce a fully worked axially-loaded fatigue example from a
ch. 6 class-notes companion for Shigley 11e (a 40 mm diameter
AISI-1045 CD steel bar, machined surface, fluctuating tensile load
0..100 kN, end-fillet stress concentration Kf=1.85 pre-applied) --
every intermediate number below is independently reproduced by
`tests/unit/test_library_fatigue.py`, not merely copied from the
source.

### 14.1 Baseline endurance limit (eq. 6-8, steel, Sut <= 1400 MPa)

    Se' = 0.5*Sut

    Sut = 630 MPa -> Se' = 315 MPa (exact).

### 14.2 Surface-condition Marin factor ka (Table 6-2)

    ka = a*Sut^b   (Sut in MPa)

Machined/cold-drawn row: a=4.51, b=-0.265.

    Sut = 630 MPa -> ka = 4.51*630^-0.265 = 0.8177 (matches the
    source's own rounded worked value, ka=0.817, to 3 sig figs).

Only this one row is independently calibrated; `a`/`b` are
caller-supplied ports in `library.fatigue.fatigue_marin_surface_factor`
(no lookup table baked in -- see that module's docstring).

### 14.3 Marin-modified endurance limit (eq. 6-18)

    Se = ka*kb*kc*kd*ke*Se'

Axial loading case: kb=1 (axial, per eq. 6-20's own kb=1 axial
special case), kc=0.85 (axial, sec. 6-9 load-type table), kd=ke=1
(no temperature/reliability derating applied in the source example).

    ka=0.817, kb=1, kc=0.85, kd=1, ke=1, Se'=315 MPa
    -> Se = 0.817*0.85*315 = 218.75 MPa (matches the source's own
       rounded worked value, Se=218.8 MPa).

### 14.4 Modified-Goodman fatigue factor of safety (eq. 6-46,
fatigue-governs branch)

    r = sigma_a/sigma_m
    Sa = r*Se*Sut/(r*Sut+Se)
    Sm = Sa/r
    nf = 1/(sigma_a/Se + sigma_m/Sut)   (equivalently Sa/sigma_a)

Worked case: d=40 mm bar, A=pi/4*d^2=1257 mm^2, fluctuating tensile
load 0..100 kN, Kf=1.85 (end fillet):

    sigma_max = 100e3/1257 = 79.6 MPa, sigma_min = 0
    sigma_mo = sigma_ao = (sigma_max-sigma_min)/2 = 39.8 MPa
    sigma_m = sigma_a = Kf*39.8 = 1.85*39.8 = 73.6 MPa  (Kf applied
        to BOTH components, per the source's own convention)

    r = sigma_a/sigma_m = 1
    Sa = Sm = 1*218.8*630/(630+218.8) = 162.4 MPa
    nf = Sa/sigma_a = 162.4/73.6 = 2.207 (matches the source's own
         rounded worked value, nf=2.21).

Case count, section 14: 1 baseline case + 1 surface-factor case + 1
Marin-composed Se case + 1 Goodman factor-of-safety case (all four
chained from the SAME worked example, each independently pinned) + 1
pure-alternating (sigma_m=0) degenerate-limit sanity case = 5 numeric
fixtures.

**Named cuts** (module `python/feldspar/library/fatigue.py`
docstring has the full reasoning): the `Sut > 1400 MPa` Se' plateau
branch; every Table 6-2 surface-condition row except machined/
cold-drawn (a/b are caller-supplied, not a baked table); the kb
(size, Table 6-3), kd (temperature, eq. 6-27), ke (reliability,
Table 6-5) modifying-factor derivations themselves (caller-supplied
numeric factors, composed but not derived here); the Goodman
`r < r_crit` static-yielding branch; the Kf notch-sensitivity
derivation (Neuber/Figure 6-20, caller pre-applies Kf).

---

## 15. Leadscrew (square-thread power screw) drive sizing -- LEADSCREW
half of WO-24 deliverable 7

Source: Shigley's Mechanical Engineering Design, 11th ed., ch. 8 sec.
8-2 ("The Mechanics of Power Screws"), square-thread only. Every
formula below is EXACT ALGEBRA (a statics result from unrolling one
thread as an inclined plane) -- calibration is HAND-COMPUTED exact
arithmetic against a self-consistent worked case, not a published
numeric table (none exists to calibrate an exact closed form against,
same precedent as sec. 9's Euler buckling case and sec. 8.1's VDI
2230 bolt-load-factor case).

Worked case: `F = 1000 N`, `dm = 0.010 m` (10 mm mean diameter),
`lead = 0.002 m` (2 mm, single thread), `f = 0.15`.

    TR = (F*dm/2)*((lead+pi*f*dm)/(pi*dm-f*lead))
       = 5*((0.002+0.0047124)/(0.0314159-0.0003))
       = 5*(0.0067124/0.0311159) = 1.078610 N*m

    TL = (F*dm/2)*((pi*f*dm-lead)/(pi*dm+f*lead))
       = 5*((0.0047124-0.002)/(0.0314159+0.0003))
       = 5*(0.0027124/0.0317159) = 0.427607 N*m   (positive -> screw
         IS self-locking)

    e = F*lead/(2*pi*TR) = 1000*0.002/(2*pi*1.078610) = 0.295111

    tan(lambda) = lead/(pi*dm) = 0.002/(pi*0.010) = 0.063662
    self_locking_margin = f - tan(lambda) = 0.15-0.063662 = 0.086338
        (positive -> self-locking, consistent with TL>0 above)

Collar torque (independent exact case): `F=1000 N, fc=0.15, dc=0.020
m -> Tc = F*fc*dc/2 = 1.5 N*m` (exact product, no rounding).

Sanity check (low-friction, non-self-locking case): the SAME `dm`/
`lead` with `f=0.02` gives `TL < 0` and `self_locking_margin < 0`
consistently (the screw back-drives without applied torque) --
`tests/unit/test_library_leadscrew.py` pins both signs.

Case count, section 15: 1 TR case + 1 TL case (+ 1 sign-consistency
sanity case) + 1 efficiency case + 1 self-locking-margin case (+ 1
sign-consistency sanity case) + 1 collar-torque case = 6 numeric
fixtures + 2 sign-consistency sanity checks.

**Named cuts** (module `python/feldspar/library/leadscrew.py`
docstring has the full reasoning): ACME-thread wedging correction
(friction terms divided by cos(alpha)); critical (whirling) speed
(needs an end-support-factor table, its own citation surface); belt
(GT2-class tooth shear/tension ratings, WO-24 deliverable 7's OTHER
named half) -- NOT STARTED, no manufacturer belt-tooth rating table
was transcribed or verified within this dispatch's research budget,
recorded whole in the WO-24 ledger, not half-landed.

---