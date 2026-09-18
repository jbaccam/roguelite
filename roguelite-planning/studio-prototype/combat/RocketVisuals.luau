local RunService=game:GetService('RunService')
local TweenService=game:GetService('TweenService')
local Debris=game:GetService('Debris')
local V={}
local Motion=require(script.Parent.RocketMotion)
function V.mount(combat,visuals)
 local template=combat:WaitForChild('RocketTemplate')
 local explode=require(combat:WaitForChild('RocketExplosionVisuals')).mount(visuals)
 local active={}
 local smokeFolder=Instance.new('Folder');smokeFolder.Name='RPGCloudTrail';smokeFolder.Parent=visuals
 local puffs={}
 local spacing,lifetime,maxPuffs=.75,1.15,144
 local rocketLength=template:GetAttribute('Length')
 -- Different silhouettes: tall billow, wide bank, diagonal plume, rounded
 -- cluster, trailing beads, and a small split cloud. Each smoothly contracts.
 local shapes={
  {{0,.3,0,1.15},{-.48,-.12,0,.82},{.46,-.08,.08,.9},{.1,.78,.02,.72}},
  {{-.55,0,0,.95},{0,.22,.06,1.1},{.58,-.06,0,.85},{.98,-.2,.05,.38}},
  {{-.48,-.3,0,.7},{-.1,.04,.1,1.05},{.32,.48,0,.98},{.67,.7,.02,.48}},
  {{0,.2,0,1.2},{-.5,-.18,.08,.75},{.45,-.12,0,.82}},
  {{-.28,.18,0,1.1},{.28,-.1,.08,.85},{.82,-.2,0,.48},{1.15,-.26,.02,.26}},
  {{-.28,.08,0,.95},{.35,.24,.08,.85},{.7,-.14,0,.55}},
 }
 local function emitCloud(position,born,seed)
  local camera=workspace.CurrentCamera
  if camera and (camera.CFrame.Position-position).Magnitude>150 then return end
  if #puffs>=maxPuffs then local oldest=table.remove(puffs,1);oldest.model:Destroy() end
  local model=Instance.new('Model');model.Name='SmokeCloud';model:SetAttribute('BornAt',born);model.Parent=smokeFolder
  local width=.83+(seed%3)*.025
  local variant=seed%#shapes+1;model:SetAttribute('Variant',variant)
  local puff={model=model,born=born,position=position,parts={},width=width}
  for i,lobe in shapes[variant] do
   local part=Instance.new('Part');part.Name='CloudLobe';part.Shape=Enum.PartType.Ball
   part.Anchored=true;part.CanCollide=false;part.CanTouch=false;part.CanQuery=false;part.CastShadow=false
   part.Material=Enum.Material.SmoothPlastic;part.Color=i==2 and Color3.fromRGB(250,251,255) or Color3.fromRGB(213,219,230)
   local mirrored=seed%2==0 and 1 or -1
   local offset=Vector3.new(lobe[1]*mirrored,lobe[2],lobe[3])
   local size=Vector3.new(1,.92,.88)*width*lobe[4]
   part.Size=size;part.Position=position+offset*width;part.Parent=model
   table.insert(puff.parts,{part=part,offset=offset,size=size})
  end
  table.insert(puffs,puff)
 end
 local function remove(id)
  local r=active[id];if r then r.model:Destroy();active[id]=nil end
 end
 combat:WaitForChild('RocketFX').OnClientEvent:Connect(function(action,id,position,velocity,started,range,projectileScale,targetDistance)
  if action=='Launch' then
   local model=template:Clone();model.Name='FlyingRPG_'..id;model:ScaleTo(template:GetScale()*(projectileScale or 1));model.Parent=visuals
   local speed=velocity.Magnitude
   local age=math.max(0,workspace:GetServerTimeNow()-started)
   local r={model=model,origin=position,velocity=velocity,started=started,range=range,targetDistance=targetDistance or range,length=rocketLength*(projectileScale or 1),
    -- The launch origin is the muzzle and position tracks the rocket tip.
    -- Do not emit until its exhaust/tail has cleared that opening.
    nextSmoke=rocketLength*(projectileScale or 1)+math.max(0,math.floor((math.max(0,age-lifetime)*speed-rocketLength)/spacing))*spacing}
   active[id]=r
   model:PivotTo(CFrame.lookAt(position,position+velocity)*CFrame.new(0,0,r.length/2))
  else
   remove(id)
   if action=='Impact' then
    explode(position,velocity) -- impact packet: position, damage radius
   end
  end
 end)
 RunService.RenderStepped:Connect(function()
  local now=workspace:GetServerTimeNow()
  for id,r in active do
   local age=math.max(0,now-r.started);local distance=age*r.velocity.Magnitude
   if distance>r.range+10 then remove(id)
   else
    local traveled=math.min(distance,r.range)
    local tip=Motion.position(r.origin,r.velocity.Unit,traveled,r.targetDistance,id)
    local heading=Motion.direction(r.origin,r.velocity.Unit,traveled,r.targetDistance,id)
    r.model:PivotTo(CFrame.lookAt(tip,tip+heading)*CFrame.new(0,0,r.length/2))
    -- Sample the traveled path, not the current frame position. Low frame rates
    -- still leave a continuous trail with correctly staggered particle ages.
    r.nextSmoke=math.max(r.nextSmoke,r.length+math.max(0,math.floor((traveled-r.velocity.Magnitude*lifetime-r.length)/spacing))*spacing)
    local samples=0
    while r.nextSmoke<=traveled and samples<40 do
     local sampleTip=Motion.position(r.origin,r.velocity.Unit,r.nextSmoke,r.targetDistance,id)
     local sampleDirection=Motion.direction(r.origin,r.velocity.Unit,r.nextSmoke,r.targetDistance,id)
     local tail=sampleTip-sampleDirection*r.length
     emitCloud(tail,r.started+r.nextSmoke/r.velocity.Magnitude,math.floor(r.nextSmoke/spacing)+id)
     r.nextSmoke+=spacing;samples+=1
    end
   end
  end
  -- Clouds stay in world space when the rocket moves or is destroyed. Older
  -- clouds contract into smaller, simpler puffs and fade before newer ones.
  for i=#puffs,1,-1 do
   local puff=puffs[i];local age=math.max(0,now-puff.born)
   if age>=lifetime then puff.model:Destroy();table.remove(puffs,i)
   else
    local t=age/lifetime
    local smooth=t*t*(3-2*t)
    local growth=1.12-.94*smooth
    local compact=1-.4*smooth
    local fade=math.clamp((t-.08)/.92,0,1)
    local position=puff.position+Vector3.yAxis*(t*.45)
    for _,lobe in puff.parts do
     lobe.part.Size=lobe.size*growth
     lobe.part.Position=position+lobe.offset*puff.width*growth*compact
     lobe.part.Transparency=.06+.94*fade
    end
   end
  end
 end)
end
return V
