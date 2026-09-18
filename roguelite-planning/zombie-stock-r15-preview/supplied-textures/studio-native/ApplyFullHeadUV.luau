local AS=game:GetService("AssetService")
local em=AS:CreateEditableMeshAsync(Content.fromUri("rbxasset://avatar/heads/head.mesh"))
local lo=Vector3.new(math.huge,math.huge,math.huge);local hi=-lo
for _,id in em:GetVertices() do local p=em:GetPosition(id);lo=lo:Min(p);hi=hi:Max(p) end
local size=hi-lo
local panels={
Front={360,355,897,919},Back={20,355,345,880},
Left={905,355,1235,880},Right={20,355,345,880},
Top={95,25,1155,280},Bottom={80,930,1170,1225}}
for _,fid in em:GetFaces() do
 local vv=em:GetFaceVertices(fid)
 local a,b,c=em:GetPosition(vv[1]),em:GetPosition(vv[2]),em:GetPosition(vv[3])
 local n=(b-a):Cross(c-a).Unit
 local face
 if math.abs(n.Y)>math.abs(n.X) and math.abs(n.Y)>math.abs(n.Z) then face=n.Y>0 and "Top" or "Bottom"
 elseif math.abs(n.X)>math.abs(n.Z) then face=n.X>0 and "Right" or "Left"
 else face=n.Z>0 and "Back" or "Front" end
 local rect=panels[face];local ids={}
 for _,vid in vv do
  local p=(em:GetPosition(vid)-lo)/size
  local u,v
  if face=="Front" then local q=em:GetPosition(vid);u=math.clamp((q.X+.4251213)/.8502426,0,1);v=math.clamp(1-(q.Y+.5131668)/1.0263336,0,1)
  elseif face=="Back" then u,v=1-p.X,1-p.Y
  elseif face=="Left" then u,v=1-p.Z,1-p.Y
  elseif face=="Right" then u,v=p.Z,1-p.Y
  elseif face=="Top" then u,v=p.X,1-p.Z
  else u,v=p.X,p.Z end
  table.insert(ids,em:AddUV(Vector2.new((rect[1]+u*(rect[3]-rect[1]))/1254,(rect[2]+v*(rect[4]-rect[2]))/1254)))
 end
 em:SetFaceUVs(fid,ids)
end
local new=AS:CreateMeshPartAsync(Content.fromObject(em),{CollisionFidelity=Enum.CollisionFidelity.Box})
local m=workspace.Zombie_R15_ProvidedTextures_Studio;local old=m.Head
new.Name="Head";new.Size=old.Size;new.CFrame=old.CFrame;new.Color=Color3.new(1,1,1);new.TextureID="rbxassetid://117306049770322";new.Material=Enum.Material.SmoothPlastic;new.CanCollide=false;new.Massless=true
for _,child in old:GetChildren() do if child:IsA("Attachment") or child:IsA("Motor6D") then child.Parent=new end end
for _,joint in m:GetDescendants() do if joint:IsA("Motor6D") then if joint.Part0==old then joint.Part0=new end if joint.Part1==old then joint.Part1=new end end end
if new:FindFirstChild("Neck") then new.Neck.Part1=new end
old.Name="ZombiePreviousDecalHead";old.Parent=game.ServerStorage;new.Parent=m
new:SetAttribute("NativeSourceMesh","rbxasset://avatar/heads/head.mesh");new:SetAttribute("UVMapping","Native EditableMesh full head UVs from provided original image; original vertices unchanged")
new:SetAttribute("ZombieBaseSkinRGB","64,131,54")
return {vertices=#em:GetVertices(),faces=#em:GetFaces(),texture=new.TextureID,size={new.Size.X,new.Size.Y,new.Size.Z},mesh=tostring(new.MeshContent)}
