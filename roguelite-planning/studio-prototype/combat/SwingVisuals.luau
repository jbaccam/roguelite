-- Melee swing presentation, after the user's "example swinging" reference:
-- a thin white swoosh follows every striking end, and heavy weapons add a
-- short ground crescent with an amber dashed rim (overheads add a slam ring).
-- Driven only by the replicated attack clock; never affects hits.
local Motion=require(script.Parent:WaitForChild('WeaponMotion'))
local Chains=require(script.Parent:WaitForChild('ChainWeaponMotion'))
local K=require(script.Parent:WaitForChild('VfxKit'))
local Tags=game:GetService('CollectionService')
local Players=game:GetService('Players')
local V={}
-- Blade: ribbon between two points along the weapon's +Y striking length.
-- Blob: camera-facing ribbon from one point, for flat/boxy/chain heads.
local Profiles={
 ['01']={mode='blade',inner=.05},
 ['02']={mode='chain',entry='payload',width=.55},
 ['03']={mode='blade',inner=.5,lifetime=.15},
 ['04']={mode='chain',entry='root',width=.7},
 ['05']={mode='blade',inner=.15},
 ['06']={mode='blade',inner=.2,heavy=true},
 ['16']={mode='blob',width=1.1,at=0},
 ['19']={mode='gloves',width=.6},
 ['20']={mode='blob',width=1.15,at=.25,heavy=true},
 ['25']={mode='chain',entry='payload',width=1.25,heavy=true},
 ['26']={mode='blade',inner=.15,heavy=true},
 ['27']={mode='blob',width=.95,at=.35,color=Color3.fromRGB(92,158,226)},
 ['31']={mode='blade',inner=.1,heavy=true},
 ['32']={mode='blade',inner=.45,heavy=true,color=Color3.fromRGB(255,240,190)},
}
V.Profiles=Profiles
local HEAVY_RIM=K.Amber

local function newRibbon(parent,profile,faceCamera,width)
 local carrier=K.part(parent,'SwingCarrier',Vector3.one*.05,K.White,1)
 local a0=Instance.new('Attachment');a0.Name='SwingA';a0.Parent=carrier
 local a1=Instance.new('Attachment');a1.Name='SwingB';a1.Parent=carrier
 local trail=Instance.new('Trail');trail.Name='SwingTrail';trail.Attachment0=a0;trail.Attachment1=a1
 trail.FaceCamera=faceCamera;trail.Lifetime=profile.lifetime or (profile.heavy and .2 or .17)
 trail.MinLength=.04;trail.LightEmission=.35;trail.LightInfluence=.15;trail.Enabled=false
 local tint=profile.color or K.White
 trail.Color=ColorSequence.new(tint,tint:Lerp(Color3.fromRGB(232,240,255),.5))
 trail.Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,.18),NumberSequenceKeypoint.new(.45,.5),NumberSequenceKeypoint.new(1,1)})
 trail.WidthScale=NumberSequence.new({NumberSequenceKeypoint.new(0,1),NumberSequenceKeypoint.new(1,faceCamera and .25 or .55)})
 trail.Parent=carrier
 return {carrier=carrier,a0=a0,a1=a1,trail=trail,width=width}
end

function V.mount(folder)
 local api={}
 -- Called once per rendered weapon model.
 function api.attach(v,id,template)
  local profile=Profiles[id];if not profile then return end
  local size=template:GetAttribute('BoundsSize') or Vector3.new(1,3,1)
  local center=template:GetAttribute('BoundsCenter') or Vector3.zero
  local sign=(id=='02' or id=='25') and -1 or 1
  local swing={profile=profile,ribbons={},size=size,center=center}
  local half=size.Y*.5
  if profile.mode=='blade' then
   swing.inner=center+Vector3.yAxis*sign*half*profile.inner
   swing.outer=center+Vector3.yAxis*sign*half
   swing.ribbons[1]=newRibbon(v.model,profile,false)
  elseif profile.mode=='blob' then
   swing.point=center+Vector3.yAxis*sign*half*(profile.at or 0)
   swing.ribbons[1]=newRibbon(v.model,profile,true,profile.width)
  elseif profile.mode=='chain' and v.chain then
   local rig=v.chain
   swing.entry=profile.entry=='root' and 1 or rig.payloadIndex
   swing.ribbons[1]=newRibbon(v.model,profile,true,profile.width)
  elseif profile.mode=='gloves' and v.gloves then
   for i,g in v.gloves do swing.ribbons[i]=newRibbon(v.model,profile,true,profile.width);swing.ribbons[i].part=g.part;swing.ribbons[i].side=g.side end
  else return end
  v.swing=swing
 end
 local function ground(position,fallback)
  local exclude={folder}
  for _,p in Players:GetPlayers() do if p.Character then table.insert(exclude,p.Character) end end
  for _,npc in Tags:GetTagged('RogueliteZombie') do table.insert(exclude,npc) end
  return K.groundBelow(position,exclude,fallback)
 end
 local function crescent(info,id)
  local root=info.attackRoot;local reach=info.range or 8
  local direction=info.direction or root.LookVector
  direction=Vector3.new(direction.X,0,direction.Z)
  if direction.Magnitude<.01 then direction=Vector3.new(root.LookVector.X,0,root.LookVector.Z) end
  if direction.Magnitude<.01 then return end
  local center=root.Position
  if not K.near(center,140) then return end
  local y=ground(center,center.Y-2.75)
  if center.Y-y>6 then y=center.Y-2.75 end
  local base=Vector3.new(center.X,y+.12,center.Z)
  local frame=CFrame.lookAt(base,base+direction.Unit)
  local side=info.side or 1
  local diagonal=info.style=='Diagonal'
  local from=math.rad((diagonal and -60 or -100)*side)
  local to=math.rad((diagonal and 40 or 100)*side)
  local radius=math.clamp(reach*.82,3,11)
  K.ring(folder,frame,{segments=12,from=from,to=to,radius0=radius*.9,radius1=radius*1.06,
   width=math.clamp(reach*.24,1,2.1),rim=HEAVY_RIM,reveal=math.max(.06,(Motion.SwingHitEnd-Motion.SwingHitStart)/(info.rate or 1)),
   hold=.05,duration=.46,bodyAlpha=.55,color=Profiles[id].color})
 end
 local function slam(position,scale)
  if not K.near(position,140) then return end
  local y=ground(position,position.Y-2)
  if math.abs(position.Y-y)>5 then return end
  local base=Vector3.new(position.X,y+.1,position.Z)
  K.ring(folder,CFrame.new(base),{segments=14,radius0=.5*scale,radius1=2.8*scale,width=.55*scale,rim=HEAVY_RIM,duration=.34,bodyAlpha=.6})
  for i=1,4 do
   local angle=i*math.pi/2+math.random()*.6
   local offset=Vector3.new(math.cos(angle),0,math.sin(angle))
   K.cloud(folder,base+offset*1.1*scale+Vector3.yAxis*.3,K.Dust,1.1*scale,.5,offset*1.6+Vector3.yAxis*.6,.35)
  end
 end
 -- info: {visible,active(age within attack),age,start,style,side,attackRoot,direction,range,rate,hand,secondAim}
 function api.step(v,pivot,info)
  local swing=v.swing;if not swing then return end
  local profile=swing.profile
  -- Thrown Mjolnir flights are drawn by ThrownVisuals, not the resting slot.
  local live=info.visible and info.active and info.kind=='Melee' and info.age>=Motion.SwingHitStart-.03 and info.age<=Motion.SwingHitEnd+.04
  if live and swing.start~=info.start then
   swing.start=info.start;swing.crescent=false;swing.slam=false
   for _,r in swing.ribbons do r.trail:Clear() end
  end
  local frames
  if profile.mode=='chain' and v.chain then frames=Chains.sample(v.chain,math.max(0,info.age or 0),pivot) end
  for _,r in swing.ribbons do
   local p0,p1
   if profile.mode=='blade' then
    p0,p1=pivot:PointToWorldSpace(swing.inner),pivot:PointToWorldSpace(swing.outer)
   else
    local point
    if profile.mode=='blob' then point=pivot:PointToWorldSpace(swing.point)
    elseif profile.mode=='gloves' then point=r.part.Position
    else
     local entry=v.chain.entries[swing.entry]
     point=(frames[swing.entry]*(entry.hitCF or CFrame.identity)).Position
    end
    p0,p1=point-Vector3.yAxis*r.width*.5,point+Vector3.yAxis*r.width*.5
   end
   r.carrier.CFrame=CFrame.new(p0)
   r.a0.WorldPosition=p0;r.a1.WorldPosition=p1
   -- Gloves: only a punching hand streaks (the second fist only with a second target).
   local on=live
   if profile.mode=='gloves' and on then on=r.side==info.hand or info.secondAim~=nil end
   if r.trail.Enabled~=on then r.trail.Enabled=on end
  end
  if not profile.heavy or not live or not info.attackRoot then return end
  if info.style=='Downward' then
   if not swing.slam and info.age>=Motion.SwingHitEnd-.05 then
    swing.slam=true
    local tip=profile.mode=='blade' and pivot:PointToWorldSpace(swing.outer) or pivot.Position
    slam(tip,math.clamp(swing.size.Magnitude/3.4,.8,1.35))
   end
  elseif not swing.crescent and info.age>=Motion.SwingHitStart then
   swing.crescent=true
   crescent(info,v.id)
  end
 end
 function api.hide(v)
  if v.swing then for _,r in v.swing.ribbons do r.trail.Enabled=false end end
 end
 return api
end
return V
