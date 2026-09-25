import bpy,bmesh,json
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parent;out=ROOT/'rock-throwing-crab';bpy.ops.wm.open_mainfile(filepath=str(out/'Model.blend'));rig=bpy.data.objects['Rig']
rig.animation_data.action=None
for t in rig.animation_data.nla_tracks:t.mute=True
for p in rig.pose.bones:p.location=(0,0,0);p.rotation_quaternion=(1,0,0,0);p.scale=(1,1,1)
o=bpy.data.objects['RightClaw_Geometry'];bm=bmesh.new();bm.from_mesh(o.data);bm.verts.ensure_lookup_table();unseen=set(bm.verts);comps=[]
while unseen:
    seed=unseen.pop();stack=[seed];comp=[seed]
    while stack:
        v=stack.pop()
        for e in v.link_edges:
            w=e.other_vert(v)
            if w in unseen:unseen.remove(w);stack.append(w);comp.append(w)
    comps.append(comp)
c=Vector(json.loads((out/'anatomy.json').read_text())['rockContact']['rockCenter']);chosen=min(comps,key=lambda vv:(sum((v.co for v in vv),Vector())/len(vv)-c).length)
keep={v.index for v in chosen};bm.free()
stone=o.copy();stone.data=o.data.copy();bpy.context.scene.collection.objects.link(stone);stone.name='HeldRock';stone['held_projectile']=True
for obj,remove in [(stone,False),(o,True)]:
    bm=bmesh.new();bm.from_mesh(obj.data);bm.verts.ensure_lookup_table();bmesh.ops.delete(bm,geom=[v for v in bm.verts if (v.index in keep)==remove],context='VERTS');bm.to_mesh(obj.data);bm.free()
bpy.ops.wm.save_as_mainfile(filepath=str(out/'Model.blend'))
projectile=stone.copy();projectile.data=stone.data.copy();bpy.context.scene.collection.objects.link(projectile);projectile.name='RockProjectile';projectile.parent=None
for m in list(projectile.modifiers):projectile.modifiers.remove(m)
for v in projectile.data.vertices:v.co-=c
projectile.vertex_groups.clear();bpy.ops.object.select_all(action='DESELECT');projectile.select_set(True);bpy.context.view_layer.objects.active=projectile
bpy.ops.export_scene.fbx(filepath=str(out/'RockProjectile.fbx'),use_selection=True,object_types={'MESH'},bake_anim=False,path_mode='COPY',embed_textures=True,axis_forward='-Z',axis_up='Y')
bpy.ops.export_scene.gltf(filepath=str(out/'RockProjectile.glb'),use_selection=True,export_format='GLB',export_animations=False)
