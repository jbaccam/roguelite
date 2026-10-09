-- Run only in Edit. Clones reviewed geometry; never changes the showcase.
assert(not game:GetService('RunService'):IsRunning(),'Stop Play before installation')
local combat=game.ReplicatedStorage:WaitForChild('RogueliteCombat')
local Presentation=require(combat:WaitForChild('WeaponPresentation'))
local Catalog=require(combat:WaitForChild('WeaponCatalog'))
local showcase=workspace:WaitForChild('RogueliteWeaponShowcase_PlaySize')
local templates=Instance.new('Folder');templates.Name='WeaponTemplates'
for _,source in showcase:GetChildren() do
 if not source:IsA('Model') then continue end
 local id=source.Name:match('^(%d%d)_');if not id then continue end
 -- Godly templates come from the Godly installer (studio-install-godly-weapons.luau); never rebuilt here.
 if Catalog.isGodly(id) then continue end
 local model=(id=='03' and combat.KatanaTemplate or source):Clone();model.Name=id;model:PivotTo(CFrame.identity)
 for _,p in model:GetDescendants() do
  if p:IsA('LuaSourceContainer') or p:IsA('JointInstance') or p:IsA('Constraint') then p:Destroy()
  elseif p:IsA('BasePart') then p.Anchored=true;p.CanCollide=false;p.CanTouch=false;p.CanQuery=false;p.PivotOffset=CFrame.identity
   if p:IsA('MeshPart') then p.RenderFidelity=p.Name=='W11_Rocket_Launcher' and Enum.RenderFidelity.Precise or Enum.RenderFidelity.Automatic end
  end
 end
 -- The launcher showcase includes a loose ammunition specimen, not a second equipped weapon.
 if id=='11' then
  local rocket=model:FindFirstChild('W11_Rocket_Component',true);if rocket then rocket:Destroy() end
 end
 local cf,size=model:GetBoundingBox()
 if id=='03' then cf=CFrame.new(model:GetAttribute('BoundsCenter')) end
 model.WorldPivot=cf;model:PivotTo(CFrame.identity)
 -- Imported guns point along +X (the cannon/launcher/washer point -X).
 local guns={['00']=true,['07']=true,['08']=true,['09']=true,['10']=true,['11']=true,['24']=true,['28']=true,['29']=true}
 local rotation=CFrame.identity
 -- The normalized katana's sharp edge points -X; turn it to combat-forward -Z.
 if id=='03' then rotation=CFrame.Angles(0,-math.pi/2,0) end
 if guns[id] then rotation=CFrame.Angles(0,(id=='10' or id=='11' or id=='29') and -math.pi/2 or math.pi/2,0)
 end
 for _,p in model:GetDescendants() do if p:IsA('BasePart') then p.CFrame=rotation*p.CFrame end end
 model.WorldPivot=CFrame.identity
 local bounds,boundsSize=model:GetBoundingBox()
 if id=='03' then
  bounds=CFrame.identity
  local original=combat.KatanaTemplate:GetAttribute('BoundsSize')
  boundsSize=Vector3.new(original.Z,original.Y,original.X)
  model:SetAttribute('KatanaEdgeForward',true)
 end
 model:SetAttribute('BoundsCenter',bounds.Position);model:SetAttribute('BoundsSize',boundsSize)
 Presentation.apply(model)
 model:SetAttribute('SourceDisplay',source:GetFullName());model.Parent=templates
end
-- 2026-10-09: it asserted exactly 36 templates and then destroyed the whole folder, which would wipe
-- the Godly templates (36-41) and any later weapon (Pizza Cutter '42') installed on their own. Now
-- every showcase weapon 00-35 must be there, and only the templates built here are replaced.
for n=0,35 do local id=string.format('%02d',n);assert(templates:FindFirstChild(id),'Showcase is missing weapon '..id..'; old templates remain untouched') end
local previous=combat:FindFirstChild('WeaponTemplates')
if previous then
 for _,model in templates:GetChildren() do local old=previous:FindFirstChild(model.Name);if old then old:Destroy() end;model.Parent=previous end
 templates:Destroy()
else templates.Parent=combat end
local sourceRocket=assert(showcase['11_Rocket_Launcher']:FindFirstChild('W11_Rocket_Component',true),'Modeled rocket missing')
local rocket=Instance.new('Model');rocket.Name='RocketTemplate'
local mesh=sourceRocket:Clone()
for _,child in mesh:GetDescendants() do if not child:IsA('SurfaceAppearance') then child:Destroy() end end
mesh.Anchored=true;mesh.CanCollide=false;mesh.CanTouch=false;mesh.CanQuery=false;mesh.PivotOffset=CFrame.identity;mesh.RenderFidelity=Enum.RenderFidelity.Automatic
mesh.CFrame=CFrame.Angles(0,-math.pi/2,0);mesh.Parent=rocket;rocket.WorldPivot=CFrame.identity
rocket:SetAttribute('Length',mesh.Size.X);rocket:SetAttribute('SourceDisplay',sourceRocket:GetFullName())
local oldRocket=combat:FindFirstChild('RocketTemplate');if oldRocket then oldRocket:Destroy() end
rocket.Parent=combat
for _,name in {'EquipWeapon','Shot','ZombiePopped','RocketFX','PlayerDamaged'} do
 if not combat:FindFirstChild(name) then
  local event=Instance.new('RemoteEvent');event.Name=name;event.Sandboxed=true
  event.Capabilities=SecurityCapabilities.new(Enum.SecurityCapability.Basic,Enum.SecurityCapability.RemoteEvent);event.Parent=combat
 end
end
return 'Installed the showcase weapon templates (00-35 and any other non-Godly) and loadout remotes'
