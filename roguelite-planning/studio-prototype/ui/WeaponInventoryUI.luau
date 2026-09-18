-- UI sends only slot + catalogue ID. The server owns the equipped state.
local RS=game:GetService('ReplicatedStorage')
local combat=RS:WaitForChild('RogueliteCombat')
local Catalog=require(combat:WaitForChild('WeaponCatalog'))
local templates=combat:WaitForChild('WeaponTemplates')
local I={}
function I.preview(parent,template,x,y,w,h)
 if not template then return end
 local v=Instance.new('ViewportFrame');v.Name='WeaponPreview';v.BackgroundTransparency=1
 v.Position=UDim2.fromOffset(x,y);v.Size=UDim2.fromOffset(w,h)
 v.Ambient=Color3.fromRGB(210,210,210);v.LightColor=Color3.fromRGB(255,248,235);v.LightDirection=Vector3.new(-1,-2,-3)
 local world=Instance.new('WorldModel');world.Parent=v
 -- Preserve TextureID, SurfaceAppearance, part colors and the authored model scale.
 local model=template:Clone()
 for _,part in model:GetDescendants() do
  if part:IsA('BaseScript') then part:Destroy()
  elseif part:IsA('BasePart') then part.Anchored=true;part.CanCollide=false;part.CanTouch=false;part.CanQuery=false;part.LocalTransparencyModifier=0 end
 end
 model.Parent=world
 local cf,size=model:GetBoundingBox()
 local camera=Instance.new('Camera');camera.FieldOfView=35
 local distance=size.Magnitude*1.4/math.min(1,math.max(.25,w/math.max(1,h)))
 camera.CFrame=CFrame.lookAt(cf.Position+Vector3.new(.85,.45,1).Unit*distance,cf.Position)
 camera.Parent=v;v.CurrentCamera=camera;v.Parent=parent
end
function I.new(player,helpers,refresh)
 local panel,label,button=helpers.panel,helpers.label,helpers.button
 local state=combat.PlayerStates:WaitForChild(tostring(player.UserId))
 local self={selected=1,filter='',state=state}
 local function updated() refresh() end
 for _,slot in state:GetChildren() do slot:GetAttributeChangedSignal('WeaponId'):Connect(updated) end
 function self:drawSlots(parent,x,y,width,compact)
  local box=panel(parent,'EquippedWeapons',x,y,width,compact and 256 or 316)
  local count=0;for i=1,6 do if state['Slot'..i]:GetAttribute('WeaponId')~='' then count+=1 end end
  label(box,'Title','Weapons ('..count..'/6)',10,8,width-20,34,25)
  local gap=8;local cell=(width-32)/3;local height=compact and 76 or 100
  for i=1,6 do
   local id=state['Slot'..i]:GetAttribute('WeaponId');local d=Catalog.ById[id]
   local slot=button(box,'Slot'..i,'',8+((i-1)%3)*(cell+gap),52+math.floor((i-1)/3)*(height+gap),cell,height,function() self.selected=i;refresh() end,true)
   slot.ImageColor3=i==self.selected and Color3.fromRGB(154,202,222) or Color3.new(1,1,1)
   label(slot,'Number',tostring(i),3,2,20,20,14)
   if d then
    I.preview(slot,templates:FindFirstChild(id),9,9,cell-18,height-33)
    label(slot,'WeaponName',d.name,3,height-28,cell-6,24,12)
   else label(slot,'Empty','+',0,17,cell,height-20,26) end
  end
  button(box,'Remove','Remove slot '..self.selected,8,compact and 214 or 274,width-16,34,function() combat.EquipWeapon:FireServer(self.selected,'') end,true).Caption.TextSize=16
  return compact and 262 or 324
 end
 function self:render(content,width)
  local usable=math.min(width,1280);local x=math.floor((width-usable)/2)
  local wide=usable>=850;local side=wide and 320 or usable
  local area=wide and usable-side-18 or usable
  local slotsHeight=self:drawSlots(content,wide and x+area+18 or x,0,side,not wide)
  local top=wide and 0 or slotsHeight+14
  label(content,'AllWeapons','All weapons  ·  36',x,top,area,35,26)
  label(content,'Instructions','Choose a slot, then equip any weapon. Duplicates allowed.',x,top+38,area,42,16)
  local columns=math.max(1,math.floor(area/205));local gap=12
  local cardW=math.floor((area-gap*(columns-1))/columns);local cardH=230
  for i,d in Catalog.List do
   local card=panel(content,'WeaponCard_'..d.id,x+((i-1)%columns)*(cardW+gap),top+92+math.floor((i-1)/columns)*(cardH+gap),cardW,cardH)
   I.preview(card,templates:FindFirstChild(d.id),12,6,cardW-24,104)
   label(card,'Name',d.name,8,110,cardW-16,36,20)
   label(card,'Stats',d.kind..'  ·  '..d.damage..' damage\n'..d.cooldown..'s cooldown',8,148,cardW-16,38,14)
   button(card,'Equip','Equip → '..self.selected,10,188,cardW-20,34,function() combat.EquipWeapon:FireServer(self.selected,d.id) end,true).Caption.TextSize=17
  end
  return math.max(slotsHeight,top+92+math.ceil(#Catalog.List/columns)*(cardH+gap))
 end
 return self
end
return I
