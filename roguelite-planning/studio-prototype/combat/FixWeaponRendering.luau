-- Edit-time render policy: Automatic by default; provisional Precise exception for the RPG bore.
assert(not game:GetService('RunService'):IsRunning(),'Apply in Edit mode')
local combat=game.ReplicatedStorage:FindFirstChild('RogueliteCombat')
local roots={}
if combat then
 for _,name in {'WeaponTemplates','KatanaTemplate','RocketTemplate'} do
  local root=combat:FindFirstChild(name);if root then table.insert(roots,root) end
 end
end
for _,name in {'RogueliteWeaponShowcase','RogueliteWeaponShowcase_PlaySize'} do
 local root=workspace:FindFirstChild(name);if root then table.insert(roots,root) end
end
local report={meshes=0,changed=0,issues={}}
for _,root in roots do
 for _,mesh in root:GetDescendants() do
  if mesh:IsA('MeshPart') then
   local size,cf,pivot,id,texture=mesh.Size,mesh.CFrame,mesh.PivotOffset,mesh.MeshId,mesh.TextureID
   local desired=mesh.Name=='W11_Rocket_Launcher' and Enum.RenderFidelity.Precise or Enum.RenderFidelity.Automatic
   if mesh.RenderFidelity~=desired then report.changed+=1 end
   mesh.RenderFidelity=desired
   assert(mesh.Size==size and mesh.CFrame==cf and mesh.PivotOffset==pivot and mesh.MeshId==id and mesh.TextureID==texture,'Appearance changed unexpectedly')
   report.meshes+=1
   if id=='' then table.insert(report.issues,mesh:GetFullName()..': missing mesh') end
  end
 end
end
if combat and combat:FindFirstChild('WeaponTemplates') then
 for _,model in combat.WeaponTemplates:GetChildren() do
  for _,part in model:GetDescendants() do
   if part:IsA('BasePart') then
    -- Visual weapons are moved with PivotTo; physics must never compete with their poses.
    part.Anchored=true;part.CanCollide=false;part.CanTouch=false;part.CanQuery=false
   end
  end
 end
end
return report
