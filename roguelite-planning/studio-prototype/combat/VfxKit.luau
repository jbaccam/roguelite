-- Shared client-only effect helpers for weapon VFX. Every part is anchored,
-- non-colliding, non-queryable and removed by its own animation. No effect
-- here can influence server combat.
local RunService=game:GetService('RunService')
local Q=require(script.Parent:WaitForChild('ClientQuality'))
local K={}
K.White=Color3.fromRGB(255,251,242)
K.Amber=Color3.fromRGB(255,178,64)
K.Dust=Color3.fromRGB(214,202,184)
local effects={}
local counts={}
local connection
local function step()
 local now=os.clock()
 for i=#effects,1,-1 do
  local e=effects[i]
  local t=(now-e.born)/e.duration
  local ok,done=pcall(e.update,math.min(t,1),now-e.born)
  if not ok then warn('VfxKit effect failed: '..tostring(done)) end
  if not ok or done or t>=1 then
   table.remove(effects,i)
   if e.category then counts[e.category]-=1 end
   if e.cleanup then e.cleanup() end
  end
 end
 if #effects==0 and connection then connection:Disconnect();connection=nil end
end
-- Runs update(t,age) every frame until t reaches 1 or update returns true.
-- Categories are budgeted; the oldest effect in a full category is retired.
function K.animate(duration,update,cleanup,category,budget)
 if not connection then connection=RunService.RenderStepped:Connect(step) end
 if budget then budget=math.max(1,math.floor(budget*Q.get().effects)) end
 if category then
  counts[category]=(counts[category] or 0)+1
  if budget and counts[category]>budget then
   for i,e in effects do if e.category==category then
    table.remove(effects,i);counts[category]-=1;if e.cleanup then e.cleanup() end;break
   end end
  end
 end
 table.insert(effects,{born=os.clock(),duration=math.max(duration,1e-3),update=update,cleanup=cleanup,category=category})
end
function K.near(position,distance)
 local camera=workspace.CurrentCamera
 return camera~=nil and (camera.CFrame.Position-position).Magnitude<=(distance or 150)
end
function K.part(parent,name,size,color,transparency,material,shape)
 local p=Instance.new('Part');p.Name=name;p.Size=size;p.Color=color;p.Transparency=transparency or 0
 p.Material=material or Enum.Material.SmoothPlastic;p.Shape=shape or Enum.PartType.Block
 p.Anchored=true;p.CanCollide=false;p.CanTouch=false;p.CanQuery=false;p.CastShadow=false
 p.TopSurface=Enum.SurfaceType.Smooth;p.BottomSurface=Enum.SurfaceType.Smooth
 p.Parent=parent;return p
end
function K.ball(parent,name,size,color,transparency,material)
 return K.part(parent,name,Vector3.one*size,color,transparency,material,Enum.PartType.Ball)
end
local function smooth(t) t=math.clamp(t,0,1);return t*t*(3-2*t) end
K.smooth=smooth
-- Soft three-lobe cloud, the same language as the rocket smoke trail.
function K.cloud(parent,position,color,size,duration,drift,opacity)
 if not K.near(position,100) then return end
 local lobes={}
 local seed=math.random()*6.28
 for i=1,(Q.get().effects<.5 and 1 or 3) do
  local angle=seed+i*2.1
  local offset=Vector3.new(math.cos(angle)*size*.28,(i==2 and .12 or -.05)*size,math.sin(angle)*size*.28)
  lobes[i]={part=K.ball(parent,'CloudLobe',size*(i==2 and .78 or .62),color,1),offset=offset,scale=i==2 and .78 or .62}
 end
 drift=drift or Vector3.yAxis*.6
 K.animate(duration,function(t)
  local grow=.55+.6*smooth(t*1.6)
  local alpha=(opacity or .25)+(1-(opacity or .25))*smooth((t-.25)/.75)
  for _,l in lobes do
   l.part.Size=Vector3.one*size*l.scale*grow
   l.part.Position=position+l.offset*grow+drift*t
   l.part.Transparency=alpha
  end
 end,function() for _,l in lobes do l.part:Destroy() end end,'cloud',96)
end
-- Small pieces flung outward from a point, falling slightly.
function K.shards(parent,position,color,count,speed,duration,size,material,up)
 if not K.near(position,100) then return end
 count=math.max(1,math.floor(count*Q.get().effects))
 local list={}
 for i=1,count do
  local angle=(i/count)*math.pi*2+math.random()*.6
  local lift=(up or .35)+math.random()*.4
  local velocity=Vector3.new(math.cos(angle),lift,math.sin(angle)).Unit*speed*(.7+math.random()*.5)
  local p=K.part(parent,'Shard',Vector3.one*(size or .16),color,0,material or Enum.Material.Neon)
  list[i]={part=p,velocity=velocity,spin=CFrame.Angles(math.random()*6,math.random()*6,math.random()*6)}
 end
 K.animate(duration,function(t,age)
  for _,s in list do
   local pos=position+s.velocity*age+Vector3.yAxis*(-9*age*age)
   s.part.CFrame=CFrame.new(pos)*s.spin*CFrame.Angles(age*9,age*7,0)
   s.part.Size=Vector3.one*(size or .16)*(1-t*.7)
   s.part.Transparency=smooth((t-.4)/.6)
  end
 end,function() for _,s in list do s.part:Destroy() end end,'shards',64)
end
-- Arc or full ring made from flat segments lying in the frame's XZ plane.
-- A crescent reveals from `from` to `to` (radians), then widens and fades.
function K.ring(parent,frame,options)
 local segments=math.max(6,math.floor((options.segments or 14)*Q.get().effects))
 local from,to=options.from or 0,options.to or math.pi*2
 local radius0,radius1=options.radius0 or 1,options.radius1 or options.radius0 or 1
 local width=options.width or .6
 local reveal=options.reveal or 0
 local duration=options.duration or .4
 local rim=options.rim
 local list={}
 local span=(to-from)/segments
 for i=1,segments do
  local body=K.part(parent,'ArcBody',Vector3.new(.1,.05,.1),options.color or K.White,1,Enum.Material.Neon)
  local edge=rim and K.part(parent,'ArcRim',Vector3.new(.1,.06,.1),(i%2==0) and K.White or rim,1,Enum.Material.Neon)
  list[i]={body=body,edge=edge,angle=from+span*(i-.5)}
 end
 K.animate(duration,function(t,age)
  local grow=smooth(math.max(0,age-reveal)/math.max(.01,duration-reveal))
  local radius=radius0+(radius1-radius0)*grow
  local fade=smooth((age-reveal-(options.hold or .04))/math.max(.01,duration-reveal-(options.hold or .04)))
  local shown=reveal>0 and smooth(age/reveal) or 1
  local thin=width*(1-.55*fade)
  for i,s in list do
   local visible=(i-.5)/segments<=shown
   -- The yaw convention matches WeaponMotion headings: lookVector=(-sin,0,-cos).
   local direction=Vector3.new(-math.sin(s.angle),0,-math.cos(s.angle))
   local chord=2*radius*math.sin(math.abs(span)/2)*1.08
   local centerRadius=math.max(.05,radius-thin*.5)
   s.body.Size=Vector3.new(chord,.05,thin)
   s.body.CFrame=frame*CFrame.lookAt(direction*centerRadius,direction*centerRadius*2)
   s.body.Transparency=visible and ((options.bodyAlpha or .45)+(1-(options.bodyAlpha or .45))*fade) or 1
   if s.edge then
    s.edge.Size=Vector3.new(chord,.07,math.max(.12,thin*.28))
    s.edge.CFrame=frame*CFrame.lookAt(direction*(radius+.02),direction*(radius+.02)*2)
    s.edge.Transparency=visible and (.08+.92*fade) or 1
   end
  end
 end,function() for _,s in list do s.body:Destroy();if s.edge then s.edge:Destroy() end end end,'ring',16)
end
-- Short-lived light for magic launches and impacts. Kept small and brief.
function K.flash(parent,position,color,range,brightness,duration)
 if Q.get().lights==0 or not K.near(position,90) then return end
 local p=K.part(parent,'FlashLight',Vector3.one*.1,color,1)
 p.Position=position
 local light=Instance.new('PointLight');light.Color=color;light.Range=range;light.Brightness=0;light.Shadows=false;light.Parent=p
 K.animate(duration,function(t)
  light.Brightness=brightness*(t<.2 and t/.2 or 1-smooth((t-.2)/.8))
 end,function() p:Destroy() end,'flash',24)
end
-- Expanding translucent shell, used for magic pops.
function K.pop(parent,position,color,size0,size1,duration,alpha)
 local p=K.ball(parent,'Pop',size0,color,alpha or .45,Enum.Material.Neon)
 p.Position=position
 K.animate(duration,function(t)
  local e=1-(1-t)^3
  p.Size=Vector3.one*(size0+(size1-size0)*e)
  p.Transparency=(alpha or .45)+(1-(alpha or .45))*smooth(t)
 end,function() p:Destroy() end,'pop',48)
end
-- Jagged polyline between two points, drawn with pooled thin parts.
-- Returns a table with :draw(a,b,seed) and :fade(t) so callers can flicker it.
function K.newBolt(parent,colors,thickness,glow)
 local bolt={core={},outer={},count=0}
 local function ensure(list,i,color,width,alpha)
  local p=list[i]
  if not p then p=K.part(parent,'BoltSegment',Vector3.new(width,width,1),color,alpha,Enum.Material.Neon);list[i]=p end
  return p
 end
 function bolt:draw(a,b,jitter,rng)
  local delta=b-a;local length=delta.Magnitude
  if length<.05 then self:hide();return end
  local direction=delta/length
  local side=direction:Cross(Vector3.yAxis);if side.Magnitude<.01 then side=Vector3.xAxis end;side=side.Unit
  local up=side:Cross(direction).Unit
  local steps=math.clamp(math.floor(length/1.4)+2,3,16)
  local points={a}
  for i=1,steps-1 do
   local f=i/steps
   local taper=math.sin(f*math.pi)
   local offset=(side*(rng:NextNumber()-.5)+up*(rng:NextNumber()-.5))*2*(jitter or .45)*taper
   points[i+1]=a+delta*f+offset
  end
  points[steps+1]=b
  for i=1,steps do
   local p0,p1=points[i],points[i+1]
   local seg=p1-p0;local mid=(p0+p1)/2
   local core=ensure(self.core,i,colors[1],thickness,0)
   core.Size=Vector3.new(thickness,thickness,seg.Magnitude+thickness*.6);core.CFrame=CFrame.lookAt(mid,p1)
   if glow then
    local outer=ensure(self.outer,i,colors[2],thickness*2.8,.6)
    outer.Size=Vector3.new(thickness*2.8,thickness*2.8,seg.Magnitude+thickness);outer.CFrame=core.CFrame
   end
  end
  for i=steps+1,#self.core do self.core[i].Transparency=1 end
  for i=steps+1,#self.outer do self.outer[i].Transparency=1 end
  self.count=steps
 end
 function bolt:fade(alpha)
  for i=1,self.count do
   self.core[i].Transparency=alpha
   if self.outer[i] then self.outer[i].Transparency=.6+.4*alpha end
  end
 end
 function bolt:hide() self.count=0;for _,p in self.core do p.Transparency=1 end;for _,p in self.outer do p.Transparency=1 end end
 function bolt:destroy() for _,p in self.core do p:Destroy() end;for _,p in self.outer do p:Destroy() end;self.core={};self.outer={} end
 return bolt
end
-- A lightning strike that flickers once and fades.
K.Lightning={Color3.fromRGB(246,251,255),Color3.fromRGB(122,196,255)}
function K.strike(parent,a,b,colors,thickness,duration)
 if not K.near(a) and not K.near(b) then return end
 local rng=Random.new()
 local bolt=K.newBolt(parent,colors or K.Lightning,thickness or .09,true)
 bolt:draw(a,b,.5,rng)
 local redrawn=false
 K.animate(duration or .2,function(t)
  if t>.35 and not redrawn then redrawn=true;bolt:draw(a,b,.5,rng) end
  bolt:fade(smooth((t-.3)/.7))
 end,function() bolt:destroy() end,'bolt',40)
end
-- One-shot particle burst (soft smoke, splash droplets) from a point.
-- o: {texture,colors={a,b},count,size0,size1,lifetime,speed,spread,drag,accel,alpha0,light,direction}
function K.burst(parent,position,o)
 if not K.near(position,120) then return end
 local holder=K.part(parent,'BurstSource',Vector3.one*.05,K.White,1)
 holder.CFrame=CFrame.lookAt(position,position+(o.direction or Vector3.yAxis))
 local e=Instance.new('ParticleEmitter');e.Name='Burst';e.Enabled=false
 e.Texture=o.texture or 'rbxasset://textures/particles/smoke_main.dds'
 e.Color=ColorSequence.new(o.colors[1],o.colors[2] or o.colors[1])
 e.Size=NumberSequence.new(o.size0 or 1,o.size1 or 2)
 e.Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,o.alpha0 or .3),NumberSequenceKeypoint.new(.6,math.min(1,(o.alpha0 or .3)+.35)),NumberSequenceKeypoint.new(1,1)})
 local life=o.lifetime or .8
 e.Lifetime=NumberRange.new(life*.7,life);e.Speed=NumberRange.new((o.speed or 4)*.5,o.speed or 4)
 e.SpreadAngle=Vector2.new(o.spread or 180,o.spread or 180);e.Drag=o.drag or 0
 e.Acceleration=o.accel or Vector3.zero;e.EmissionDirection=Enum.NormalId.Front
 e.Rotation=NumberRange.new(0,360);e.RotSpeed=NumberRange.new(-60,60)
 e.LightEmission=o.light or .2;e.LightInfluence=.4
 e.Parent=holder
 e:Emit(math.max(1,math.floor((o.count or 10)*Q.get().effects)))
 K.animate(life+.1,function() end,function() holder:Destroy() end,'burst',48)
end
-- Standard projectile ribbon: FaceCamera trail between two attachments.
function K.trail(part,width,lifetime,color0,color1,alpha0,faceCamera)
 local a0=Instance.new('Attachment');a0.Name='TrailA';a0.Position=Vector3.new(0,width/2,0);a0.Parent=part
 local a1=Instance.new('Attachment');a1.Name='TrailB';a1.Position=Vector3.new(0,-width/2,0);a1.Parent=part
 local trail=Instance.new('Trail');trail.Name='FxTrail';trail.Attachment0=a0;trail.Attachment1=a1
 trail.Lifetime=lifetime;trail.MinLength=.05;trail.FaceCamera=faceCamera~=false
 trail.LightEmission=.35;trail.LightInfluence=.2
 trail.Color=ColorSequence.new(color0,color1 or color0)
 trail.Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,alpha0 or .2),NumberSequenceKeypoint.new(.55,.6),NumberSequenceKeypoint.new(1,1)})
 trail.WidthScale=NumberSequence.new(1,.15)
 trail.Parent=part
 return trail
end
function K.groundBelow(position,exclude,fallback)
 local params=RaycastParams.new();params.FilterType=Enum.RaycastFilterType.Exclude
 params.FilterDescendantsInstances=exclude;params.IgnoreWater=true
 local hit=workspace:Raycast(position+Vector3.yAxis*1.5,-Vector3.yAxis*12,params)
 return hit and hit.Position.Y or fallback
end
return K
