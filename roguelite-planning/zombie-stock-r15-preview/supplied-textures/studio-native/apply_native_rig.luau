local assets=game:GetService("HttpService"):JSONDecode([==[{"Head_Bottom":"rbxassetid://73667909234400","LeftFoot":"rbxassetid://135171195679571","LowerTorso":"rbxassetid://118474913079213","RightUpperArm":"rbxassetid://92519573641665","Head_Right":"rbxassetid://121901059984961","LeftUpperLeg":"rbxassetid://113277626641332","UpperTorso":"rbxassetid://93586886253048","Head_Back":"rbxassetid://121901059984961","LeftUpperArm":"rbxassetid://103928526643097","RightLowerArm":"rbxassetid://117365719587734","RightUpperLeg":"rbxassetid://128003154948411","LeftHand":"rbxassetid://105067620531363","Head_Top":"rbxassetid://75831283730947","RightFoot":"rbxassetid://137088233067331","RightHand":"rbxassetid://81031579010296","Head_Left":"rbxassetid://124907645007968","Head_Front":"rbxassetid://93427997944729","LeftLowerLeg":"rbxassetid://108640702326513","LeftLowerArm":"rbxassetid://85922687116599","RightLowerLeg":"rbxassetid://74976207569745"}]==])
local m=game.ServerStorage.Zombie_R15_ProvidedTextures_Studio
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
m:PivotTo(CFrame.new(70,6,410))
m.Parent=workspace
game:GetService("Selection"):Set({m})
return {model=m:GetFullName(),parts=16,motors=#links,rig=tostring(m.Humanoid.RigType),head="Native MeshType.Head"}

