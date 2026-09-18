-- Run once in Studio Edit mode after the native Weapon_Showcase.fbx import.
-- Owns only this import and Workspace.RogueliteWeaponShowcase.
local imported = assert(workspace:FindFirstChild('Weapon_Showcase'), 'Native import missing')
assert(not workspace:FindFirstChild('RogueliteWeaponShowcase'), 'Showcase already exists; inspect before replacing')
local names = {'Glock','Frying Pan','Nunchucks','Katana','Kusarigama','Spatula','Baseball Bat','Draco','Fart Gun','Shotgun','T-Shirt Cannon','Rocket Launcher','Boomerang','Kunai','Molotov','Egg','Steak','Rubber Duck','Deck of Cards','Boxing Gloves','Cinder Block','Yo-Yo','Bowling Ball','Bowling Pin','Nail Gun','Wrecking Ball','Shovel','Paint Roller','Vacuum Cleaner','Power Washer','Magic Staff','Mjolnir','Excalibur',"Pandora's Box","Medusa's Head",'Crystal Ball'}
local history = game:GetService('ChangeHistoryService')
history:SetWaypoint('Before weapon showcase arrangement')
local backup = imported:Clone(); backup.Name='Weapon_Import_Rigged_Backup'; backup.Parent=game.ServerStorage
local showcase=Instance.new('Folder'); showcase.Name='RogueliteWeaponShowcase'; showcase.Parent=workspace
showcase:SetAttribute('Source','Locally authored Blender weapon models, native FBX import')
local models={}
for i=0,35 do local m=Instance.new('Model');m.Name=string.format('%02d_%s',i,names[i+1]:gsub('[^%w]+','_'));m:SetAttribute('WeaponIndex',i);m:SetAttribute('DisplayName',names[i+1]);m.Parent=showcase;models[i]=m end
local rigParts={}
for _,p in imported:GetChildren() do
 if p:IsA('MeshPart') then
  local idx=tonumber(p.Name:match('^W(%d+)_'));assert(idx,'Unidentified mesh')
  p.Anchored=true;p.CanCollide=false;p.CanTouch=false;p.CanQuery=true;p.Locked=false
  for _,c in p:GetChildren()do if c:IsA('Motor6D')then c:Destroy()end end
  p.Parent=models[idx]
  if idx==2 or idx==4 or idx==25 or idx==33 then rigParts[idx]=p end
 end
end
-- Rehome each uniquely named skeleton with its own skinned weapon, preserving rest coordinates.
local root=imported:FindFirstChild('RootPart')
if root then
 for _,bone in root:GetChildren() do
  if bone:IsA('Bone')then
   local idx=tonumber(bone.Name:match('^W(%d+)_'));local p=assert(rigParts[idx],'Unidentified skeleton')
   local world=bone.WorldCFrame;bone.Parent=p;bone.CFrame=p.CFrame:ToObjectSpace(world)
  end
 end
end
for idx,p in rigParts do
 local count=0;for _,d in p:GetDescendants()do if d:IsA('Bone')then count+=1 end end
 local expected=({[2]=7,[4]=13,[25]=9,[33]=2})[idx];assert(count==expected, 'Bone count mismatch '..idx..' '..count)
 models[idx]:SetAttribute('RigBoneCount',count)
 local controller=Instance.new('AnimationController');controller.Parent=models[idx]
end
local bases=Instance.new('Folder');bases.Name='DisplayBases';bases.Parent=showcase
for idx=0,35 do
 local m=models[idx]
 local _,size=m:GetBoundingBox();local biggest=math.max(size.X,size.Y,size.Z)
 m:ScaleTo(m:GetScale()*5/biggest)
 local cf,s=m:GetBoundingBox();local origin=Vector3.new(100+(idx%6)*11,2.65,460+math.floor(idx/6)*12)
 m:PivotTo(CFrame.new(origin-Vector3.new(cf.X,cf.Y-s.Y/2,cf.Z))*m:GetPivot())
 local pedestal=Instance.new('Part');pedestal.Name=string.format('Base_%02d',idx);pedestal.Size=Vector3.new(8,.45,8);pedestal.CFrame=CFrame.new(origin.X,2.225,origin.Z);pedestal.Anchored=true;pedestal.Color=Color3.fromRGB(43,51,61);pedestal.Material=Enum.Material.SmoothPlastic;pedestal.Parent=bases
 local plaque=Instance.new('Part');plaque.Name='Label';plaque.Size=Vector3.new(7,.1,1.4);plaque.CFrame=CFrame.new(origin.X,2.51,origin.Z+3.1);plaque.Anchored=true;plaque.CanCollide=false;plaque.Color=Color3.fromRGB(30,35,43);plaque.Parent=pedestal
 local gui=Instance.new('SurfaceGui');gui.Face=Enum.NormalId.Top;gui.CanvasSize=Vector2.new(700,140);gui.Parent=plaque
 local label=Instance.new('TextLabel');label.Size=UDim2.fromScale(1,1);label.BackgroundTransparency=1;label.Text=names[idx+1];label.TextColor3=Color3.fromRGB(240,241,235);label.TextScaled=true;label.Font=Enum.Font.GothamMedium;label.Parent=gui
 m:SetAttribute('ShowcaseOnly',true)
end
imported.Name='Weapon_Import_ExtraMetadata';imported.Parent=game.ServerStorage
game:GetService('Selection'):Set({showcase})
workspace.CurrentCamera.CFrame=CFrame.lookAt(Vector3.new(164,65,564),Vector3.new(127,3,490))
history:SetWaypoint('Imported all 36 weapon families into showcase')
return 'Showcase arranged: 36 families, 42 meshes, four independent rigs'

