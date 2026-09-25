"""Geometry/inspection helpers. No shared character templates or proportions."""
import bpy,bmesh,math,random,json,sys
from pathlib import Path
from mathutils import Vector,Quaternion
ROOT=Path(__file__).resolve().parent
random.seed(82)

def reset(name):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    out=ROOT/name;out.mkdir(parents=True,exist_ok=True)
    return out

def mat(name,color,variation=.15,scale=5,rough=.83):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
    n=m.node_tree.nodes;l=m.node_tree.links;p=n.get('Principled BSDF')
    p.inputs['Roughness'].default_value=rough;p.inputs['Specular IOR Level'].default_value=.18
    tex=n.new('ShaderNodeTexNoise');tex.inputs['Scale'].default_value=scale;tex.inputs['Detail'].default_value=2;tex.inputs['Roughness'].default_value=.65
    ramp=n.new('ShaderNodeValToRGB');ramp.color_ramp.interpolation='EASE'
    ramp.color_ramp.elements.remove(ramp.color_ramp.elements[1])
    for i,(pos,value) in enumerate([(.18,1-variation),(.40,1-variation*.25),(.60,1+variation*.40),(.75,1+variation)]):
        e=ramp.color_ramp.elements[0] if i==0 else ramp.color_ramp.elements.new(pos);e.position=pos;e.color=(*(min(1,c*value) for c in color),1)
    l.new(tex.outputs['Fac'],ramp.inputs[0]);l.new(ramp.outputs[0],p.inputs['Base Color'])
    return m

def finish(o,name,m=None):
    o.name=name
    if m:o.data.materials.clear();o.data.materials.append(m)
    return o

def ell(name,p,s,m,segments=24,rings=16):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments,ring_count=rings,location=p)
    o=bpy.context.object;o.scale=s;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    return finish(o,name,m)

def cube(name,p,s,m,bevel=.1):
    bpy.ops.mesh.primitive_cube_add(size=1,location=p);o=bpy.context.object;o.dimensions=s
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if bevel:
        mod=o.modifiers.new('Form roundover','BEVEL');mod.width=bevel;mod.segments=3;bpy.ops.object.modifier_apply(modifier=mod.name)
    return finish(o,name,m)

def mesh(name,v,f,m):
    me=bpy.data.meshes.new(name);me.from_pydata(v,[],f);me.update();o=bpy.data.objects.new(name,me);bpy.context.collection.objects.link(o)
    bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free()
    return finish(o,name,m)

def tube(name,points,radii,m,n=12):
    pts=[Vector(p) for p in points];v=[];previous=None
    # Parallel transported frame avoids the reference-up flip that pinched the old snake.
    for i,p in enumerate(pts):
        tangent=(pts[min(i+1,len(pts)-1)]-pts[max(0,i-1)]).normalized()
        if previous is None:
            ref=Vector((1,0,0)) if abs(tangent.x)<.9 else Vector((0,1,0));u=(ref-tangent*tangent.dot(ref)).normalized()
        else:u=(previous-tangent*tangent.dot(previous)).normalized()
        w=tangent.cross(u).normalized();previous=u
        rr=radii[i] if isinstance(radii,list) else radii;rx,ry=rr if isinstance(rr,tuple) else (rr,rr)
        for k in range(n):
            a=k*math.tau/n;v.append(p+u*math.cos(a)*rx+w*math.sin(a)*ry)
    f=[tuple(range(n-1,-1,-1))]
    for j in range(len(pts)-1):
        for k in range(n):f.append((j*n+k,j*n+(k+1)%n,(j+1)*n+(k+1)%n,(j+1)*n+k))
    f.append(tuple(range((len(pts)-1)*n,len(pts)*n)))
    return mesh(name,v,f,m)

def join(objects,name):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:o.select_set(True)
    bpy.context.view_layer.objects.active=objects[0];bpy.ops.object.join();o=bpy.context.object;o.name=name
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    return o

def fuse(objects,name,m,voxel=.065,triangles=15000,smooth=3):
    o=join(objects,name);o.data.remesh_voxel_size=voxel
    bpy.ops.object.voxel_remesh()
    mod=o.modifiers.new('Sculpt blend','SMOOTH');mod.factor=.72;mod.iterations=smooth;bpy.ops.object.modifier_apply(modifier=mod.name)
    o.data.calc_loop_triangles();count=len(o.data.loop_triangles)
    if count>triangles:
        mod=o.modifiers.new('Sculpt topology','DECIMATE');mod.ratio=triangles/count;bpy.ops.object.modifier_apply(modifier=mod.name)
    finish(o,name,m)
    return o

def cut(o,cutter):
    bpy.context.view_layer.objects.active=o
    mod=o.modifiers.new('Carved anatomy','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter
    bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(cutter,do_unlink=True)

def rigid(o,bone):
    o['rigid_bone']=bone;return o

def grip(name,center,axis,m,side=1,handle_radius=.105,bone_name=None,wrist=None):
    """Boxed palm behind the handle; four bent phalanges and an opposing thumb.
    Fingers are open three-joint chains, never circular cuffs/rings. All pieces
    connect to the palm, which meets the wrist on the back of the grasp.
    """
    c=Vector(center);a=Vector(axis).normalized();u=Vector((side,0,0));u=(u-a*a.dot(u)).normalized()
    front=-(Vector(wrist)-c) if wrist is not None else Vector((0,-1,0));front=(front-a*front.dot(a)-u*front.dot(u))
    if front.length<.01:front=a.cross(u)
    front.normalize();r=handle_radius;objects=[]
    def at(x,y,z):return c+u*x+front*y+a*z
    palm=cube(name+' metacarpal palm',(0,0,0),(.43,.17,.55),m,.035)
    for vertex in palm.data.vertices:
        x,y,z=vertex.co;vertex.co=at(x,y-r-.09,z)
    objects.append(palm)
    for j in range(4):
        z=.207-j*.138;tip=.94 if j==3 else 1
        pts=[at(.17,-r-.05,z),at(r+.067,-r*.28,z),at(r+.045,r+.053,z),at(-r*.28,r+.063,z),at(-r-.012,r*.34,z)]
        objects.append(tube(name+' finger '+str(j+1),pts,[(.066*tip,.061*tip)]*5,m,8))
    thumb=[at(-.21,-r-.025,.19),at(-r-.15,-.02,.20),at(-r-.10,r+.062,.11),at(-.035,r+.115,.075)]
    objects.append(tube(name+' opposing thumb',thumb,[(.092,.083),(.090,.083),(.084,.075),(.071,.063)],m,8))
    for o in objects:
        if bone_name:rigid(o,bone_name)
    return objects

def cloth_shell(name,levels,m,n=40,hem=.0,vneck=0):
    vertices=[]
    for j,(z,rx,ry) in enumerate(levels):
        for k in range(n):
            a=k*math.tau/n;zz=z
            if j==0:zz+=hem*(.6*math.sin(k*2.74)+.4*math.sin(k*4.83))
            if j==len(levels)-1:zz-=vneck*max(0,-math.sin(a))**6
            vertices.append((rx*math.cos(a),ry*math.sin(a),zz))
    faces=[(j*n+k,j*n+(k+1)%n,(j+1)*n+(k+1)%n,(j+1)*n+k) for j in range(len(levels)-1) for k in range(n)]
    o=mesh(name,vertices,faces,m);bpy.context.view_layer.objects.active=o
    mod=o.modifiers.new('Cloth thickness','SOLIDIFY');mod.thickness=.035;bpy.ops.object.modifier_apply(modifier=mod.name)
    return o

def render(out,objects,aim_at=None,size=None):
    scene=bpy.context.scene
    coords=[o.matrix_world@v.co for o in objects for v in o.data.vertices]
    lo=Vector([min(v[a] for v in coords) for a in range(3)]);hi=Vector([max(v[a] for v in coords) for a in range(3)])
    center=(lo+hi)/2 if aim_at is None else Vector(aim_at);span=max(hi-lo) if size is None else size
    stage=bpy.data.collections.new('REVIEW_ONLY');scene.collection.children.link(stage)
    def add(o):
        for c in list(o.users_collection):c.objects.unlink(o)
        stage.objects.link(o)
    def aim(o):o.rotation_euler=(center-o.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.mesh.primitive_plane_add(size=100,location=(0,0,min(lo.z-.015,0)));floor=bpy.context.object;add(floor)
    floor.data.materials.append(mat('Stage',(.23,.22,.21),0))
    scene.world=bpy.data.worlds.new('Neutral');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.60,.62,.68,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.42
    for position,power,scale in [((-1.3,-1.6,1.8),1200,.85),((1.5,-.6,1),420,1),((.3,1.1,1.7),1000,.65)]:
        bpy.ops.object.light_add(type='AREA',location=center+Vector(position)*span);o=bpy.context.object;o.data.energy=power*(span/6)**2;o.data.size=span*scale;aim(o);add(o)
    bpy.ops.object.camera_add(location=center+Vector((.9,-2.6,.65))*span);cam=bpy.context.object;cam.data.type='ORTHO';cam.data.ortho_scale=span*1.2;aim(cam);add(cam);scene.camera=cam
    scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True
    scene.render.resolution_x=1100;scene.render.resolution_y=1100;scene.render.resolution_percentage=100;scene.view_settings.view_transform='AgX'
    scene.render.image_settings.file_format='PNG'
    for label,pos in [('Preview',(.9,-2.6,.65)),('Front',(0,-3,.12)),('Side',(3,0,.15)),('Back',(-.7,2.7,.5))]:
        cam.location=center+Vector(pos)*span;aim(cam);scene.render.filepath=str(out/(label+'.png'));bpy.ops.render.render(write_still=True)
    cam.location=center+Vector((.9,-2.6,.65))*span;aim(cam)
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'Sculpt.blend'))
