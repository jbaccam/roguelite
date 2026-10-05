-- Local, reusable suction funnel. Width is the far-end HALF-WIDTH in studs.
-- Nine soft curved wind ribbons and twelve inward motes, allocated once per pooled funnel.
-- No assets, targets, physics, event subscriptions, or live-world lookups; also used by showcase.
local V={Rings=3,ArcsPerRing=3,Motes=12}
local AIR=ColorSequence.new(Color3.fromRGB(225,244,233),Color3.fromRGB(159,213,200))
local OPACITY={}
for i=0,32 do OPACITY[i]=NumberSequence.new(.58+.42*i/32) end
local function frame(position,tangent,axis)
 return CFrame.fromMatrix(position,tangent,axis,tangent:Cross(axis))
end
function V.new(parent)
 local model=Instance.new('Model');model.Name='VacuumFunnel'
 local anchor=Instance.new('Part');anchor.Name='WindAnchor';anchor.Size=Vector3.one*.1
 anchor.Transparency=1;anchor.Anchored=true;anchor.CanCollide=false;anchor.CanTouch=false;anchor.CanQuery=false;anchor.CastShadow=false;anchor.Parent=model
 local rings={};local motes={}
 for ring=1,V.Rings do
  local arcs={};rings[ring]=arcs
  for arc=1,V.ArcsPerRing do
   local a=Instance.new('Attachment');a.Parent=anchor;local b=Instance.new('Attachment');b.Parent=anchor
   local beam=Instance.new('Beam');beam.Name='CurvedWind';beam.Attachment0=a;beam.Attachment1=b
   beam.Segments=8;beam.FaceCamera=true;beam.Color=AIR;beam.LightEmission=.08;beam.LightInfluence=.7
   beam.Transparency=OPACITY[18];beam.Parent=anchor;arcs[arc]={a=a,b=b,beam=beam}
  end
 end
 for i=1,V.Motes do
  local p=Instance.new('Part');p.Name='InwardMote';p.Shape=Enum.PartType.Ball
  p.Size=Vector3.new(.09,.09,.23);p.Color=Color3.fromRGB(232,243,213);p.Material=Enum.Material.SmoothPlastic
  p.Anchored=true;p.CanCollide=false;p.CanTouch=false;p.CanQuery=false;p.CastShadow=false;p.Parent=model;motes[i]=p
 end
 local self={model=model}
 function self:hide() model.Parent=nil end
 function self:destroy() model:Destroy() end
 function self:update(origin,finish,width,now)
  local delta=finish-origin;local length=delta.Magnitude
  if length<.1 then self:hide();return end
  model.Parent=parent;anchor.Position=origin
  local axis=delta.Unit;local right=axis:Cross(Vector3.yAxis)
  right=right.Magnitude>.01 and right.Unit or Vector3.xAxis
  local up=right:Cross(axis).Unit
  -- The damaging cone is broad; leave transparent space around this readable central funnel.
  local mouth=math.clamp(width*.66,.25,7)
  local function offset(angle,radius) return (right*math.cos(angle)+up*math.sin(angle))*radius end
  local function tangent(angle) return -right*math.sin(angle)+up*math.cos(angle) end
  for ring,arcs in rings do
   local t=1-((now*.85+(ring-1)/V.Rings)%1)
   local center=origin+delta*t;local radius=.12+mouth*t
   local spin=now*2.8+ring*2.05
   local fade=math.clamp(math.min(t/.12,(1-t)/.16),0,1)
   for arc,line in arcs do
    -- A three-quarter wind ribbon with a visible gap, rotating as it narrows into the nozzle.
    local a=spin+(arc-1)*math.pi/2;local b=a+math.pi/2
    line.a.WorldCFrame=frame(center+offset(a,radius),tangent(a),axis)
    line.b.WorldCFrame=frame(center+offset(b,radius),tangent(b),axis)
    line.beam.CurveSize0=radius*.55228475;line.beam.CurveSize1=radius*.55228475
    line.beam.Width0=(.075+.16*t)*(arc==1 and .45 or 1)
    line.beam.Width1=(.075+.16*t)*(arc==3 and .4 or 1)
    line.beam.Transparency=OPACITY[math.clamp(math.floor(32*(1-fade*.75)+.5),0,32)]
   end
  end
  for i,p in motes do
   local phase=(now*(1.1+(i%3)*.08)+i/V.Motes)%1
   local t=(1-phase)^.72 -- accelerates toward the nozzle
   local angle=now*2.8+i*2.399
   local radius=(.1+mouth*t)*(.35+.6*((i*7)%11)/11)
   local position=origin+delta*t+offset(angle,radius)
   local inward=origin-position
   p.CFrame=inward.Magnitude>.01 and CFrame.lookAt(position,origin) or CFrame.new(position)
   p.Transparency=1-.58*math.clamp(math.min(t/.06,(1-t)/.1),0,1)
  end
 end
 return self
end
return V
