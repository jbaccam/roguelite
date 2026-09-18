local assets=game:GetService("HttpService"):JSONDecode([==[{"Head_Bottom":"rbxassetid://131693245082965","LeftFoot":"rbxassetid://135171195679571","LowerTorso":"rbxassetid://118474913079213","RightUpperArm":"rbxassetid://92519573641665","Head_Right":"rbxassetid://120849309457035","LeftUpperLeg":"rbxassetid://113277626641332","UpperTorso":"rbxassetid://93586886253048","Head_Back":"rbxassetid://120849309457035","LeftUpperArm":"rbxassetid://103928526643097","RightLowerArm":"rbxassetid://117365719587734","RightUpperLeg":"rbxassetid://128003154948411","LeftHand":"rbxassetid://105067620531363","Head_Top":"rbxassetid://130203658812129","RightFoot":"rbxassetid://137088233067331","RightHand":"rbxassetid://81031579010296","Head_Left":"rbxassetid://86331677760704","Head_Front":"rbxassetid://114240095855963","LeftLowerLeg":"rbxassetid://108640702326513","LeftLowerArm":"rbxassetid://85922687116599","RightLowerLeg":"rbxassetid://74976207569745"}]==])
assert(not workspace:FindFirstChild("Zombie_R15_ProvidedTextures_Studio"),"Comparison NPC already exists; preserve it or rename before rebuilding.")
local d=Instance.new("HumanoidDescription")
d.BodyTypeScale=0;d.ProportionScale=0;d.HeightScale=1;d.WidthScale=1;d.DepthScale=1;d.HeadScale=1
local m=game.Players:CreateHumanoidModelFromDescriptionAsync(d,Enum.HumanoidRigType.R15)
m.Name="Zombie_R15_ProvidedTextures_Studio"
for _,x in m:GetDescendants() do
 if x:IsA("BaseScript") or x:IsA("Accessory") or x:IsA("Constraint") or x:IsA("JointInstance") or x:IsA("SurfaceAppearance") then x:Destroy() end
end
local old=m.Head
local head=Instance.new("Part"); head.Name="Head"; head.Size=old.Size; head.CFrame=old.CFrame
for _,a in old:GetChildren() do if a:IsA("Attachment") then a:Clone().Parent=head end end
head.Parent=m;old:Destroy()
local mesh=Instance.new("SpecialMesh");mesh.Name="ClassicRobloxHead";mesh.MeshType=Enum.MeshType.Head;mesh.Parent=head
for _,face in {"Front","Back","Left","Right","Top","Bottom"} do
 local d=Instance.new("Decal");d.Name="ProvidedHead_"..face;d.Face=Enum.NormalId[face];d.Texture=assets["Head_"..face];d.Parent=head
end
for _,p in m:GetChildren() do
 if p:IsA("BasePart") then
 p.Material=Enum.Material.SmoothPlastic;p.Color=Color3.fromRGB(64,131,54);p.Anchored=p.Name=="HumanoidRootPart";p.CanCollide=false
 if p:IsA("MeshPart") then p.TextureID=assets[p.Name];p.Color=Color3.new(1,1,1) end
 p:SetAttribute("ZombieBaseSkinRGB","64,131,54")
 end
end
head.Color=Color3.new(1,1,1)
local links={{"LowerTorso","HumanoidRootPart","Root"},{"UpperTorso","LowerTorso","Waist"},{"Head","UpperTorso","Neck"}}
for _,side in {"Left","Right"} do
 table.insert(links,{side.."UpperArm","UpperTorso",side.."Shoulder"})
 table.insert(links,{side.."LowerArm",side.."UpperArm",side.."Elbow"})
 table.insert(links,{side.."Hand",side.."LowerArm",side.."Wrist"})
 table.insert(links,{side.."UpperLeg","LowerTorso",side.."Hip"})
 table.insert(links,{side.."LowerLeg",side.."UpperLeg",side.."Knee"})
 table.insert(links,{side.."Foot",side.."LowerLeg",side.."Ankle"})
end
for _,link in links do
 local child,parent,joint=m[link[1]],m[link[2]],link[3]
 local ca=child:FindFirstChild(joint.."RigAttachment");local pa=parent:FindFirstChild(joint.."RigAttachment")
 local motor=Instance.new("Motor6D");motor.Name=joint;motor.Part0=parent;motor.Part1=child;motor.C0=pa.CFrame;motor.C1=ca.CFrame;motor.Parent=child
end
m.Humanoid.RigType=Enum.HumanoidRigType.R15;m.Humanoid.DisplayDistanceType=Enum.HumanoidDisplayDistanceType.None;m.Humanoid.WalkSpeed=15.2
m.PrimaryPart=m.HumanoidRootPart
m:SetAttribute("Workflow","Roblox Studio native stock R15 rig; provided textures UV-aligned only; no Blender geometry imported")
m:SetAttribute("ComparisonPreview",true)
local atlases=game:GetService("HttpService"):JSONDecode([==[{"LeftArm":"rbxassetid://104527573352654","RightLeg":"rbxassetid://97498265662380","RightArm":"rbxassetid://74400295976437","LeftLeg":"rbxassetid://139143564029844","Torso":"rbxassetid://140609339752453"}]==])
for _,p in m:GetChildren() do
 if p:IsA("MeshPart") then
  local group
  if p.Name:find("Torso") then group="Torso"
  else local side=p.Name:sub(1,4)=="Left" and "Left" or "Right";group=side..((p.Name:find("Arm") or p.Name:find("Hand")) and "Arm" or "Leg") end
  p.TextureID=atlases[group]
 end
end
m:PivotTo(CFrame.new(70,5,410))
m.Parent=workspace
game:GetService("Selection"):Set({m})
local fullHeadResult=(function()
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

end)()
return {model=m:GetFullName(),parts=16,motors=#links,rig=tostring(m.Humanoid.RigType),head=fullHeadResult}
