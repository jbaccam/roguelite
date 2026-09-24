local M={REST_SECONDS=.3,PULL_SECONDS=.42,BOB_HEIGHT=.16}
function M.idle(origin,born,now)
 return origin+Vector3.new(0,math.sin((now-born)*2.7+born%6.28)*M.BOB_HEIGHT,0)
end
function M.rotation(born,now)
 local age=now-born
 return CFrame.Angles(math.sin(age*2.7)*math.rad(3),age*.65+born%6.28,math.sin(age*1.35)*math.rad(2))
end
function M.pull(origin,target,elapsed)
 local t=math.clamp(elapsed/M.PULL_SECONDS,0,1)
 return origin:Lerp(target,t*t)
end
return M
