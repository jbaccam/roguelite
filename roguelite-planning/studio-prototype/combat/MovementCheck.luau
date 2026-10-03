-- Server movement check for run members (launch audit C1): speed, flying and arena bounds. Pure
-- logic over position samples; MovementGuard.server.luau feeds it and moves cheaters back to their
-- last safe spot. Limits are generous on purpose: a false snap-back on a real player is worse than
-- a slow cheat slipping by, so only blatant speed, hovering or leaving the arena trips it.
-- Example: MoveSpeed 24 -> up to 24 x 1.5 + 16 = 52 studs in any 1 s window (a 2x speed hack is
-- 48, so it passes; the usual 100+ studs/s ones don't). Normal top speed is 40 x 1.6 in the air
-- (MovementGuard passes speed with CharacterStats' air multiplier already in it).
local M={
 WINDOW=1, -- seconds of movement each speed test covers
 SPEED_SLACK=1.5, -- x the player's own move speed (lag bursts, the air bonus, boss knockback)
 EXTRA=16, -- studs on top of that per window
 STRIKES=4, -- speed tests in a row (0.1 s apart) over the limit before a snap-back
 TELEPORT=120, -- studs between two samples: snapped back at once
 FLY_GAP=16, -- studs above the ground (a jump peaks near 9.5)
 FLY_SECONDS=2.5, -- that high, and not falling, for this long
 FALLING=-10, -- studs/s down: falling off a ledge never counts as flying
 OUTSIDE_SECONDS=1, -- outside the arena walls for this long
 SAFE_GAP=6, -- standing (ground within this) is a safe spot to go back to
}
function M.new(position,t) local s={snaps=0};M.reset(s,position,t);return s end
-- A fresh start at `position`: a new body, or the server moved it (a revive, a respawn, a snap-back).
function M.reset(s,position,t)
 s.samples={{t=t,position=position,ok=true}};s.strikes=0;s.airSince=nil;s.outSince=nil;s.safe=position
end
local function flat(a,b) return Vector3.new(a.X-b.X,0,a.Z-b.Z).Magnitude end
-- One sample. speed: the player's own top speed (studs/s); gap: studs down to the ground (math.huge
-- over nothing); vy: vertical speed; inside: within the arena's walls. Returns nil, or why the
-- player should go back to s.safe: 'teleport', 'speed', 'fly' or 'bounds'.
function M.step(s,t,position,speed,gap,vy,inside)
 local samples=s.samples
 local previous=samples[#samples]
 table.insert(samples,{t=t,position=position,ok=gap<=M.SAFE_GAP and inside})
 -- Keep the newest sample that is at least WINDOW old as the start of the window.
 while #samples>2 and t-samples[2].t>=M.WINDOW do table.remove(samples,1) end
 if previous and flat(position,previous.position)>M.TELEPORT then return 'teleport' end
 local first=samples[1];local dt=math.max(t-first.t,.05)
 if flat(position,first.position)>(speed or 16)*M.SPEED_SLACK*dt+M.EXTRA then s.strikes+=1 else s.strikes=0 end
 if s.strikes>=M.STRIKES then return 'speed' end
 if gap>M.FLY_GAP and vy>M.FALLING then s.airSince=s.airSince or t else s.airSince=nil end
 if s.airSince and t-s.airSince>=M.FLY_SECONDS then return 'fly' end
 if inside then s.outSince=nil else s.outSince=s.outSince or t end
 if s.outSince and t-s.outSince>=M.OUTSIDE_SECONDS then return 'bounds' end
 -- The safe spot is the window's start, once the whole second after it has passed clean: a speed
 -- hack's first 0.3 s still looks fine, so the newest position can't be trusted yet.
 if s.strikes==0 and not s.airSince and not s.outSince and first.ok then s.safe=first.position end
 return nil
end
-- The arena's walls as an XZ box with a margin: {minX,maxX,minZ,maxZ}. parts: the wall parts.
function M.bounds(parts,margin)
 local box
 for _,part in parts do
  local cf,size=part.CFrame,part.Size
  local hx=math.abs(cf.RightVector.X)*size.X/2+math.abs(cf.UpVector.X)*size.Y/2+math.abs(cf.LookVector.X)*size.Z/2
  local hz=math.abs(cf.RightVector.Z)*size.X/2+math.abs(cf.UpVector.Z)*size.Y/2+math.abs(cf.LookVector.Z)*size.Z/2
  local p=cf.Position
  if not box then box={p.X-hx,p.X+hx,p.Z-hz,p.Z+hz}
  else box={math.min(box[1],p.X-hx),math.max(box[2],p.X+hx),math.min(box[3],p.Z-hz),math.max(box[4],p.Z+hz)} end
 end
 if not box then return nil end
 margin=margin or 0
 return {box[1]-margin,box[2]+margin,box[3]-margin,box[4]+margin}
end
function M.inside(box,position) return box==nil or (position.X>=box[1] and position.X<=box[2] and position.Z>=box[3] and position.Z<=box[4]) end
return M
