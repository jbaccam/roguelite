local M={}
M.profiles={
 ['12']={height=.7,spin='flat',returns=true},
 ['13']={height=0,spin='point'},
 ['14']={height=5,spin='tumble',zone='Fire'},
 ['15']={height=3,spin='tumble',reserve=true},
 ['22']={height=0,spin='roll'},
 ['23']={height=5,spin='tumble',reserve=true},
 ['31']={height=0,spin='rock',returns=true},
 ['08']={height=.4,spin='cloud',zone='Poison'},
 -- Poseidon's Trident: thrown point-first and spinning, flies back; its landing raises the tidal wave.
 ['37']={height=.6,spin='spear',returns=true,wave=true},
}
function M.position(origin,finish,t,height)
 return origin:Lerp(finish,t)+Vector3.yAxis*(4*height*t*(1-t))
end
function M.duration(origin,finish,speed)
 return math.clamp((finish-origin).Magnitude/math.max(8,speed),.16,2.5)
end
function M.rotation(id,age,direction)
 if direction.Magnitude<.001 then direction=-Vector3.zAxis end
 local cf=CFrame.lookAt(Vector3.zero,direction)
 local p=M.profiles[id]
 if p.spin=='rock' then
  -- Small bounded pitch/bank, never an accumulating tumble. Age stays
  -- continuous across outbound/return segments and the caller locks heading.
  local blend=1-math.exp(-math.max(0,age)*12)
  return cf*CFrame.Angles(math.rad(9)*math.sin(age*9)*blend,math.rad(5)*math.sin(age*6)*blend,math.rad(7)*math.sin(age*11)*blend)*CFrame.Angles(-math.pi/2,0,0)
 end
 if p.spin=='point' then return cf*CFrame.Angles(-math.pi/2,0,0) end
 if p.spin=='spear' then return cf*CFrame.Angles(-math.pi/2,0,0)*CFrame.Angles(0,age*14,0) end
 if p.spin=='flat' then return cf*CFrame.Angles(math.pi/2,0,age*18) end
 return cf*CFrame.Angles(age*(id=='23' and 9 or 13),0,0)
end
return M
