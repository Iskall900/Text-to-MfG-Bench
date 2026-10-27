"""A15 high-200-Hz continuation. New direct-to-pad spatial fan-web load paths.
No keep-out cylinder (waived). Build123d geometry; CalculiX via shared analysis.
"""
import sys,json,math
from pathlib import Path
import numpy as np
from build123d import *
T=[(30.03, -21.45, 0), (30.03, 42.047, 0), (-58.86, 42.047, 0)]
S=[(11.075, -7.164, 112.51), (-14.32, -7.164, 112.51), (-14.32, -7.164, 137.91), (11.075, -7.164, 137.91)]
CG=(-1.6225, -57.164, 125.21)
def box(x0,x1,y0,y1,z0,z1):
 return Pos(x0,y0,z0)*Box(x1-x0,y1-y0,z1-z0,align=(Align.MIN,Align.MIN,Align.MIN))
ROOT=Path('/workspace')

def framed_face(face,th,n,p):
 n=np.array(n,dtype=float);inner=None
 if p.get('fan_window_margin',0):
  q=offset(face,amount=-p['fan_window_margin'],kind=Kind.INTERSECTION)
  if q is not None and q.faces():
   inner=q.faces()[0]
   if p.get('window_radius',0):
    try: inner=inner.fillet_2d(p['window_radius'],inner.vertices())
    except ValueError:
     # An inset quad can leave a very short edge at its narrow tip. Merge
     # that edge into an inscribed triangular tip, keeping full R3 corners.
     e=min(inner.edges(),key=lambda e:e.length);ends=[v.center() for v in e.vertices()]
     remain=[v.center() for v in inner.vertices() if all((v.center()-x).length>1e-6 for x in ends)]
     inner=Face(Wire.make_polygon([(ends[0]+ends[1])*0.5]+remain,close=True))
     try:
      inner=inner.fillet_2d(p['window_radius'],inner.vertices())
      p.setdefault('construction_notes',[]).append('Merged short inset edge before R3 window fillets; initial construction failure retained.')
     except ValueError:
      inner=None
      p.setdefault('construction_notes',[]).append('Omitted narrow window that could not accommodate R3 corners; retained solid skin for DfM.')
 skin=extrude(face if inner is None else face-inner,amount=th,dir=tuple(n))
 if p.get('rib_depth_each_side',0):
  q=offset(face,amount=-p['rib_width'],kind=Kind.INTERSECTION)
  ring=face-q.faces()[0]
  depth=p['rib_depth_each_side']
  rib=Pos(*(-n*depth))*extrude(ring,amount=th+2*depth,dir=tuple(n))
  skin+=rib
 return skin

def rear_fan(foot,top_x,top_y,p):
 th=p['rear_web'];base=p['base']
 if p.get('deep_stage',False):
  from scipy.spatial import ConvexHull
  b=np.array([foot[0],foot[1],base-3]);lo=np.array([top_x,top_y,p['stage_bottom']]);hi=np.array([top_x,p['deep_back_y'],148.])
  n=np.cross(lo-b,hi-b);n/=np.linalg.norm(n)
  u=np.cross(n,[0,0,1]);u/=np.linalg.norm(u)
  pts=np.array([b-u*p['foot_half_width'],b+u*p['foot_half_width'],lo,hi])
  vv=np.cross(n,u);xy=np.array([[(q-b)@u,(q-b)@vv] for q in pts]);order=ConvexHull(xy).vertices
  points=[(pts[i]-th/2*n).tolist() for i in order]
 else:
  u=np.array([top_x-foot[0],top_y-foot[1],0.]);L=np.linalg.norm(u);u/=L;n=np.array([-u[1],u[0],0.]);points=[]
  for uu,zz in [(-p['foot_half_width'],base-3),(p['foot_half_width'],base-3),(L,p['stage_bottom']),(L,148)]:
   v=np.array([foot[0],foot[1],zz])+uu*u-th/2*n;points.append(v.tolist())
 face=Face(Wire.make_polygon(points,close=True));web=framed_face(face,th,n,p)
 return web

def build_high(p,out):
 base=p['base'];shape=None
 for x,y,z in T:
  pad=Pos(x,y,0)*Cylinder(p['pad_radius'],base,align=(Align.CENTER,Align.CENTER,Align.MIN))
  shape=pad if shape is None else shape+pad
 # All spatial fans feed the full stage mounting plate, not a base cantilever.
 stage=box(-28,25,-7.164,-7.164+p['stage'],p['stage_bottom'],148)
 shape+=stage
 shape+=rear_fan(T[2],-26,-7.164+p['stage'],p)
 shape+=rear_fan(T[1],23,-7.164+p['stage'],p)
 foot=T[0];z0=base-3;zt=p['front_top'];y0=foot[1];yt=p['front_top_y'];w=p['foot_half_width']
 face=Face(Wire.make_polygon([(foot[0]-w,y0,z0),(foot[0]+w,y0,z0),(25,yt,zt),(-28,yt,zt)],close=True))
 fp=p.copy()
 if p.get('solid_front_skin',False):fp['fan_window_margin']=0
 fan=framed_face(face,p['front_web'],(0,1,0),fp);shape+=fan
 if p.get('deep_stage',False):
  yb=-7.164+p['stage'];back=p['deep_back_y'];cw=p['cheek_wall'];zb=p['stage_bottom']
  for x in [-28,25-cw]:
   f=Face(Wire.make_polygon([(x,yb,zb),(x,yb,148),(x,back,148)],close=True))
   shape+=extrude(f,amount=cw,dir=(1,0,0))
  cap=box(-28,25,yb,back,148-p['cap_wall'],148)
  win=Pos(-1.5,20,147-p['cap_wall'])*extrude(RectangleRounded(37,28,4),amount=p['cap_wall']+2)
  cap-=win;shape+=cap
 if p.get('stage_return_depth',0):
  yb=-7.164+p['stage'];d=p['stage_return_depth'];t=p['stage_return_wall'];zb=p['stage_bottom']
  shape+=box(-28,-28+t,yb-.2,yb+d,zb,148)
  shape+=box(25-t,25,yb-.2,yb+d,zb,148)
  shape+=box(-28,25,yb-.2,yb+d,zb,zb+t)
  shape+=box(-28,25,yb-.2,yb+d,148-t,148)
 # The assumed stage envelope on -Y above Z=100 remains clear.
 if p.get('trim_stage_negative_y',False):shape-=box(-100,100,-100,-7.164,100,180)
 blend=[]
 if p.get('root_blend',0):
  candidates=[]
  for e in shape.edges():
   c=e.center()
   if abs(c.Z-base)<1e-4 and e.geom_type==GeomType.LINE and e.length>5 and min(math.hypot(c.X-x,c.Y-y) for x,y,z in T)<p['pad_radius']-1:
    candidates.append(e)
  try:
   shape=fillet(candidates,p['root_blend']);blend=['applied',len(candidates)]
  except Exception as exc:blend=['failed',str(exc)]
 # Access sweeps remain separate reference envelopes; relief in solid for their path.
 for x,y,z in T:
  shape-=Pos(x,y,base)*Cylinder(p['access_radius'],170,align=(Align.CENTER,Align.CENTER,Align.MIN))
  shape-=Pos(x,y,-1)*Cylinder(3.4,base+2,align=(Align.CENTER,Align.CENTER,Align.MIN))
 for x,y,z in S:
  shape-=Pos(x,y+p['stage'],z)*Rot(-90,0,0)*Cylinder(p['stage_access_radius'],150,align=(Align.CENTER,Align.CENTER,Align.MIN))
  shape-=Pos(x,y-1,z)*Rot(-90,0,0)*Cylinder(3.4,p['stage']+2,align=(Align.CENTER,Align.CENTER,Align.MIN))
 if p.get('front_window',False):
  # Optional face-normal through-window; rounded aperture, no blind recess.
  f=Face(Wire.make_polygon([(9,-15,35),(27,-15,35),(7,-15,86),(-10,-15,86)],close=True))
  f=f.fillet_2d(4,f.vertices());shape-=extrude(f,amount=30,dir=(0,1,0))
 assert shape.is_valid and len(shape.solids())==1,(shape.is_valid,len(shape.solids()))
 export_step(shape,str(out/'bracket.step'));export_stl(shape,str(out/'bracket.stl'),tolerance=.10,angular_tolerance=.12)
 data={'geometry_family':'deep_stage_wedge_fan_frame' if p.get('deep_stage',False) else 'direct_to_pad_spatial_fan_webs','volume_mm3':shape.volume,'mass_kg':shape.volume*2.7e-6,'solid_count':len(shape.solids()),'valid':shape.is_valid,'center_of_mass_mm':list(shape.center(CenterOf.MASS)),'fillets':blend,'parameters':p,'material':{'density_kg_m3':2700,'E_MPa':68900,'poisson':.33,'yield_MPa':240,'status':'engineering assumptions, not certified material/temperature allowables'},'keepout':'waived_by_user','frequency_requirement_hz':200}
 (out/'cad_metrics.json').write_text(json.dumps(data,indent=2));return data

if __name__ == "__main__":
 out=Path(__file__).parent/"reproduced_CAD"
 out.mkdir(exist_ok=True)
 build_high({'base': 8, 'pad_radius': 15.5, 'rear_web': 3.2, 'front_web': 3, 'stage': 6, 'stage_bottom': 100, 'foot_half_width': 12, 'front_top': 110, 'front_top_y': -3.164, 'root_blend': 0.8, 'access_radius': 8.5, 'stage_access_radius': 8.5, 'fan_window_margin': 6.5, 'window_radius': 3, 'rib_width': 2.5, 'rib_depth_each_side': 4.5, 'deep_stage': True, 'deep_back_y': 42, 'cheek_wall': 3.2, 'cap_wall': 2.5, 'solid_front_skin': True, 'trim_stage_negative_y': True, 'distributed_remote': True, 'remote_samples_per_ring': 8, 'h': 3.5},out)
