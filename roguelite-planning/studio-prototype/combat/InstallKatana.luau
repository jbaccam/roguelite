-- Edit-only installer. Script Sources are supplied from the accompanying files by tooling.
local RS=game:GetService('ReplicatedStorage')
assert(not RS:FindFirstChild('RogueliteCombat'),'Combat already installed; update scripts explicitly')
local source=assert(workspace.RogueliteWeaponShowcase_PlaySize:FindFirstChild('03_Katana'),'Resized katana is missing')
local package=Instance.new('Folder');package.Name='RogueliteCombat';package:SetAttribute('ZombiesEnabled',true);package.Parent=RS
local template=source:Clone();template.Name='KatanaTemplate'
-- Preserve the user's exact mesh dimensions; only normalize its display rake and grip pivot.
template:PivotTo(CFrame.identity)
for _,p in template:GetDescendants()do if p:IsA('BasePart')then p.PivotOffset=CFrame.identity;p.CFrame=CFrame.Angles(0,0,.97)*p.CFrame;p.Anchored=true;p.CanCollide=false;p.CanTouch=false;p.CanQuery=false end end
-- Measured from actual Blender mesh vertices, not the inflated rotated MeshPart box.
local factor=source:FindFirstChildWhichIsA('BasePart',true).Size.X/4.410099983215332
local grip=Vector3.new(.51046747,-2.2885015,0)*factor
template.WorldPivot=CFrame.new(grip)
template:PivotTo(CFrame.identity)
local boundsSize=Vector3.new(1.5445101,5.9588652,.8493093)*factor
-- User requested reversing the blade facing by 180 degrees while keeping it blade-up.
for _,p in template:GetDescendants()do if p:IsA('BasePart')then p.CFrame=CFrame.Angles(0,math.pi,0)*p.CFrame end end
template.WorldPivot=CFrame.identity
template:SetAttribute('BoundsCenter',Vector3.new(.344366,2.383546,0)*factor);template:SetAttribute('BoundsSize',boundsSize)
template:SetAttribute('SourceDisplay','RogueliteWeaponShowcase_PlaySize.03_Katana')
template:SetAttribute('UserSized',true)
template.Parent=package
local states=Instance.new('Folder');states.Name='PlayerStates';states.Parent=package
for _,name in {'Hit','SetTestOption'}do local remote=Instance.new('RemoteEvent');remote.Name=name;remote.Sandboxed=true;remote.Capabilities=SecurityCapabilities.new(Enum.SecurityCapability.Basic,Enum.SecurityCapability.RemoteEvent);remote.Parent=package end
local backup=Instance.new('Folder');backup.Name='BeforeKatanaCombat';backup.Parent=game.ServerStorage
local original=Instance.new('StringValue');original.Name='OriginalZombieChaseSource';original.Value=game.ServerScriptService.RogueliteZombieChase.Source;original.Parent=backup
game:GetService('ChangeHistoryService'):SetWaypoint('Installed user-sized katana combat assets')
return {bounds=tostring(boundsSize),scale=template:GetScale()}
