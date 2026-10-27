# Iteration 10 — best-attempt 5-axis CNC geometric review

## Status
**Not CNC-qualified.** This is the final geometry within the 10-iteration budget; its frequency is 126.6192 Hz, failing the revised 200 Hz requirement. Nominal mass is 198.710 g, leaving only 1.290 g below 200 g, not a tolerance-qualified production margin.

## Geometry
Three circular mounting pads: radius 15.5 mm, thickness 8 mm, exact Z=0 bearing datum and 6.8 mm bores. Rear fan skins 3.2 mm, front fan skin 3 mm; 2.5 mm-wide stiffener rims extend 4.5 mm to each side (12–12.2 mm total local depth). Rear fan windows use nominal 6.5 mm borders and R3 internal corners. The front fan skin is solid. The stage mounting panel is 6 mm thick at exact Y=-7.164; 3.2 mm triangular cheeks and a 2.5 mm top rim form an open wedge to Y=42 mm. The top through-window is 37 × 28 mm with R4 corners. No closed cavity or fabricated stage/telescope details are included.

The attempted R0.8 pad-root blends **failed**, so roots in the actual STEP remain sharp. Window radii are present; do not conflate them with root fillets. Sharp/thin terminations around head-access cuts, acute junctions and 2.5 mm ribs are DfM concerns. No automated full minimum-wall-thickness or minimum-feature audit has been passed. These should be resolved before manufacture; the geometry/modal budgets do not permit another design here.

## Proposed process, not validation
Billet roughing, datum establishment, indexed through-bore drilling, and 5-axis indexed milling of the fan openings and wedge recesses. Continuous rails and plates avoid cylindrical strut networks. Large open side/back/top spaces provide candidate approach directions; they are not proof that a selected tool/holder can reach every transition. Thin rims need a distortion-aware roughing sequence, suitable clamping, and finishing support. Internal windows are through-cuts rather than deep blind slots, but local relief/root access still needs CAM and supplier review.

## Hardware access evidence
`access_check.json` and separate STEP envelopes test all seven exact interfaces. Assumed washer OD16/ID6.8/thickness1.5 mm; head OD11/height6.5 mm; driver OD11/reach100 mm; complete insertion sweep radius8/length100 mm. Full annular washer bearing area is checked. All these generic envelopes pass. Base screws approach +Z/travel -Z, stage screws approach +Y/travel -Y. Shank envelope is only the portion through the bracket because actual length/engagement is unspecified. Real NAS1352/NAS620 compatibility, engagement, supporting threads and assembly tolerances are **unverified**.

Conservative stage/telescope half-box proxies have no overlap, but real bodies and optical-path dimensions are not supplied. The cylindrical keep-out is **waived by user**, not passed. No physical hardware testing, CAM, cutter/holder simulation, fixture validation, temperature qualification or supplier approval exists.
