"""Deterministic B-rep CNC screening; see README.md for coverage and units.

The six policy checks below are deliberately separate. All geometry operations
are serial, all sample counts/tolerances come from config, and no meshing or
random sampling is used. A sampled pass is not a global manufacturability proof.
"""
from __future__ import annotations

import argparse
import copy
import csv
from dataclasses import dataclass
import hashlib
import io
import json
from math import cos, isfinite, pi, sin, sqrt
from pathlib import Path
import platform
import sys
from importlib.metadata import version

from build123d import Face, Shape, Vector, import_step
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepClass import BRepClass_FaceClassifier
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.BRepGProp import BRepGProp
from OCP.BRepLProp import BRepLProp_SLProps
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeSphere
from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane, GeomAbs_Cone
from OCP.GProp import GProp_GProps
from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector
from OCP.TopAbs import TopAbs_COMPOUND, TopAbs_COMPSOLID, TopAbs_IN, TopAbs_OUT, TopAbs_REVERSED, TopAbs_SOLID
from OCP.TopoDS import TopoDS_Iterator
from OCP.gp import gp_Ax2, gp_Dir, gp_Lin, gp_Pnt, gp_Pnt2d

CHECK_NAMES = ("MIN_WALL_THICKNESS", "INTERNAL_CORNER_RADIUS", "TOOL_ACCESSIBILITY",
               "POCKET_DEPTH_WIDTH", "MIN_HOLE_DIAMETER", "MAX_HOLE_DEPTH")
CSV_FIELDS = ("check_name", "x", "y", "z", "face_id", "measured_value", "limit", "explanation")
XYZ = tuple[float, float, float]
KERNEL_ERRORS = (RuntimeError, ValueError, TypeError, ArithmeticError)


def xyz(p) -> XYZ:
    return (float(p.X()), float(p.Y()), float(p.Z()))


def add(a, b):
    return tuple(a[i] + b[i] for i in range(3))


def sub(a, b):
    return tuple(a[i] - b[i] for i in range(3))


def mul(a, k):
    return tuple(v * k for v in a)


def dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def norm(a):
    return sqrt(dot(a, a))


def unit(a):
    return mul(a, 1 / norm(a))


def frame(axis):
    reference = min(((1., 0., 0.), (0., 1., 0.), (0., 0., 1.)), key=lambda d: abs(dot(d, axis)))
    first = unit(cross(axis, reference))
    return first, cross(axis, first)


def canonical_axis(a):
    a = unit(a)
    largest = max(range(3), key=lambda i: abs(a[i]))
    return a if a[largest] >= 0 else mul(a, -1)


@dataclass(frozen=True)
class Violation:
    check_name: str
    x: float
    y: float
    z: float
    face_id: int
    measured_value: float
    limit: float
    explanation: str


@dataclass(frozen=True)
class Inconclusive:
    check_name: str
    face_id: int
    location: XYZ
    explanation: str


@dataclass(frozen=True)
class Report:
    violations: tuple[Violation, ...]
    inconclusive: tuple[Inconclusive, ...]
    coverage: tuple[tuple[str, int], ...]
    face_map: tuple[tuple[int, str, XYZ], ...]
    config_json: str
    runtime: str
    precision: int

    @property
    def status(self):
        return "FAIL" if self.violations else "INCONCLUSIVE" if self.inconclusive else "SCREENED"


@dataclass(frozen=True)
class Sample:
    point: XYZ
    normal: XYZ


@dataclass
class FaceData:
    id: int
    face: Face
    surface: BRepAdaptor_Surface
    samples: tuple[Sample, ...]
    concave: bool = False

    @property
    def kind(self):
        return self.surface.GetType()


@dataclass(frozen=True)
class Pocket:
    floor: FaceData
    axis: XYZ
    depth: float
    width: float
    walls: tuple[FaceData, ...]


@dataclass(frozen=True)
class Bore:
    faces: tuple[FaceData, ...]
    axis: XYZ
    origin: XYZ
    radius: float
    low: float
    high: float


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate config key: {key}")
        result[key] = value
    return result


def load_config(config=None):
    """Accept a JSON path or dictionary; validate and return an independent copy."""
    if config is None:
        config = Path(__file__).with_name("config.json")
    if isinstance(config, (str, Path)):
        with Path(config).open(encoding="utf-8") as stream:
            config = json.load(stream, object_pairs_hook=_unique_object)
    if not isinstance(config, dict):
        raise ValueError("config must be a dictionary or JSON path")
    config = copy.deepcopy(config)
    schema = {
        "limits": {"min_wall_mm", "min_internal_radius_mm", "min_accessible_directions",
                   "max_pocket_depth_width", "min_hole_diameter_mm", "max_hole_depth_mm"},
        "sampling": {"face_u", "face_v", "edge_points", "hole_axial_samples", "approach_directions", "pocket_angles"},
        "tolerances": {"linear_mm", "angular_rad", "ratio", "collision_volume_mm3"},
    }
    if set(config) != set(schema) | {"tools", "report_precision"}:
        raise ValueError("config sections must be limits, sampling, tolerances, tools, report_precision")
    for section, keys in schema.items():
        if not isinstance(config[section], dict) or set(config[section]) != keys:
            raise ValueError(f"incorrect keys in {section}")
        for name, value in config[section].items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
                raise ValueError(f"{name} must be a finite number")
            if value < 0 or (value == 0 and name != "min_internal_radius_mm"):
                raise ValueError(f"{name} must be positive (corner radius may be zero)")
    for name, value in config["sampling"].items():
        minimum = 3 if name == "edge_points" else 4 if name == "pocket_angles" else 1
        if type(value) is not int or value < minimum:
            raise ValueError(f"{name} must be an integer >= {minimum}")
    count = config["limits"]["min_accessible_directions"]
    if type(count) is not int or count < 1:
        raise ValueError("min_accessible_directions must be an integer >= 1")
    precision = config["report_precision"]
    if type(precision) is not int or not 0 <= precision <= 12:
        raise ValueError("report_precision must be an integer from 0 to 12")
    if config["tolerances"]["angular_rad"] >= 0.1:
        raise ValueError("angular_rad must be below 0.1 radians")
    tools = config["tools"]
    if not isinstance(tools, list) or not tools:
        raise ValueError("tools must be a nonempty list")
    dimensions = {"diameter_mm", "cutting_length_mm", "shank_diameter_mm", "stickout_mm",
                  "holder_diameter_mm", "holder_length_mm", "holder_clearance_mm"}
    names = []
    for tool in tools:
        if not isinstance(tool, dict) or set(tool) != dimensions | {"name", "kind"}:
            raise ValueError("each tool must define name, kind, and all seven dimensions")
        if tool["kind"] not in ("flat", "ball"):
            raise ValueError("tool kind must be flat or ball")
        if not isinstance(tool["name"], str) or not tool["name"] or not tool["name"].isprintable():
            raise ValueError("tool name must be nonempty printable text")
        names.append(tool["name"])
        for name in dimensions:
            value = tool[name]
            if type(value) not in (int, float) or not isfinite(value) or value < 0 or (value == 0 and name != "holder_clearance_mm"):
                raise ValueError(f"invalid tool dimension: {name}")
        if tool["cutting_length_mm"] > tool["stickout_mm"]:
            raise ValueError("cutting length must not exceed stickout")
        if tool["kind"] == "ball" and tool["cutting_length_mm"] < tool["diameter_mm"] / 2:
            raise ValueError("ball cutting length must be at least its radius")
    if len(set(names)) != len(names):
        raise ValueError("tool names must be unique")
    return config


class Geometry:
    """Per-run state: topology, exact line intersections, and solid classifier."""
    def __init__(self, part, config):
        if isinstance(part, (str, Path)):
            if Path(part).suffix.lower() not in (".step", ".stp"):
                raise ValueError("only STEP file input is supported")
            part = import_step(part)
        if not isinstance(part, Shape):
            raise TypeError("part must be a Build123d Part/Solid or STEP path")
        solids = part.solids()
        if len(solids) != 1 or part.wrapped is None:
            raise ValueError("input must contain exactly one closed solid")
        content = part.wrapped
        while content.ShapeType() in (TopAbs_COMPOUND, TopAbs_COMPSOLID):
            children = TopoDS_Iterator(content)
            if not children.More():
                raise ValueError("empty geometry wrapper")
            content = children.Value()
            children.Next()
            if children.More():
                raise ValueError("input contains additional geometry beyond its single solid")
        if content.ShapeType() != TopAbs_SOLID:
            raise ValueError("input must contain only one solid, without loose geometry")
        if not BRepCheck_Analyzer(part.wrapped).IsValid():
            raise ValueError("input B-rep is invalid")
        if any(not BRep_Tool.IsClosed_s(shell.wrapped) for shell in solids[0].shells()):
            raise ValueError("input solid has an open shell")
        # Copy before querying/colliding: callers keep their geometry and caches.
        self.solid = copy.deepcopy(solids[0])
        self.config = config
        self.tol = config["tolerances"]["linear_mm"]
        self.angle = config["tolerances"]["angular_rad"]
        self.span = self.solid.bounding_box().diagonal
        if not isfinite(self.span) or self.span <= self.tol or self.solid.volume <= 0:
            raise ValueError("input must be a nonempty positive-volume solid")
        self.eps = max(32 * self.tol, self.span * 1e-9)
        self.classifier = BRepClass3d_SolidClassifier(self.solid.wrapped)
        self.intersector = IntCurvesFace_ShapeIntersector()
        self.intersector.Load(self.solid.wrapped, self.tol)
        self.violations = []
        self.inconclusive = []
        self.coverage = {name: 0 for name in CHECK_NAMES}
        self.faces = []
        for index, face in enumerate(self.solid.faces(), 1):
            surface = BRepAdaptor_Surface(face.wrapped, True)
            data = FaceData(index, face, surface, ())
            self.faces.append(data)
            samples = []
            try:
                u0, u1 = surface.FirstUParameter(), surface.LastUParameter()
                v0, v1 = surface.FirstVParameter(), surface.LastVParameter()
                if not all(isfinite(x) for x in (u0, u1, v0, v1)):
                    raise ValueError("unbounded face")
                for i in range(config["sampling"]["face_u"]):
                    u = u0 + (u1-u0) * (i+0.5) / config["sampling"]["face_u"]
                    for j in range(config["sampling"]["face_v"]):
                        v = v0 + (v1-v0) * (j+0.5) / config["sampling"]["face_v"]
                        if BRepClass_FaceClassifier(face.wrapped, gp_Pnt2d(u, v), self.tol).State() != TopAbs_IN:
                            continue
                        props = BRepLProp_SLProps(surface, u, v, 2, self.tol)
                        if not props.IsNormalDefined():
                            continue
                        p = xyz(surface.Value(u, v))
                        n = xyz(props.Normal())
                        if face.wrapped.Orientation() == TopAbs_REVERSED:
                            n = mul(n, -1)
                        if self.state(add(p, mul(n, self.eps))) == TopAbs_IN:
                            n = mul(n, -1)
                        if (self.state(add(p, mul(n, self.eps))) != TopAbs_OUT or
                                self.state(sub(p, mul(n, self.eps))) != TopAbs_IN):
                            for name in (CHECK_NAMES[0], CHECK_NAMES[2]):
                                self.unknown(name, data, p, "sample normal/material side is ambiguous")
                            continue
                        if props.IsCurvatureDefined():
                            sign = 1 if dot(n, xyz(props.Normal())) >= 0 else -1
                            if max(sign*props.MinCurvature(), sign*props.MaxCurvature())*self.span > sin(self.angle):
                                data.concave = True
                        samples.append(Sample(p, n))
            except KERNEL_ERRORS:
                for name in (CHECK_NAMES[0], CHECK_NAMES[2]):
                    self.unknown(name, data, self.point(data), "face sampling failed in the geometry kernel")
            data.samples = tuple(samples)
            if not samples:
                for name in (CHECK_NAMES[0], CHECK_NAMES[2]):
                    self.unknown(name, data, self.point(data), "fixed UV grid found no valid interior surface samples")
        # ponytail: quadratic topology matching; use an indexed OCCT map if large
        # parts make this dominant. Never use process-dependent topology hashes.
        self.edges = []
        for data in self.faces:
            for edge in data.face.edges():
                entry = next((item for item in self.edges if item[0].is_same(edge)), None)
                if entry is None:
                    self.edges.append((edge, [data]))
                elif data not in entry[1]:
                    entry[1].append(data)

    def state(self, p):
        self.classifier.Perform(gp_Pnt(*p), self.tol)
        return self.classifier.State()

    def point(self, face):
        if face.samples:
            return face.samples[0].point
        edges = face.face.edges()
        if edges:
            return tuple(edges[0].position_at(0.5))
        return tuple(face.face.vertices()[0])

    def unknown(self, name, face, point, explanation):
        self.inconclusive.append(Inconclusive(name, face.id, point, explanation))

    def fail(self, name, face, point, measured, limit, explanation):
        self.violations.append(Violation(name, *point, face.id, measured, limit, explanation))

    def hits(self, p, d, low, high):
        self.intersector.Perform(gp_Lin(gp_Pnt(*p), gp_Dir(*d)), low, high)
        if not self.intersector.IsDone():
            raise RuntimeError("line intersection failed")
        hits = []
        for i in range(1, self.intersector.NbPnt()+1):
            face = self.intersector.Face(i)
            face_id = next(f.id for f in self.faces if f.face.wrapped.IsSame(face))
            hits.append((self.intersector.WParameter(i), face_id, xyz(self.intersector.Pnt(i))))
        return sorted(hits, key=lambda item: (item[0], item[1], item[2]))

    def edge_points(self, edge):
        count = self.config["sampling"]["edge_points"]
        return [tuple(edge.position_at(i/(count-1))) for i in range(count)]


# ============================================================================
# 1. MINIMUM WALL THICKNESS
# Measurement: exact B-rep normal-ray material interval at each fixed UV sample.
# Intersections are sorted and intervals classified so a tangency or an air gap
# is never confused with a wall. The measured length includes the start offset.
# ============================================================================
def check_wall_thickness(g):
    name = CHECK_NAMES[0]
    limit = g.config["limits"]["min_wall_mm"]
    for face in g.faces:
        for sample in face.samples:
            try:
                origin = sub(sample.point, mul(sample.normal, g.eps))
                direction = mul(sample.normal, -1)
                hits = g.hits(origin, direction, 0, g.span * 2)
                distances = []
                for t, _, _ in hits:
                    if t > g.tol and (not distances or t-distances[-1] > g.tol):
                        distances.append(t)
                end = None
                for i, t in enumerate(distances):
                    next_t = distances[i+1] if i+1 < len(distances) else g.span*2
                    if self_interval_outside(g, origin, direction, t, next_t):
                        end = t + g.eps
                        break
                if end is None:
                    raise ValueError("no material exit")
                g.coverage[name] += 1
                if end < limit - g.tol:
                    g.fail(name, face, sample.point, end, limit,
                           "normal-ray wall thickness (mm) is below the minimum")
            except KERNEL_ERRORS:
                g.unknown(name, face, sample.point, "normal-ray material exit could not be measured")


def self_interval_outside(g, p, d, first, second):
    return g.state(add(p, mul(d, (first+second)/2))) == TopAbs_OUT


# Shared feature recognition for checks 2/4 and 5/6. Only proved analytic
# feature families are measured; other cavity geometry gets an explicit review.
def group_bores(g, bores, same_radius):
    """Merge every connected interval, including a new interval bridging groups."""
    groups = []
    for bore in bores:
        matches = [group for group in groups if
                   norm(sub(group[0].origin, bore.origin)) <= g.tol and
                   dot(group[0].axis, bore.axis) >= cos(g.angle) and
                   (not same_radius or abs(group[0].radius-bore.radius) <= g.tol) and
                   bore.low <= max(b.high for b in group)+g.tol and
                   bore.high >= min(b.low for b in group)-g.tol]
        groups = [group for group in groups if group not in matches] + [
            [bore] + [member for group in matches for member in group]]
    return groups


def recognize_bores(g):
    candidates = []
    for face in g.faces:
        if face.kind != GeomAbs_Cylinder or not face.samples:
            continue
        cylinder = face.surface.Cylinder()
        axis = canonical_axis(xyz(cylinder.Axis().Direction()))
        origin = xyz(cylinder.Location())
        origin = sub(origin, mul(axis, dot(origin, axis)))
        sample = face.samples[0]
        radial = sub(sub(sample.point, origin), mul(axis, dot(sub(sample.point, origin), axis)))
        if dot(sample.normal, unit(radial)) > -cos(g.angle):
            continue  # convex bosses are not bores
        points = [p for edge in face.face.edges() for p in g.edge_points(edge)]
        low = min(dot(sub(p, origin), axis) for p in points)
        high = max(dot(sub(p, origin), axis) for p in points)
        candidates.append(Bore((face,), axis, origin, float(cylinder.Radius()), low, high))
    groups = []
    for members in group_bores(g, candidates, same_radius=True):
        first = members[0]
        groups.append(Bore(tuple(f for b in members for f in b.faces), first.axis, first.origin,
                           first.radius, min(b.low for b in members), max(b.high for b in members)))
    result = []
    for bore in groups:
        first, second = frame(bore.axis)
        closed = True
        count = g.config["sampling"]["edge_points"]
        # Fixed axial/circumferential probes prove sampled enclosure. Partial
        # cylindrical blends fail this test and remain pocket-corner candidates.
        axial_count = g.config["sampling"]["hole_axial_samples"]
        for axial_index in range(axial_count):
            fraction = (axial_index+1)/(axial_count+1)
            center = add(bore.origin, mul(bore.axis, bore.low+(bore.high-bore.low)*fraction))
            if g.state(center) != TopAbs_OUT:
                closed = False
                break
            for i in range(count):
                radial = add(mul(first, cos(2*pi*(i+0.5)/count)), mul(second, sin(2*pi*(i+0.5)/count)))
                if (g.state(add(center, mul(radial, bore.radius-g.eps))) != TopAbs_OUT or
                        g.state(add(center, mul(radial, bore.radius+g.eps))) != TopAbs_IN):
                    closed = False
                    break
            if not closed:
                break
        if closed:
            result.append(bore)
    return result


def bore_cones(g, bores):
    """Recognize coaxial inward conical ends/entries attached to validated bores."""
    pairs = []
    for face in g.faces:
        if face.kind != GeomAbs_Cone or not face.samples:
            continue
        cone = face.surface.Cone()
        axis = canonical_axis(xyz(cone.Axis().Direction()))
        origin = xyz(cone.Location())
        origin = sub(origin, mul(axis, dot(origin, axis)))
        radial = sub(sub(face.samples[0].point, origin),
                     mul(axis, dot(sub(face.samples[0].point, origin), axis)))
        if dot(face.samples[0].normal, radial) >= 0:
            continue
        for bore in bores:
            if norm(sub(origin, bore.origin)) > g.tol or dot(axis, bore.axis) < cos(g.angle):
                continue
            if any(face in adjacent and any(f in adjacent for f in bore.faces) for _, adjacent in g.edges):
                pairs.append((face, bore))
    return pairs


def recognize_pockets(g, bores):
    previous_unknown = len(g.inconclusive)
    bore_ids = {face.id for bore in bores for face in bore.faces}
    pockets = []
    for floor in g.faces:
        if floor.kind != GeomAbs_Plane or not floor.samples:
            continue
        n = floor.samples[0].normal
        floor_level = dot(floor.samples[0].point, n)
        neighbors = []
        boundary = []
        for edge, adjacent in g.edges:
            if floor not in adjacent:
                continue
            for other in adjacent:
                if other is not floor:
                    neighbors.append(other)
            boundary.append(edge)
        neighbors = list({f.id: f for f in neighbors}.values())
        if not neighbors or all(f.id in bore_ids for f in neighbors):
            continue  # circular bore bottom is not an extra milling pocket
        levels = [dot(p, n) for other in neighbors for edge in other.face.edges() for p in g.edge_points(edge)]
        if not levels or max(levels) <= floor_level + g.eps:
            continue  # external top faces have no rising sidewalls
        extends_below = min(levels) < floor_level - g.eps
        if extends_below:
            rising = False
            for other in neighbors:
                side_levels = [dot(p, n) for edge in other.face.edges() for p in g.edge_points(edge)]
                if min(side_levels) >= floor_level-g.eps and max(side_levels) > floor_level+g.eps:
                    rising = True
            if not rising:
                continue  # exterior face, rather than a recessed floor
        try:
            if extends_below:
                raise ValueError("pocket has an open side or stepped sidewalls")
            if len(floor.face.wires()) != 1:
                raise ValueError("floor has islands or additional boundary loops")
            walls = []
            for wall in neighbors:
                if wall.id in bore_ids:
                    raise ValueError("pocket intersects a bore")
                if not wall.samples:
                    raise ValueError("wall has no surface samples")
                if wall.kind == GeomAbs_Plane:
                    if abs(dot(wall.samples[0].normal, n)) > sin(g.angle):
                        raise ValueError("walls are not perpendicular to the floor")
                elif wall.kind == GeomAbs_Cylinder:
                    a = xyz(wall.surface.Cylinder().Axis().Direction())
                    if abs(dot(a, n)) < cos(g.angle):
                        raise ValueError("curved wall is not a constant-section extrusion")
                else:
                    raise ValueError("freeform, tapered, or blended floor-to-wall geometry")
                walls.append(wall)
            tops = []
            for wall in walls:
                wall_points = [p for edge in wall.face.edges() for p in g.edge_points(edge)]
                top = max(dot(p, n) for p in wall_points)
                bottom = min(dot(p, n) for p in wall_points)
                if abs(bottom-floor_level) > g.eps:
                    raise ValueError("stepped or nonconstant pocket walls")
                tops.append(top)
            rim_level = tops[0]
            if max(tops)-min(tops) > g.eps:
                raise ValueError("pocket rim is not coplanar")
            # Every floor boundary must have a rising wall, and each wall's top
            # edge must join a face in the rim plane (closed mouth, no open slot).
            for edge, adjacent in g.edges:
                if floor in adjacent and (len(adjacent) != 2 or not any(f in walls for f in adjacent)):
                    raise ValueError("pocket has an open side")
                if not any(f in walls for f in adjacent):
                    continue
                points = g.edge_points(edge)
                if all(abs(dot(p, n)-rim_level) <= g.eps for p in points):
                    rim = [f for f in adjacent if f not in walls]
                    if len(rim) != 1 or rim[0].kind != GeomAbs_Plane or not rim[0].samples or abs(dot(rim[0].samples[0].normal, n)) < cos(g.angle):
                        raise ValueError("pocket has an unverified or open rim")
            # Convexity: the inward-facing wall normal must place every floor
            # boundary sample in the same free-space half-plane. This rejects
            # reentrant outlines instead of letting a convex hull hide a neck.
            points = [p for edge in boundary for p in g.edge_points(edge)]
            for wall in walls:
                for sample in wall.samples:
                    plane_point = sub(sample.point, mul(n, dot(sample.point, n)-floor_level))
                    if any(dot(sub(p, plane_point), sample.normal) < -g.eps for p in points):
                        raise ValueError("pocket cross-section is nonconvex")
            first, second = frame(n)
            widths = []
            directions = [wall.samples[0].normal for wall in walls if wall.kind == GeomAbs_Plane]
            for i in range(g.config["sampling"]["pocket_angles"]):
                angle = pi*i/g.config["sampling"]["pocket_angles"]
                directions.append(add(mul(first, cos(angle)), mul(second, sin(angle))))
            # Supplement the fixed grid with exact planar-wall directions: a
            # rotated rectangular pocket must retain its known caliper width.
            for d in directions:
                # Native B-rep extrema in each direction (not chord endpoints)
                # preserve rounded-wall width without polygon approximation.
                from build123d import Plane
                local_face = floor.face.moved(Plane(origin=(0, 0, 0), x_dir=d, z_dir=n).location.inverse())
                widths.append(local_face.bounding_box().size.X)
            width = min(widths)
            if width <= g.eps:
                raise ValueError("pocket width is unresolved")
            pockets.append(Pocket(floor, n, rim_level-floor_level, width, tuple(walls)))
        except KERNEL_ERRORS as exc:
            # Exception text here is from our fixed recognition rules only.
            reason = str(exc) if isinstance(exc, ValueError) else "kernel feature measurement failed"
            g.unknown(CHECK_NAMES[3], floor, g.point(floor), reason)
            g.unknown(CHECK_NAMES[1], floor, g.point(floor), "sidewall corner recognition is incomplete: " + reason)
    # A curved cavity can have no planar floor at all. Flag inward freeform
    # surfaces rather than claiming no pockets/holes from absence of recognition.
    recognized = ({f.id for p in pockets for f in (p.floor, *p.walls)} | bore_ids |
                  {face.id for face, _ in bore_cones(g, bores)})
    # A wall may look like an open "floor" from a different axis. Once it is
    # part of a verified pocket/bore, that alternate candidate is resolved.
    g.inconclusive[previous_unknown:] = [r for r in g.inconclusive[previous_unknown:]
                                         if r.face_id not in recognized or r.check_name not in (CHECK_NAMES[1], CHECK_NAMES[3])]
    for face in g.faces:
        if face.id in recognized:
            continue
        if not face.samples or face.concave:
            inward = True
        else:
            inward = False
            for sample in face.samples:
                # A concave surface lies ahead of another part boundary along
                # its outward normal. External convex surfaces do not.
                try:
                    if g.hits(add(sample.point, mul(sample.normal, g.eps)), sample.normal, 0, g.span*2):
                        inward = True
                        break
                except KERNEL_ERRORS:
                    inward = True
                    break
        if inward:
            for name in (CHECK_NAMES[1], CHECK_NAMES[3], CHECK_NAMES[4], CHECK_NAMES[5]):
                g.unknown(name, face, g.point(face), "cavity surface is outside verified analytic pocket/hole recognition")
    return pockets


# ============================================================================
# 2. INTERNAL CORNER RADIUS (POCKET SIDEWALLS ONLY)
# Measurement: native cylindrical fillet radius, or zero at a non-tangent,
# concave junction of two prismatic sidewalls. Floor-wall edges, bosses, and
# circular bores are excluded. The policy concerns the pocket cross-section.
# ============================================================================
def check_corner_radius(g, pockets):
    name = CHECK_NAMES[1]
    limit = g.config["limits"]["min_internal_radius_mm"]
    for pocket in pockets:
        for wall in pocket.walls:
            if wall.kind != GeomAbs_Cylinder:
                continue
            radius = float(wall.surface.Cylinder().Radius())
            g.coverage[name] += 1
            if radius < limit - g.tol:
                g.fail(name, wall, g.point(wall), radius, limit,
                       "concave pocket sidewall fillet radius (mm) is below the minimum")
        ids = {f.id for f in pocket.walls}
        for edge, adjacent in g.edges:
            walls = [f for f in adjacent if f.id in ids]
            if len(walls) != 2:
                continue
            points = g.edge_points(edge)
            if norm(cross(unit(sub(points[-1], points[0])), pocket.axis)) > sin(g.angle):
                continue
            p = points[len(points)//2]
            try:
                n1 = tuple(walls[0].face.normal_at(Vector(p)))
                n2 = tuple(walls[1].face.normal_at(Vector(p)))
                if dot(n1, n2) >= cos(g.angle):
                    continue  # tangent blend seam has no sharp corner
                # Material at p - (n1+n2)*epsilon establishes an inside corner.
                if g.state(sub(p, mul(unit(add(n1, n2)), g.eps))) != TopAbs_IN:
                    continue
                g.coverage[name] += 1
                if 0 < limit - g.tol:
                    g.fail(name, min(walls, key=lambda f: f.id), p, 0, limit,
                           "sharp concave pocket sidewall junction has zero radius (mm)")
            except KERNEL_ERRORS:
                g.unknown(name, walls[0], p, "sidewall junction concavity could not be measured")


# ============================================================================
# 3. TOOL ACCESSIBILITY / UNDERCUTS (UNRESTRICTED FIVE-AXIS ORIENTATION)
# Measurement: continuous straight-insertion swept solids, not point visibility.
# A flat cutter's bottom-rim contact is offset radially for a tilted approach;
# a ball cutter's center is p + radius*normal. Shank and holder envelopes are
# tested independently, including configured holder clearance. The direction
# search is finite: zero successes means failure under this sampling policy.
# ============================================================================
def common_volume(g, shape):
    operation = BRepAlgoAPI_Common()
    from OCP.collections import List_TopoDS_Shape
    arguments, tools = List_TopoDS_Shape(), List_TopoDS_Shape()
    arguments.Append(g.solid.wrapped)
    tools.Append(shape)
    operation.SetArguments(arguments)
    operation.SetTools(tools)
    operation.SetRunParallel(False)
    operation.SetNonDestructive(True)
    operation.SetFuzzyValue(g.tol)
    operation.Build()
    if not operation.IsDone():
        raise RuntimeError("collision Boolean failed")
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(operation.Shape(), props)
    result = float(props.Mass())
    if not isfinite(result):
        raise RuntimeError("collision volume is nonfinite")
    return abs(result)


def cylinder_shape(p, d, radius, length):
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(*p), gp_Dir(*d)), radius, length).Shape()


def tool_clear(g, sample, d, tool):
    radius = tool["diameter_mm"] / 2
    alignment = dot(sample.normal, d)
    if alignment < -sin(g.angle):
        return False
    # Shift outward by the linear tolerance to separate permitted contact from
    # positive-volume penetration; do not remove the target face from collision.
    p = add(sample.point, mul(sample.normal, g.tol))
    if tool["kind"] == "flat":
        tangent = sub(sample.normal, mul(d, alignment))
        center = add(p, mul(unit(tangent), radius)) if norm(tangent) > sin(g.angle) else p
        cut_start, cut_length = center, tool["cutting_length_mm"]
        tip = center
    else:
        center = add(p, mul(sample.normal, radius))
        tip = sub(center, mul(d, radius))
        cut_start, cut_length = center, tool["cutting_length_mm"]-radius
    travel = g.span*2 + tool["stickout_mm"] + tool["holder_length_mm"]
    volume_tolerance = g.config["tolerances"]["collision_volume_mm3"]
    if tool["kind"] == "ball":
        # Sweeping a full sphere gives a capsule. The upper hemisphere lies in
        # the cutter cylinder, so this union is the actual ball-end envelope.
        sphere = BRepPrimAPI_MakeSphere(gp_Pnt(*center), radius).Shape()
        if common_volume(g, sphere) > volume_tolerance:
            return False
    if common_volume(g, cylinder_shape(cut_start, d, radius, cut_length+travel)) > volume_tolerance:
        return False
    shank_start = add(tip, mul(d, tool["cutting_length_mm"]))
    shank_length = tool["stickout_mm"]-tool["cutting_length_mm"]
    if shank_length > 0:
        if common_volume(g, cylinder_shape(shank_start, d, tool["shank_diameter_mm"]/2,
                                          shank_length+travel)) > volume_tolerance:
            return False
    holder_start = add(tip, mul(d, tool["stickout_mm"]-tool["holder_clearance_mm"]))
    return common_volume(g, cylinder_shape(holder_start, d,
                                           tool["holder_diameter_mm"]/2+tool["holder_clearance_mm"],
                                           tool["holder_length_mm"]+2*tool["holder_clearance_mm"]+travel)) <= volume_tolerance


def approach_directions(g, normal, feature_axes):
    candidates = [normal, *feature_axes]
    count = g.config["sampling"]["approach_directions"]
    golden_angle = pi * (3-sqrt(5))
    for i in range(count):
        z = 1-2*(i+0.5)/count
        radial = sqrt(max(0, 1-z*z))
        candidates.append((radial*cos(i*golden_angle), radial*sin(i*golden_angle), z))
    result = []
    for d in candidates:
        d = unit(d)
        if not any(dot(d, existing) >= cos(g.angle) for existing in result):
            result.append(d)
    return result


def check_accessibility(g, pockets, bores):
    name = CHECK_NAMES[2]
    required = g.config["limits"]["min_accessible_directions"]
    axes = [p.axis for p in pockets] + [d for bore in bores for d in (bore.axis, mul(bore.axis, -1))]
    for face in g.faces:
        for sample in face.samples:
            directions = approach_directions(g, sample.normal, axes)
            successes, uncertain = 0, False
            for tool in g.config["tools"]:
                tool_successes = 0
                tool_uncertain = False
                for d in directions:
                    try:
                        if tool_clear(g, sample, d, tool):
                            tool_successes += 1
                    except KERNEL_ERRORS:
                        tool_uncertain = True
                    if tool_successes >= required:
                        break  # count is a lower bound once the policy is met
                successes = max(successes, tool_successes)
                uncertain = uncertain or tool_uncertain
                if successes >= required:
                    break
            if successes >= required or not uncertain:
                g.coverage[name] += 1
            if successes < required:
                if uncertain:
                    g.unknown(name, face, sample.point, "collision evaluation failed for at least one candidate approach")
                else:
                    g.fail(name, face, sample.point, successes, required,
                           "clear straight-insertion directions for any single configured cutter/shank/holder are below the minimum; sampled five-axis access failure")


# ============================================================================
# 4. POCKET DEPTH-TO-WIDTH RATIO
# Measurement: actual rim-to-floor projection divided by the minimum B-rep
# caliper width over the fixed angular grid in the pocket plane. Recognition
# proves a sampled convex, constant-section, closed pocket before using this.
# ============================================================================
def check_pocket_ratio(g, pockets):
    name = CHECK_NAMES[3]
    limit = g.config["limits"]["max_pocket_depth_width"]
    for pocket in pockets:
        ratio = pocket.depth/pocket.width
        g.coverage[name] += 1
        if ratio > limit + g.config["tolerances"]["ratio"]:
            g.fail(name, pocket.floor, g.point(pocket.floor), ratio, limit,
                   "rim-to-floor depth / sampled minimum caliper width exceeds the maximum (dimensionless)")


# ============================================================================
# 5. MINIMUM HOLE DIAMETER
# Measurement: 2*analytic cylinder radius after inward-normal, coaxial split-face
# grouping and fixed circumferential enclosure validation. Each stepped bore
# diameter is checked separately. A cylindrical surface alone is not a hole.
# ============================================================================
def check_hole_diameter(g, bores):
    name = CHECK_NAMES[4]
    limit = g.config["limits"]["min_hole_diameter_mm"]
    for bore in bores:
        face = min(bore.faces, key=lambda f: f.id)
        diameter = 2*bore.radius
        g.coverage[name] += 1
        if diameter < limit - g.tol:
            g.fail(name, face, g.point(face), diameter, limit,
                   "validated cylindrical bore diameter (mm) is below the minimum")


# ============================================================================
# 6. MAXIMUM HOLE DEPTH
# Measurement: full connected axial cavity interval between mouths or between
# a mouth and a recognized planar/conical bottom. An axis ray measures blind
# bottoms, including a drill point. Counterbore steps share one total depth.
# Through-hole depth is never halved for potential drilling from two ends.
# ============================================================================
def check_hole_depth(g, bores):
    name = CHECK_NAMES[5]
    limit = g.config["limits"]["max_hole_depth_mm"]
    # Include actual conical mouth/bottom extents before grouping steps. A
    # countersink extends the mouth beyond the cylindrical sidewall's end.
    expanded = []
    cones = bore_cones(g, bores)
    for bore in bores:
        levels = [bore.low, bore.high]
        for cone, attached in cones:
            if attached is bore:
                levels.extend(dot(sub(p, bore.origin), bore.axis)
                              for edge in cone.face.edges() for p in g.edge_points(edge))
        expanded.append(Bore(bore.faces, bore.axis, bore.origin, bore.radius, min(levels), max(levels)))
    groups = group_bores(g, expanded, same_radius=False)
    for group in groups:
        bore = group[0]
        face = min((f for b in group for f in b.faces), key=lambda f: f.id)
        low, high = min(b.low for b in group), max(b.high for b in group)
        try:
            center = add(bore.origin, mul(bore.axis, (low+high)/2))
            hits = g.hits(center, bore.axis, -g.span*2, g.span*2)
            negative = [h for h in hits if h[0] < -g.tol]
            positive = [h for h in hits if h[0] > g.tol]
            bottoms = []
            for side, end in ((negative[-1:] if negative else [], low), (positive[:1] if positive else [], high)):
                if not side:
                    bottoms.append(end)
                    continue
                _, face_id, p = side[0]
                endpoint = dot(sub(p, bore.origin), bore.axis)
                if g.faces[face_id-1].kind not in (GeomAbs_Plane, GeomAbs_Cone):
                    raise ValueError("unrecognized blind-hole termination")
                if endpoint < low-g.eps or endpoint > high+g.eps:
                    # A cone can extend past the cylindrical sidewall to an apex;
                    # a remote unrelated face cannot define this hole's bottom.
                    if g.faces[face_id-1].kind != GeomAbs_Cone or not any(
                            other.id == face_id for edge, adjacent in g.edges
                            if any(f in adjacent for b in group for f in b.faces)
                            for other in adjacent):
                        bottoms.append(end)
                        continue
                bottoms.append(endpoint)
            depth = bottoms[1]-bottoms[0]
            if depth <= g.tol:
                raise ValueError("unresolved hole depth")
            g.coverage[name] += 1
            if depth > limit + g.tol:
                g.fail(name, face, g.point(face), depth, limit,
                       "full geometric axial hole depth (mm), including connected bore steps, exceeds the maximum")
        except KERNEL_ERRORS:
            g.unknown(name, face, g.point(face), "full geometric hole depth or termination could not be measured")


def check(part, config=None):
    """Return a deterministic Report for one valid closed Build123d solid."""
    config = load_config(config)
    g = Geometry(part, config)
    check_wall_thickness(g)
    # A feature-kernel failure must not discard wall measurements or abort
    # tool collision checks. Mark the affected feature family unresolved.
    try:
        bores = recognize_bores(g)
    except KERNEL_ERRORS:
        bores = []
        for face in g.faces:
            if face.kind == GeomAbs_Cylinder:
                for name in (CHECK_NAMES[4], CHECK_NAMES[5]):
                    g.unknown(name, face, g.point(face), "hole feature recognition failed in the geometry kernel")
    try:
        pockets = recognize_pockets(g, bores)
    except KERNEL_ERRORS:
        pockets = []
        for face in g.faces:
            for name in (CHECK_NAMES[1], CHECK_NAMES[3]):
                g.unknown(name, face, g.point(face), "pocket feature recognition failed in the geometry kernel")
    check_corner_radius(g, pockets)
    check_accessibility(g, pockets, bores)
    check_pocket_ratio(g, pockets)
    check_hole_diameter(g, bores)
    try:
        check_hole_depth(g, bores)
    except KERNEL_ERRORS:
        for bore in bores:
            face = bore.faces[0]
            g.unknown(CHECK_NAMES[5], face, g.point(face), "hole endpoint recognition failed in the geometry kernel")
    order = {name: index for index, name in enumerate(CHECK_NAMES)}
    violations = sorted(set(g.violations), key=lambda r: (order[r.check_name], r.face_id, r.x, r.y, r.z,
                                                         r.measured_value, r.limit, r.explanation))
    inconclusive = sorted(set(g.inconclusive), key=lambda r: (order[r.check_name], r.face_id, r.location, r.explanation))
    runtime = f"Python {platform.python_version()}; build123d {version('build123d')}; OCP {version('cadquery-ocp-novtk')}; {platform.system()} {platform.machine()}"
    return Report(tuple(violations), tuple(inconclusive), tuple(g.coverage.items()),
                  tuple((f.id, str(f.kind).split('.')[-1], g.point(f)) for f in g.faces),
                  json.dumps(config, sort_keys=True, separators=(",", ":"), allow_nan=False),
                  runtime, config["report_precision"])


def write_reports(report, output_dir):
    """Write report.txt plus an eight-column violations.csv, UTF-8 with LF."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)

    def number(value):
        result = f"{value:.{report.precision}f}"
        return result[1:] if result.startswith("-") and float(result) == 0 else result

    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CSV_FIELDS)
    for row in report.violations:
        writer.writerow((row.check_name, number(row.x), number(row.y), number(row.z), row.face_id,
                         number(row.measured_value), number(row.limit), row.explanation))
    csv_text = stream.getvalue()
    lines = ["CNC DfM violation summary (reported locations)"]
    for name in CHECK_NAMES:
        lines.append(f"{name}: {sum(r.check_name == name for r in report.violations)}")
    lines += [f"TOTAL: {len(report.violations)}", f"STATUS: {report.status}", "", "Coverage / inconclusive findings"]
    for name, count in report.coverage:
        lines.append(f"{name}: measured={count}, inconclusive={sum(r.check_name == name for r in report.inconclusive)}")
    lines += ["", "Violations", csv_text.rstrip(), "", "Inconclusive findings"]
    for row in report.inconclusive:
        lines.append(f"{row.check_name} | face {row.face_id} | {', '.join(number(v) for v in row.location)} | {row.explanation}")
    if not report.inconclusive:
        lines.append("None")
    lines += ["", "Face IDs (one-based solid.faces() traversal; same persisted B-rep only)"]
    for face_id, kind, p in report.face_map:
        lines.append(f"{face_id}: {kind}; representative surface point ({', '.join(number(v) for v in p)})")
    lines += ["", "Measurement policy", "Coordinates and lengths: mm. Ratios: dimensionless. Accessibility: direction count.",
              "Fixed UV/edge/direction sampling; unsampled geometry is not certified.",
              "Straight insertion against the finished part; unrestricted orientation; fixtures, stock, machine limits and full toolpaths excluded.",
              "SCREENED means no findings at tested locations, not a global minimum or CNC qualification.",
              "Zero recognized analytic features does not prove that every possible freeform feature was recognized.",
              "Accessibility counts stop once the configured minimum is met for one tool.",
              f"Runtime: {report.runtime}",
              f"Config SHA256: {hashlib.sha256(report.config_json.encode()).hexdigest()}",
              f"Config: {report.config_json}"]
    text = "\n".join(lines) + "\n"
    # Render both completely before replacing either destination. Atomic writes
    # prevent truncated reports; the pair is not a multi-file transaction.
    for name, content in (("report.txt", text), ("violations.csv", csv_text)):
        import os
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=directory,
                                         prefix=f".{name}.", delete=False) as temporary:
            temporary.write(content)
            temporary_path = Path(temporary.name)
        try:
            os.replace(temporary_path, directory/name)
        finally:
            temporary_path.unlink(missing_ok=True)
    return directory/"report.txt", directory/"violations.csv"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", type=Path, help="one-solid .step/.stp file")
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    args = parser.parse_args(argv)
    try:
        report = check(args.part, args.config)
        write_reports(report, args.output_dir)
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        print(f"DfM input/measurement error: {exc}", file=sys.stderr)
        return 2
    print(f"{report.status}: {len(report.violations)} violations; {len(report.inconclusive)} inconclusive findings")
    return 1 if report.violations else 3 if report.inconclusive else 0


if __name__ == "__main__":
    raise SystemExit(main())
