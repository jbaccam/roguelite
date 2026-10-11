local M={}
-- Three distinct fuel pulses, then a mandatory quiet interval even at high attack speed.
-- Concentrate the old sustained DPS into the burst rather than silently nerfing the weapon.
function M.duckTiming(cooldown)
 local cd=math.max(.03,cooldown)
 local cycle=math.max(.78,cd*3)
 return {pulses=3,spacing=.12,emission=.11,cycle=cycle,damageScale=cycle/(3*cd)}
end
M.profiles={
 ['12']={height=.7,spin='flat',returns=true},
 ['13']={height=0,spin='point'},
 ['14']={height=3,spin='tumble',zone='Fire'},
 ['15']={height=3,spin='tumble',reserve=true},
 ['22']={height=0,spin='roll'},
 ['23']={height=2,spin='tumble',reserve=true},
 ['31']={height=0,spin='rock',returns=true},
 ['08']={height=0,spin='cloud',zone='Poison'},
 -- Poseidon's Trident: thrown point-first and spinning, flies back; its landing raises the tidal wave.
 ['37']={height=.6,spin='spear',returns=true,wave=true},
}
-- Molotov fire (2026-10-10 play-test: "Molotovs are kinda shit. Increase radius ... an initial bigger
-- AoE that gets smaller"). base = the old flat radius (4.5 x Area Size, clamped 2-12). The fire starts
-- at start x base, holds `hold` s, then eases (smoothstep) to finish x base at the end of its life.
-- Server ticks (SpecialWeapons) and the client pool (ThrownVisuals.fireZone) both read zoneRadius, so
-- what burns is what you see. Every `tick` s it hits for `factor` of the throw's damage (was .4); the
-- first tick, the ignition, hits for `ignite` across the full start radius. cap: fires per player and
-- weapon id at once (was 3: at Tier IV, 4 s / 1.21 s = 3.3 fires were alive, so the 4th was cut).
-- Example, no Area Size: 7.2 studs for 0.4 s, 5.4 at 2.2 s, 3.6 at 4 s (old: 4.5 the whole 4 s).
-- Poison clouds (Fart Gun) keep a flat radius, .4 ticks and a cap of 3 (M.Poison).
M.Fire={base=4.5,start=1.6,finish=.8,hold=.4,duration=4,tick=.4,factor=.45,ignite=1,cap=4,maxRadius=16}
M.Poison={base=5.5,start=1,finish=1,hold=0,duration=5,tick=.4,factor=.4,ignite=.4,cap=3,maxRadius=12}
-- Start and end radius for a zone kind at an Area Size multiplier (CharacterStats.mult(AreaSize)).
-- Example: fireRadii(1) = 7.2, 3.6; fireRadii(1.5) = 10.8, 5.4.
function M.zoneRadii(kind,areaMult)
 local z=kind=='Fire' and M.Fire or M.Poison
 local base=math.clamp(z.base*(tonumber(areaMult) or 1),2,12)
 return math.min(base*z.start,z.maxRadius),base*z.finish
end
function M.fireRadii(areaMult) return M.zoneRadii('Fire',areaMult) end
-- The hold before shrinking, for a zone that lives `duration` s (never more than a quarter of it).
function M.zoneHold(kind,duration)
 local z=kind=='Fire' and M.Fire or M.Poison
 return math.min(z.hold,math.max(0,tonumber(duration) or 0)*.25)
end
-- Radius `age` s into a zone's life: r0 until `hold`, then smoothstep to r1 at `duration`.
-- Example: zoneRadius(7.2,3.6,2.2,4,.4) = 5.4.
function M.zoneRadius(r0,r1,age,duration,hold)
 r1=r1 or r0;hold=hold or 0
 local span=math.max(1e-3,(duration or 0)-hold)
 local t=math.clamp(((age or 0)-hold)/span,0,1)
 return r0+(r1-r0)*t*t*(3-2*t)
end
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
