-- Run after importing Magic_Material_Fix.fbx. Only edits the owned showcase.
local show=assert(workspace:FindFirstChild('RogueliteWeaponShowcase'))
local imported=assert(workspace:FindFirstChild('Magic_Material_Fix'))
local backup=Instance.new('Folder');backup.Name='Weapon_Material_Correction_Backup';backup.Parent=game.ServerStorage
local raw=imported:Clone();raw.Name='CorrectedNativeImport';raw.Parent=backup
for _,idx in {33,35} do
 local old
 for _,m in show:GetChildren()do if m:GetAttribute('WeaponIndex')==idx then old=m end end
 assert(old)
 local target,size=old:GetBoundingBox()
 local m=Instance.new('Model');m.Name=old.Name
 for k,v in old:GetAttributes()do m:SetAttribute(k,v)end
 for _,p in imported:GetChildren()do
  if p:IsA('MeshPart')and tonumber(p.Name:match('^W(%d+)_'))==idx then
   p.Anchored=true;p.CanCollide=false;p.CanTouch=false;p.CanQuery=true;p.Locked=false;p.Color=Color3.new(1,1,1)
   for _,c in p:GetChildren()do if c:IsA('Motor6D')then c:Destroy()end end
   p.Parent=m
   if p.Name=='W35_Crystal_Shell' then p.Transparency=.38 end
   if p.Name=='W35_Crystal_Core' then p.Color=Color3.fromRGB(151,100,255);p.Material=Enum.Material.Neon end
  end
 end
 if idx==33 then
  local p=m:FindFirstChildWhichIsA('MeshPart')
  for _,b in imported.RootPart:GetChildren()do if b:IsA('Bone')then local cf=b.WorldCFrame;b.Parent=p;b.CFrame=p.CFrame:ToObjectSpace(cf)end end
  Instance.new('AnimationController',m)
 end
 m.Parent=show
 local _,s=m:GetBoundingBox();m:ScaleTo(m:GetScale()*math.max(size.X,size.Y,size.Z)/math.max(s.X,s.Y,s.Z))
 local cf=m:GetBoundingBox();m:PivotTo(CFrame.new(target.Position-cf.Position)*m:GetPivot())
 old.Parent=backup
end
imported.Parent=backup
show['20_Cinder_Block']:FindFirstChildWhichIsA('MeshPart').TextureID='rbxassetid://72121203546781'
show['22_Bowling_Ball']:FindFirstChildWhichIsA('MeshPart').TextureID='rbxassetid://114276616497392'
-- Avoid grazing-angle shimmering of very dense top-facing plaque text.
for _,g in show.DisplayBases:GetDescendants()do if g:IsA('SurfaceGui')then g.LightInfluence=0;g.PixelsPerStud=70;g.SizingMode=Enum.SurfaceGuiSizingMode.PixelsPerStud end end
game:GetService('ChangeHistoryService'):SetWaypoint('Correct weapon showcase materials')
return 'Corrected block, bowling ball, Pandora exterior/interior atlas, and crystal transparency'

