-- Cosmetic contact between one player's floating weapons. Each model is a
-- capsule built from its reviewed BoundsSize/BoundsCenter; overlapping
-- capsules are pushed apart so weapons may touch but never pass through each
-- other. Server hit poses are untouched.
local S={}
S.RadiusScale=.82 -- slightly inside the box so neighbours visibly touch
S.Iterations=4
S.MaxOffset=3.2
S.AttackMass=6 -- a swinging weapon shoves idle ones instead of yielding

-- Capsule in the model's pivot space: segment along the longest box axis.
function S.capsule(size,center)
 center=center or Vector3.zero
 local axis,length,a,b
 if size.X>=size.Y and size.X>=size.Z then axis,length,a,b=Vector3.xAxis,size.X,size.Y,size.Z
 elseif size.Y>=size.Z then axis,length,a,b=Vector3.yAxis,size.Y,size.X,size.Z
 else axis,length,a,b=Vector3.zAxis,size.Z,size.X,size.Y end
 local radius=math.max(a,b)*.5*S.RadiusScale
 local half=math.max(0,length*.5-radius)
 return {a=center-axis*half,b=center+axis*half,r=math.max(.15,radius)}
end

-- Closest points between segments p1-q1 and p2-q2 (Ericson, RTCD 5.1.9).
function S.closest(p1,q1,p2,q2)
 local d1,d2=q1-p1,q2-p2
 local r=p1-p2
 local a,e=d1:Dot(d1),d2:Dot(d2)
 local f=d2:Dot(r)
 local s,t
 if a<=1e-9 and e<=1e-9 then return p1,p2 end
 if a<=1e-9 then s=0;t=math.clamp(f/e,0,1)
 else
  local c=d1:Dot(r)
  if e<=1e-9 then t=0;s=math.clamp(-c/a,0,1)
  else
   local b=d1:Dot(d2);local denom=a*e-b*b
   s=denom>1e-9 and math.clamp((b*f-c*e)/denom,0,1) or 0
   t=(b*s+f)/e
   if t<0 then t=0;s=math.clamp(-c/a,0,1)
   elseif t>1 then t=1;s=math.clamp((b-c)/a,0,1) end
  end
 end
 return p1+d1*s,p2+d2*t
end

-- bodies: array of {a=Vector3,b=Vector3,r=number,mass=number,center=Vector3?}
-- in world space. Returns world translation offsets, one per body.
function S.solve(bodies,iterations)
 local offsets={}
 for i=1,#bodies do offsets[i]=Vector3.zero end
 for _=1,iterations or S.Iterations do
  local moved=false
  for i=1,#bodies-1 do
   local bi=bodies[i]
   for j=i+1,#bodies do
    local bj=bodies[j]
    local oi,oj=offsets[i],offsets[j]
    local ci,cj=S.closest(bi.a+oi,bi.b+oi,bj.a+oj,bj.b+oj)
    local delta=cj-ci;local distance=delta.Magnitude
    local depth=bi.r+bj.r-distance
    if depth>.001 then
     local normal
     if distance>1e-4 then normal=delta/distance
     else
      -- Coincident axes: separate horizontally along the centers, then +X.
      local centers=((bj.a+bj.b)-(bi.a+bi.b))*.5
      centers=Vector3.new(centers.X,0,centers.Z)
      normal=centers.Magnitude>1e-4 and centers.Unit or Vector3.xAxis
     end
     -- Prefer sideways separation; floating weapons read better side by side.
     normal=Vector3.new(normal.X,normal.Y*.6,normal.Z)
     normal=normal.Magnitude>1e-4 and normal.Unit or Vector3.xAxis
     local mi,mj=bi.mass or 1,bj.mass or 1
     local share=mj/(mi+mj)
     offsets[i]=oi-normal*depth*share
     offsets[j]=oj+normal*depth*(1-share)
     moved=true
    end
   end
  end
  if not moved then break end
 end
 for i,o in offsets do
  if o.Magnitude>S.MaxOffset then offsets[i]=o.Unit*S.MaxOffset end
 end
 return offsets
end

-- Per-visual smoothing: separate quickly, relax slowly, so contact never
-- visibly interpenetrates but released weapons drift home without snapping.
function S.smooth(current,target,dt)
 current=current or Vector3.zero
 -- A fast sword sweep moves ~2 studs per frame, so any lag on the push shows
 -- as clipping. Push out immediately; only the return home is eased.
 local relaxed=current:Lerp(target,1-math.exp(-9*math.clamp(dt,0,.1)))
 local pushing=target.Magnitude>1e-4 and (target-relaxed):Dot(target.Unit)>0
 return pushing and target or relaxed
end
return S
