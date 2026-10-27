"""A15 parametric Build123d billet bracket. All dimensions mm.
Run once per new geometry iteration. Not a hardware-qualified design.
"""
from build123d import *
from pathlib import Path
import numpy as np
import json, argparse, math

ROOT=Path('/workspace')
T=[(30.03,-21.45,0),(30.03,42.047,0),(-58.86,42.047,0)]
S=[(11.075,-7.164,112.51),(-14.32,-7.164,112.51),(-14.32,-7.164,137.91),(11.075,-7.164,137.91)]

def cylinder_between(a,b,r):
    a=np.array(a,float); b=np.array(b,float); d=b-a
    return Plane(origin=tuple(a),z_dir=tuple(d))*Cylinder(r,float(np.linalg.norm(d)),align=(Align.CENTER,Align.CENTER,Align.MIN))

def capsule(a,b,r):
    return cylinder_between(a,b,r)+Pos(*a)*Sphere(r)+Pos(*b)*Sphere(r)

def volume(s): return 0.0 if s is None else float(sum(q.volume for q in s.solids()))

def overlap(a,b):
    # Solid boolean common avoids compound include_touched intersections.
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    op=BRepAlgoAPI_Common(a.wrapped,b.wrapped); op.Build()
    prop=GProp_GProps(); BRepGProp.VolumeProperties_s(op.Shape(),prop)
    return max(0.,float(prop.Mass()))

def build(iteration, radius=4.5, pad_t=5., plate_t=6., mesh_size=4., fillet_r=0.):
    folder=ROOT/f'iteration{iteration}'
    for sub in ['DfM1','geometry1','FEA1']: (folder/sub).mkdir(parents=True,exist_ok=True)
    cfg=dict(iteration=iteration,strut_radius_mm=radius,pad_thickness_mm=pad_t,plate_thickness_mm=plate_t,mesh_size_mm=mesh_size,fillet_radius_mm=fillet_r)
    (folder/'parameters.json').write_text(json.dumps(cfg,indent=2))
    parts=[]
    for x,y,z in T:
        parts.append(Pos(x,y,0)*Cylinder(12,pad_t,align=(Align.CENTER,Align.CENTER,Align.MIN)))
    # Closed open-backed mounting frame; exact stage plane is its front face.
    plane=Plane(origin=(-1.6225,-7.164,125.21),x_dir=(1,0,0),z_dir=(0,1,0))
    profile=RectangleRounded(44.4,44.4,9.5)-RectangleRounded(12,12,3)
    frame=extrude(plane*profile, amount=plate_t)
    parts.append(frame)
    foot_z=pad_t
    feet=[(19.53,-21.45,foot_z),(21.43,35.647,foot_z),(-51.76,34.647,foot_z)]
    corners=[(-21.0,1.5,105.0),(18.0,1.5,105.0),(-21.0,-0.664,146.0),(18.0,-0.664,146.0)]
    cfg['foot_centers_mm']=[list(p) for p in feet]
    cfg['stage_strut_ends_mm']=[list(p) for p in corners]
    (folder/'parameters.json').write_text(json.dumps(cfg,indent=2))
    links=[(0,0),(0,1),(1,3),(2,0),(2,2),(2,3)]
    for i,j in links: parts.append(capsule(feet[i],corners[j],radius))
    # Union together. Do not count reference geometry as bracket material.
    body=parts[0]
    for k,part in enumerate(parts[1:]):
        body=body.fuse(part)
        print('union',k,'valid',body.is_valid,'solids',len(body.solids()),'volume',body.volume,flush=True)
        if not body.is_valid: raise RuntimeError(f'Invalid union {k}')
    # Rod radii <= pad thickness ensure no member extends below z=0.
    # Drill bores and provide independent washer/head/tool insertion corridors.
    envelopes=[]; access=[]
    for i,(x,y,z) in enumerate(T):
        body=body-Pos(x,y,-1)*Cylinder(3.3,10,align=(Align.CENTER,Align.CENTER,Align.MIN))
        corridor=Pos(x,y,pad_t)*Cylinder(8.25,200,align=(Align.CENTER,Align.CENTER,Align.MIN))
        body=body-corridor
        print('T cut',i,body.is_valid,len(body.solids()),body.volume,flush=True)
        if not body.is_valid: raise RuntimeError(f'Invalid T cut {i}')
        env={
          'bolt':Pos(x,y,-10)*Cylinder(3.175,10+pad_t,align=(Align.CENTER,Align.CENTER,Align.MIN)),
          'washer':Pos(x,y,pad_t)*Cylinder(8.,1.6,align=(Align.CENTER,Align.CENTER,Align.MIN)),
          'head':Pos(x,y,pad_t+1.6)*Cylinder(5.,6.5,align=(Align.CENTER,Align.CENTER,Align.MIN)),
          'straight_insertion':Pos(x,y,pad_t+8.1)*Cylinder(5.25,60,align=(Align.CENTER,Align.CENTER,Align.MIN)),
          'driver':Pos(x,y,pad_t+8.1)*Cylinder(4.,150,align=(Align.CENTER,Align.CENTER,Align.MIN))}
        envelopes.append((f'T{i+1}',env))
    for i,(x,y,z) in enumerate(S):
        body=body-cylinder_between((x,-30,z),(x,25,z),3.3)
        yback=-7.164+plate_t
        body=body-cylinder_between((x,yback,z),(x,100,z),8.25)
        print('S cut',i,body.is_valid,len(body.solids()),body.volume,flush=True)
        if not body.is_valid: raise RuntimeError(f'Invalid S cut {i}')
        env={
          'bolt':cylinder_between((x,-17.164,z),(x,yback,z),3.175),
          'washer':cylinder_between((x,yback,z),(x,yback+1.6,z),8.),
          'head':cylinder_between((x,yback+1.6,z),(x,yback+8.1,z),5.),
          'straight_insertion':cylinder_between((x,yback+8.1,z),(x,yback+68.1,z),5.25),
          'driver':cylinder_between((x,yback+8.1,z),(x,yback+158.1,z),4.)}
        envelopes.append((f'S{i+1}',env))
    body=body.clean()
    # Optional concave-edge blend. Its successes/failures are explicitly preserved.
    fillet_log=[]
    if fillet_r:
        # Select only cylinder intersection seam edges (not hole rims).
        candidates=[]
        for e in body.edges():
            c=e.center()
            if 8<c.Z<100 and e.length>2:
                candidates.append(e)
        try:
            body=fillet(candidates,fillet_r).clean()
            fillet_log.append(dict(status='success',edges=len(candidates),radius=fillet_r))
        except Exception as ex:
            fillet_log.append(dict(status='failed_no_silent_substitution',error=str(ex)))
            (folder/'geometry1'/'fillet_diagnostic.json').write_text(json.dumps(fillet_log,indent=2))
            raise
    body.label=f'A15 iteration{iteration} 6061-T651 bracket only'
    export_step(body,str(folder/'geometry1'/'bracket.step'))
    export_brep(body,str(folder/'geometry1'/'bracket.brep'))
    export_stl(body,str(folder/'geometry1'/'bracket.stl'),tolerance=0.08,angular_tolerance=0.15)
    keepout=Pos(79.4,19.5,-77.8)*Cylinder(70,109.2,align=(Align.CENTER,Align.CENTER,Align.MIN))
    export_step(keepout,str(folder/'geometry1'/'keepout_STEP_coordinates.step'))
    ko_vol=overlap(body,keepout)
    for ident,env in envelopes:
        for name,shape in env.items():
            export_step(shape,str(folder/'DfM1'/f'{ident}_{name}.step'))
            overlap_vol=overlap(body,shape)
            access.append(dict(interface=ident,type=name,overlap_mm3=overlap_vol,passes_nominal_envelope=overlap_vol<1e-5))
    # Assumed attachment envelopes; no fabrication of missing telescope/stage geometry.
    stage_ko=Pos(-31.6225,-107.164,95.21)*Box(60,100,60,align=(Align.MIN,Align.MIN,Align.MIN))
    telescope_ko=Pos(-150,-150,-100)*Box(300,300,100,align=(Align.MIN,Align.MIN,Align.MIN))
    export_step(stage_ko,str(folder/'DfM1'/'assumed_stage_keepout.step'))
    export_step(telescope_ko,str(folder/'DfM1'/'assumed_telescope_halfspace.step'))
    geom=dict(parameters=cfg,valid=body.is_valid,solid_count=len(body.solids()),volume_mm3=body.volume,
              bracket_mass_kg=body.volume*2.7e-6,cad_center_mm=list(body.center(CenterOf.MASS)),
              bbox_min_mm=list(body.bounding_box().min),bbox_max_mm=list(body.bounding_box().max),
              required_STEP_keepout_overlap_mm3=ko_vol,
              keepout_registration_status='No STEP-to-JSON transform supplied. Overlap uses numerical coordinates directly; not a claim of registration.',
              assumed_stage_overlap_mm3=overlap(body,stage_ko),assumed_telescope_overlap_mm3=overlap(body,telescope_ko),
              hardware_envelope_basis='Conservative nominal assumptions, NOT verified NAS hardware dimensions. Bore diameter 6.6; washer OD16/ID6.6/t1.6; head OD10/h6.5; insertion OD10.5 L60; driver OD8 L150.',
              access=access,fillet_log=fillet_log,
              interfaces=[dict(id=f'T{i+1}',location=list(p),hole_axis=[0,0,1],hole_diameter_mm=6.6,insertion_direction=[0,0,-1]) for i,p in enumerate(T)]+
                         [dict(id=f'S{i+1}',location=list(p),hole_axis=[0,1,0],hole_diameter_mm=6.6,insertion_direction=[0,-1,0]) for i,p in enumerate(S)])
    (folder/'geometry1'/'geometry_checks.json').write_text(json.dumps(geom,indent=2))
    print(json.dumps({k:v for k,v in geom.items() if k not in ['interfaces','access']},indent=2))
    return folder

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('iteration',type=int);p.add_argument('--radius',type=float,default=4.5);p.add_argument('--pad',type=float,default=5.);p.add_argument('--plate',type=float,default=6.);p.add_argument('--size',type=float,default=4.);p.add_argument('--fillet',type=float,default=0.)
    a=p.parse_args();build(a.iteration,a.radius,a.pad,a.plate,a.size,a.fillet)
