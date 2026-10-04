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
-- Crystal colour per player (user, 2026-10-03: "different color crystals for diff people who
-- killed"). A kill's crystal is its killer's to take (ShardDropService owner), so with 2+ players in
-- the run it wears the killer's colour: ShardDropService gives each player a CrystalSlot (the lowest
-- free number on the server) and slot n wears colour n, wrapping after 4. Slot 1 is today's blue,
-- and solo runs stay all blue. Blue / orange / pink / yellow (after the Okabe-Ito colour-blind set)
-- stand apart and read on grass and sand; none is red, the heart pickup's colour. Public crystals
-- (anyone's to take) are white. dark/light: the crystal's deep and pale facets; glow: its light,
-- aura and pickup burst; mark: the HUD and over-head diamonds (ShardVisuals, RogueliteUI).
M.CRYSTAL_COLORS={
 {name='Blue',dark=Color3.fromRGB(19,92,186),light=Color3.fromRGB(135,217,242),glow=Color3.fromRGB(100,210,255),mark=Color3.fromRGB(70,175,255)},
 {name='Orange',dark=Color3.fromRGB(205,90,10),light=Color3.fromRGB(255,200,115),glow=Color3.fromRGB(255,165,60),mark=Color3.fromRGB(255,150,40)},
 {name='Pink',dark=Color3.fromRGB(196,70,150),light=Color3.fromRGB(255,180,225),glow=Color3.fromRGB(255,130,210),mark=Color3.fromRGB(240,110,195)},
 {name='Yellow',dark=Color3.fromRGB(190,155,0),light=Color3.fromRGB(255,242,135),glow=Color3.fromRGB(255,228,80),mark=Color3.fromRGB(255,220,50)},
}
M.PUBLIC_COLOR={name='White',dark=Color3.fromRGB(150,162,176),light=Color3.fromRGB(250,252,255),glow=Color3.fromRGB(225,235,250),mark=Color3.fromRGB(235,240,245)}
-- Which colour a CrystalSlot wears: 1-4, then round again (5 -> 1; only Studio has 5+ players).
function M.colorIndex(slot)
 local n=math.max(1,math.floor(tonumber(slot) or 1))
 return (n-1)%#M.CRYSTAL_COLORS+1
end
function M.slotColor(slot) return M.CRYSTAL_COLORS[M.colorIndex(slot)] end
return M
