import bpy, json, math, struct, urllib.request, zlib, random, gzip
from pathlib import Path
from mathutils import Vector
import numpy as np

OUT=Path(__file__).resolve().parent
(OUT/'textures').mkdir(exist_ok=True)
(OUT/'stock_meshes').mkdir(exist_ok=True)
data=json.loads((OUT/'stock_r15.json').read_text())
parts={p['name']:p for p in data['parts']}
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene
GREEN=np.array([64,131,54],dtype=float)
SHIFT=3.000011
def cv(v): return (v[0],v[2],v[1]+SHIFT)

# Lossless image-based color maps, authored here inside Blender.
def png(name,pixels):
    p=OUT/'textures'/name
    arr=np.asarray(np.clip(pixels,0,255),dtype=np.uint8)
    h,w,_=arr.shape
    def chunk(t,d): return struct.pack('>I',len(d))+t+d+struct.pack('>I',zlib.crc32(t+d)&0xffffffff)
    p.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(b'\x00'+row.tobytes() for row in arr)))+chunk(b'IEND',b''))
    im=bpy.data.images.load(str(p));im.pack();return im
def imagematerial(name,im):
    m=bpy.data.materials.new(name);m.use_nodes=True
    bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Roughness'].default_value=1
    bs.inputs['Specular IOR Level'].default_value=.12
    n=m.node_tree.nodes.new('ShaderNodeTexImage');n.image=im;n.interpolation='Linear'
    m.node_tree.links.new(n.outputs['Color'],bs.inputs['Base Color']);return m

skinarr=np.tile(GREEN,(256,256,1))
yy,xx=np.mgrid[0:256,0:256]
for cx,cy,rx,ry in []:
    mask=((xx-cx)/rx)**2+((yy-cy)/ry)**2<1
    skinarr[mask]=GREEN*.89
skin=imagematerial('Skin RGB 64 131 54',png('Zombie_Skin.png',skinarr))

# Flat Roblox-style face, no modeled eye sockets, lips, nose, or teeth.
facearr=np.tile(GREEN,(512,512,1)); yy,xx=np.mgrid[0:512,0:512]
def rect(x0,y0,x1,y1,c): facearr[y0:y1,x0:x1]=c
def ellipse(cx,cy,rx,ry,c): facearr[((xx-cx)/rx)**2+((yy-cy)/ry)**2<1]=c
for cx in (163,349):
    ellipse(cx,225,57,49,(35,71,29))
    ellipse(cx,226,39,31,(222,217,155))
    rect(cx-54,175,cx+54,215,(25,43,20))
# An uneven flat dark mouth with a few irregular intact teeth.
rect(158,322,348,382,(23,31,17));rect(176,306,318,394,(23,31,17))
for x,y,w,h in [(181,308,25,24),(242,308,24,20),(297,322,24,20),(202,370,25,23),(275,371,24,22)]:rect(x,y,x+w,y+h,(203,195,145))
for cx,cy in []:ellipse(cx,cy,7,9,(49,108,41))
face=imagematerial('Flat zombie face image',png('Zombie_Face.png',facearr))

# Clothing atlas: one six-face tile per stock body part. Skin-color holes
# indicate torn cloth only; all underlying limbs remain complete.
names=[n for n in parts if n not in ('HumanoidRootPart','Head')]
N=192; atlas=np.zeros((4*2*N,4*3*N,3),dtype=np.uint8)
def painted(name,xyz):
    x,y,z=xyz
    shape=x.shape
    rgb=np.zeros(shape+(3,),float)
    rgb[:]=GREEN
    arm='Arm' in name
    torso='Torso' in name
    leg='Leg' in name
    foot='Foot' in name
    # Broad, quiet wear, no repeated dot/speckle pattern.
    noise=np.sin(x*2.7+z*1.3+y*.8)+.55*np.cos(y*3.1-z*2.2+x*.6)
    dirt=1-.065*np.clip(noise-.25,0,1)
    if torso or arm:
        # Irregular spaced tears with distinct lengths, not a periodic sawtooth.
        hem=-.77+.025*np.sin(x*3.2+z*2)
        hem+=.23*np.maximum(0,1-abs(x+.64)/.14)
        hem+=.12*np.maximum(0,1-abs(x+.12)/.075)
        hem+=.31*np.maximum(0,1-abs(x-.48)/.22)
        if arm:
            side=1 if 'Left' in name else -1
            hem=.03+.05*np.sin(x*3+z*4)
            hem+=(.23 if side==1 else .13)*np.maximum(0,1-abs(z+(.17 if side==1 else -.22))/.19)
            hem+=(.09 if side==1 else .28)*np.maximum(0,1-abs(z-(.35 if side==1 else .04))/.09)
        clothmask=y>hem
        rgb[clothmask]=np.array([112,86,60])*dirt[clothmask,None]
        # Simple crew neckline, not a lapelled vest.
        neck=(abs(x)<.30)&(y>.81)&(z<-.42)
        rgb[neck]=GREEN
        # Torn small patches exposing skin, no holes in body geometry.
        tear=(abs(x+.58+(y-.13)*.32)+abs((y-.13)*1.8)<.11)&(z<-.42)
        if torso:rgb[tear]=GREEN
        # A plain understated central shirt seam.
        seam=(abs(x)<.012)&(z<-.46)&clothmask
        if torso:rgb[seam]=[87,65,45]
    elif leg or foot:
        rgb[:]=np.array([74,56,42])*dirt[...,None]
        patch=(abs(x+.52+(y+2.10)*.35)+abs((y+2.10)*1.5)<.15)&(z<-.42)
        rgb[patch]=GREEN
        edge=-2.68+.02*np.sin(x*4+z*3)
        edge+=.19*np.maximum(0,1-abs(x-.63)/.13)
        edge+=.09*np.maximum(0,1-abs(x+.35)/.08)
        ragged=(y<edge)&(y>-2.72)&(z<-.4)
        rgb[ragged]=GREEN
        shoe=y<-2.72
        rgb[shoe]=[48,37,28]
        sole=y<-2.94
        rgb[sole]=[34,28,22]
    return rgb

# Per-face projections use unmodified Roblox stock part coordinates.
def facecoords(side,u,v,p):
    sx,sy,sz=p['size'];px,py,pz=p['cf'][:3]
    if side==0:return px+(u-.5)*sx,py+(v-.5)*sy,np.full(u.shape,pz-sz/2)
    if side==1:return px+(.5-u)*sx,py+(v-.5)*sy,np.full(u.shape,pz+sz/2)
    if side==2:return np.full(u.shape,px-sx/2),py+(v-.5)*sy,pz+(.5-u)*sz
    if side==3:return np.full(u.shape,px+sx/2),py+(v-.5)*sy,pz+(u-.5)*sz
    if side==4:return px+(u-.5)*sx,np.full(u.shape,py+sy/2),pz+(v-.5)*sz
    return px+(u-.5)*sx,np.full(u.shape,py-sy/2),pz+(.5-v)*sz
for i,name in enumerate(names):
    for side in range(6):
        vv,uu=np.mgrid[0:N,0:N]/(N-1)
        rgb=painted(name,facecoords(side,uu,1-vv,parts[name]))
        row=(i//4)*2+side//3;col=(i%4)*3+side%3
        atlas[row*N:(row+1)*N,col*N:(col+1)*N]=rgb
clothes=imagematerial('Basic worn brown clothing image',png('Zombie_Clothing.png',atlas))

objects={}
for name,p in parts.items():
    if name=='HumanoidRootPart':continue
    if name=='Head':
        bpy.ops.mesh.primitive_cube_add(size=1,location=cv(p['cf'][:3]));o=bpy.context.object
        o.dimensions=(p['size'][0],p['size'][2],p['size'][1]);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        o.data.materials.append(skin);o.data.materials.append(face)
        uv=o.data.uv_layers.active
        for poly in o.data.polygons:
            front=sum(o.data.vertices[vi].co.y for vi in poly.vertices)/len(poly.vertices)<-p['size'][2]*.49
            poly.material_index=1 if front else 0
            for li in poly.loop_indices:
                v=o.data.vertices[o.data.loops[li].vertex_index].co
                uv.data[li].uv=(v.x/p['size'][0]+.5,v.z/p['size'][1]+.5)
        bevel=o.modifiers.new('Tiny block-head edge','BEVEL');bevel.width=.018;bevel.segments=1
        bpy.ops.object.modifier_apply(modifier=bevel.name)
    else:
        asset=p['mesh']; file=OUT/'stock_meshes'/(name+'.mesh')
        if not file.exists():file.write_bytes(urllib.request.urlopen(asset).read())
        raw=file.read_bytes()
        if raw[:2]==b'\x1f\x8b':raw=gzip.decompress(raw)
        end=raw.index(b'\n')+1
        assert raw[:end].startswith(b'version 2.00'),(name,raw[:end])
        hs,vs,fs,nv,nf=struct.unpack_from('<HBBII',raw,end)
        verts=np.array([struct.unpack_from('<fff',raw,end+hs+i*vs) for i in range(nv)])
        lo,hi=verts.min(axis=0),verts.max(axis=0)
        verts=(verts-(lo+hi)/2)/(hi-lo)*np.array(p['size'])
        faces=[struct.unpack_from('<III',raw,end+hs+nv*vs+i*fs) for i in range(nf)]
        # Swap Y/Z (reflection), reversing faces to retain outward winding.
        coords=[(v[0],v[2],v[1]) for v in verts]
        me=bpy.data.meshes.new(name);me.from_pydata(coords,[],[tuple(reversed(f)) for f in faces]);me.update()
        o=bpy.data.objects.new(name,me);scene.collection.objects.link(o);o.location=cv(p['cf'][:3])
        o.data.materials.append(skin if 'Hand' in name else clothes)
        uv=me.uv_layers.new(name='UVMap');idx=names.index(name)
        for poly in me.polygons:
            normal=poly.normal;axis=max(range(3),key=lambda k:abs(normal[k]))
            side= (3 if normal.x>0 else 2) if axis==0 else ((1 if normal.y>0 else 0) if axis==1 else (4 if normal.z>0 else 5))
            for li in poly.loop_indices:
                v=me.vertices[me.loops[li].vertex_index].co;sx,sy,sz=p['size']
                if side==0:u,w=v.x/sx+.5,v.z/sy+.5
                elif side==1:u,w=.5-v.x/sx,v.z/sy+.5
                elif side==2:u,w=.5-v.y/sz,v.z/sy+.5
                elif side==3:u,w=v.y/sz+.5,v.z/sy+.5
                elif side==4:u,w=v.x/sx+.5,v.y/sz+.5
                else:u,w=v.x/sx+.5,.5-v.y/sz
                if 'Hand' in name:uv.data[li].uv=(u,w)
                else:uv.data[li].uv=(((idx%4)*3+side%3+(.003+u*.994))/12,1-((idx//4)*2+side//3+(.003+(1-w)*.994))/8)
    o.name=name;objects[name]=o

# All fifteen sections, with exact stock joint attachments retained as metadata.
parents={'LowerTorso':'HumanoidRootPart','UpperTorso':'LowerTorso','Head':'UpperTorso'}
jointnames={'LowerTorso':'Root','UpperTorso':'Waist','Head':'Neck'}
for side in ('Left','Right'):
    for part,parent,j in [('UpperArm','UpperTorso','Shoulder'),('LowerArm',side+'UpperArm','Elbow'),('Hand',side+'LowerArm','Wrist'),('UpperLeg','LowerTorso','Hip'),('LowerLeg',side+'UpperLeg','Knee'),('Foot',side+'LowerLeg','Ankle')]:parents[side+part]=parent;jointnames[side+part]=side+j
bpy.ops.object.armature_add();rig=bpy.context.object;rig.name='Stock_R15_Zombie_Rig'
bpy.ops.object.mode_set(mode='EDIT');eb=rig.data.edit_bones;eb.remove(eb[0]);root=eb.new('HumanoidRootPart');root.head=cv((0,0,0));root.tail=cv((0,.3,0))
for name,o in objects.items():
    att=next(a for a in data['attachments'] if a['parent']==name and a['name']==jointnames[name]+'RigAttachment')
    p=parts[name];position=[p['cf'][i]+att['cf'][i] for i in range(3)]
    bone=eb.new(name);bone.head=cv(position);bone.tail=bone.head+Vector((0,0,.25))
for name in objects:eb[name].parent=eb[parents[name]]
bpy.ops.object.mode_set(mode='OBJECT')
for name,o in objects.items():
    vg=o.vertex_groups.new(name=name);vg.add(list(range(len(o.data.vertices))),1,'REPLACE')
    mod=o.modifiers.new('Stock R15 joint rig','ARMATURE');mod.object=rig;o.parent=rig
    o['RobloxStockMesh']=parts[name]['mesh'];o['StockSize']=parts[name]['size']
rig['SkinRGB']='64,131,54';rig['RigType']='R15';rig['PreviewOnly']=True
assert len(objects)==15 and len(rig.data.bones)==16

def aim(o,p):o.rotation_euler=(Vector(p)-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.mesh.primitive_plane_add(size=200);floor=bpy.context.object;floor.name='Preview ground'
fm=bpy.data.materials.new('Neutral gray');fm.diffuse_color=(.12,.14,.16,1);floor.data.materials.append(fm)
bpy.ops.object.camera_add(location=(7,-23,8));cam=bpy.context.object;aim(cam,(0,0,2.6));cam.data.type='ORTHO';cam.data.ortho_scale=6.6;scene.camera=cam
for loc,power,size in [((-5,-7,10),650,7),((5,-3,7),350,6),((0,5,9),500,5)]:
    bpy.ops.object.light_add(type='AREA',location=loc);o=bpy.context.object;o.data.energy=power;o.data.size=size;aim(o,(0,0,2.5))
scene.world.color=(.20,.20,.20);scene.render.engine='CYCLES';scene.cycles.samples=48;scene.cycles.use_denoising=True
scene.render.resolution_x=1000;scene.render.resolution_y=1100;scene.render.resolution_percentage=100
scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.render.image_settings.file_format='PNG'
scene.render.filepath=str(OUT/'Zombie_Stock_R15_Preview.png')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Zombie_Stock_R15_Preview.blend'))
bpy.ops.render.render(write_still=True)
print('STOCK_R15_PREVIEW_COMPLETE: 15 sections, 16 bones, actual Roblox limb meshes; no export or Studio replacement.')
