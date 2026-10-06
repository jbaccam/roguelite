-- Additive finish for the reviewed imported meshes; no replacement asset upload.
local C={}
local definitions={
 {suffix='03',name='Deck',angle=0},
 {suffix='04',name='HeartCard',angle=-.26},
 {suffix='02',name='SpadeCard',angle=.18},
 {suffix='01',name='DiamondCard',angle=.32},
}
local cream=Color3.fromRGB(241,224,191)
local red=Color3.fromRGB(117,25,43)
local function frame(parent,name,x,y,w,h,color,rotation)
 local f=Instance.new('Frame');f.Name=name;f.AnchorPoint=Vector2.new(.5,.5)
 f.Position=UDim2.fromScale(x,y);f.Size=UDim2.fromScale(w,h)
 f.BorderSizePixel=0;f.BackgroundColor3=color;f.Rotation=rotation or 0;f.Parent=parent
 return f
end
local function back(component,mesh,isDeck,angle)
 local scale=mesh.Size/mesh.MeshSize
 local w,h=(isDeck and 155 or 83)*scale.X,(isDeck and 228 or 132)*scale.Y
 local plate=Instance.new('Part');plate.Name='PatternedBack';plate.Size=Vector3.new(w*.9,h*.93,.5*scale.Z)
 local z=isDeck and mesh.Size.Z/2-4.6*scale.Z or mesh.Size.Z/2+.6*scale.Z
 plate.CFrame=mesh.CFrame*CFrame.new(0,0,z)*CFrame.Angles(0,0,angle)
 plate.Color=cream;plate.Material=Enum.Material.SmoothPlastic;plate.Anchored=true
 plate.CanCollide=false;plate.CanTouch=false;plate.CanQuery=false;plate.CastShadow=false;plate.Parent=component
 local gui=Instance.new('SurfaceGui');gui.Name='CrimsonDiamondBack';gui.Face=Enum.NormalId.Back
 gui.CanvasSize=Vector2.new(300,480);gui.LightInfluence=0;gui.AlwaysOnTop=false;gui.Parent=plate
 local field=frame(gui,'CreamBorder',.5,.5,1,1,cream)
 local inset=frame(field,'CrimsonField',.5,.5,.93,.955,red)
 local border=Instance.new('UIStroke');border.Color=cream;border.Thickness=2;border.Parent=inset
 -- Repeated paired diagonal strokes read as a traditional diamond lattice.
 for row=0,6 do for col=0,3 do
  local x=.12+col*.25;local y=.075+row*.14
  local diamond=frame(inset,'LatticeDiamond',x,y,.10,.0625,red,45)
  local stroke=Instance.new('UIStroke');stroke.Color=Color3.fromRGB(191,105,108);stroke.Thickness=1.7;stroke.Parent=diamond
 end end
 local seal=frame(inset,'CenterSeal',.5,.5,.32,.20,cream,45)
 frame(seal,'CrimsonDiamond',.5,.5,.76,.76,red)
 local dot=frame(seal,'GoldCenter',.5,.5,.23,.23,cream)
 dot.ZIndex=2
end
function C.prepare(model)
 if model:GetAttribute('CardPresentationVersion')==1 then return end
 local pivot=model:GetPivot()
 for index,d in definitions do
  local mesh=assert(model:FindFirstChild('W18_Deck_of_Cards__'..d.suffix,true),'Missing card mesh '..d.name)
  local component=Instance.new('Model');component.Name=d.name;component.Parent=model
  mesh.Parent=component;component.PrimaryPart=mesh
  component:SetAttribute('ProjectileCard',index>1)
  component:SetAttribute('CardIndex',index-1)
  component:SetAttribute('RestPose',pivot:ToObjectSpace(component:GetPivot()))
  back(component,mesh,index==1,d.angle)
 end
 model:SetAttribute('CardPresentationVersion',1)
end
function C.bind(model,id)
 if id~='18' then return nil end
 C.prepare(model)
 local rig={model=model,cards={}}
 local pivot=model:GetPivot()
 for _,d in definitions do
  local card=model:WaitForChild(d.name)
  local mesh=card:WaitForChild('W18_Deck_of_Cards__'..d.suffix)
  if d.name~='Deck' then
   card.PrimaryPart=mesh
   local parts,guis={},{}
   for _,d in card:GetDescendants() do
    if d:IsA('BasePart') then table.insert(parts,d) elseif d:IsA('SurfaceGui') then table.insert(guis,d) end
   end
   table.insert(rig.cards,{model=card,parts=parts,guis=guis,rest=pivot:ToObjectSpace(card:GetPivot()),height=mesh.Size.Y})
  end
 end
 return rig
end
function C.step(rig,now)
 if not rig then return end
 local pivot=rig.model:GetPivot()
 for index,entry in rig.cards do
  local phase=now*(2.4+index*.13)+index*2.1
  local offset=CFrame.new(math.sin(phase*.73)*entry.height*.035,math.sin(phase)*entry.height*.085,math.cos(phase*.87)*entry.height*.025)
  local flutter=CFrame.Angles(math.sin(phase*1.3)*.035,math.sin(phase*.91)*.045,math.sin(phase*1.1)*.045)
  entry.model:PivotTo(pivot*entry.rest*offset*flutter)
 end
end
return C
