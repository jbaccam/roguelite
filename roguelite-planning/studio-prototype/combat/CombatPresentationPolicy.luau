-- Pure client presentation rules. No damage, targeting, remotes or saved state.
local P={HeadlineDistance=140}
function P.ownsCue(ownerId,viewerId,preview)
 return preview==true or (type(ownerId)=='number' and type(viewerId)=='number' and ownerId==viewerId)
end
-- Perspective-aware text, with the same screen-space cap for owner and spectator.
-- Pop motion is included BEFORE the cap: no child UIScale can blow past it.
function P.headline(viewport,depth,verticalFov,nominal,age)
 local scale=math.clamp(math.min(viewport.X,viewport.Y)/900,.25,1.35)
 local cap=math.min(nominal or 44,48)*scale
 local visible=viewport.X>0 and viewport.Y>0 and depth>0 and depth<=P.HeadlineDistance
 local projection=viewport.Y/(2*math.max(depth,1)*math.tan(math.rad(math.clamp(verticalFov,1,120))*.5))
 local pop=age<.13 and (.78+.3*math.clamp(age/.13,0,1)) or (1+.08*(1-math.clamp((age-.13)/.15,0,1)))
 local pixels=math.min(cap,projection*((nominal or 44)/24)*pop)
 return {
  visible=visible and pixels>=8,
  text=math.max(1,math.floor(pixels)),
  width=math.min(360*scale,viewport.X*.46),
  height=math.max(1,pixels*1.6+6*scale),
  stroke=math.clamp(pixels*.075,.6,3*scale),
 }
end
return P
