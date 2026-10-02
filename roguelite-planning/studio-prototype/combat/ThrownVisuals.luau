-- Trails and landing effects for modeled throws (SpecialWeapons flights).
-- Kept light: short transparent trails, one small signature impact each.
local K=require(script.Parent:WaitForChild('VfxKit'))
local T={}
local YOLK=Color3.fromRGB(255,196,64)
local SHELL=Color3.fromRGB(250,244,230)
local GLASS=Color3.fromRGB(176,226,206)
local FLAME={Color3.fromRGB(255,170,64),Color3.fromRGB(214,72,24)}
local PIN_RED=Color3.fromRGB(214,58,52)

local function mainPart(model)
 return model.PrimaryPart or model:FindFirstChildWhichIsA('BasePart',true)
end
function T.decorate(model,id)
 local part=mainPart(model);if not part then return end
 if id=='13' then K.trail(part,.14,.12,K.White,K.White,.3)
 elseif id=='12' then
  -- A ribbon out along one wing sweeps a soft spinning disc as it turns.
  local reach=part.Size.X*.5
  local a0=Instance.new('Attachment');a0.Position=Vector3.new(reach*.35,0,0);a0.Parent=part
  local a1=Instance.new('Attachment');a1.Position=Vector3.new(reach*.95,0,0);a1.Parent=part
  local trail=Instance.new('Trail');trail.Name='FxTrail';trail.Attachment0=a0;trail.Attachment1=a1
  trail.Lifetime=.09;trail.FaceCamera=false;trail.LightEmission=.3;trail.MinLength=.04
  trail.Color=ColorSequence.new(K.White)
  trail.Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,.45),NumberSequenceKeypoint.new(1,1)})
  trail.Parent=part
 elseif id=='15' or id=='23' then K.trail(part,.3,.14,K.White,K.White,.55)
 elseif id=='22' then K.trail(part,.5,.12,K.Dust,K.Dust,.7)
 elseif id=='14' then K.trail(part,.38,.2,FLAME[1],FLAME[2],.3)
 elseif id=='31' then K.trail(part,.55,.18,K.Lightning[1],K.Lightning[2],.35)
 elseif id=='37' then require(script.Parent.GodlyVisuals).decorateThrown(model,id)
 end
end
function T.step(folder,r,position)
 if r.id=='22' then
  -- Rolling ball kicks up small dust puffs at intervals.
  if not r.lastDust or (position-r.lastDust).Magnitude>1.4 then
   r.lastDust=position
   if K.near(position,120) then K.cloud(folder,position-Vector3.yAxis*.6,K.Dust,.7,.45,Vector3.yAxis*.5,.45) end
  end
 elseif r.id=='31' then
  -- Thrown Mjolnir crackles with short sparks around its head.
  local now=os.clock()
  if not r.lastCrackle or now-r.lastCrackle>.09 then
   r.lastCrackle=now
   if K.near(position,120) then
    local a=position+Vector3.new(math.random()-.5,math.random()-.5,math.random()-.5)*1.4
    local b=position+Vector3.new(math.random()-.5,math.random()-.5,math.random()-.5)*2.2
    K.strike(folder,a,b,nil,.05,.1)
   end
  end
 end
end
function T.impact(folder,id,position)
 if not K.near(position,140) then return end
 if id=='15' then
  -- Egg: yolk splat with shell bits.
  K.pop(folder,position,YOLK,.4,1.6,.18,.25)
  K.shards(folder,position,SHELL,6,6,.4,.16,Enum.Material.SmoothPlastic,.8)
  K.shards(folder,position,YOLK,4,4,.35,.2,Enum.Material.SmoothPlastic,.6)
 elseif id=='23' then
  K.shards(folder,position,K.White,5,8,.28,.14,nil,.6)
  K.shards(folder,position,PIN_RED,3,6,.28,.12,nil,.6)
  K.cloud(folder,position,K.Dust,.8,.35,Vector3.yAxis*.4,.5)
 elseif id=='22' then
  for i=1,3 do
   local angle=i*2.1
   K.cloud(folder,position+Vector3.new(math.cos(angle),-.4,math.sin(angle))*.8,K.Dust,1.2,.5,Vector3.new(math.cos(angle),.6,math.sin(angle)),.35)
  end
 elseif id=='14' then
  K.shards(folder,position,GLASS,7,8,.35,.14,Enum.Material.Glass,.9)
  K.pop(folder,position,FLAME[1],.5,2.6,.22,.35)
  K.flash(folder,position,FLAME[1],10,2,.3)
 elseif id=='13' then
  K.shards(folder,position,K.White,3,6,.16,.1,nil,.5)
 end
end
return T
