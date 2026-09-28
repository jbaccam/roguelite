-- Pandora's Box presentation: a faint glow leaking from the closed lid, a burst
-- of purple light when it opens, a cursed spirit skull on the mortar arc, and
-- a curse ring where it lands. Visual only; ArcProjectiles owns the blast.
local K=require(script.Parent:WaitForChild('VfxKit'))
local P={}
local VIOLET=Color3.fromRGB(156,96,236)
local DEEP=Color3.fromRGB(74,34,118)
local EYE=Color3.fromRGB(214,164,255)
local BONE=Color3.fromRGB(236,229,212)
local SOCKET=Color3.fromRGB(44,22,58)
P.Colors={violet=VIOLET,deep=DEEP,eye=EYE,bone=BONE}

local function wisps(parent,rate,size,lifetime)
 local e=Instance.new('ParticleEmitter');e.Name='SpiritWisps'
 e.Texture='rbxasset://textures/particles/smoke_main.dds'
 e.Color=ColorSequence.new(VIOLET,DEEP);e.LightEmission=.6;e.LightInfluence=.2
 e.Size=NumberSequence.new({NumberSequenceKeypoint.new(0,size),NumberSequenceKeypoint.new(1,size*.2)})
 e.Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,.45),NumberSequenceKeypoint.new(1,1)})
 e.Lifetime=NumberRange.new(lifetime*.7,lifetime);e.Rate=rate;e.Speed=NumberRange.new(.2,.8)
 e.SpreadAngle=Vector2.new(40,40);e.Rotation=NumberRange.new(0,360);e.RotSpeed=NumberRange.new(-40,40)
 e.Parent=parent;return e
end
local function sparkles(parent,rate,size)
 local e=Instance.new('ParticleEmitter');e.Name='CurseSparkles'
 e.Texture='rbxasset://textures/particles/sparkles_main.dds'
 e.Color=ColorSequence.new(EYE);e.LightEmission=1;e.LightInfluence=0
 e.Size=NumberSequence.new({NumberSequenceKeypoint.new(0,size),NumberSequenceKeypoint.new(1,0)})
 e.Lifetime=NumberRange.new(.3,.55);e.Rate=rate;e.Speed=NumberRange.new(.5,1.5)
 e.SpreadAngle=Vector2.new(180,180);e.Parent=parent;return e
end

-- Called once per rendered box: a soft leak of light from the lid seam.
function P.idle(model)
 local size=model:GetAttribute('BoundsSize') or Vector3.new(2.5,2.4,2.1)
 local seam=K.part(model,'PandoraSeamGlow',Vector3.new(size.X*.7,.05,size.Z*.7),VIOLET,1)
 local attachment=Instance.new('Attachment');attachment.Name='Seam';attachment.Parent=seam
 local drift=wisps(attachment,1.6,.55,1.1);drift.Speed=NumberRange.new(.4,.9);drift.EmissionDirection=Enum.NormalId.Top
 local light=Instance.new('PointLight');light.Color=VIOLET;light.Range=4.5;light.Brightness=.35;light.Shadows=false;light.Parent=seam
 return {seam=seam,offset=CFrame.new(0,size.Y*.5-.12,0),light=light,drift=drift}
end
function P.stepIdle(state,pivot,visible,lid)
 if not state then return end
 state.seam.CFrame=pivot*state.offset
 state.drift.Enabled=visible
 state.light.Enabled=visible
 -- Brighter while the lid is open.
 state.light.Brightness=.35+1.1*(lid or 0)
 state.light.Range=4.5+1.5*(lid or 0)
end

-- The lid bursts open: a column of light, dark smoke, and a handful of
-- ghostly souls that spiral up out of the box and fade as they escape.
local SOUL=Color3.fromRGB(206,176,255)
local function soul(folder,top,index,count)
 local head=K.ball(folder,'EscapingSoul',.38,SOUL,.4,Enum.Material.Neon)
 local trail=K.trail(head,.28,.34,SOUL,VIOLET,.5)
 trail.WidthScale=NumberSequence.new({NumberSequenceKeypoint.new(0,1),NumberSequenceKeypoint.new(1,0)})
 local angle=index/count*math.pi*2+math.random()*.5
 local turn=(index%2==0 and 1 or -1)*(2.6+math.random())
 local rise=4.5+math.random()*2.5
 local reach=1.4+math.random()*1.4
 local delay=(index-1)*.05
 K.animate(1+delay,function(t,age)
  local local_t=math.clamp((age-delay)/1,0,1)
  local e=1-(1-local_t)^2
  local a=angle+turn*local_t
  local r=.3+reach*e
  head.Position=top+Vector3.new(math.cos(a)*r,.2+rise*e+math.sin(local_t*9+index)*.15,math.sin(a)*r)
  head.Size=Vector3.one*(.38-.16*local_t)
  head.Transparency=local_t<=0 and 1 or .4+.6*K.smooth((local_t-.5)/.5)
 end,function() head:Destroy() end,'soul',40)
end
function P.open(folder,pivot,size)
 local top=pivot:PointToWorldSpace(Vector3.new(0,(size and size.Y or 2.4)*.5,0))
 if not K.near(top,150) then return end
 K.flash(folder,top,VIOLET,10,2.6,.6)
 local column=K.part(folder,'CurseColumn',Vector3.new(.4,.1,.4),VIOLET,.5,Enum.Material.Neon,Enum.PartType.Cylinder)
 K.animate(.42,function(t)
  local rise=1-(1-t)^3
  local height=.2+3.4*rise
  column.Size=Vector3.new(height,1.1-.6*t,1.1-.6*t)
  column.CFrame=CFrame.new(top+Vector3.yAxis*height*.5)*CFrame.Angles(0,0,math.pi/2)
  column.Transparency=.45+.55*K.smooth((t-.3)/.7)
 end,function() column:Destroy() end,'pandora',12)
 for i=1,5 do soul(folder,top,i,5) end
 K.burst(folder,top,{colors={VIOLET,DEEP},count=10,size0=.9,size1=2.4,lifetime=.9,speed=3.5,spread=35,drag=2,alpha0=.35,light=.4})
 K.burst(folder,top,{texture='rbxasset://textures/particles/sparkles_main.dds',colors={EYE},count=12,size0=.35,size1=0,lifetime=.6,speed=7,spread=40,drag=3,alpha0=0,light=1})
end

-- Stylized cursed spirit skull built from simple rounded parts; faces -Z.
function P.skull(folder)
 local m=Instance.new('Model');m.Name='PandoraSpiritSkull'
 local cranium=K.part(m,'ReplaceableProjectile',Vector3.new(.95,.9,1),BONE,0)
 local mesh=Instance.new('SpecialMesh');mesh.MeshType=Enum.MeshType.Sphere;mesh.Parent=cranium
 local jaw=K.part(m,'Jaw',Vector3.new(.6,.24,.46),BONE,0)
 local parts={cranium=cranium,jaw=jaw,pieces={{part=jaw,offset=CFrame.new(0,-.4,-.2)}}}
 local function piece(name,size,color,material,offset,shape)
  local p=K.part(m,name,size,color,0,material,shape);table.insert(parts.pieces,{part=p,offset=offset});return p
 end
 for side=-1,1,2 do
  piece('Socket',Vector3.one*.3,SOCKET,nil,CFrame.new(side*.21,.03,-.38),Enum.PartType.Ball)
  piece('Eye',Vector3.one*.15,EYE,Enum.Material.Neon,CFrame.new(side*.21,.03,-.47),Enum.PartType.Ball)
 end
 piece('Nose',Vector3.new(.1,.14,.06),SOCKET,nil,CFrame.new(0,-.16,-.47))
 for i=-1,1 do piece('Tooth',Vector3.new(.1,.1,.05),BONE,nil,CFrame.new(i*.13,-.3,-.44)) end
 local aura=K.ball(m,'SpiritAura',1.5,VIOLET,.8,Enum.Material.Neon)
 parts.aura=aura
 m.PrimaryPart=cranium
 local tail=K.trail(cranium,.8,.45,VIOLET,DEEP,.3)
 tail.WidthScale=NumberSequence.new({NumberSequenceKeypoint.new(0,1),NumberSequenceKeypoint.new(1,0)})
 local attachment=Instance.new('Attachment');attachment.Name='WispOrigin';attachment.Position=Vector3.new(0,0,.3);attachment.Parent=cranium
 wisps(attachment,34,.8,.55)
 sparkles(attachment,10,.25)
 local l=Instance.new('PointLight');l.Color=VIOLET;l.Range=7;l.Brightness=1.2;l.Shadows=false;l.Parent=cranium
 m.Parent=folder
 return m,parts
end
function P.stepSkull(parts,cf,age)
 -- Slight bob/roll and a chattering jaw read as "alive" at a distance.
 local base=cf*CFrame.Angles(math.sin(age*7)*.12,0,math.sin(age*5)*.18)
 parts.cranium.CFrame=base
 for _,p in parts.pieces do
  local offset=p.offset
  if p.part==parts.jaw then offset=offset*CFrame.new(0,-math.max(0,math.sin(age*18))*.07,0)*CFrame.Angles(math.max(0,math.sin(age*18))*.25,0,0) end
  p.part.CFrame=base*offset
 end
 parts.aura.CFrame=base
 parts.aura.Size=Vector3.one*(1.45+.12*math.sin(age*22))
end

-- Purple splash of cursed smoke where the skull lands: a billow, a rolling
-- smoke ring, droplets arcing out, and a soft ripple on the ground.
local SMOKE=Color3.fromRGB(128,78,196)
function P.impact(folder,position,radius)
 if not K.near(position,160) then return end
 radius=math.clamp(radius or 5,2,12)
 local y=K.groundBelow(position,{folder},position.Y-1)
 if math.abs(position.Y-y)>4 then y=position.Y-.5 end
 local base=Vector3.new(position.X,y+.15,position.Z)
 K.flash(folder,base+Vector3.yAxis,VIOLET,radius*2,2.6,.35)
 -- Low central puff that spreads out instead of rising into a column.
 K.burst(folder,base+Vector3.yAxis*.5,{colors={SMOKE,DEEP},count=10,size0=1.2,size1=math.min(3,radius*.45),lifetime=.8,speed=2.2,spread=75,drag=4,alpha0=.35,light=.1})
 -- Low smoke rolling outward along the ground.
 for i=1,10 do
  local angle=i/10*math.pi*2
  local direction=Vector3.new(math.cos(angle),.08,math.sin(angle))
  K.burst(folder,base+direction*.6,{colors={SMOKE,DEEP},count=2,size0=1.1,size1=2.2,lifetime=.8,speed=radius*1.3,spread=12,drag=3.5,alpha0=.4,light=.1,direction=direction})
 end
 -- Splash droplets thrown up and out, falling back under gravity.
 K.burst(folder,base,{colors={VIOLET,EYE},count=22,size0=.4,size1=.12,lifetime=.6,speed=radius*1.6,spread=60,drag=1,accel=Vector3.new(0,-45,0),alpha0=.15,light=.4})
 K.ring(folder,CFrame.new(base),{segments=18,radius0=radius*.3,radius1=radius*.95,width=.8,color=SMOKE,duration=.45,bodyAlpha=.62})
end
return P
