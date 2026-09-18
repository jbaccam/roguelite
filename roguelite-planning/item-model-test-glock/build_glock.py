"""One reference-matched, non-functional game prop. No internal mechanism."""
import bpy, bmesh, math, json, random
from mathutils import Vector
from pathlib import Path

OUT=Path(__file__).resolve().parent
random.seed(17)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene
asset=bpy.data.collections.new('GLOCK | Export geometry')
scene.collection.children.link(asset)
stage=bpy.data.collections.new('REVIEW | Cameras and lighting (not exported)')
scene.collection.children.link(stage)

def move_to(obj,col):
    for c in list(obj.users_collection): c.objects.unlink(obj)
    col.objects.link(obj)

def srgb(v): return ((v+.055)/1.055)**2.4 if v>.04045 else v/12.92
def material(name,rgb,facets=False):
    m=bpy.data.materials.new(name);m.use_nodes=True
    base=tuple(srgb(v) for v in rgb)
    m.diffuse_color=(*base,1)
    bs=m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value=(*base,1)
    bs.inputs['Roughness'].default_value=.82
    bs.inputs['Specular IOR Level'].default_value=.25
    if facets:
        nt=m.node_tree; n=nt.nodes
        tex=n.new('ShaderNodeTexCoord')
        vor=n.new('ShaderNodeTexVoronoi');vor.distance='EUCLIDEAN';vor.feature='F1';vor.inputs['Scale'].default_value=1.55
        nt.links.new(tex.outputs['Object'],vor.inputs['Vector'])
        bw=n.new('ShaderNodeRGBToBW');nt.links.new(vor.outputs['Color'],bw.inputs[0])
        ramp=n.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].position=.15;ramp.color_ramp.elements[0].color=(*(v*.90 for v in base),1)
        ramp.color_ramp.elements[1].position=.85;ramp.color_ramp.elements[1].color=(*(v*1.07 for v in base),1)
        nt.links.new(bw.outputs[0],ramp.inputs[0]);nt.links.new(ramp.outputs['Color'],bs.inputs['Base Color'])
    return m

slide_mat=material('01 warm charcoal slide',(.195,.185,.181),True)
frame_mat=material('02 charcoal polymer frame',(.179,.173,.168),True)
edge_mat=material('03 exposed broad bevels',(.263,.25,.24),True)
detail_mat=material('04 sight and serration charcoal',(.155,.15,.146))
metal_mat=material('05 controls and muzzle rim',(.232,.219,.212),True)
dark_mat=material('06 recessed cavity',(.035,.033,.031))
trigger_mat=material('07 trigger',(.158,.150,.143),True)

def finish(o,mat,bevel=0,edge=None):
    move_to(o,asset);o.data.materials.append(mat)
    if edge:o.data.materials.append(edge)
    if bevel:
        mod=o.modifiers.new('Single-segment silhouette bevel','BEVEL');mod.width=bevel;mod.segments=1
        mod.affect='EDGES';mod.profile=.5
        if edge:mod.material=1
        bpy.context.view_layer.objects.active=o
        bpy.ops.object.modifier_apply(modifier=mod.name)
    for p in o.data.polygons:p.use_smooth=False
    return o

def prism(name,profile,width,mat,bevel=0,edge=None,y=0):
    # Profile is counter-clockwise in X/Z; thickness along Y.
    vertices=[(x,y-width/2,z) for x,z in profile]+[(x,y+width/2,z) for x,z in profile]
    n=len(profile)
    faces=[tuple(range(n)),tuple(range(2*n-1,n-1,-1))]
    faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    me=bpy.data.meshes.new(name);me.from_pydata(vertices,[],faces);me.update()
    o=bpy.data.objects.new(name,me);asset.objects.link(o)
    bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(me);bm.free()
    return finish(o,mat,bevel,edge)

def box(name,loc,dim,mat,bevel=0,edge=None):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc)
    o=bpy.context.object;o.name=name;o.dimensions=dim
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    return finish(o,mat,bevel,edge)

# Main silhouette. Long rectangular slide, blunt nose and broad one-step chamfers.
slide=box('Slide',(-.12,0,4.115),(6.6,1.06,1.18),slide_mat,.115,edge_mat)
box('Slide to frame recessed seam',(-.10,0,3.507),(6.52,.96,.045),dark_mat,.01)
frame_profile=[(-3.40,3.47),(3.20,3.47),(3.24,3.19),(2.92,3.06),(2.65,2.88),
               (2.54,2.63),(2.65,2.27),(3.23,.61),(3.17,.40),(1.43,.39),
               (.99,1.84),(.74,2.70),(.45,2.91),(-1.03,2.91),(-1.36,2.89),
               (-2.98,2.90),(-3.29,3.00),(-3.42,3.18)]
frame=prism('Frame and raked grip',frame_profile,1.04,frame_mat,.14,edge_mat)
# Fullness at bottom of the grip; the magazine floorplate is distinctly stepped.
prism('Magazine floorplate',[(1.37,.42),(3.19,.43),(3.27,.08),(1.39,.035),(1.31,.14)],1.17,frame_mat,.065,edge_mat)

# Broad dust-cover step at the front and a raised middle receiver ledge.
prism('Front lower dust cover',[(-3.41,3.42),(-1.27,3.42),(-1.27,2.96),(-2.99,2.94),(-3.32,3.03)],1.10,frame_mat,.065,edge_mat)
prism('Receiver side ledge',[(-1.30,3.43),(.54,3.43),(.59,3.02),(-1.21,2.91),(-1.36,3.04)],1.135,frame_mat,.065,edge_mat)

# Guard is one closed ring with a real opening, not a dark inset or filled polygon.
outer=[(-1.30,3.00),(.65,3.00),(1.08,2.69),(1.30,2.10),(1.06,1.60),(.66,1.40),(-.79,1.37),(-1.16,1.51),(-1.25,1.70)]
inner=[(-.92,2.81),(.52,2.81),(.76,2.60),(.96,2.11),(.79,1.85),(.56,1.68),(-.65,1.64),(-.87,1.78),(-.92,1.94)]
verts=[]
for y in [-.445,.445]:
    verts += [(x,y,z) for x,z in outer] + [(x,y,z) for x,z in inner]
n=len(outer);faces=[]
for i in range(n):
    j=(i+1)%n
    faces += [(i,j,n+j,n+i),(2*n+i,3*n+i,3*n+j,2*n+j),
              (i,2*n+i,2*n+j,j),(n+i,n+j,3*n+j,3*n+i)]
me=bpy.data.meshes.new('Guard ring');me.from_pydata(verts,[],faces);me.update()
guard=bpy.data.objects.new('Squared open trigger guard',me);asset.objects.link(guard)
bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(me);bm.free()
finish(guard,frame_mat,.045,edge_mat)

# Curved chunky trigger: visible game-prop surface only, no mechanical internals.
prism('Curved trigger',[(.11,2.96),(.47,2.96),(.51,2.74),(.38,2.43),(.15,2.12),(-.12,1.74),(-.42,1.86),(-.16,2.27),(.015,2.58)],.38,trigger_mat,.038,metal_mat)

# Small side controls seen in the supplied image; mirrored for a clean reverse view.
for side in [-1,1]:
    y=side*.60
    prism('Slide catch '+str(side),[(.44,3.51),(1.10,3.51),(1.16,3.14),(.48,3.12),(.41,3.25)],.13,metal_mat,.04,edge_mat,y)
    prism('Slide catch inset '+str(side),[(.52,3.37),(1.07,3.38),(1.08,3.25),(.52,3.24)],.015,detail_mat,.018,None,side*.675)
    button=prism('Angled magazine release '+str(side),[(1.14,2.26),(1.39,2.32),(1.56,1.90),(1.28,1.81)],.12,metal_mat,.025,edge_mat,side*.573)
    for i in range(2):
        ridge=box('Release rib %s %s'%(side,i),(1.30+i*.074,side*.641,2.071),(.025,.018,.34),detail_mat,.005)
        ridge.rotation_euler.y=-.30

# Six tall rear serrations. Narrow dark grooves and proud bevel-edged lands.
for side in [-1,1]:
    for i in range(6):
        x=1.57+i*.225
        box('Rear groove %s %s'%(side,i),(x-.026,side*.535,4.035),(.085,.024,.88),detail_mat,.015)
        box('Rear serration %s %s'%(side,i),(x+.025,side*.567,4.035),(.079,.071,.885),slide_mat,.016,metal_mat)

# Raised trapezoid front blade and paired rear notch shoulders.
prism('Front sight',[(-3.06,4.67),(-2.36,4.67),(-2.46,5.01),(-2.91,5.01)],.35,detail_mat,.025,metal_mat)
for side in [-1,1]:
    prism('Rear sight notch shoulder '+str(side),[(2.32,4.70),(2.94,4.70),(2.86,5.00),(2.40,5.00)],.22,detail_mat,.024,metal_mat,side*.29)
box('Rear sight base',(2.63,0,4.717),(.64,.86,.065),detail_mat,.018)

# Octagonal muzzle collar and a genuinely recessed, closed blind bore.
def muzzle_ring():
    center=4.10; N=8
    rings=[(-3.40,.435),(-3.555,.395),(-3.565,.292),(-3.455,.265)]
    v=[]
    for x,r in rings:
        for i in range(N):
            a=2*math.pi*(i+.5)/N
            v.append((x,math.cos(a)*r,center+math.sin(a)*r))
    f=[];mi=[]
    for k in range(len(rings)-1):
        for i in range(N):f.append((k*N+i,k*N+(i+1)%N,(k+1)*N+(i+1)%N,(k+1)*N+i));mi.append(0 if k<2 else 1)
    f.append(tuple(range(3*N,4*N)));mi.append(1)
    # Rear cap and the blind bore cap are separate, keeping the shell manifold.
    f.append(tuple(range(N-1,-1,-1)));mi.append(0)
    me=bpy.data.meshes.new('8 sided recessed muzzle');me.from_pydata(v,[],f);me.update()
    o=bpy.data.objects.new('Octagonal muzzle with dark recessed bore',me);asset.objects.link(o)
    o.data.materials.append(metal_mat);o.data.materials.append(dark_mat)
    for p,m in zip(o.data.polygons,mi):p.material_index=m
    bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(me);bm.free()
    # The dark interior overlays the hidden slide nose, making a blind cavity.
    box('Bore shadow at slide face',(-3.432,0,4.10),(.006,.485,.485),dark_mat,.06)
    return o
muzzle_ring()
# Small lower front cap under the barrel.
o=prism('Lower nose cap',[(-.34,3.41),(.34,3.41),(.34,3.12),(.23,3.01),(-.23,3.01),(-.34,3.12)],.055,detail_mat,.025,metal_mat)
# This front-facing cap is authored in Y/Z and placed on the nose.
for v in o.data.vertices:
    x,y,z=v.co;v.co=(-3.445+y,x,z)

# Bake the subtle material breakup to one portable image. Final materials are simple.
objects=list(asset.objects)
bpy.ops.object.select_all(action='DESELECT')
for o in objects:o.select_set(True)
bpy.context.view_layer.objects.active=slide
bpy.ops.object.join()
gun=bpy.context.object;gun.name='Glock_Reference_Test'
bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
# Match the atlas scale to world coordinates (join leaves the slide origin offset).
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(55),island_margin=.012)
bpy.ops.object.mode_set(mode='OBJECT')
atlas=bpy.data.images.new('Glock_BaseColor',width=1024,height=1024,alpha=False)
atlas.colorspace_settings.name='sRGB'
scene.render.engine='CYCLES';scene.cycles.samples=1
scene.render.bake.margin=6
for mat in gun.data.materials:
    nt=mat.node_tree;bs=nt.nodes.get('Principled BSDF');output=nt.nodes.get('Material Output')
    emission=nt.nodes.new('ShaderNodeEmission')
    if bs.inputs['Base Color'].is_linked:nt.links.new(bs.inputs['Base Color'].links[0].from_socket,emission.inputs['Color'])
    else:emission.inputs['Color'].default_value=bs.inputs['Base Color'].default_value
    nt.links.new(emission.outputs[0],output.inputs['Surface'])
    tex=nt.nodes.new('ShaderNodeTexImage');tex.image=atlas;nt.nodes.active=tex
bpy.ops.object.bake(type='EMIT')
atlas.filepath_raw=str(OUT/'Glock_BaseColor.png');atlas.file_format='PNG';atlas.save();atlas.pack()
final=material('Glock | baked base color',(.3,.29,.28))
tex=final.node_tree.nodes.new('ShaderNodeTexImage');tex.image=atlas;tex.interpolation='Linear'
final.node_tree.links.new(tex.outputs['Color'],final.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
gun.data.materials.clear();gun.data.materials.append(final)
for p in gun.data.polygons:p.material_index=0
# Pivot at the grip center. Asset stays one mesh; no hidden stage in export.
scene.cursor.location=(2.08,0,1.50)
bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
gun['Reference']='ChatGPT Image Sep 17, 2026, 03_13_24 PM (7).png'
gun['Status']='Single-item workflow trial; awaiting user approval'
gun['Forward']='-X in Blender; game prop only'

bpy.ops.export_scene.fbx(filepath=str(OUT/'Glock_Reference_Test.fbx'),use_selection=True,object_types={'MESH'},bake_anim=False,axis_forward='-Z',axis_up='Y',path_mode='COPY',embed_textures=True)
bpy.ops.export_scene.gltf(filepath=str(OUT/'Glock_Reference_Test.glb'),use_selection=True,export_format='GLB',export_animations=False)

# Review scene, deliberately neutral to expose the asset without blue presentation.
def aim(o,p):o.rotation_euler=(Vector(p)-o.location).to_track_quat('-Z','Y').to_euler()
floor=material('Review neutral ground',(.56,.56,.56))
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.02));ground=bpy.context.object;ground.name='Review ground';ground.data.materials.append(floor);move_to(ground,stage)
for name,loc,power,size in [('Large soft key',(-4,-6,10),1600,7),('Front fill',(4,-8,6),850,6),('Rim',(1,5,9),1500,5)]:
    bpy.ops.object.light_add(type='AREA',location=loc);o=bpy.context.object;o.name=name;o.data.energy=power;o.data.shape='DISK';o.data.size=size;aim(o,(0,0,2.6));move_to(o,stage)
scene.world.use_nodes=True;scene.world.node_tree.nodes.get('Background').inputs[0].default_value=(.35,.35,.35,1);scene.world.node_tree.nodes.get('Background').inputs[1].default_value=.65
def camera(name,loc,target,scale):
    bpy.ops.object.camera_add(location=loc);o=bpy.context.object;o.name=name;aim(o,target);o.data.type='ORTHO';o.data.ortho_scale=scale;move_to(o,stage);return o
hero=camera('01 Reference comparison',(-7.8,-18,8.3),(-.1,0,2.50),8.55)
side=camera('02 Clear side profile',(0,-22,2.60),(0,0,2.60),8.1)
reverse=camera('03 Opposite side',(7.5,18,8.0),(0,0,2.5),8.55)
scene.render.engine='CYCLES';scene.cycles.samples=48;scene.cycles.use_denoising=True
scene.render.resolution_x=1200;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='AgX'
scene.camera=hero
bpy.ops.object.select_all(action='DESELECT');gun.select_set(True);bpy.context.view_layer.objects.active=gun
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_perspective='CAMERA'
            area.spaces.active.shading.type='MATERIAL'
scene.render.filepath=str(OUT/'Glock_Comparison.png')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Glock_Reference_Test.blend'))
bpy.ops.render.render(write_still=True)
scene.camera=side;scene.render.filepath=str(OUT/'Glock_Side.png');bpy.ops.render.render(write_still=True)
scene.camera=reverse;scene.render.filepath=str(OUT/'Glock_Reverse.png');bpy.ops.render.render(write_still=True)
scene.camera=hero;scene.render.filepath=str(OUT/'Glock_Comparison.png')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Glock_Reference_Test.blend'))
bm=bmesh.new();bm.from_mesh(gun.data)
stats={'vertices':len(gun.data.vertices),'triangles':sum(len(p.vertices)-2 for p in gun.data.polygons),'mesh_objects':1,'materials':len(gun.data.materials),'texture':'1024 x 1024 base color','nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'loose_vertices':sum(not v.link_edges for v in bm.verts),'dimensions':list(gun.dimensions),'status':'Awaiting user visual approval; Roblox import not performed.'}
bm.free();(OUT/'validation.json').write_text(json.dumps(stats,indent=2))
print('GL0CK_TEST_COMPLETE',json.dumps(stats))
