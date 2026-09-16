-- Imported actual FBX meshes; normalize FBX centimeters to authored studs.
local specs={{name="01_Short_Squat_Grass",stem="01-short-squat-grass",size=Vector3.new(8.021342277526855,4.786563396453857,7.280717849731445)},
{name="02_Medium_Grass",stem="02-medium-grass",size=Vector3.new(8.57907485961914,8.800248146057129,7.616178512573242)},
{name="03_Tall_Narrow_Grass",stem="03-tall-narrow-grass",size=Vector3.new(7.973809242248535,14.396145820617676,6.735424518585205)},
{name="04_Wide_Low_Plateau",stem="04-wide-low-plateau",size=Vector3.new(18.36430549621582,3.9859864711761475,13.479005813598633)},
{name="05_Broad_Medium_Plateau",stem="05-broad-medium-plateau",size=Vector3.new(15.908100128173828,7.696900367736816,13.100112915039062)},
{name="06_Tall_Wide_Mass",stem="06-tall-wide-mass",size=Vector3.new(16.320026397705078,13.376635551452637,13.01995849609375)},
{name="07_Slightly_Tapered_Grass",stem="07-slightly-tapered-grass",size=Vector3.new(10.356525421142578,9.19838809967041,9.061853408813477)},
{name="08_Double_Eroded_Terrace",stem="08-double-eroded-terrace",size=Vector3.new(20.71953582763672,11.605205535888672,14.858415603637695)},
{name="09_Triple_Eroded_Terrace",stem="09-triple-eroded-terrace",size=Vector3.new(21.921602249145508,14.270000457763672,14.825847625732422)},
{name="10_Bare_Low_Filler",stem="10-bare-low-filler",size=Vector3.new(11.986343383789062,2.9208598136901855,8.370407104492188)},
{name="11_Medium_Boulder",stem="11-medium-boulder",size=Vector3.new(6.781913757324219,4.708181858062744,5.519160270690918)},
{name="12_Large_Boulder",stem="12-large-boulder",size=Vector3.new(10.628684997558594,6.645061016082764,8.646673202514648)},
{name="13_Rock_Cluster",stem="13-rock-cluster",size=Vector3.new(10.131604194641113,5.027630805969238,7.3177490234375)},
{name="14_Standing_Narrow_Rock",stem="14-standing-narrow-rock",size=Vector3.new(5.38887882232666,10.717269897460938,4.263914585113525)},
{name="15_Short_Moss_Only",stem="15-short-moss-only",size=Vector3.new(8.021370887756348,4.786563396453857,7.280717849731445)},
{name="16_Medium_Moss_Only",stem="16-medium-moss-only",size=Vector3.new(8.57907485961914,8.800248146057129,7.616178512573242)},
{name="17_Tall_Moss_Only",stem="17-tall-moss-only",size=Vector3.new(7.973809242248535,14.396145820617676,6.735424518585205)},
{name="18_Wide_Low_Moss_Only",stem="18-wide-low-moss-only",size=Vector3.new(18.36431121826172,3.9859864711761475,13.479005813598633)},
{name="19_Mossy_Boulder_Filler",stem="19-mossy-boulder-filler",size=Vector3.new(10.419829368591309,5.7471208572387695,8.795434951782227)}}
assert(not workspace:FindFirstChild("RogueliteCliffPack"),"Pack already exists")
local targets={}
for _,s in ipairs(specs) do local model=workspace:FindFirstChild(s.stem) assert(model and model:IsA("Model"),"Missing "..s.stem) local p=model:FindFirstChildWhichIsA("MeshPart",true) assert(p and p.MeshId~="" and p.TextureID~="","Missing mesh/atlas "..s.name) table.insert(targets,{s=s,model=model,p=p}) end
local folder=Instance.new("Folder") folder.Name="RogueliteCliffPack" folder:SetAttribute("SourcePack","blender-rounded-lightstone-revision") folder:SetAttribute("AssetCount",19) folder.Parent=workspace
local out={}
for i,t in ipairs(targets) do local s,m,p=t.s,t.model,t.p m.Parent=folder m.Name=s.name p.Name=s.name p.Anchored=true p.Size=s.size p.Color=Color3.new(1,1,1) p.Material=Enum.Material.SmoothPlastic p.Reflectance=0
local x=160+((i-1)%5)*28 local z=40+math.floor((i-1)/5)*30 p.CFrame=CFrame.new(x,s.size.Y/2,z) p.PivotOffset=CFrame.new(0,-s.size.Y/2,0) m.PrimaryPart=p m.WorldPivot=CFrame.new(x,0,z) m:SetAttribute("SourceFBX",s.stem..".fbx") m:SetAttribute("AtlasFile",string.lower(s.name).."-atlas.png")
local gui=Instance.new("BillboardGui") gui.Name="AssetLabel" gui.Size=UDim2.fromOffset(200,40) gui.StudsOffset=Vector3.new(0,s.size.Y/2+2,0) gui.AlwaysOnTop=false gui.MaxDistance=400 gui.Parent=p
local label=Instance.new("TextLabel") label.Size=UDim2.fromScale(1,1) label.BackgroundTransparency=1 label.Text=s.name:gsub("_"," ") label.TextColor3=Color3.new(1,1,1) label.TextStrokeTransparency=.25 label.TextSize=13 label.Font=Enum.Font.GothamMedium label.TextWrapped=true label.Parent=gui
 table.insert(out,{name=s.name,meshId=p.MeshId,textureId=p.TextureID,size={p.Size.X,p.Size.Y,p.Size.Z},position={p.Position.X,p.Position.Y,p.Position.Z},anchored=p.Anchored,sourceFBX=s.stem..".fbx"}) end
workspace.CurrentCamera.CFrame=CFrame.lookAt(Vector3.new(218,107,238),Vector3.new(218,4,82)) game:GetService("Selection"):Set({folder}) return out
