-- Edit-time, idempotent repair for the reviewed RPG. Preserve mesh, texture, scale and pose.
assert(not game:GetService('RunService'):IsRunning(),'Apply in Edit mode')
local roots={}
local combat=game.ReplicatedStorage:FindFirstChild('RogueliteCombat')
local templates=combat and combat:FindFirstChild('WeaponTemplates')
if templates and templates:FindFirstChild('11') then table.insert(roots,templates['11']) end
for _,name in {'RogueliteWeaponShowcase','RogueliteWeaponShowcase_PlaySize'} do
 local showcase=workspace:FindFirstChild(name)
 if showcase then for _,model in showcase:GetChildren() do if model.Name:match('^11_') then table.insert(roots,model) end end end
end
local changed=0
for _,model in roots do for _,mesh in model:GetDescendants() do
 if mesh:IsA('MeshPart') and mesh.Name=='W11_Rocket_Launcher' then
  mesh.RenderFidelity=Enum.RenderFidelity.Precise
  changed+=1
 end
end end
return {reviewedLauncherMeshes=changed,renderFidelity='Precise'}
