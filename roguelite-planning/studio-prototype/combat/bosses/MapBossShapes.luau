-- Shared boss hit and warning geometry. The server's hit tests and the client's ground
-- warnings read the same shape tables, so a warning is exactly where damage lands. The attack
-- windows and lane timing (S.window, S.laneTimes) are shared the same way.
-- Shapes are flat on the ground; `contains` also requires the point within a height band.
local S={}
S.HEIGHT_BELOW,S.HEIGHT_ABOVE=2,5.5 -- players jumping over a low wave clear it
local function flat(v) return Vector3.new(v.X,0,v.Z) end
S.flat=flat
-- Signed yaw from a to b about +Y; positive turns toward -X for a -Z forward (CFrame.Angles).
function S.yaw(a,b) a,b=flat(a),flat(b);return math.atan2(a:Cross(b).Y,a:Dot(b)) end
-- A frame's heading as a CFrame.Angles(0,yaw,0) angle (0 = facing -Z), and an angle wrapped to
-- [-pi, pi).
function S.yawOf(cf) local l=cf.LookVector;return math.atan2(-l.X,-l.Z) end
function S.wrap(a) return (a+math.pi)%(2*math.pi)-math.pi end
-- A shape turned `angle` (CFrame.Angles yaw) about the vertical axis through pivot. A boss frame that
-- turns about its root (aim, the breath) turns every shape built from it the same way, so the client
-- turns the commit's shapes instead of rebuilding them.
local POINTS,DIRS={center=true,origin=true,pivot=true,a=true,b=true},{direction=true,forward=true}
function S.rotated(shape,pivot,angle)
 local r=CFrame.Angles(0,angle,0);local s=table.clone(shape)
 local function turn(v) local base=Vector3.new(pivot.X,v.Y,pivot.Z);return base+r:VectorToWorldSpace(v-base) end
 for k in POINTS do if typeof(shape[k])=='Vector3' then s[k]=turn(shape[k]) end end
 for k in DIRS do if typeof(shape[k])=='Vector3' then s[k]=r:VectorToWorldSpace(shape[k]) end end
 if type(shape.points)=='table' then s.points={};for i,v in shape.points do s.points[i]=typeof(v)=='Vector3' and turn(v) or v end end
 return s
end
-- A shape's own height (the Hammer's Slam circle: 6) raises the top of its band, so a plain jump
-- doesn't clear it; without one, HEIGHT_ABOVE.
local function band(shape,point)
 local base=(shape.center or shape.origin or shape.pivot or shape.a).Y
 return point.Y>=base-S.HEIGHT_BELOW and point.Y<=base+(shape.height or S.HEIGHT_ABOVE)
end
local function inCapsule(a,b,radius,point)
 local ab=flat(b-a);local ap=flat(point-a);local t=math.clamp(ap:Dot(ab)/math.max(ab:Dot(ab),1e-6),0,1)
 return (ap-ab*t).Magnitude<=radius
end
function S.contains(shape,point)
 if not band(shape,point) then return false end
 local k=shape.kind
 if k=='circle' then return flat(point-shape.center).Magnitude<=shape.radius end
 if k=='line' then
  local d=flat(point-shape.origin);local along=d:Dot(shape.direction)
  return along>=0 and along<=shape.length and (d-shape.direction*along).Magnitude<=shape.width/2
 end
 if k=='cone' then
  local d=flat(point-shape.origin);local dist=d.Magnitude
  return dist<=shape.length and (dist<1e-3 or math.abs(S.yaw(shape.direction,d))<=shape.halfAngle)
 end
 if k=='arc' then
  local d=flat(point-shape.pivot);local dist=d.Magnitude
  if dist<shape.inner or dist>shape.outer then return false end
  local a=S.yaw(shape.forward,d);return a>=shape.from and a<=shape.to
 end
 if k=='capsule' then return inCapsule(shape.a,shape.b,shape.radius,point) end
 -- A bent body like a tail: capsules joint to joint (points[i] to points[i+1], radii[i]).
 if k=='chain' then
  for i=1,#shape.points-1 do
   if inCapsule(shape.points[i],shape.points[i+1],shape.radii[i],point) then return true end
  end
  return false
 end
 return false
end
-- Outline points (world, flat) for a warning renderer: a closed polygon.
function S.outline(shape,n)
 n=n or 32;local pts={}
 local function rot(v,a) return CFrame.Angles(0,a,0):VectorToWorldSpace(v) end
 if shape.kind=='circle' then
  for i=0,n-1 do local a=i/n*math.pi*2;table.insert(pts,shape.center+Vector3.new(math.sin(a),0,math.cos(a))*shape.radius) end
 elseif shape.kind=='line' then
  local side=Vector3.new(-shape.direction.Z,0,shape.direction.X)*shape.width/2;local far=shape.origin+shape.direction*shape.length
  pts={shape.origin+side,far+side,far-side,shape.origin-side}
 elseif shape.kind=='cone' then
  table.insert(pts,shape.origin)
  for i=0,n do local a=-shape.halfAngle+2*shape.halfAngle*i/n;table.insert(pts,shape.origin+rot(shape.direction,a)*shape.length) end
 elseif shape.kind=='arc' then
  for i=0,n do local a=shape.from+(shape.to-shape.from)*i/n;table.insert(pts,shape.pivot+rot(shape.forward,a)*shape.outer) end
  for i=n,0,-1 do local a=shape.from+(shape.to-shape.from)*i/n;table.insert(pts,shape.pivot+rot(shape.forward,a)*shape.inner) end
 end
 return pts
end
-- A sampled track {{t,x,y,z},...} (MapBossTiming samples) at time t, clamped to its window.
function S.sample(list,t)
 if not list or #list==0 then return nil end
 local lo,hi=1,#list
 if t<=list[1][1] then hi=1 elseif t>=list[hi][1] then lo=hi else
  while hi-lo>1 do local mid=(lo+hi)//2;if list[mid][1]<=t then lo=mid else hi=mid end end
 end
 local a,b=list[lo],list[hi];local f=b[1]>a[1] and (t-a[1])/(b[1]-a[1]) or 0
 return Vector3.new(a[2],a[3],a[4]):Lerp(Vector3.new(b[2],b[3],b[4]),f)
end
-- Boss projectile path: level flight along a world yaw (0 = -Z), easing from its release
-- point to hit height over the first 0.25 s so a high muzzle can still reach a player.
function S.shot(origin,yaw,speed,height,t)
 local d=CFrame.Angles(0,yaw,0).LookVector;local p=origin+d*speed*t;local k=1-math.clamp(t/.25,0,1)
 return Vector3.new(p.X,height+(origin.Y-height)*k*k,p.Z),d
end
-- MapBossShotEnds is {serial,ends}: when the server stopped each shot of one attack's volley, keyed
-- by shot index. The client launches on its own clock and can read the attribute before the new
-- volley's reset arrives, so ends carrying another attack's serial are stale and stop nothing.
function S.shotEnds(t,serial) return type(t)=='table' and t.serial==serial and type(t.ends)=='table' and t.ends or nil end
-- Attack timing the server (MapBossService X) and the client (MapBossPresentation P) both read, so
-- the two can't drift. T is MapBossDefs.timing: scaled and rate-adjusted (real seconds).
-- An attack's window: its clip's timing, or a lane's (the crab's rush, the Hammer's charge): the start
-- clip, travel at `speed` for `length` (default def.length), the end clip, both clips at def.rate.
-- nil without both clips' timing.
function S.window(def,T,length)
 if def.clips then
  local c=T.clips or {};local rate=def.rate or 1;local rs,re=c[def.clips[1]],c[def.clips[3]];if not rs or not re then return nil end
  rs,re=rs/rate,re/rate;local move=(length or def.length)/def.speed
  return {warnStart=0,impact=rs,activeEnd=rs+move,recoveryEnd=rs+move+re,duration=rs+move+re}
 end
 return T.attacks and T.attacks[def.clip]
end
-- The attack def with a part's fields on top: one combo phase (def.phases[i]) or a lane's finish part.
function S.merged(def,part) local m=table.clone(def);m.phases=nil;m.finish=nil;for k,v in part do m[k]=v end;return m end
-- The Hammer-style charge (a forward lane or a contact run): its length can change as he runs.
function S.isCharge(def) return def.shape=='lane' and (def.facing=='forward' or def.contact~=nil) end
-- A lane's finish hits (def.finish): one part (the old single circle) or a list of parts (the Hammer's
-- slam circle and rubble wave, 2026-10-09). Always a list; nil without a finish.
function S.finishParts(def)
 local f=def.finish;if type(f)~='table' then return nil end
 return f[1]~=nil and f or {f}
end
-- A clip's timing for its hit i (a combo phase, a finish part): the clip's phase i on top of its own
-- times (MapBossTiming phases: the Slam's {circle, wave}). Past the clip's last timed phase, that last
-- phase's times ("the same timing as the slam circle": a clip baked without the wave phase still
-- slams); a clip without phases, its own times (the old circle). Cached per clip timing; read only.
local partWindows=setmetatable({},{__mode='k'})
function S.partWindow(fa,i)
 local list=fa.phases;local ph=list and (list[i] or list[#list]);if not ph then return fa end
 local cache=partWindows[fa];if not cache then cache={};partWindows[fa]=cache end
 if cache[ph] then return cache[ph] end
 local w=table.clone(fa);w.phases=nil;for k,v in ph do w[k]=v end
 cache[ph]=w;return w
end
-- A clip's first hit: its impact, else its first phase's (a combo clip may carry only phase times).
function S.impactOf(at) return at.impact or (at.phases and at.phases[1] and at.phases[1].impact) end
-- When one hit is over on its clip's clock: its impact, or for a wave (def.travel) the front reaching
-- its far end, impact + length / travel (MapBossService X.waveHit).
function S.hitEnd(def,at)
 local impact=S.impactOf(at) or 0
 if def.shape=='wave' and def.travel then return impact+def.length/def.travel end
 return impact
end
-- A lane's times for `length`: {at (S.window), duration (its recovery; with a finish, until just past
-- the finish's impact), finishAt (the end clip's timing), finishStart (where the run ends) and
-- finishImpact (both on the attack clock)}. The finish fields only with def.finish and its timing.
-- nil without the window. A finish wave's front runs on after the attack on its own clock
-- (MapBossService s.waves), so it doesn't hold the attack open.
function S.laneTimes(def,T,length)
 local at=S.window(def,T,length);if not at then return nil end
 local t={at=at,duration=at.recoveryEnd or at.duration}
 local fa=def.finish and def.clips and T.attacks and T.attacks[def.clips[3]]
 if fa then
  -- finishImpact: the first part's (the slam circle's) impact, from its phase when the clip has phases.
  t.finishAt,t.finishStart=fa,at.activeEnd;t.finishImpact=t.finishStart+S.impactOf(S.partWindow(fa,1));t.duration=math.max(t.duration,t.finishImpact+.05)
  -- A finish list: every part lands before the attack ends (each part's own phase impact).
  if def.finish[1]~=nil then
   for i in def.finish do t.duration=math.max(t.duration,t.finishStart+S.impactOf(S.partWindow(fa,i))+.05) end
  end
 end
 return t
end
-- JSON-safe copies for the MapBossAttackData attribute (Vector3 <-> {x,y,z}).
local VEC={center=true,origin=true,pivot=true,direction=true,forward=true,a=true,b=true}
function S.encode(shape) local t={};for k,v in shape do t[k]=typeof(v)=='Vector3' and {v.X,v.Y,v.Z} or v end;return t end
function S.decode(t) local s={};for k,v in t do s[k]=VEC[k] and type(v)=='table' and Vector3.new(v[1],v[2],v[3]) or v end;return s end
-- An expanding ground ring (round 10: the DJ Crab's Claw Slam). Its front leaves `center` at the
-- attack's impact at radius `inner` and runs out at `travel` studs/s to `outer`; it is `width` thick
-- and hits players its front passes, except inside the `gaps` (yaws, CFrame.Angles convention, 0 =
-- -Z) `gap` radians either side, which never hit: the way through. Only the front hits, never the
-- filled inside (a player it already passed is safe). Example: inner 3, outer 34, travel 26 -> the
-- front reaches a player 16 studs out 0.5 s after impact, and is gone 1.19 s after it.
function S.ringRadius(ring,t) return ring.inner+ring.travel*math.max(0,t) end
function S.ringEnd(ring) return (ring.outer-ring.inner)/ring.travel end
function S.inGap(ring,point)
 local d=flat(point-ring.center);if d.Magnitude<1e-3 then return false end
 local yaw=S.yaw(Vector3.new(0,0,-1),d)
 for _,g in ring.gaps or {} do if math.abs(S.wrap(yaw-g))<=ring.gap then return true end end
 return false
end
-- True when the front crossed `point` between t0 and t1 seconds after impact (clamped to its travel),
-- inside the height band, outside every gap.
function S.ringHit(ring,point,t0,t1)
 local stop=S.ringEnd(ring);t0,t1=math.max(0,t0),math.min(t1,stop);if t1<t0 then return false end
 if point.Y<ring.center.Y-S.HEIGHT_BELOW or point.Y>ring.center.Y+(ring.height or S.HEIGHT_ABOVE) then return false end
 local d=flat(point-ring.center).Magnitude;local half=ring.width/2
 if d<S.ringRadius(ring,t0)-half or d>S.ringRadius(ring,t1)+half then return false end
 return not S.inGap(ring,point)
end
-- The ring's warning as arcs (Shapes.contains 'arc'), one per solid stretch between the gaps.
function S.ringArcs(ring)
 local gaps=table.clone(ring.gaps or {});table.sort(gaps,function(a,b) return S.wrap(a)<S.wrap(b) end)
 local forward=Vector3.new(0,0,-1);local arcs={}
 if #gaps==0 then return {{kind='arc',pivot=ring.center,forward=forward,from=-math.pi,to=math.pi,inner=ring.inner,outer=ring.outer}} end
 for i,g in gaps do
  local a=S.wrap(g)+ring.gap;local b=S.wrap(gaps[i%#gaps+1])-ring.gap
  if i==#gaps then b+=2*math.pi end
  if b>a then
   local mid=(a+b)/2;local half=(b-a)/2
   table.insert(arcs,{kind='arc',pivot=ring.center,forward=CFrame.Angles(0,mid,0):VectorToWorldSpace(forward),from=-half,to=half,inner=ring.inner,outer=ring.outer})
  end
 end
 return arcs
end
function S.encodeRing(ring) local t=table.clone(ring);t.center={ring.center.X,ring.center.Y,ring.center.Z};return t end
function S.decodeRing(t) if type(t)~='table' or type(t.center)~='table' then return nil end;local r=table.clone(t);r.center=Vector3.new(t.center[1],t.center[2],t.center[3]);return r end
return S
