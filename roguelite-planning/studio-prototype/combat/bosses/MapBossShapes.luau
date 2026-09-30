-- Shared boss hit and warning geometry. The server's hit tests and the client's ground
-- warnings read the same shape tables, so a warning is exactly where damage lands.
-- Shapes are flat on the ground; `contains` also requires the point within a height band.
local S={}
S.HEIGHT_BELOW,S.HEIGHT_ABOVE=2,5.5 -- players jumping over a low wave clear it
local function flat(v) return Vector3.new(v.X,0,v.Z) end
S.flat=flat
-- Signed yaw from a to b about +Y; positive turns toward -X for a -Z forward (CFrame.Angles).
function S.yaw(a,b) a,b=flat(a),flat(b);return math.atan2(a:Cross(b).Y,a:Dot(b)) end
local function band(shape,point)
 local base=(shape.center or shape.origin or shape.pivot or shape.a).Y
 return point.Y>=base-S.HEIGHT_BELOW and point.Y<=base+S.HEIGHT_ABOVE
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
 if k=='capsule' then
  local ab=flat(shape.b-shape.a);local ap=flat(point-shape.a);local t=math.clamp(ap:Dot(ab)/math.max(ab:Dot(ab),1e-6),0,1)
  return (ap-ab*t).Magnitude<=shape.radius
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
-- JSON-safe copies for the MapBossAttackData attribute (Vector3 <-> {x,y,z}).
local VEC={center=true,origin=true,pivot=true,direction=true,forward=true,a=true,b=true}
function S.encode(shape) local t={};for k,v in shape do t[k]=typeof(v)=='Vector3' and {v.X,v.Y,v.Z} or v end;return t end
function S.decode(t) local s={};for k,v in t do s[k]=VEC[k] and type(v)=='table' and Vector3.new(v[1],v[2],v[3]) or v end;return s end
return S
