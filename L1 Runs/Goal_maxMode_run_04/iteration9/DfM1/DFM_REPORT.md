# A15 iteration9: 5-axis CNC design review (not qualification)

- Material: 6061-T651 billet; procurement certificate and temperature allowables pending.
- One connected structural solid. Bracket mass: 198.386 g.
- Envelope: 112.89 × 87.50 × 148.00 mm.
- Integral, continuous plate/gusset load paths, nominal web thickness 3.50 mm; no intersecting cylindrical-member network.
- Stage and base bearing plates are 6 mm thick. Seven Ø6.8 mm clearance holes accept nominal Ø6.35 mm shanks; depth/diameter = 0.88.
- Base pads Ø24 mm, outer edge distance 12 mm. Stage minimum nominal outer edge distance is approximately 10 mm.
- Main through-window internal corners R3 mm; front windows R4 mm. Use ≤Ø6 mm cutters for R3 details; finish fillet surfaces with appropriate ball tools.
- Windows are open through thin planar walls, not deep narrow blind pockets. Faceted planar front gussets and accessible rear/side windows permit indexed or simultaneous 5-axis approaches.
- Rough from billet with stock support; machine pad plane Z=0 and telescope holes in one datum setup, stage face Y=-7.164 and its pattern in a controlled indexed setup. Finish thin webs last, using soft-jaw/fixture support and light cuts. Deburr edges without altering bearing planes or hole axes.
- Candidate stock envelope approximately 120 × 95 × 155 mm; high material removal and thin-web distortion make this a demanding, costly machining concept.
- Some web intersections retain sharp re-entrant edges. Tool radius, reach, holder clearance, corner blending, setup workholding and residual-stress distortion require a machinist/CAM review. No machine simulation or produced part exists; CNC qualification is UNVERIFIED.

## Fastener access
`access_and_keepout_checks.json` records separate shank, washer, head, straight screw insertion and driver intersections, plus washer bearing area. All dimensions are explicit screening assumptions, not measured NAS hardware. Separate STEP bodies are provided for every envelope. Contact with a bearing face is allowed; positive overlap is not. Washer placement is separate from straight screw insertion.

## Keep-outs and interface inconsistency
The supplied cylinder is in STEP coordinates, but no STEP model or STEP-to-A15 transform was provided. Literal overlap is 9278.654 mm³. T1 and T2 lie inside that literal cylinder at Z=0. This cannot be resolved by changing bracket ribs while retaining their prescribed mounting interfaces. The user text says four pads, whereas A15.json specifies exactly three telescope interfaces. No fourth mounting hole or invented transform was added. The real-hardware fit remains UNVERIFIED; literal cylinder clearance FAILS.
