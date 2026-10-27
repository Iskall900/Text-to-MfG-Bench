# A15 — DfM1 review, selected iteration10

**Status: CNC-oriented candidate only; NOT released for manufacture.**

## Nominal definition
- Material target: Aluminum 6061-T651 billet, material certificate required.
- One connected solid, bracket-only mass 189.532 g; six Ø10 load-path members, three Ø24×6 pads, 7 mm stage frame.
- Nominal Ø6.6 bores at all seven A15 centers. Telescope underside Z=0; stage mating face Y=−7.164. Production position, flatness and surface-finish tolerances were not specified; agree these with the assembly owner before drawings/NC release.
- Example stock allowance only: 125×100×165 mm billet (5.569 kg at nominal density). About 96.6% material removal; this is an expensive deep open-truss machining problem, not an economical plate bracket.

## Suggested process concept — not verified NC instructions
1. Use sacrificial billet clamping material; rough accessible pockets from indexed orientations, leaving stiffness stock on all slender members.
2. Index/5-axis contour open frame members while maintaining temporary support. Avoid relying on final Ø10 members for heavy roughing restraint.
3. Finish mounting faces and bores in controlled setups; validate datum transfer and remove sacrificial clamping stock without distorting interfaces.
4. Verify critical hole centers, mating-plane locations/flatness and dimensions by metrology after unclamping.

## Actual checks performed
- The exact CAD is one valid solid; no assembled floating members.
- Five separate envelope STEP files per interface: bolt, washer, head, straight insertion, driver (35 files). Boolean volumetric overlap with bracket is zero to the CAD check tolerance.
- Assumptions: Ø6.35 bolt; washer OD16/ID6.6/t1.6; head OD10/h6.5; straight insertion OD10.5×60; driver OD8×150 mm. These dimensions are not verified NAS620/NAS1352 dimensions.
- Insertion from +Z toward −Z for T holes; from +Y toward −Y for S holes. Actual bolt/thread arrangement and lengths are unresolved.
- Assumed washer bearing: full annulus 166.849986 mm² at each hole, checked using a 0.1mm material slice under the bearing face. `bearing_checks.json` records all seven results.
- T axis-to-outer-edge distance12 mm (bore-edge ligament8.7); stage nominal nearest outer-edge distance9.4975 mm (ligament6.1975). Minimum allowable values were not given; these are measured design values, not certified margins.
- Conservative assumed stage and telescope envelopes clear this selected candidate. The explicit cylinder does not clear under direct registration; see FINAL_REPORT.md.

## Unverified release blockers
- **Original STEP coordinate registration and keep-out:** mandatory; do not machine this candidate as an accepted fit.
- Exact cutter/holder access and reach into all intersections, risk of holder collision, deep-pocket chatter, 5-axis singularities and fixturing are not simulated.
- Round member intersections and access reliefs include re-entrant lines without fully specified CNC tool-radius blends. These require manufacturability review and probably a new, blended geometry iteration plus FEA; no such unanalysed change has been passed off as the selected model.
- No CAM project, NC code, setup-sheet validation, shop trial, CMM result, NAS fastener installation or hardware qualification exists.
- No material lot/thickness/temperature allowable substantiation or environmental test evidence exists.

CAD and screening are useful starting points, **not CNC or flight qualification**.
