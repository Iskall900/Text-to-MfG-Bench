import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle
root=Path(__file__).resolve().parents[1]
g=json.loads((root/'A15.json').read_text())['geometry']
s=g['loading_interfaces'][0]['load_fastners']; t=g['constrained_fasteners']
c=g['stage_pattern_center']; x,y,z=c['x'],c['y'],c['z']; r=50; ymin=y-109.2
assert all(abs(sum(p['location'][a] for p in s)/4-c[a])<1e-9 for a in 'xyz')
assert abs(ymin+116.364)<1e-9
assert f'{2*r} mm in diameter' in (root/'prompt.md').read_text()
assert f'{2*r} mm in diameter' in (root/'Docker contents/prompt.md').read_text()
orange='#d98b22'; blue='#176baf'; red='#c03232'
plt.rcParams.update({'font.size':11})
fig=plt.figure(figsize=(15,7),layout='constrained')
a=fig.add_subplot(131,projection='3d'); theta=np.linspace(0,2*np.pi,100); A,Y=np.meshgrid(theta,[ymin,y])
a.plot_surface(x+r*np.cos(A),Y,z+r*np.sin(A),alpha=.18,color=orange,shade=False)
for yy in [ymin,y]:a.plot(x+r*np.cos(theta),np.full_like(theta,yy),z+r*np.sin(theta),color=orange)
for p in t+s:
 q=p['location']; color=red if p in s else blue
 a.scatter(q['x'],q['y'],q['z'],color=color,s=35,depthshade=False);a.text(q['x'],q['y'],q['z']+5,p['id'],color=color)
a.set(xlabel='X (mm)',ylabel='Y (mm)',zlabel='Z (mm)',title='3D · cylinder axis along Y',xlim=(-85,85),ylim=(-130,20),zlim=(-10,210));a.set_box_aspect((170,190,220));a.view_init(elev=22,azim=-65)
b=fig.add_subplot(132);b.add_patch(Circle((x,z),r,fc=orange,ec=orange,alpha=.22))
b.plot(x,z,'+',color='black',ms=12)
for p in s:
 q=p['location'];b.plot(q['x'],q['z'],'o',color=red)
 b.annotate(p['id'],(q['x'],q['z']),xytext=(8 if q['x']>x else -25,7 if q['z']>z else -17),textcoords='offset points',color=red)
b.annotate(f'Center ({x}, {z})',(x,z),xytext=(-63,85),arrowprops={'arrowstyle':'-','color':'#555555'},fontsize=10)
b.text(x,z+r-12,'Ø100 mm',ha='center',color='#88520c')
b.set(title='Front view · XZ at Y = −7.164',xlabel='X (mm)',ylabel='Z (mm)',xlim=(-85,85),ylim=(40,210));b.set_aspect('equal');b.grid(alpha=.18)
d=fig.add_subplot(133);d.add_patch(Rectangle((ymin,z-r),109.2,2*r,fc=orange,ec=orange,alpha=.22))
for zz,lab in [(112.51,'S1 / S2'),(137.91,'S3 / S4')]:
 d.plot(y,zz,'o',color=red);d.annotate(lab,(y,zz),xytext=(8,0),textcoords='offset points',color=red,fontsize=10)
d.annotate('',xy=(ymin,43),xytext=(y,43),arrowprops={'arrowstyle':'<->','color':'#555555'});d.text((y+ymin)/2,33,'109.2 mm · toward −Y',ha='center',fontsize=10)
d.text(ymin,202,'−116.364',ha='center',fontsize=10);d.text(y,202,'−7.164',ha='center',fontsize=10)
d.set(title='Side view · YZ',xlabel='Y (mm)',ylabel='Z (mm)',xlim=(-135,30),ylim=(20,215));d.set_aspect('equal');d.grid(alpha=.18)
fig.suptitle('Keep-out centered on S1–S4, extending toward negative Y',fontsize=17)
fig.text(.5,-.015,'Orange: keep-out cylinder  •  Red: S1–S4 centers on the circular face  •  Blue: T1–T3 telescope interfaces',ha='center',fontsize=11)
fig.text(.5,-.055,'Interface coordinates from A15.json. Cylinder placement from prompt.md. Points show interface centers; actual bracket and hardware geometry are not shown.',ha='center',fontsize=10,color='#444444')
for ext in ['png','svg']:fig.savefig(root/f'diagrams/keepout-comparison.{ext}',dpi=180,bbox_inches='tight')
print('PASS: circle center equals S1–S4 centroid; Y extent = [−116.364, −7.164] mm.')

# XY top projection; paired stage bolts share the same projected coordinates.
f, ax=plt.subplots(figsize=(8,8),layout='constrained')
ax.add_patch(Rectangle((x-r,ymin),2*r,y-ymin,facecolor=orange,edgecolor=orange,alpha=.23))
ax.plot([x,x],[ymin,y],ls='--',color=orange,lw=1)
ax.annotate('Toward −Y',xy=(x,y-78),xytext=(x,y-40),ha='center',arrowprops={'arrowstyle':'->','color':orange},color='#88520c')
for p in t:
 q=p['location'];ax.plot(q['x'],q['y'],'o',color=blue);ax.annotate(p['id']+' · Z = 0',(q['x'],q['y']),xytext=(8,8),textcoords='offset points',color=blue)
for xx,label in [(s[0]['location']['x'],'S1 / S4'),(s[1]['location']['x'],'S2 / S3')]:
 ax.plot(xx,y,'o',color=red);ax.annotate(label,(xx,y),xytext=(12 if xx>x else -12,13),textcoords='offset points',ha='left' if xx>x else 'right',color=red)
ax.text(x,ymin+8,f'Cylinder projection\nZ = {z-r:.2f} to {z+r:.2f} mm',ha='center',va='bottom',color='#88520c')
ax.annotate('',xy=(x-r,-129),xytext=(x+r,-129),arrowprops={'arrowstyle':'<->'});ax.text(x,-134,f'{2*r} mm',ha='center',va='top')
ax.set(xlabel='X (mm)',ylabel='Y (mm)',title='Top view · looking down −Z\nKeep-out diameter 100 mm · cylinder toward −Y',xlim=(-90,90),ylim=(-145,65));ax.set_aspect('equal');ax.grid(alpha=.18)
f.text(.5,-.025,'S1/S4 and S2/S3 coincide in this projection.\nT1 lies below the cylinder; projected overlap is not a 3D collision.',ha='center',fontsize=10)
f.savefig(root/'diagrams/keepout-top-view.png',dpi=180,bbox_inches='tight')
