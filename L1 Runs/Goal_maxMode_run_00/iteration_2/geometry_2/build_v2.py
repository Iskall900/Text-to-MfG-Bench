import sys, time
sys.path.insert(0,"/workspace/tools")
from bracket_model import *
from build123d import export_step, export_stl
p = Params()
t0=time.time()
part = build(p)
print("build time", round(time.time()-t0,1))
print("volume mm3", round(part.volume,1), "mass g", round(mass_g(part),2))
print("solids", len(part.solids()), "faces", len(part.faces()))
bb=part.bounding_box(); print("bbox", bb.min, bb.max)
ce=concave_edges(part)
print("remaining concave", len(ce))
for e in ce:
    pm=e.position_at(0.5); print("  ", (round(pm.X,2),round(pm.Y,2),round(pm.Z,2)), round(e.length,2))
export_step(part, "bracket_v2.step")
export_stl(part, "bracket_v2.stl")
