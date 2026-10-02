-- UI sends only slot, catalogue ID and tier. The server owns the equipped state.
local RS=game:GetService('ReplicatedStorage')
local combat=RS:WaitForChild('RogueliteCombat')
local Catalog=require(combat:WaitForChild('WeaponCatalog'))
local templates=combat:WaitForChild('WeaponTemplates')
local T=require(RS:WaitForChild('UITheme'))
local I={}
local Icons={
 ["00"]="rbxassetid://71681559132362",
 ["01"]="rbxassetid://74038074720581",
 ["02"]="rbxassetid://76889402145049",
 ["03"]="rbxassetid://73585837146439",
 ["04"]="rbxassetid://127806745831113",
 ["05"]="rbxassetid://121554503484361",
 ["06"]="rbxassetid://134396865555784",
 ["07"]="rbxassetid://84542339301153",
 ["08"]="rbxassetid://112649154217616",
 ["09"]="rbxassetid://73440448199095",
 ["10"]="rbxassetid://115253509624247",
 ["11"]="rbxassetid://103774125799202",
 ["12"]="rbxassetid://118992831327433",
 ["13"]="rbxassetid://120683597299222",
 ["14"]="rbxassetid://109291367860600",
 ["15"]="rbxassetid://121569294705128",
 ["16"]="rbxassetid://71303617489138",
 ["17"]="rbxassetid://71258102069801",
 ["18"]="rbxassetid://129927573684272",
 ["19"]="rbxassetid://79395868823763",
 ["20"]="rbxassetid://114400357979821",
 ["21"]="rbxassetid://109920978940018",
 ["22"]="rbxassetid://129583469525829",
 ["23"]="rbxassetid://73824260587783",
 ["24"]="rbxassetid://91528182457764",
 ["25"]="rbxassetid://127178962598755",
 ["26"]="rbxassetid://130332437914726",
 ["27"]="rbxassetid://113480577519275",
 ["28"]="rbxassetid://75288200196273",
 ["29"]="rbxassetid://72612950703220",
 ["30"]="rbxassetid://73425705945211",
 ["31"]="rbxassetid://77232331953832",
 ["32"]="rbxassetid://122594538852083",
 ["33"]="rbxassetid://95730314118939",
 ["34"]="rbxassetid://137554573636900",
 ["35"]="rbxassetid://115596756605971",
 ["36"]="rbxassetid://107381256092734",
 ["37"]="rbxassetid://111945334431090",
 ["38"]="rbxassetid://86787843399026",
 ["39"]="rbxassetid://112261102861999",
 ["40"]="rbxassetid://90868128996170",
 ["41"]="rbxassetid://74294498569772",
}
-- Godly art exists before the weapons become playable. Match names instead of guessing IDs.
I.IconsByName={
	["Reaper's Scythe"] = "rbxassetid://98038611477072",
	["Poseidon's Trident"] = "rbxassetid://115347871654580",
	["Storm Bow"] = "rbxassetid://88739156797064",
	["Shadow Daggers"] = "rbxassetid://115284484769679",
	["Vampire Blade"] = "rbxassetid://122685349145201",
	["Ray Gun"] = "rbxassetid://110188341033662",
}
for _,weapon in Catalog.List do
 local asset=I.IconsByName[weapon.name]
 if asset then Icons[weapon.id]=asset end
end
I.Icons=Icons

function I.preview(parent,template,x,y,w,h)
 if not template then return end
 local asset=Icons[template.Name]
 if asset then
  local icon=Instance.new('ImageLabel');icon.Name='WeaponIcon';icon.BackgroundTransparency=1;icon.Image=asset;icon.Position=UDim2.fromOffset(x,y);icon.Size=UDim2.fromOffset(w,h);icon.ScaleType=Enum.ScaleType.Fit;icon.Parent=parent;return icon
 end
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
 -- The state folder can replicate before its six slots; wait before reading nextFree.
 for slot=1,Catalog.Slots do state:WaitForChild('Slot'..slot) end
 -- Give weapon (ADMIN panel): the selected slot starts at, and moves on to, the next free slot.
 local function nextFree() for i=1,6 do if state['Slot'..i]:GetAttribute('WeaponId')=='' then return i end end end
 local self={selected=nextFree() or 1,filter='',state=state,tier=1}
 local function updated()
  if state['Slot'..self.selected]:GetAttribute('WeaponId')~='' then self.selected=nextFree() or self.selected end
  refresh()
 end
 for _,slot in state:GetChildren() do slot:GetAttributeChangedSignal('WeaponId'):Connect(updated) end
 function self:drawSlots(parent,x,y,width,compact)
  local box=panel(parent,'EquippedWeapons',x,y,width,compact and 256 or 316)
  local count=0;for i=1,6 do if state['Slot'..i]:GetAttribute('WeaponId')~='' then count+=1 end end
  label(box,'Title','Weapons ('..count..'/6)',10,8,width-20,34,25)
  local gap=8;local cell=(width-32)/3;local height=compact and 76 or 100
  for i=1,6 do
   local id=state['Slot'..i]:GetAttribute('WeaponId');local d=Catalog.ById[id]
   local slot=button(box,'Slot'..i,'',8+((i-1)%3)*(cell+gap),52+math.floor((i-1)/3)*(height+gap),cell,height,function() self.selected=i;refresh() end,true)
   T.setPrimary(slot,i==self.selected) -- Selected slot takes the lime face.
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
  label(content,'Instructions','Choose a slot and a tier, then equip any weapon. Duplicates allowed.',x,top+38,area-236,42,16)
  for tier=1,4 do
   local b=button(content,'Tier'..tier,T.Roman[tier],x+area-232+(tier-1)*58,top+42,52,34,function() self.tier=tier;refresh() end,tier~=self.tier)
   b.Caption.TextSize=16
  end
  local columns=math.max(1,math.floor(area/205));local gap=12
  local cardW=math.floor((area-gap*(columns-1))/columns);local cardH=230
  for i,d in Catalog.List do
   local card=panel(content,'WeaponCard_'..d.id,x+((i-1)%columns)*(cardW+gap),top+92+math.floor((i-1)/columns)*(cardH+gap),cardW,cardH)
   I.preview(card,templates:FindFirstChild(d.id),12,6,cardW-24,104)
   label(card,'Name',d.name,8,110,cardW-16,36,20)
   label(card,'Stats',d.kind..'  ·  '..d.damage..' damage\n'..d.cooldown..'s cooldown',8,148,cardW-16,38,14)
   button(card,'Equip','Equip '..T.Roman[self.tier]..' → '..self.selected,10,188,cardW-20,34,function() T.sound('ui_equip');combat.EquipWeapon:FireServer(self.selected,d.id,self.tier) end,true).Caption.TextSize=17
  end
  return math.max(slotsHeight,top+92+math.ceil(#Catalog.List/columns)*(cardH+gap))
 end
 return self
end
return I
