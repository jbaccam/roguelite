-- Independent Blender-authored cloth: works on textured and vertex-colored mobs.
local C=script.Parent
local Geometry=require(C.RolledShirtVisual)
local Torso=require(C.TeeTorsoData)
local Sleeve=require(C.TeeSleeveData)
local V={}
local templates={}
local templateOrder={}
local function panel(body,sleeve,head)
 local size=body.Size
 local neck=head and body.CFrame:PointToObjectSpace(head.Position)
 local key=(sleeve and 's' or 't')..tostring(size)..(not sleeve and neck and tostring(math.round(neck.Y*20)/20) or '')
 if not templates[key] then
  local data=sleeve and Sleeve or Torso
  if not sleeve and neck then
   data=table.clone(Torso);data.vertices={}
   local neckline=math.min(.54,(neck.Y-head.Size.Y*.45)/size.Y)
   for i,v in Torso.vertices do
    local y=v[2]
    if y>.35 then
     local weight=math.clamp((.44-math.abs(v[1]))/.23,0,1)
     y=y-math.max(0,y-neckline)*weight
    end
    data.vertices[i]={v[1],y,v[3]}
   end
  end
  templates[key]=Geometry.geometry(nil,data,size,sleeve and 'Sleeve' or 'CottonBody')
  table.insert(templateOrder,key)
  if #templateOrder>64 then local old=table.remove(templateOrder,1);templates[old]:Destroy();templates[old]=nil end
 end
 return templates[key]:Clone()
end
function V.create(npc,parent)
 local torso=npc:FindFirstChild('UpperTorso') or npc:FindFirstChild('Torso')
 if not torso then return nil end
 local model=Instance.new('Model');model.Name='DesignerTee'
 local pieces={}
 for _,name in {'UpperTorso','Torso','LeftUpperArm','RightUpperArm','Left Arm','Right Arm'} do
  local body=npc:FindFirstChild(name)
  if body and body:IsA('BasePart') then
   local p=panel(body,string.find(name,'Arm')~=nil,npc:FindFirstChild('Head'));p.Parent=model
   table.insert(pieces,{part=p,body=body,offset=CFrame.identity})
  end
 end
 local badge=Instance.new('Part');badge.Name='SupermemeLabel'
 badge.Anchored=true;badge.CanCollide=false;badge.CanTouch=false;badge.CanQuery=false;badge.CastShadow=false
 badge.Color=Color3.fromRGB(186,28,42);badge.Material=Enum.Material.SmoothPlastic
 badge.Size=Vector3.new(torso.Size.X*.55,torso.Size.Y*.19,.025);badge.Parent=model
 local offset=CFrame.new(0,torso.Size.Y*.10,-torso.Size.Z*.567-.02)
 table.insert(pieces,{part=badge,body=torso,offset=offset})
 local gui=Instance.new('SurfaceGui');gui.Face=Enum.NormalId.Front;gui.CanvasSize=Vector2.new(400,100);gui.LightInfluence=1;gui.Parent=badge
 local text=Instance.new('TextLabel');text.Size=UDim2.fromScale(1,1);text.BackgroundTransparency=1
 text.Text='supermeme';text.Font=Enum.Font.GothamBold;text.TextScaled=true;text.TextColor3=Color3.fromRGB(255,249,235);text.Parent=gui
 local result={model=model,pieces=pieces};V.step(result);model.Parent=parent;return result
end
function V.step(r)
 for _,p in r.pieces do if p.body.Parent then
  if p.part:IsA('Model') then p.part:PivotTo(p.body.CFrame*p.offset) else p.part.CFrame=p.body.CFrame*p.offset end
 end end
end
return V
