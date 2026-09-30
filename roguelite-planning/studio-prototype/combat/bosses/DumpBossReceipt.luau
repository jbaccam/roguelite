-- Edit-mode only. Returns a JSON receipt of one raw boss import (bones, meshes, scale) in the
-- regular-mob receipt schema, for retarget_boss.py. Set ID, paste into execute_luau.
local ID=ID or 'KingCrab'
local Http=game:GetService('HttpService')
local raw=game.ServerStorage.MapBossRawImports:FindFirstChild(ID);assert(raw,'missing raw import '..ID)
local function cf(c) local t={c:GetComponents()};for i,v in t do t[i]=math.round(v*1e7)/1e7 end;return t end
local rootPart=raw:FindFirstChild('RootPart') or raw.PrimaryPart
local bones,meshes={},{}
for _,d in raw:GetDescendants() do
 if d:IsA('Bone') then
  local parent=d.Parent:IsA('Bone') and d.Parent.Name or 'RootPart'
  table.insert(bones,{name=d.Name,parent=parent,cframe=cf(d.CFrame)})
 elseif d:IsA('MeshPart') then
  table.insert(meshes,{name=d.Name,meshId=d.MeshId,textureId=d.TextureID,cframe=cf(rootPart.CFrame:ToObjectSpace(d.CFrame)),size={d.Size.X,d.Size.Y,d.Size.Z}})
 end
end
return Http:JSONEncode({id=ID,scale=raw:GetScale(),pivot=cf(raw:GetPivot()),rootPartCFrame=cf(rootPart.CFrame),bones=bones,meshes=meshes})
