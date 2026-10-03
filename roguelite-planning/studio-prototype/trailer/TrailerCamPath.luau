-- Smooth camera paths for TrailerCam (TRAILER_CAM.md). Pure math, no services, so it can be
-- tested with loadstring in Edit. A path is a list of keys {cf=CFrame, fov=number}.
-- Positions follow a centripetal Catmull-Rom curve through every key, rotations a Catmull-Rom
-- on quaternions (renormalised), FOV a Catmull-Rom on the number. Time is spread by arc length,
-- so the camera moves at an even speed, and the whole move eases in and out.
local P={}

local function lerp(a,b,t) return a+(b-a)*t end

-- Ease in and out with zero speed and zero acceleration at both ends.
function P.smoother(t)
 t=math.clamp(t,0,1)
 return t*t*t*(t*(t*6-15)+10)
end

-- Blend between linear (0) and smoother (1): 1 gives the slow start and stop a dolly move needs,
-- lower values keep more of the middle speed for long paths.
function P.ease(t,amount)
 return lerp(t,P.smoother(t),math.clamp(amount or 1,0,1))
end

-- Centripetal Catmull-Rom (alpha 0.5): no loops or overshoot when keys are unevenly spaced.
local function knot(ti,a,b)
 local d=(b-a).Magnitude
 return ti+math.max(d,1e-4)^.5
end
function P.catmull(p0,p1,p2,p3,t)
 local t0=0
 local t1=knot(t0,p0,p1)
 local t2=knot(t1,p1,p2)
 local t3=knot(t2,p2,p3)
 local u=lerp(t1,t2,t)
 local a1=p0*((t1-u)/(t1-t0))+p1*((u-t0)/(t1-t0))
 local a2=p1*((t2-u)/(t2-t1))+p2*((u-t1)/(t2-t1))
 local a3=p2*((t3-u)/(t3-t2))+p3*((u-t2)/(t3-t2))
 local b1=a1*((t2-u)/(t2-t0))+a2*((u-t0)/(t2-t0))
 local b2=a2*((t3-u)/(t3-t1))+a3*((u-t1)/(t3-t1))
 return b1*((t2-u)/(t2-t1))+b2*((u-t1)/(t2-t1))
end

-- Uniform Catmull-Rom on plain numbers (FOV) and on 4-vectors (quaternions).
local function cr(a,b,c,d,t)
 local t2,t3=t*t,t*t*t
 return .5*((2*b)+(-a+c)*t+(2*a-5*b+4*c-d)*t2+(-a+3*b-3*c+d)*t3)
end

-- CFrame rotation <-> quaternion {x,y,z,w}.
function P.quat(cf)
 local _,_,_,m00,m01,m02,m10,m11,m12,m20,m21,m22=cf:GetComponents()
 local tr=m00+m11+m22
 local x,y,z,w
 if tr>0 then
  local s=math.sqrt(tr+1)*2
  w=.25*s;x=(m21-m12)/s;y=(m02-m20)/s;z=(m10-m01)/s
 elseif m00>m11 and m00>m22 then
  local s=math.sqrt(1+m00-m11-m22)*2
  w=(m21-m12)/s;x=.25*s;y=(m01+m10)/s;z=(m02+m20)/s
 elseif m11>m22 then
  local s=math.sqrt(1+m11-m00-m22)*2
  w=(m02-m20)/s;x=(m01+m10)/s;y=.25*s;z=(m12+m21)/s
 else
  local s=math.sqrt(1+m22-m00-m11)*2
  w=(m10-m01)/s;x=(m02+m20)/s;y=(m12+m21)/s;z=.25*s
 end
 return {x,y,z,w}
end
local function qdot(a,b) return a[1]*b[1]+a[2]*b[2]+a[3]*b[3]+a[4]*b[4] end
local function qneg(a) return {-a[1],-a[2],-a[3],-a[4]} end
local function qnorm(a)
 local m=math.sqrt(qdot(a,a))
 if m<1e-9 then return {0,0,0,1} end
 return {a[1]/m,a[2]/m,a[3]/m,a[4]/m}
end

-- Builds the sampled path. Returns nil for fewer than 2 keys.
-- samples: points per segment for the arc-length table (more = more even speed).
function P.build(keys,samples)
 local n=#keys
 if n<2 then return nil end
 samples=samples or 48
 local pos,rot,fov={},{},{}
 for i,k in keys do
  pos[i]=k.cf.Position
  local q=P.quat(k.cf)
  -- Keep every quaternion in the same hemisphere as the one before, or the camera spins the
  -- long way round.
  if i>1 and qdot(q,rot[i-1])<0 then q=qneg(q) end
  rot[i]=q
  fov[i]=k.fov or 70
 end
 -- Phantom end points mirror the first and last segments so the curve starts and ends on a key.
 local function at(list,i,mirror)
  if i<1 then return mirror(list[1],list[2]) end
  if i>n then return mirror(list[n],list[n-1]) end
  return list[i]
 end
 local function vmirror(a,b) return a*2-b end
 local function nmirror(a,b) return a*2-b end
 local function qmirror(a,b) return {a[1]*2-b[1],a[2]*2-b[2],a[3]*2-b[3],a[4]*2-b[4]} end

 local path={n=n,segments={},length=0}
 for s=1,n-1 do
  local p0,p1,p2,p3=at(pos,s-1,vmirror),pos[s],pos[s+1],at(pos,s+2,vmirror)
  local q0,q1,q2,q3=at(rot,s-1,qmirror),rot[s],rot[s+1],at(rot,s+2,qmirror)
  local f0,f1,f2,f3=at(fov,s-1,nmirror),fov[s],fov[s+1],at(fov,s+2,nmirror)
  -- Coincident keys (a pan from one spot) would divide by zero in the centripetal knots.
  local still=(p2-p1).Magnitude<1e-3
  local seg={p0=p0,p1=p1,p2=p2,p3=p3,q={q0,q1,q2,q3},f={f0,f1,f2,f3},still=still,table={0},length=0}
  local prev=p1
  for j=1,samples do
   local t=j/samples
   local p=still and p1 or P.catmull(p0,p1,p2,p3,t)
   seg.length+=(p-prev).Magnitude;prev=p
   seg.table[j+1]=seg.length
  end
  path.segments[s]=seg
  path.length+=seg.length
 end
 -- Segments get time by length, but every segment gets at least a share, so a pan in place
 -- (no length) still takes time to turn.
 local total=0
 for _,seg in path.segments do
  seg.weight=math.max(seg.length,path.length*.15/(n-1),1e-3)
  total+=seg.weight
 end
 local acc=0
 for _,seg in path.segments do
  seg.from=acc/total;acc+=seg.weight;seg.to=acc/total
 end
 path.samples=samples
 return path
end

-- Within one segment: turn a 0..1 share of its length into the curve parameter t.
local function tForLength(seg,share,samples)
 if seg.still or seg.length<1e-6 then return share end
 local want=share*seg.length
 local tbl=seg.table
 local lo,hi=1,#tbl
 while hi-lo>1 do
  local mid=(lo+hi)//2
  if tbl[mid]<want then lo=mid else hi=mid end
 end
 local a,b=tbl[lo],tbl[hi]
 local f=b>a and (want-a)/(b-a) or 0
 return ((lo-1)+f)/samples
end

-- Pose at overall progress u in 0..1 (already eased by the caller, or pass ease amount).
function P.sample(path,u)
 u=math.clamp(u,0,1)
 local segs=path.segments
 local seg=segs[#segs]
 for _,s in segs do if u<=s.to then seg=s;break end end
 local share=(seg.to>seg.from) and (u-seg.from)/(seg.to-seg.from) or 1
 local t=tForLength(seg,math.clamp(share,0,1),path.samples)
 local p=seg.still and seg.p1 or P.catmull(seg.p0,seg.p1,seg.p2,seg.p3,t)
 local q0,q1,q2,q3=seg.q[1],seg.q[2],seg.q[3],seg.q[4]
 local q=qnorm({cr(q0[1],q1[1],q2[1],q3[1],t),cr(q0[2],q1[2],q2[2],q3[2],t),
  cr(q0[3],q1[3],q2[3],q3[3],t),cr(q0[4],q1[4],q2[4],q3[4],t)})
 local f=seg.f
 local fov=math.clamp(cr(f[1],f[2],f[3],f[4],t),5,110)
 return CFrame.new(p.X,p.Y,p.Z,q[1],q[2],q[3],q[4]),fov
end

-- Exponential smoothing factor for a rate per second, frame-rate independent.
function P.alpha(rate,dt) return 1-math.exp(-rate*dt) end

-- Orbit pose: centre, radius, height above centre, angle in radians. Looks at the centre.
function P.orbit(centre,radius,height,angle)
 local eye=centre+Vector3.new(math.cos(angle)*radius,height,math.sin(angle)*radius)
 return CFrame.lookAt(eye,centre)
end

return P
