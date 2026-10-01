-- Client-only helpers for the map-boss effects (plan F Task 10), wrapping VfxKit. Effects never
-- touch hits. Every part lives in workspace.BossVfx and is named BossVfx*, so a check can count
-- leftovers. Also the fallback effects module: a boss without its own BossVfx module gets these
-- no-op hooks and a plain projectile.
local RunService=game:GetService('RunService')
local TweenService=game:GetService('TweenService')
local Players=game:GetService('Players')
local combat=script.Parent.Parent
local K=require(combat:WaitForChild('VfxKit'))
local Shapes=require(combat:WaitForChild('MapBossShapes'))
local C={K=K,Shapes=Shapes,CULL=160}
local up=Vector3.yAxis
-- One effects folder. VfxKit helpers name their parts Pop, Shard, ArcBody...; inside this folder
-- they are renamed BossVfx* as they arrive, so every effect part carries the prefix.
local folder
function C.folder()
 if folder and folder.Parent==workspace then return folder end
 folder=workspace:FindFirstChild('BossVfx')
 if not folder or not folder:IsA('Folder') then folder=Instance.new('Folder');folder.Name='BossVfx';folder.Parent=workspace end
 folder.DescendantAdded:Connect(function(d) if d:IsA('BasePart') and d.Name:sub(1,7)~='BossVfx' then d.Name='BossVfx'..d.Name end end)
 return folder
end
function C.near(pos,extra) return K.near(pos,C.CULL+(extra or 0)) end
-- BossVfxAssets: {Textures={[name]=id}, Flipbook={[name]='4x4'}, Sounds={[cue]=id}}; mesh templates are its children.
local EMPTY={Textures={},Flipbook={},Sounds={}}
function C.assets()
 local m=combat:FindFirstChild('BossVfxAssets');if not m then return EMPTY end
 local ok,a=pcall(require,m);return ok and type(a)=='table' and a or EMPTY
end
-- Lookups by name. A missing texture, flipbook, sound or mesh returns nil and that layer is skipped.
-- Flipbooks may be keyed 'FrostMist' or 'FrostMist_Flipbook4x4'; both resolve.
function C.texture(name) local T=C.assets().Textures or {};return T[name] or T[name..'_Flipbook4x4'] end
local FLIPBOOK={FrostMist=true,Flame=true,SmokePuff=true,Hieroglyphs=true,SandBurst=true,WaterSplash=true,SandSpray=true,DustPuff=true} -- the kit's 4x4 sheets
function C.flipbook(name) local F=C.assets().Flipbook or {};return F[name] or F[name..'_Flipbook4x4'] or (FLIPBOOK[name] and '4x4') or nil end
function C.template(name) local a=combat:FindFirstChild('BossVfxAssets');return a and a:FindFirstChild(name) end
local function part(name,size,cf,color,transparency)
 local p=K.part(C.folder(),'BossVfx'..name,size,color or K.White,transparency or 0);p.CFrame=cf;return p
end
C.part=part
-- Small maths: NumberSequence/ColorSequence from {t,v} pairs, a {lo,hi} roll, flat vectors, aim frames.
function C.ns(...) local k={};for i,p in {...} do k[i]=NumberSequenceKeypoint.new(p[1],p[2]) end;return NumberSequence.new(k) end
function C.cs(...) local k={};for i,p in {...} do k[i]=ColorSequenceKeypoint.new(p[1],p[2]) end;return ColorSequence.new(k) end
function C.rand(r) return type(r)=='table' and r[1]+(r[2]-r[1])*math.random() or r end
function C.flat(v) return Vector3.new(v.X,0,v.Z) end
function C.ground(ctx,p) return Vector3.new(p.X,ctx.groundY,p.Z) end
function C.aim(pos,dir) dir=dir.Magnitude>1e-4 and dir.Unit or up;return CFrame.lookAt(pos,pos+dir,math.abs(dir.Y)>.98 and Vector3.zAxis or up) end
-- The attack clock and whether its effects should keep going: false once the boss dies, is
-- removed, is reset by the server (ZombiesEnabled off) or starts another attack.
function C.age(ctx) return workspace:GetServerTimeNow()-ctx.start end
function C.live(ctx)
 local npc=ctx.npc
 if not npc.Parent or npc:GetAttribute('BossDeathStart') or npc:GetAttribute('BossSerial')~=ctx.serial or npc:GetAttribute('BossStart')~=ctx.start then return false end
 local h=npc:FindFirstChildOfClass('Humanoid');return not h or h.Health>0
end
-- The server's warning/hit shape for this attack (MapBossAttackData.shape), decoded to Vector3s.
function C.shape(ctx) local s=ctx.data and ctx.data.shape;return type(s)=='table' and Shapes.decode(s) or nil end
-- Per-frame driver for one effect layer: update(age,dt) runs on the attack's server clock until it
-- returns true, age reaches untilAge, or the attack stops. cleanup(stopped) always runs.
function C.follow(ctx,untilAge,update,cleanup)
 local last,stopped=os.clock(),false
 K.animate(math.max(.05,untilAge-C.age(ctx))+.5,function(t)
  local now=os.clock();local dt=now-last;last=now
  if not C.live(ctx) then stopped=true;return true end
  local age=C.age(ctx);if age>=untilAge or t>=1 then return true end
  return update(age,dt)
 end,cleanup and function() cleanup(stopped) end,'bossFollow',64)
end
-- Runs fn once when the attack clock reaches `when`, if the attack is still live.
function C.at(ctx,when,fn)
 if C.age(ctx)>=when then if C.live(ctx) then fn() end;return end
 K.animate(when-C.age(ctx)+.3,function(t)
  if C.age(ctx)>=when or t>=1 then if C.live(ctx) then fn() end;return true end
 end,nil,'bossAt',64)
end
-- Stops emitters and lights on hosts, lets live particles and trails finish, then destroys them.
function C.retire(hosts,linger)
 for _,h in hosts do if h and h.Parent then for _,d in h:GetDescendants() do if d:IsA('ParticleEmitter') or d:IsA('Light') then d.Enabled=false end end end end
 K.animate(linger or 1,function() end,function() for _,h in hosts do if h then h:Destroy() end end end,'bossRetire',128)
end
-- A host that trails a projectile part; once the part is gone (stopped, hit, or the boss removed)
-- its emitters stop and it is destroyed after `linger`, so trails fade instead of popping.
function C.tail(core,seconds,linger)
 local host=part('Tail',Vector3.one*.1,core.CFrame,K.White,1)
 K.animate(seconds,function() if not core.Parent then return true end;host.CFrame=core.CFrame end,function() C.retire({host},linger or .9) end,'bossTail',48)
 return host
end
-- Neon boss sections named <Boss>_<suffix> or <Boss>_<suffix>_<Piece> (LavaGlow, EyeGlow; the
-- Dragon's oversize sections are split into pieces): ramped for charge-ups and always
-- returned to the colour they had first.
function C.glow(npc,suffix)
 local list={}
 for _,p in npc:GetDescendants() do
  if p:IsA('BasePart') and (p.Name:match('_'..suffix..'$') or p.Name:match('_'..suffix..'_')) then
   local base=p:GetAttribute('BossVfxBaseColor');if typeof(base)~='Color3' then base=p.Color;p:SetAttribute('BossVfxBaseColor',base) end
   table.insert(list,{part=p,base=base})
  end
 end
 return list
end
function C.setGlow(list,color,k) for _,g in list do if g.part.Parent then g.part.Color=(k<=0 or not color) and g.base or g.base:Lerp(color,math.min(k,1)) end end end
-- Camera shake near the boss: strength fades to nothing 60 studs away; the Screen shake setting
-- (Setting_ScreenShake) turns it off. Nested outside the damage shake's RenderStep pair.
local shake={untilT=0,start=0,strength=0,offset=CFrame.identity,camera=nil}
RunService:BindToRenderStep('BossShakeRestore',Enum.RenderPriority.Camera.Value-2,function()
 if shake.camera and shake.camera==workspace.CurrentCamera then shake.camera.CFrame*=shake.offset:Inverse() end
 shake.offset=CFrame.identity;shake.camera=nil
end)
RunService:BindToRenderStep('BossShake',Enum.RenderPriority.Camera.Value+2,function()
 local now=os.clock();local camera=workspace.CurrentCamera
 if now>=shake.untilT or not camera or camera.CameraType==Enum.CameraType.Scriptable then return end
 local age=now-shake.start;local e=math.clamp((shake.untilT-now)/(shake.untilT-shake.start),0,1)^2*shake.strength
 shake.offset=CFrame.new(math.sin(age*91)*.12*e,math.sin(age*117)*.08*e,0)*CFrame.Angles(0,0,math.rad(math.sin(age*83)*.6*e))
 camera.CFrame*=shake.offset;shake.camera=camera
end)
function C.shake(pos,strength,seconds)
 local camera=workspace.CurrentCamera;if not camera or Players.LocalPlayer:GetAttribute('Setting_ScreenShake')==false then return end
 local s=strength*math.max(0,1-(camera.CFrame.Position-pos).Magnitude/60);if s<=.02 then return end
 local now=os.clock();local left=shake.untilT>now and (shake.untilT-now)/(shake.untilT-shake.start) or 0
 if s<shake.strength*left then return end -- a stronger shake is still running
 shake.start,shake.untilT,shake.strength=now,now+seconds,s
end
-- A flat decal on the ground: fades in, holds, fades out. size in studs, rotation in degrees.
function C.decal(pos,textureId,size,color,fadeIn,hold,fadeOut,rotation)
 local p=part('Decal',Vector3.new(size,.05,size),CFrame.new(pos)*CFrame.Angles(0,math.rad(rotation or 0),0),K.White,1)
 local d=Instance.new('Decal');d.Face=Enum.NormalId.Top;d.Texture=textureId or '';d.Color3=color or Color3.new(1,1,1);d.Transparency=1;d.Parent=p
 fadeIn,hold,fadeOut=fadeIn or .1,hold or .5,fadeOut or .5
 K.animate(fadeIn+hold+fadeOut,function(_,age)
  d.Transparency=age<fadeIn and 1-age/fadeIn or age<fadeIn+hold and 0 or K.smooth((age-fadeIn-hold)/fadeOut)
 end,function() p:Destroy() end,'bossDecal',48)
 return p,d
end
-- A flat textured plate on the ground, unanimated. glow (true or a brightness) draws it unlit through
-- a SurfaceGui, so lava and magic circles read in shade; otherwise a lit Decal (frost, scorch).
-- Plates step up a few thousandths of a stud each so overlapping stains never z-fight.
-- Returns the part and set(alpha, color?, size?, rotationDeg?, brightness?).
local layer=0
function C.plate(pos,name,size,color,rotation,glow)
 local id=C.texture(name);if not id then return nil end
 layer=layer%16+1;pos+=up*layer*.004
 local p=part('Plate',Vector3.new(size,.05,size),CFrame.new(pos)*CFrame.Angles(0,math.rad(rotation or math.random(0,359)),0),K.White,1)
 local img,gui
 if glow then
  gui=Instance.new('SurfaceGui');gui.Name='BossVfxGlow';gui.Face=Enum.NormalId.Top;gui.LightInfluence=0;gui.Brightness=type(glow)=='number' and glow or 1.5
  gui.SizingMode=Enum.SurfaceGuiSizingMode.PixelsPerStud;gui.PixelsPerStud=20;gui.Parent=p
  img=Instance.new('ImageLabel');img.BackgroundTransparency=1;img.BorderSizePixel=0;img.Size=UDim2.fromScale(1,1);img.Image=id;img.ImageColor3=color or K.White;img.ImageTransparency=1;img.Parent=gui
 else
  img=Instance.new('Decal');img.Face=Enum.NormalId.Top;img.Texture=id;img.Color3=color or K.White;img.Transparency=1;img.Parent=p
 end
 local function set(alpha,col,s,r,bright)
  if gui then img.ImageTransparency=alpha;if col then img.ImageColor3=col end;if bright then gui.Brightness=bright end
  else img.Transparency=alpha;if col then img.Color3=col end end
  if s then p.Size=Vector3.new(s,.05,s) end
  if r then p.CFrame=CFrame.new(pos)*CFrame.Angles(0,math.rad(r),0) end
 end
 return p,set
end
-- An expanding ring plate (shockwaves): diameter d0 -> d1 with a fast ease-out, fading late.
function C.ring(pos,name,d0,d1,seconds,color,alpha,glow)
 local p,set=C.plate(pos,name,d0,color,nil,glow);if not p then return end
 alpha=alpha or 0
 K.animate(seconds,function(t) set(alpha+(1-alpha)*K.smooth((t-.3)/.7),nil,d0+(d1-d0)*(1-(1-t)^4)) end,function() p:Destroy() end,'bossRing',32)
end
-- A ground stain: fades in to `alpha` (spreading from spread*size), holds, fades out.
function C.stain(pos,name,size,color,fadeIn,hold,fadeOut,alpha,spread,glow)
 spread=spread or 1;alpha=alpha or 0
 local p,set=C.plate(pos,name,size*spread,color,nil,glow);if not p then return nil end
 K.animate(fadeIn+hold+fadeOut,function(_,age)
  local a=age<fadeIn and 1-(1-alpha)*age/fadeIn or age<fadeIn+hold and alpha or alpha+(1-alpha)*K.smooth((age-fadeIn-hold)/fadeOut)
  set(a,nil,spread<1 and size*(spread+(1-spread)*(1-(1-math.min(1,age/.3))^3)) or nil)
 end,function() p:Destroy() end,'bossPlate',64)
 return p,set
end
-- A camera-facing, unlit sprite (BillboardGui) on a new invisible part at a position, or on a given part.
function C.sprite(at,name,size,color,alpha)
 local id=C.texture(name);if not id then return nil end
 local host=typeof(at)=='Instance' and at or part('Sprite',Vector3.one*.05,CFrame.new(at),K.White,1)
 local g=Instance.new('BillboardGui');g.Name='BossVfxSprite';g.Size=UDim2.fromScale(size,size);g.LightInfluence=0;g.Brightness=1.4;g.MaxDistance=C.CULL;g.Parent=host
 local img=Instance.new('ImageLabel');img.BackgroundTransparency=1;img.BorderSizePixel=0;img.Size=UDim2.fromScale(1,1);img.Image=id;img.ImageColor3=color or K.White;img.ImageTransparency=alpha or 0;img.Parent=g
 return host,g,img
end
-- The chunky 8-point ImpactStar: snaps open and fades in a blink.
function C.star(pos,color,size,seconds)
 if not C.near(pos) then return end
 local p,g,img=C.sprite(pos,'ImpactStar',size*.3,color,0);if not p then return end
 img.Rotation=math.random(0,44)
 K.animate(seconds or .2,function(t) local s=size*(.3+.7*(1-(1-t)^3));g.Size=UDim2.fromScale(s,s);img.ImageTransparency=K.smooth((t-.3)/.7) end,function() p:Destroy() end,'bossStar',24)
end
-- A ParticleEmitter from a props table: plain properties, plus shorthands
-- Color={a,b}, Size/Transparency={a,b} or number, Lifetime/Speed/RotSpeed/Rotation={lo,hi},
-- SpreadAngle=number or {x,y}, flipbook='4x4' (+ flipbookMode, fps), emit=count.
local SEQ={Size=true,Transparency=true};local RANGE={Lifetime=true,Speed=true,RotSpeed=true,Rotation=true}
local LAYOUT={['2x2']=Enum.ParticleFlipbookLayout.Grid2x2,['4x4']=Enum.ParticleFlipbookLayout.Grid4x4,['8x8']=Enum.ParticleFlipbookLayout.Grid8x8}
function C.emitter(host,props)
 local e=Instance.new('ParticleEmitter');e.Name='BossVfxEmitter';e.Enabled=(props.Rate or 0)>0
 for k,v in props do
  if k=='Color' and type(v)=='table' then e.Color=ColorSequence.new(v[1],v[2] or v[1])
  elseif k=='Color' and typeof(v)=='Color3' then e.Color=ColorSequence.new(v)
  elseif SEQ[k] and type(v)=='table' then e[k]=NumberSequence.new(v[1],v[2] or v[1])
  elseif SEQ[k] and type(v)=='number' then e[k]=NumberSequence.new(v)
  elseif RANGE[k] and type(v)=='table' then e[k]=NumberRange.new(v[1],v[2] or v[1])
  elseif RANGE[k] and type(v)=='number' then e[k]=NumberRange.new(v)
  elseif k=='SpreadAngle' and type(v)=='number' then e.SpreadAngle=Vector2.new(v,v)
  elseif k=='SpreadAngle' and type(v)=='table' then e.SpreadAngle=Vector2.new(v[1],v[2] or v[1])
  elseif k=='flipbook' then e.FlipbookLayout=LAYOUT[v] or Enum.ParticleFlipbookLayout.None;e.FlipbookMode=props.flipbookMode or Enum.ParticleFlipbookMode.OneShot
   if props.fps then e.FlipbookFramerate=NumberRange.new(props.fps) end
  elseif k~='emit' and k~='flipbookMode' and k~='fps' then e[k]=v end
 end
 e.Parent=host
 if props.emit then e:Emit(props.emit) end
 return e
end
-- An emitter using a kit texture by name (nil, and no emitter, when it is missing). Flipbook sheets
-- get Grid4x4 automatically: OneShot, except Hieroglyphs, which picks a Random glyph per particle.
-- Emission defaults to the host's LookVector.
function C.fx(host,name,props)
 local id=host and C.texture(name);if not id then return nil end
 props.Texture=id;props.EmissionDirection=props.EmissionDirection or Enum.NormalId.Front
 local layout=C.flipbook(name)
 if layout then props.flipbook=layout;props.flipbookMode=props.flipbookMode or (name=='Hieroglyphs' and Enum.ParticleFlipbookMode.Random or Enum.ParticleFlipbookMode.OneShot) end
 return C.emitter(host,props)
end
-- An anchored host part for emitters, removed after `seconds`.
function C.host(pos,seconds,look)
 local p=part('Host',Vector3.one*.05,C.aim(pos,look or up),K.White,1)
 K.animate(seconds,function() end,function() p:Destroy() end,'bossHost',128)
 return p
end
-- A one-shot burst from pos along look; its host lives as long as the longest particle.
local function longest(v) return type(v)=='table' and (v[2] or v[1]) or type(v)=='number' and v or 1.5 end
function C.emit(pos,look,name,props)
 if not C.texture(name) or not C.near(pos) then return nil end
 return C.fx(C.host(pos,longest(props.Lifetime)+.3,look),name,props)
end
-- Clone of a BossVfxAssets mesh template, anchored and non-colliding.
function C.mesh(name,cf,scale)
 local template=C.template(name);if not template then return nil end
 local p=template:Clone();p.Name='BossVfx'..name;p.Anchored=true;p.CanCollide=false;p.CanQuery=false;p.CanTouch=false;p.CastShadow=false
 p:SetAttribute('BaseSize',template.Size);p.Size=template.Size*(scale or 1);p.CFrame=cf;p.Parent=C.folder();return p
end
-- Chunks flung from pos (meshes picked at random from names): they arc under gravity, skid once on
-- groundY and shrink away. o: count, speed/up/scale={lo,hi}, life, gravity, spin, dir (a flat
-- bias), fallback={color,material} when the meshes are missing, trail={color0,color1,width}.
function C.chunks(pos,groundY,names,o)
 if not C.near(pos) then return end
 local list={};local n=o.count or 4;local seed=math.random()*6.28
 for i=1,n do
  local s=C.rand(o.scale or 1);local rot=CFrame.Angles(math.random()*6.28,math.random()*6.28,math.random()*6.28)
  local p=C.mesh(names[math.random(#names)],CFrame.new(pos)*rot,s)
  if not p and o.fallback then p=part('Chunk',Vector3.new(.5,.4,.5)*s,CFrame.new(pos),o.fallback[1],0);p.Material=o.fallback[2] or Enum.Material.SmoothPlastic end
  if p then
   local a=seed+i/n*math.pi*2+math.random()*.8;local h=Vector3.new(math.cos(a),0,math.sin(a))
   if o.dir then h=(h*.5+o.dir).Unit end
   if o.trail then K.trail(p,o.trail[3] or .4,.22,o.trail[1],o.trail[2],.15) end
   table.insert(list,{part=p,pos=pos,v=h*C.rand(o.speed or {8,14})+up*C.rand(o.up or {10,18}),rot=rot,base=p.Size,
    spin=Vector3.new(math.random()-.5,math.random()-.5,math.random()-.5)*(o.spin or 16)})
  end
 end
 if #list==0 then return end
 local last,g=0,o.gravity or 70
 K.animate(o.life or 1.3,function(t,age)
  local dt=math.min(age-last,1/20);last=age;local k=1-K.smooth((t-.72)/.28)
  for _,c in list do
   local half=(c.base.X+c.base.Y+c.base.Z)/6*k
   if not c.rest then
    c.v-=up*g*dt;c.pos+=c.v*dt;c.rot*=CFrame.Angles(c.spin.X*dt,c.spin.Y*dt,c.spin.Z*dt)
    if c.pos.Y<groundY+half and c.v.Y<0 then
     if c.v.Y<-8 and not c.bounced then c.bounced=true;c.v=Vector3.new(c.v.X*.45,-c.v.Y*.28,c.v.Z*.45);c.spin*=.5 else c.rest=true end
    end
   end
   c.pos=Vector3.new(c.pos.X,c.rest and groundY+half or math.max(c.pos.Y,groundY+half),c.pos.Z)
   c.part.Size=c.base*math.max(.05,k);c.part.CFrame=CFrame.new(c.pos)*c.rot
  end
 end,function() for _,c in list do c.part:Destroy() end end,'bossChunks',48)
end
-- Scale a part from fromScale to toScale of its base size; ease is an Enum.EasingStyle or f(t).
function C.grow(part,fromScale,toScale,seconds,ease,done)
 local base=part:GetAttribute('BaseSize') or part.Size;part:SetAttribute('BaseSize',base)
 K.animate(seconds,function(t)
  if not part.Parent then return true end
  local k=type(ease)=='function' and ease(t) or TweenService:GetValue(t,ease or Enum.EasingStyle.Quad,Enum.EasingDirection.Out)
  part.Size=base*(fromScale+(toScale-fromScale)*k)
 end,done,'bossGrow',96)
end
-- A positional sound through the RogueliteSFX group (the Settings SFX slider), removed when done.
function C.sound(id,pos,volume,pitch,looped)
 if not id then return nil end
 local host=part('Sound',Vector3.one*.05,CFrame.new(pos),K.White,1)
 local s=Instance.new('Sound');s.SoundId=type(id)=='number' and 'rbxassetid://'..id or id;s.Volume=volume or .6;s.PlaybackSpeed=pitch or 1;s.Looped=looped==true
 s.RollOffMaxDistance=140;s.SoundGroup=game:GetService('SoundService'):FindFirstChild('RogueliteSFX');s.Parent=host
 if not looped then s.Ended:Connect(function() host:Destroy() end);game:GetService('Debris'):AddItem(host,12) end
 s:Play();return s,host
end
-- A BossVfxAssets sound cue by name, slightly detuned so repeats don't phase. Looped cues are
-- capped at 12 s by Debris even if their owner never stops them.
function C.cue(name,pos,volume,pitch,looped)
 local id=(C.assets().Sounds or {})[name];if not id or not C.near(pos) then return nil end
 local s,host=C.sound(id,pos,volume,(pitch or 1)*(.96+math.random()*.08),looped)
 if looped and host then game:GetService('Debris'):AddItem(host,12) end
 return s,host
end
function C.stopSound(s,host,seconds)
 if not s or not host or not host.Parent then return end
 local v=s.Volume;K.animate(seconds or .2,function(t) s.Volume=v*(1-t) end,function() host:Destroy() end,'bossSound',32)
end
function C.light(pos,color,range,brightness,seconds) K.flash(C.folder(),pos,color,range,brightness,seconds) end
-- A dust ring thrown outward along the ground at radius r (landings, stomps, the spawn intro).
function C.dustRing(pos,r,count,color,speed,size)
 for i=1,count do
  local a=i/count*math.pi*2+math.random()*.3;local out=Vector3.new(math.cos(a),0,math.sin(a))
  C.emit(pos+out*r+up*.5,out+up*.25,'DustPuff',{emit=2,Speed=speed or {14,20},SpreadAngle=25,Drag=3.5,Lifetime={.7,1.1},Size=C.ns({0,(size or 3)*.5},{1,size or 3}),Color=color or K.Dust,Transparency=C.ns({0,.2},{.6,.4},{1,1}),LightInfluence=.8,Rotation={0,360},RotSpeed={-40,40}})
 end
end
-- Ground height under the boss (the root centre sits Size.Y/2 + HipHeight above it).
function C.feet(npc)
 local root=npc.PrimaryPart;if not root then return nil end
 local h=npc:FindFirstChildOfClass('Humanoid');local drop=root.Size.Y*.5+(h and h.HipHeight or 0)
 return K.groundBelow(root.Position-up*(drop-1),{npc,C.folder()},root.Position.Y-drop)
end
-- Per-boss aura while enraged: {texture, colour, emission}.
local AURA={
 Dragon={'Flame',Color3.fromRGB(255,120,40),.9},FrostCyclops={'FrostMist',Color3.fromRGB(170,225,255),.3},
 Pharaoh={'Hieroglyphs',Color3.fromRGB(255,206,96),.8},KingCrab={'Bubble',Color3.fromRGB(236,250,255),.3},
}
-- Fallback hooks (MapBossPresentation calls these when a boss module does not define them).
function C.windup(ctx) end
function C.impact(ctx) end
function C.active(ctx,age) end
-- Spawn intro: the boss lands with a double shockwave, a dust wall and a heavy shake.
function C.intro(m)
 local root=m.npc.PrimaryPart;if not root then return end
 local y=C.feet(m.npc);local g=Vector3.new(root.Position.X,y or root.Position.Y,root.Position.Z)
 C.shake(g,1.6,.7);if not C.near(g,40) then return end
 local tint=m.tint or K.Amber;local r=8*(m.scale or 1)
 C.cue('ground_quake',g,.8,.85)
 C.ring(g+up*.06,'ShockwaveRing',r*.5,r*4.5,.6,K.White,0,true);C.ring(g+up*.09,'ShockwaveRing',r*.3,r*3,.9,tint,.25,true)
 C.dustRing(g,r*.8,14,nil,{20,28},r*.55);C.light(g+up*4,tint,40,3,.7)
 C.emit(g+up*.5,up,'DustPuff',{emit=18,Speed={10,18},SpreadAngle=80,Drag=3,Lifetime={1,1.5},Size=C.ns({0,r*.4},{1,r*.9}),Color=K.Dust,Transparency=C.ns({0,.3},{.6,.45},{1,1}),LightInfluence=.8,Rotation={0,360},RotSpeed={-30,30}})
end
-- Enrage (below half health): a flash and shockwave, the glows ramp to the tint, and an aura keeps
-- rising off the body for the rest of the fight so the danger stays readable.
function C.enrage(m)
 local npc=m.npc;local root=npc.PrimaryPart;if not root then return end
 local tint=m.tint or Color3.fromRGB(255,90,60);local p=root.Position;local r=6*(m.scale or 1)
 C.shake(p,1.2,.6)
 if C.near(p,40) then
  K.pop(C.folder(),p,tint,r,r*5,.5,.35);C.star(p+up*2,tint,r*2.2,.28);C.light(p,tint,50,4,.8)
  local y=C.feet(npc);if y then C.ring(Vector3.new(p.X,y+.08,p.Z),'ShockwaveRing',r,r*6,.7,tint,0,true) end
  C.cue('dragon_windup',p,.7,.8)
 end
 C.setGlow(C.glow(npc,'EyeGlow'),Color3.fromRGB(255,70,50),.8)
 local a=AURA[m.id] or {'Ember',tint,.8}
 C.fx(root,a[1],{Rate=14,EmissionDirection=Enum.NormalId.Top,Speed={2,5},SpreadAngle=40,Lifetime={.8,1.3},Size=C.ns({0,r*.2},{.4,r*.45},{1,0}),Color=a[2],Transparency=C.ns({0,1},{.2,.35},{1,1}),LightEmission=a[3],LightInfluence=.4,Acceleration=Vector3.new(0,4,0),Rotation={0,360},RotSpeed={-40,40}})
end
-- Follow-up eruption at each circle: a column burst, shockwave and debris in the boss tint.
function C.aftershock(m)
 local tint=m.tint or K.Amber
 for i,p in m.points do
  if C.near(p) then
   local r=m.radius or 5
   C.ring(p+up*.07,'ShockwaveRing',1,r*2.4,.35,tint,0,true);C.star(p+up*2,tint,r*1.6,.2);C.light(p+up*3,tint,r*3,2.5,.35)
   C.emit(p+up*.4,up,'DustPuff',{emit=10,Speed={16,26},SpreadAngle=18,Drag=2,Lifetime={.6,.9},Size=C.ns({0,r*.4},{1,r*.8}),Color=K.Dust,Transparency=C.ns({0,.2},{.6,.4},{1,1}),LightInfluence=.8,Rotation={0,360}})
   if i==1 then C.cue('sand_burst',p,.6) end;C.shake(p,.6,.25)
  end
 end
end
-- A plain glowing ball; returns the part, a per-frame update and a finish(pos) for the pop.
function C.projectile(ctx,i)
 local color=ctx.tint or K.Amber;local radius=ctx.def.radius or 1
 local ball=K.ball(C.folder(),'BossVfxShot',radius*2,color,.25,Enum.Material.Neon)
 return ball,function(dt) end,function(pos) if C.near(pos) then K.pop(C.folder(),pos,color,radius,radius*3,.25,.4) end end
end
return C
