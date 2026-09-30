-- Client-only helpers for the map-boss effects (plan F Task 10), wrapping VfxKit. Effects never
-- touch hits. Every part lives in workspace.BossVfxEffects and is named BossVfx*, so a check can
-- count leftovers. Also the fallback effects module: a boss without its own BossVfx module gets
-- these no-op hooks and a plain projectile.
local RunService=game:GetService('RunService')
local TweenService=game:GetService('TweenService')
local Players=game:GetService('Players')
local combat=script.Parent.Parent
local K=require(combat:WaitForChild('VfxKit'))
local C={K=K,CULL=160}
function C.folder()
 local f=workspace:FindFirstChild('BossVfxEffects')
 if not f then f=Instance.new('Folder');f.Name='BossVfxEffects';f.Parent=workspace end
 return f
end
function C.near(pos) return K.near(pos,C.CULL) end
-- BossVfxAssets: {Textures={[name]=id}, Flipbook={[name]='4x4'}, Sounds={[name]=id}}; mesh templates are its children.
function C.assets()
 local m=combat:FindFirstChild('BossVfxAssets');if not m then return {Textures={},Flipbook={},Sounds={}} end
 local ok,a=pcall(require,m);return ok and a or {Textures={},Flipbook={},Sounds={}}
end
function C.texture(name) return C.assets().Textures[name] end
local function part(name,size,cf,color,transparency)
 local p=K.part(C.folder(),'BossVfx'..name,size,color or K.White,transparency or 0);p.CFrame=cf;return p
end
C.part=part
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
-- An anchored host part for emitters, removed after `seconds`.
function C.host(pos,seconds,look)
 local p=part('Host',Vector3.one*.05,CFrame.lookAt(pos,pos+(look or Vector3.yAxis)),K.White,1)
 K.animate(seconds,function() end,function() p:Destroy() end,'bossHost',64)
 return p
end
-- Clone of a BossVfxAssets mesh template, anchored and non-colliding.
function C.mesh(name,cf,scale)
 local template=combat:FindFirstChild('BossVfxAssets') and combat.BossVfxAssets:FindFirstChild(name);if not template then return nil end
 local p=template:Clone();p.Name='BossVfx'..name;p.Anchored=true;p.CanCollide=false;p.CanQuery=false;p.CanTouch=false;p.CastShadow=false
 p:SetAttribute('BaseSize',template.Size);p.Size=template.Size*(scale or 1);p.CFrame=cf;p.Parent=C.folder();return p
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
function C.light(pos,color,range,brightness,seconds) K.flash(C.folder(),pos,color,range,brightness,seconds) end
-- Fallback hooks (MapBossPresentation calls these when a boss has no effects module).
function C.windup(ctx) end
function C.impact(ctx) end
function C.active(ctx,age) end
-- A plain glowing ball; returns the part, a per-frame update and a finish(pos) for the pop.
function C.projectile(ctx,i)
 local color=ctx.tint or K.Amber;local radius=ctx.def.radius or 1
 local ball=K.ball(C.folder(),'BossVfxShot',radius*2,color,.25,Enum.Material.Neon)
 return ball,function(dt) end,function(pos) if C.near(pos) then K.pop(C.folder(),pos,color,radius,radius*3,.25,.4) end end
end
return C
