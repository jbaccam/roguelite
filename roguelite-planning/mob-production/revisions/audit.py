from pathlib import Path
import json,hashlib
root=Path(__file__).resolve().parent
ids=['ice-elf']+[x[0] for x in json.loads((root.parent/'briefs.json').read_text())]
rows=[];errors=[]
for mob in ids:
    out=root/mob
    manifest=json.loads((out/'manifest.json').read_text())
    report=json.loads((out/'validation.json').read_text()) if (out/'validation.json').exists() else {}
    hashes=report.get('fileHashes',{})
    ok=bool(hashes) and all(hashlib.sha256((out/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
    if not ok:errors.append(mob)
    geometry=json.loads((out/'Geometry.json').read_text())
    verts=[v for p in geometry.values() for v in p['vertices']]
    lo=[min(v[a] for v in verts) for a in range(3)];hi=[max(v[a] for v in verts) for a in range(3)]
    manifest['boundsAuthoring']={'minimum':lo,'maximum':hi,'size':[hi[a]-lo[a] for a in range(3)]}
    manifest['status']='Revision candidate; exchange checks passed; Studio validation pending' if ok else 'Revision candidate; exchange validation pending'
    manifest['textureMethod']='Original AI-generated revisions/Materials.png atlas, packed and exported; no source-pixel edits.'
    manifest['optionalLaterMob']=mob=='spitter-zombie'
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    rows.append(f"| {mob} | {manifest['triangles']:,} | {manifest['boneCount']} | {hi[2]-lo[2]:.2f} | {'Passed' if ok else 'Pending'} |")
text='''# Revised mob asset verification

The table reflects hashes of the actual final BLEND, FBX, GLB, texture and five animation FBX files. Each passing asset was independently reopened/imported in Blender. Checks cover finite geometry, nonzero faces, closed component topology, UVs, loaded textures, normalized skin weights (at most four), expected bones, actual mesh deformation, five nonconstant animation clips and GLB actions.

These are asset checks, not artistic approval, Roblox import, combat correctness, mobile performance or multiplayer testing. Base authoring meshes have no LOD system. Height includes any raised equipment. Import scale and collider dimensions still need verification in the actual game.

Existing user-made Pine Valley zombie masters are preserved. Spitter Zombie is an optional later-roster candidate. No bosses were built.

| Mob | Triangles | Bones | Authoring height | Exchange checks |
|---|---:|---:|---:|---|
'''+ '\n'.join(rows)+'\n'
(root/'VALIDATION.md').write_text(text)
(root/'audit.json').write_text(json.dumps({'checked':len(ids),'passed':len(ids)-len(errors),'pending':errors},indent=2))
print(json.dumps({'checked':len(ids),'passed':len(ids)-len(errors),'pending':errors}))
