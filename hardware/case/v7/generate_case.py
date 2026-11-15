"""Pura electronics-only enclosure, unpowered fit-check draft. Dimensions in mm.
Run with numpy, trimesh, manifold3d, matplotlib installed. No mains-use validation.
"""
from pathlib import Path
import json, math, zipfile
import numpy as np
import trimesh
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'print-files'
OUT.mkdir(exist_ok=True)
DATA=json.loads((ROOT/'measurements.json').read_text())
M=DATA['measured']; A=DATA['assumed']
R=M['board_diameter']/2
RI=R+A['radial_board_clearance']; RO=RI+A['wall']
W=A['wall']; SEAM=A['case_seam_z']; LID=A['lid_thickness']
NECK=A['plug_neck_opening_diameter']; FLANGE=A['plug_flange_recess_diameter']
PX=A['plug_center_x']; PY=A['plug_center_y']
HY=R-M['led_edge_to_mount_hole_line_approx']
HOLES=[(-M['mount_hole_spacing']/2,HY),(M['mount_hole_spacing']/2,HY)]
EARS=[(-49,0),(49,0)]
PLUG_SCREWS=[(PX+17.5*math.cos(math.radians(a)),PY+17.5*math.sin(math.radians(a))) for a in (45,135,225,315)]

def cyl(r,z0,z1,x=0,y=0):
    o=trimesh.creation.cylinder(radius=r,height=z1-z0,sections=128)
    o.apply_translation([x,y,(z0+z1)/2]); return o

def box(size,center):
    o=trimesh.creation.box(extents=size);o.apply_translation(center);return o

def union(*meshes):return trimesh.boolean.union(list(meshes),engine='manifold')
def diff(a,*b):return trimesh.boolean.difference([a,*b],engine='manifold')

def sensor_cut():
    # Sensor angle corrected using physical fit feedback; LED edge at 12 oclock.
    angle=math.radians(90-30*A['sensor_clock_position'])
    direction=np.array([math.cos(angle),math.sin(angle),0])
    cut=trimesh.creation.cylinder(radius=A['sensor_bore_diameter']/2,height=16,sections=128)
    cut.apply_transform(trimesh.geometry.align_vectors([0,0,1],direction))
    cut.apply_translation([*(direction[:2]*(RI+W/2)),A['sensor_center_z']])
    return cut

def led_cuts():
    cuts=[]
    for a in A['led_arc_angles_degrees']:
        angle=math.radians(a)
        direction=np.array([math.cos(angle),math.sin(angle),0])
        cut=trimesh.creation.cylinder(radius=A['led_hole_diameter']/2,height=16,sections=128)
        cut.apply_transform(trimesh.geometry.align_vectors([0,0,1],direction))
        cut.apply_translation([*(direction[:2]*(RI+W/2)),A['led_center_z']])
        cuts.append(cut)
    return cuts

def base():
    shell=diff(cyl(RO,0,SEAM),cyl(RI,W,SEAM+1))
    parts=[shell]
    # External ears keep enclosure screws outside the PCB perimeter.
    for x,y in EARS:
        parts += [cyl(4.8,0,SEAM,x,y),box((7,8,SEAM),(x-math.copysign(3,x),y,SEAM/2))]
    for x,y in HOLES:
        parts += [cyl(4,W,A['board_bottom_z'],x,y),cyl(2.65,A['board_bottom_z'],A['board_bottom_z']+1.7,x,y)]
    parts += [cyl(17.5,0,7.4,PX,PY)]
    for x,y in PLUG_SCREWS:parts += [cyl(3.2,W,7.4,x,y)]
    solid=union(*parts)
    cuts=[cyl(NECK/2,-1,8,PX,PY),cyl(FLANGE/2,W,8,PX,PY),sensor_cut(),*led_cuts()]
    for x,y in HOLES:cuts += [cyl(1.0,A['board_bottom_z']-6,A['board_bottom_z']+2,x,y)]
    for x,y in EARS:cuts += [cyl(1.25,SEAM-9,SEAM+1,x,y)]
    for x,y in PLUG_SCREWS:cuts += [cyl(.8,3.4,8,x,y)]
    return diff(solid,*cuts)

def lid():
    pieces=[cyl(RO,0,LID)]
    for x,y in EARS:pieces += [cyl(4.8,0,LID,x,y),box((7,8,LID),(x-math.copysign(3,x),y,LID/2))]
    # Printed outside-face down; locating lip extends upward.
    pieces += [diff(cyl(RI-.25,LID,LID+2.5),cyl(RI-1.65,LID-.1,LID+3))]
    solid=union(*pieces)
    cuts=[]
    for x,y in EARS:cuts += [cyl(1.65,-1,LID+1,x,y)]
    return diff(solid,*cuts)

def keeper():
    parts=[cyl(17.5,0,2.4,PX,PY)]
    for x,y in PLUG_SCREWS:parts += [cyl(3.2,0,2.4,x,y)]
    s=union(*parts)
    cuts=[cyl(NECK/2,-1,3,PX,PY)]
    for x,y in PLUG_SCREWS:cuts += [cyl(1.1,-1,3,x,y)]
    s=diff(s,*cuts);s.apply_translation([-PX,-PY,0]);return s

def split_keeper(upper):
    # Split in local Y so both halves each retain two complete screw holes.
    halfspace=box((100,50,10),(0,(25+A['keeper_split_gap']/2)*(1 if upper else -1),2))
    return trimesh.boolean.intersection([keeper(),halfspace],engine='manifold')

meshes={'base-TEST-v7':base(),'lid-TEST-v7':lid(),'plug-keeper-upper-v7':split_keeper(True),'plug-keeper-lower-v7':split_keeper(False)}
def component_count(mesh):
    parent=list(range(len(mesh.vertices)))
    def find(x):
        while parent[x]!=x:
            parent[x]=parent[parent[x]]; x=parent[x]
        return x
    for a,b,c in mesh.faces:
        a,b,c=int(a),int(b),int(c)
        parent[find(b)]=find(a); parent[find(c)]=find(a)
    return len({find(int(v)) for v in mesh.faces.ravel()})

report={}
for name,mesh in meshes.items():
    assert mesh.is_watertight and mesh.is_volume, name
    assert component_count(mesh)==1, name
    mesh.export(OUT/(name+'.stl'))
    report[name]={'watertight':bool(mesh.is_watertight),'connected_solids':component_count(mesh),'bounds_mm':mesh.extents.round(3).tolist(),'volume_mm3':round(float(mesh.volume),2)}
(ROOT/'validation.json').write_text(json.dumps(report,indent=2)+'\n')

fig=plt.figure(figsize=(15,8),facecolor='#f5f5f3')
ax=fig.add_subplot(121,projection='3d');ax.set_title('Base — unpowered fit-check draft',pad=16)
b=meshes['base-TEST-v7']; faces=b.triangles
# Reduce visual density of cylinder triangulation by drawing solid faces without edges.
light=np.array([-.3,-.5,.8]); light/=np.linalg.norm(light)
shade=.58+.42*np.clip(b.face_normals@light,0,1)
colors=np.array([.55,.72,.79])[None,:]*shade[:,None]
ax.add_collection3d(Poly3DCollection(faces,facecolor=colors,edgecolor='none',alpha=1))
# PCB schematic intentionally shows bounding circle, not an invented cutout.
t=np.linspace(0,2*np.pi,180)
ax.plot(R*np.cos(t),R*np.sin(t),np.full_like(t,A['board_bottom_z']+1.7),color='#286544',linewidth=2,linestyle='--')
for x,y in HOLES:ax.scatter([x],[y],[A['board_bottom_z']+M['board_thickness']],color='#286544',s=35)
ax.set(xlim=(-55,55),ylim=(-50,50),zlim=(0,40),xlabel='X (mm)',ylabel='Y (mm)',zlabel='Depth (mm)')
ax.set_box_aspect((110,100,55));ax.view_init(elev=48,azim=-65)
ax2=fig.add_subplot(122);ax2.set_aspect('equal');ax2.set_title('Mounting layout — viewed from inside')
for radius,color,style in [(RO,'#35677a','-'),(R,'#286544','--')]:ax2.plot(radius*np.cos(t),radius*np.sin(t),style,color=color)
for x,y in HOLES:ax2.add_patch(plt.Circle((x,y),2.9,fill=False,color='#286544'))
for x,y in EARS:ax2.add_patch(plt.Circle((x,y),4.8,fill=False,color='#35677a'))
ax2.add_patch(plt.Circle((PX,PY),FLANGE/2,fill=False,color='#c17d32'))
ax2.annotate('Plug center: provisional',(PX,PY),(0,-53),ha='center',arrowprops={'arrowstyle':'->'},color='#9a6024')
ax2.annotate('42.8 mm between holes',(-21.4,HY),(0,25),ha='center',arrowprops={'arrowstyle':'->'})
a=math.radians(90-30*A['sensor_clock_position'])
sensor_xy=(RO*math.cos(a),RO*math.sin(a))
ax2.plot([sensor_xy[0]],[sensor_xy[1]],'o',color='#b04a8b',markersize=9)
ax2.annotate('Sensor shifted 15 mm toward 8 oclock',sensor_xy,(-55,-16),ha='left',fontsize=9,arrowprops={'arrowstyle':'->'},color='#963671')
for led_angle in A['led_arc_angles_degrees']:
    la=math.radians(led_angle)
    ax2.plot([RO*math.cos(la)],[RO*math.sin(la)],'o',color='#df9639',markersize=7)
ax2.text(0,48,'Six LED wall openings',ha='center',color='#286544')
ax2.text(0,-62,'Dashed circle = PCB envelope; actual cutout not modeled.\nPlug / PCB interference still requires physical verification.',ha='center',fontsize=9)
ax2.set(xlim=(-58,58),ylim=(-67,55),xlabel='X (mm)',ylabel='Y (mm)');ax2.grid(alpha=.15)
fig.suptitle(f'Pura electronics-only enclosure v7 | {RO*2:.1f} mm body × {SEAM+LID:.1f} mm depth',fontsize=17,y=.98)
fig.text(.5,.02,'DRAFT • Geometry checked for printable solids; electrical, thermal and plug-retention suitability not established.',ha='center',fontsize=10,color='#8c4a20')
fig.tight_layout(rect=(0,.08,1,.94));fig.savefig(ROOT/'case-preview.png',dpi=160);plt.close(fig)
print(json.dumps(report,indent=2))

# Actual meshes, viewed from the LED side. Lid raised for inspection only.
fig=plt.figure(figsize=(10,8)); ax=fig.add_subplot(111,projection='3d')
for name,color in [('base-TEST-v7',[.48,.67,.76]),('lid-TEST-v7',[.72,.77,.80])]:
    mesh=meshes[name].copy()
    if name.startswith('lid'):
        mesh.apply_transform(trimesh.transformations.rotation_matrix(math.pi,[1,0,0]))
        mesh.apply_translation([0,0,SEAM+LID+12])
    light=np.array([-.3,.5,.8]); light/=np.linalg.norm(light)
    shade=.5+.5*np.clip(mesh.face_normals@light,0,1)
    visible=mesh.face_normals@np.array([0,math.cos(math.radians(22)),math.sin(math.radians(22))])>1e-5
    ax.add_collection3d(Poly3DCollection(mesh.triangles[visible],facecolors=(np.array(color)*shade[:,None])[visible],edgecolors='none',linewidths=0,antialiased=False))
ax.set(xlim=(-56,56),ylim=(-48,48),zlim=(0,51))
ax.set_box_aspect((112,96,55)); ax.view_init(elev=22,azim=90);ax.set_axis_off()
fig.suptitle('v7 — six LED openings in case wall; solid lid',fontsize=15)
fig.text(.5,.04,'Lid shown raised for inspection. LED and sensor positions corrected from your fit feedback.',ha='center',fontsize=10)
fig.tight_layout();fig.savefig(ROOT/'case-led-preview.png',dpi=150);plt.close(fig)
