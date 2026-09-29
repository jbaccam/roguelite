-- Builds the egg chicken templates after ONE Studio 3D Import of
-- roguelite-planning/blender-derp-chicken/exports/fbx/derp-chicken.fbx (default settings).
-- Run in Edit from the command bar or MCP. Creates:
--   ServerStorage.RogueliteAllies.EggChicken       server-owned Humanoid rig (EggChickens.luau)
--   ReplicatedStorage.RogueliteCombat.ChickenFeather  one feather for the pop (RogueliteChickens)
-- and moves the raw import to ServerStorage.RogueliteAllies.RawImport. Safe to re-run after a
-- re-import: the old templates are replaced.
--
-- Part centres and joint pivots come from blender-derp-chicken/studio-install-data.json (Studio
-- axes, origin = ground point under the hip line, identity rest rotation). Textures use
-- MeshPart.TextureID: a SurfaceAppearance from the importer is converted, because
-- SurfaceAppearance can render blank in Play.
local ServerStorage=game:GetService('ServerStorage')
local RS=game:GetService('ReplicatedStorage')
local HIP=0.55 -- hip line height = Humanoid.HipHeight (root part bottom)
local DATA={
 Chicken_Body={center=Vector3.new(0,1.24,0.3482),pivot=Vector3.new(0,0.55,0),size=Vector3.new(1.2945,1.4324,1.936)},
 Chicken_Head={center=Vector3.new(-0.0065,1.8999,-0.901),pivot=Vector3.new(0,1.38,-0.55),size=Vector3.new(0.9102,1.4397,1.118)},
 Chicken_WingL={center=Vector3.new(-0.6354,1.1567,0.0943),pivot=Vector3.new(-0.61,1.44,-0.36),size=Vector3.new(0.1657,0.6021,1.0998)},
 Chicken_WingR={center=Vector3.new(0.6354,1.1567,0.0943),pivot=Vector3.new(0.61,1.44,-0.36),size=Vector3.new(0.1657,0.6021,1.0998)},
 Chicken_LegL={center=Vector3.new(-0.3,0.31,-0.105),pivot=Vector3.new(-0.3,0.55,0),size=Vector3.new(0.3559,0.62,0.43)},
 Chicken_LegR={center=Vector3.new(0.3,0.31,-0.105),pivot=Vector3.new(0.3,0.55,0),size=Vector3.new(0.3559,0.62,0.43)},
}
-- Joint name -> {parent part, child part}. Legs hang off the root so the body's waddle bob
-- never lifts the feet.
local JOINTS={
 Body={'HumanoidRootPart','Chicken_Body'},Neck={'Chicken_Body','Chicken_Head'},
 LeftWing={'Chicken_Body','Chicken_WingL'},RightWing={'Chicken_Body','Chicken_WingR'},
 LeftHip={'HumanoidRootPart','Chicken_LegL'},RightHip={'HumanoidRootPart','Chicken_LegR'},
}
local function findImport()
 for _,container in {workspace,ServerStorage} do
  for _,d in container:GetDescendants() do
   if d:IsA('MeshPart') and d.Name=='Chicken_Body' and not d:FindFirstAncestor('RogueliteAllies') then
    local model=d:FindFirstAncestorOfClass('Model')
    while model and model.Parent and model.Parent:IsA('Model') do model=model.Parent end
    return model or d.Parent
   end
  end
 end
end
local function textured(part)
 local sa=part:FindFirstChildOfClass('SurfaceAppearance')
 if sa then if sa.ColorMap~='' then part.TextureID=sa.ColorMap end;sa:Destroy() end
 for _,c in part:GetChildren() do if not c:IsA('Attachment') then c:Destroy() end end
 return part
end
local import=assert(findImport(),'Import derp-chicken.fbx with File > Import 3D first')
local function source(name) return assert(import:FindFirstChild(name,true),'Import is missing '..name) end
local problems={}
local model=Instance.new('Model');model.Name='EggChicken'
local root=Instance.new('Part');root.Name='HumanoidRootPart'
root.Size=Vector3.new(1.2,1,1.4);root.CFrame=CFrame.new(0,HIP+root.Size.Y/2,0)
root.Transparency=1;root.CanCollide=true;root.CanQuery=false;root.CanTouch=false;root.CastShadow=false
root.TopSurface=Enum.SurfaceType.Smooth;root.BottomSurface=Enum.SurfaceType.Smooth;root.Parent=model
local parts={HumanoidRootPart=root}
for name,d in DATA do
 local p=textured(source(name):Clone())
 if (p.Size-d.size).Magnitude>0.05 then table.insert(problems,name..' size '..tostring(p.Size)..' expected '..tostring(d.size)) end
 p.Size=d.size;p.CFrame=CFrame.new(d.center)
 p.Anchored=false;p.Massless=true;p.CanCollide=false;p.CanQuery=false;p.CanTouch=false;p.CastShadow=true
 p.Parent=model;parts[name]=p
end
for jointName,pair in JOINTS do
 local part0,part1=parts[pair[1]],parts[pair[2]]
 local pivot=CFrame.new(DATA[pair[2]].pivot)
 local j=Instance.new('Motor6D');j.Name=jointName;j.Part0=part0;j.Part1=part1
 j.C0=part0.CFrame:ToObjectSpace(pivot);j.C1=part1.CFrame:ToObjectSpace(pivot);j.Parent=part1
end
local humanoid=Instance.new('Humanoid')
humanoid.RigType=Enum.HumanoidRigType.R15;humanoid.HipHeight=HIP
humanoid.AutomaticScalingEnabled=false;humanoid.RequiresNeck=false;humanoid.BreakJointsOnDeath=false
humanoid.DisplayDistanceType=Enum.HumanoidDisplayDistanceType.None;humanoid.HealthDisplayType=Enum.HumanoidHealthDisplayType.AlwaysOff
humanoid.UseJumpPower=true;humanoid.JumpPower=40;humanoid.WalkSpeed=22;humanoid.MaxSlopeAngle=60
humanoid:SetStateEnabled(Enum.HumanoidStateType.Climbing,false)
humanoid.Parent=model
model.PrimaryPart=root
model:SetAttribute('SourceAsset','roguelite-planning/blender-derp-chicken/exports/fbx/derp-chicken.fbx')
local allies=ServerStorage:FindFirstChild('RogueliteAllies') or Instance.new('Folder')
allies.Name='RogueliteAllies';allies.Parent=ServerStorage
local old=allies:FindFirstChild('EggChicken');if old then old:Destroy() end
model.Parent=allies
-- The feather is optional until the kit exports one.
local featherSource=import:FindFirstChild('Chicken_Feather',true)
local combat=RS:WaitForChild('RogueliteCombat')
local oldFeather=combat:FindFirstChild('ChickenFeather');if oldFeather then oldFeather:Destroy() end
if featherSource then
 local f=textured(featherSource:Clone());f.Name='ChickenFeather'
 f.Anchored=true;f.CanCollide=false;f.CanQuery=false;f.CanTouch=false;f.CastShadow=false;f.Massless=true
 f.Parent=combat
else table.insert(problems,'no Chicken_Feather in the import; the pop uses plain feather blocks') end
local oldRaw=allies:FindFirstChild('RawImport');if oldRaw then oldRaw:Destroy() end
import.Name='RawImport';import.Parent=allies
return 'EggChicken installed. '..(#problems>0 and ('Check: '..table.concat(problems,'; ')) or 'All part sizes match the Blender data.')
