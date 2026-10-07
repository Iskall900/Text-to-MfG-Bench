# Deterministic five-axis CNC DfM checker

Checks a single closed Build123d solid, directly or imported from STEP, and
writes `report.txt` and `violations.csv`. Every manufacturing limit, sampling
count, measurement tolerance, and tool dimension is in `config.json`. Its
manufacturing numbers are **editable examples**, not material/machine standards.

## Run

From the repository root, using the local environment created for this checker:

```sh
DfM/.venv/bin/python DfM/check_dfm.py part.step --config DfM/config.json --output-dir results
DfM/.venv/bin/python DfM/verify_dfm.py
```

To recreate the environment, use **CPython 3.13.2** (also pinned by
`.python-version`), then install the full lock:

```sh
python3.13 -m venv DfM/.venv
DfM/.venv/bin/python -m pip install -r DfM/requirements.lock
```

The lock includes Build123d 0.13.0 and OCP 8.0.1.1.0. Verification used macOS
arm64. Other operating systems/architectures need compatible wheels and their
own verification run; reproducibility is within the same runtime/platform.
The checker itself adds no dependency beyond Build123d's dependencies.

For a direct Build123d Part or Solid (including `BuildPart.part`):

```python
from build123d import Box
from DfM.check_dfm import check, load_config, write_reports

config = load_config("DfM/config.json")
config["limits"]["min_wall_mm"] = 1.5
report = check(Box(20, 20, 1), config)
write_reports(report, "results")
print(report.status)
```

Run that code from the repository root with the same virtual environment.
`check` also accepts a config JSON path; omitting config uses the example file.
It copies input geometry and configuration. No repair, unit rescaling, meshing,
or execution of a supplied Python model file takes place. STEP uses Build123d's
importer; direct objects must already be modeled in **millimeters**.

## Configuration

All keys are required. Unknown/duplicate keys, nonfinite values, booleans in
numeric fields, unsupported tools, invalid lengths, and invalid counts fail
validation. Limits/tolerances are positive; corner radius and holder clearance
may be zero. `report_precision` is an integer from 0 through 12.

| Limit | Meaning |
|---|---|
| `min_wall_mm` | Minimum sampled material thickness, mm |
| `min_internal_radius_mm` | Minimum pocket sidewall corner radius, mm |
| `min_accessible_directions` | Minimum clear directions for any **one** tool |
| `max_pocket_depth_width` | Maximum pocket depth / caliper width, dimensionless |
| `min_hole_diameter_mm` | Minimum validated cylindrical bore diameter, mm |
| `max_hole_depth_mm` | Maximum **full geometric** hole depth, mm |

`face_u`/`face_v` define a fixed midpoint UV grid **on every face**. The trimmed
face classifier excludes grid points outside its wires. Sampling is uniform
in parameters, not physical distance: the counts do not guarantee a maximum
surface spacing. `edge_points` fixes the number of equal edge-position samples,
including endpoints, and the number of circumferential bore probes.
`hole_axial_samples` fixes the equally spaced interior bore stations (the
default three give 25%, 50%, 75%). There is no adaptive refinement or
silent sample cap.

`approach_directions` defines a deterministic Fibonacci sphere, supplemented
in fixed order by the sample normal and recognized pocket/bore axes; coincident
directions are deduplicated using `angular_rad`. `pocket_angles` defines a
half-circle caliper grid, supplemented by exact planar-wall normal directions
so rotated rectangular pockets retain their known width.

`linear_mm` controls point/face classification, ray-hit merging, analytic
feature matching, contact separation, and dimensional comparisons.
Normal-side probes use `max(32*linear_mm, bbox_diagonal*1e-9)` to stay beyond
the classifier boundary band. `angular_rad` is the angular tolerance in
radians, `ratio` is the ratio comparison tolerance, and
`collision_volume_mm3` is the permitted Boolean overlap volume. Comparisons
use unrounded measurements: minimum checks fail below `limit - tolerance`;
maximum checks fail above `limit + tolerance`. Direction counts compare exactly.

Each tool defines `name`, `kind` (`flat` or `ball`), `diameter_mm`,
`cutting_length_mm`, `shank_diameter_mm`, `stickout_mm`, `holder_diameter_mm`,
`holder_length_mm`, and `holder_clearance_mm`. Cutting length must not exceed
stickout; a ball cutter's cutting length must reach at least its ball radius.
Stickout is tip-to-holder distance. Holder clearance expands its cylinder
radially and at both axial ends. Tool names must be unique printable strings.

## Measurement methods

The script has one commented section for each of the six checks:

1. **Wall thickness:** classify the material side, cast an inward normal ray,
   and measure its first continuous material interval to the exit. Report
   every undersized tested location, including floors. No percentile filter,
   face-centroid-only shortcut, or air-gap measurement is used.
2. **Internal corner radius:** examine recognized pocket sidewall fillets and
   concave, non-tangent sidewall junctions. Native cylindrical radius measures
   a fillet; a sharp junction measures zero. Circular bores, convex edges,
   and floor-to-wall junctions do not receive this policy.
3. **Accessibility/undercuts:** place each finite cutter at the correct surface
   contact, then check continuous straight insertion against the finished
   solid using serial B-rep Boolean intersections. The flat cutter contacts
   its bottom rim when tilted and can side-mill with its axis tangent to the
   surface. The ball center is offset by its radius along the outward normal.
   Cutter, shank, and holder are tested, including holder clearance. Intentional
   contact is allowed within configured tolerances. Counts stop once one tool
   meets the minimum; a reported failure uses the best tool's tested count.
4. **Pocket ratio:** recognize a closed convex constant-section pocket with
   a planar floor and coplanar verified rim. Depth is the rim-to-floor
   projection, width the minimum B-rep caliper width over configured directions.
   Rectangular/rounded rectangular pockets work at arbitrary orientations.
   Width is a caliper definition, not an inscribed-circle or cutter-fit metric.
5. **Hole diameter:** distinguish inward cylindrical bores from bosses and
   blends, merge connected same-radius split faces, and verify circumferential
   enclosure at the fixed stations before reporting `2*radius`. Check each
   cylindrical diameter of a stepped hole separately.
6. **Hole depth:** group connected coaxial bore steps and measure the entire
   axial cavity, including recognized attached conical mouths/drill points.
   Through-holes use their full length; they are never halved for drilling from
   both ends. Remote surfaces beyond a hole mouth do not extend its depth.

Open-sided, nonconvex, stepped, tapered, and freeform cavities that cannot be
reliably classified are listed as **inconclusive**, while supported measurements
and observed violations are retained. Signed principal curvature relative to
the verified material normal also detects concave open bowls whose normal rays
exit through the mouth. Fixed probes can still miss tiny
interruptions or features between samples; no feature recognizer is exhaustive.

## Reports, statuses, and identity

`report.txt` begins with violation totals for all six checks, then measured
coverage/inconclusive counts, violations, a separate inconclusive section,
face mapping, runtime, and the complete normalized config plus SHA256.

`violations.csv` is a single table of confirmed **policy failures** with exactly:

```text
check_name,x,y,z,face_id,measured_value,limit,explanation
```

The CSV contains no summary block or inconclusive rows. Read `report.txt` or
`report.inconclusive` as well: an empty CSV alone is not a green result.
Accessibility failure means no sufficient approaches **under the configured
finite direction/tool policy**, not proof that every conceivable toolpath fails.

Coordinates lie on the implicated surface in the model's world frame. Face IDs
are **one-based `solid.faces()` traversal IDs**, preserved on the copied B-rep;
the text report provides surface type and a representative surface point for
each ID. IDs are stable for the same persisted input, not promised across
remodeling, re-export, topology changes, or kernel versions.

Reports count distinct reported locations, not manufactured features.
Only completely identical findings are deduplicated. Rows sort by the fixed
check order, face ID, coordinates, measurements, and explanation. All numbers
use fixed configured precision; negative zero is normalized. Both files use
UTF-8 and LF. Timestamps, elapsed times, memory addresses, and source/output
absolute paths are omitted. Each destination is replaced atomically after both
reports have been rendered; the pair is not a transactional filesystem update.

| Status / CLI exit | Meaning |
|---|---|
| `SCREENED` / `0` | No findings at tested locations; **not certification** |
| `FAIL` / `1` | At least one policy violation; inconclusive findings may also exist |
| Input/runtime error / `2` | Invalid input/config, dependency/geometry error, or output failure |
| `INCONCLUSIVE` / `3` | No violations, but at least one unresolved measurement/feature |

The public `Report` exposes `violations`, `inconclusive`, `coverage`, `face_map`,
`config_json`, `runtime`, `precision`, and `status`. `write_reports` returns the
two report paths. Kernel measurement failures are inconclusive; malformed
input geometry is rejected. Input must contain one valid closed solid, not an
assembly, shell, surface, mesh, or STL.

## Determinism and verification

The same persisted B-rep, config, pinned runtime, and platform produce identical
report bytes. All kernel operations run serially; sample order and thresholds
are fixed. There is no randomness, wall-clock dependency, or topology hash in
report identity. Rebuilt shapes with different topology and runs on different
kernel/Python/platform versions are outside that guarantee.

The standard-library verification script creates real Build123d geometry for
thin walls, rotated sharp/filleted pockets, holes, split cylindrical faces,
blind/through/stepped/conical holes, side milling, ball contact, trapped cavities,
and holder collisions. It checks limit boundaries, configuration errors,
unsupported features, surface coordinates, input preservation, native collision
failure handling, CSV/text agreement, and byte-identical output from fresh STEP
CLI processes with different Python hash seeds. Missing dependencies fail the
run: no geometry tests silently skip.

This assumes unrestricted five-axis orientation around the **finished part**.
It does not model fixtures, workholding, stock-removal order, feeds/speeds,
machine travel/rotary limits, or continuous changing-orientation CAM paths.
Straight insertion is intentionally a simpler geometric accessibility policy.
Finite sampling and analytic feature recognition are reproducible screening,
not an exhaustive CNC manufacturability guarantee.
