"""A15 parametric build123d bracket; millimetres, A15 global XYZ.
Run: python design.py iteration1 --wall 3.5 --mesh 4
Every design revision is written to a fresh iteration folder.
"""
import argparse,json,math,shutil
from pathlib import Path
import numpy as np
from build123d import *

def face3(pts,r=0):
    f=Face(Wire.make_polygon(pts,close=True))
    return f.fillet_2d(r,f.vertices()) if r else f

def barquad(a,b,width):
    a=np.array(a,float);b=np.array(b,float);v=b-a;perp=np.array([-v[1],v[0]])/np.linalg.norm(v)*width/2
    return [a+perp,b+perp,b-perp,a-perp]

def split_window(poly,a,b,width):
    """Clip a convex window either side of a continuous diagonal ligament."""
    a=np.array(a,float);v=np.array(b,float)-a;n=np.array([-v[1],v[0]])/np.linalg.norm(v)
    answer=[]
    for sign in [-1,1]:
        q=[np.array(p,float) for p in poly];pout=[]
        for i,p in enumerate(q):
            prev=q[i-1];dp=sign*np.dot(p-a,n)-width/2;dq=sign*np.dot(prev-a,n)-width/2
            if (dp>=0)!=(dq>=0):pout.append(prev+(p-prev)*dq/(dq-dp))
            if dp>=0:pout.append(p)
        if len(pout)>=3:answer.append(pout)
    return answer

def make(out,wall):
    g=out/'geometry1';d=out/'DfM1';f=out/'FEA1'
    for p in [g,d,f]:p.mkdir(parents=True,exist_ok=True)
    shutil.copy2(__file__,g/'design_source.py')
    z0=3.;zt=148.;front=-1.164
    xl=lambda z:-58.86+(34.86)*(z-z0)/(zt-z0)
    xr=lambda z:30.03-(9.03)*(z-z0)/(zt-z0)
    yr=lambda z:48.-23.*(z-z0)/(zt-z0)
    # Side webs are planar leaning plates, through-windows with R4 internal corners.
    parts=[]
    for side,xfun in [('right',xr),('left',xl)]:
        yz=[(-28.,z0),(48.,z0),(25.,zt),(front,zt),(front,101.)] if side=='right' else [(34.,z0),(48.,z0),(25.,zt),(front,zt),(front,101.)]
        outer=face3([(xfun(z)-wall/2,y,z) for y,z in yz])
        solid=Solid.extrude(outer,(wall,0,0))
        if side=='right': wins=[[(-12,18),(34,18),(21,91),(2,91)],[(6,106),(26,106),(21,137),(6,137)]]
        else: wins=[[(6,106),(26,106),(21,137),(6,137)]]
        if side=='right':wins=split_window(wins[0],(-14,16),(23,94),8.)+wins[1:]
        for yzwin in wins:
            try:
                wf=face3([(xfun(z)-wall,y,z) for y,z in yzwin],3.)
                solid=solid.cut(Solid.extrude(wf,(2*wall,0,0)))
            except Exception as e:
                raise RuntimeError((side,yzwin,str(e)))
        parts.append(solid)
    # Rear web: one open rounded lower window and an upper tool-access window.
    outer=face3([(xl(z0)-wall/2,yr(z0)-wall/2,z0),(xr(z0)+wall/2,yr(z0)-wall/2,z0),(xr(zt)+wall/2,yr(zt)-wall/2,zt),(xl(zt)-wall/2,yr(zt)-wall/2,zt)])
    rear=Solid.extrude(outer,(0,wall,0))
    rearwins=split_window([(-42,17),(17,17),(15,88),(-25,88)],(-46,15),(17,92),10.)
    rearwins.append([(-26,101),(21,101),(17.7,143.5),(-22.8,143.5)])
    for xz in rearwins:
        wf=face3([(x,yr(z)-wall,z) for x,z in xz],3.)
        rear=rear.cut(Solid.extrude(wf,(0,2*wall,0)))
    parts.append(rear)
    # Two planar, broad front gussets close the torsional load path. They are
    # CNC-accessible open triangular webs, not physical remote-connection rods.
    A=np.array([xr(z0),-21.45,z0]);B=np.array([xl(z0),42.047,z0])
    C=np.array([xl(101),front,101.]);D=np.array([xr(101),front,101.])
    for tri in [[A,B,C],[A,C,D]]:
        tri=np.array(tri);normal=np.cross(tri[1]-tri[0],tri[2]-tri[0]);normal/=np.linalg.norm(normal)
        outer=face3([p-normal*wall/2 for p in tri]);web=Solid.extrude(outer,normal*wall)
        center=tri.mean(0);inner=center+(tri-center)*0.79
        cutface=face3([p-normal*wall for p in inner],4.)
        web=web.cut(Solid.extrude(cutface,normal*2*wall));parts.append(web)
    # Exact stage outer face Y=-7.164. Trapezoidal outline follows the two webs.
    faceplate=face3([(xl(101)-wall/2,-7.164,101),(xr(101)+wall/2,-7.164,101),(xr(zt)+wall/2,-7.164,zt),(xl(zt)-wall/2,-7.164,zt)])
    parts.append(Solid.extrude(faceplate,(0,6.,0)))
    T=[(30.03,-21.45),(30.03,42.047),(-58.86,42.047)]
    for x,y in T:parts.append(Pos(x,y,0)*Cylinder(12,6,align=(Align.CENTER,Align.CENTER,Align.MIN)))
    bracket=parts[0].fuse(*parts[1:]).clean()
    # Bolt washer/head/driver paths; the broad clearance above each base pad is
    # intentionally subtracted, rather than assuming that a wall can occupy it.
    for x,y in T:
        bracket=bracket.cut(Pos(x,y,-1)*Cylinder(3.4,9,align=(Align.CENTER,Align.CENTER,Align.MIN)))
        bracket=bracket.cut(Pos(x,y,6)*Cylinder(7.5,1.5,align=(Align.CENTER,Align.CENTER,Align.MIN)))
        bracket=bracket.cut(Pos(x,y,7.5)*Cylinder(5.5,180,align=(Align.CENTER,Align.CENTER,Align.MIN)))
    S=[(11.075,112.51),(-14.32,112.51),(-14.32,137.91),(11.075,137.91)]
    for x,z in S:
        cutter=Solid.make_cylinder(3.4,12,Plane(origin=(x,-10,z),z_dir=(0,1,0)))
        bracket=bracket.cut(cutter)
        # Backside screw and driver access through the open rear window.
        cutter=Solid.make_cylinder(5.5,100,Plane(origin=(x,0.336,z),z_dir=(0,1,0)))
        bracket=bracket.cut(cutter)
    bracket=bracket.clean()
    # Stepped access cuts can leave micron-scale islands at intersections of
    # overlapping webs. These are not manufacturable material: explicitly omit
    # only disconnected scraps below 0.1 mm^3, recording the exact volume.
    solids=sorted(bracket.solids(),key=lambda s:s.volume,reverse=True)
    scraps=[s for s in solids[1:] if s.volume<0.1]
    omitted_scrap_volume=sum(s.volume for s in scraps)
    if len(solids)>1 and len(scraps)==len(solids)-1:bracket=solids[0]
    export_step(bracket,str(g/'bracket.step'))
    export_brep(bracket,str(g/'bracket.brep'))
    export_stl(bracket,str(g/'bracket.stl'),tolerance=0.08,angular_tolerance=0.1)
    keep=Pos(79.4,19.5,-77.8)*Cylinder(70,109.2,align=(Align.CENTER,Align.CENTER,Align.MIN))
    export_step(keep,str(g/'keepout_literal_STEP_coordinates.step'))
    inter=bracket.intersect(keep)
    intervol=sum(s.volume for s in inter.solids()) if inter else 0
    b=bracket.bounding_box()
    result=dict(wall_mm=wall,omitted_disconnected_scrap_mm3=omitted_scrap_volume,volume_mm3=bracket.volume,mass_kg=bracket.volume*2.7e-6,solids=len(bracket.solids()),valid=bracket.is_valid,bbox_min=list(b.min),bbox_max=list(b.max),keepout_literal_intersection_mm3=intervol,holes_diameter_mm=6.8,stage_face_y_mm=-7.164,base_face_z_mm=0)
    (g/'geometry_checks.json').write_text(json.dumps(result,indent=2))
    (g/'parameters.json').write_text(json.dumps({'wall_mm':wall,'pad_radius_mm':12,'pad_thickness_mm':6,'stage_plate_thickness_mm':6,'window_corner_radius_mm':3,'units':'mm','coordinates':'A15 global XYZ'},indent=2))
    print(json.dumps(result,indent=2),flush=True)
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('iteration');ap.add_argument('--wall',type=float,default=3.5);a=ap.parse_args()
    make(Path('/workspace')/a.iteration,a.wall)
