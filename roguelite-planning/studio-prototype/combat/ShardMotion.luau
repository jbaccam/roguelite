local M={REST_SECONDS=.3,PULL_SECONDS=.42,BOB_HEIGHT=.16}
function M.idle(origin,born,now)
 return origin+Vector3.new(0,math.sin((now-born)*2.7+born%6.28)*M.BOB_HEIGHT,0)
end
function M.rotation(born,now)
 local age=now-born
 return CFrame.Angles(math.sin(age*2.7)*math.rad(3),age*.65+born%6.28,math.sin(age*1.35)*math.rad(2))
end
-- A boss crystal bursting out of him (ShardDropService BurstFrom): `age` seconds after its delay
-- it flies from `from` to its spot `to` on an arc over BURST seconds, then hops once as it lands.
-- Returns its position (inside the boss before it leaves), or nil once it has landed.
M.BURST=.55;M.HOP=.28
function M.burst(from,to,age)
 if age<=0 then return from end
 local k=age/M.BURST
 if k<1 then return from:Lerp(to,k)+Vector3.new(0,(4+(to-from).Magnitude*.45)*4*k*(1-k),0) end
 local h=(age-M.BURST)/M.HOP
 if h<1 then return to+Vector3.new(0,1.3*4*h*(1-h),0) end
 return nil
end
function M.pull(origin,target,elapsed)
 local t=math.clamp(elapsed/M.PULL_SECONDS,0,1)
 return origin:Lerp(target,t*t)
end
return M
