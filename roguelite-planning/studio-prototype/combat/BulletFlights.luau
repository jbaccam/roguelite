-- Client flight of server bullets (StatProjectiles, launch audit P1). The server used to send a Shot
-- row for every bullet on every Heartbeat (a 40-stud shot at 110 studs/s was ~22 rows). Now it
-- sends a 'Fly' row for each straight leg (the launch, the leg after a pierce or bounce, a
-- retarget), 'Land' where a leg stops (terminal once the bullet is done) and 'Drop' when it is
-- cancelled. Each leg is flown here at the server's 60 steps a second, and every step is handed to
-- draw(...) with the old per-frame row's 16 arguments, so tracers, styled heads, muzzle flashes and
-- impacts are drawn by the same code as before. Pure: `now` is passed in, so BulletFlightTests
-- runs it with a fake draw.
local F={StepRate=60}
local KINDS={Fly=true,Land=true,Drop=true}
function F.new(draw)
 local bullets,fresh={},{}
 local flights={bullets=bullets}
 -- One step of `step` seconds along the current leg, stopping at its end.
 local function advance(key,b,step,now)
  local left=b.to-b.at;local length=left.Magnitude
  if length<=.01 then return end
  local move=b.speed*step
  local at=move>=length and b.to or b.at+left*(move/length)
  draw(b.at,at,'Ranged',b.id,b.thickness,nil,false,nil,b.ownerId,b.slotIndex,b.first,false,b.shotId,key,b.speed,false)
  b.first=false;b.at=at;b.heard=now;b.stepped=now
 end
 -- A Shot row. Returns false for rows that aren't bullet rows (the caller draws those itself).
 function flights.row(now,origin,finish,kind,id,thickness,_,contact,normal,ownerId,slotIndex,first,mobContact,shotId,key,speed,terminal)
  if not KINDS[kind] then return false end
  if typeof(origin)~='Vector3' or key==nil then return true end
  local b=bullets[key]
  if kind=='Fly' then
   if typeof(finish)~='Vector3' then return true end
   if not b then
    b={id=id,thickness=thickness,ownerId=ownerId,slotIndex=slotIndex,first=first,shotId=shotId,speed=speed or 110,born=now,at=origin}
    bullets[key]=b;fresh[key]=b
   elseif not b.parked and (origin-b.at).Magnitude>.01 then
    -- A retarget turns it where the server has it: join the drawn path to that point.
    draw(b.at,origin,'Ranged',b.id,b.thickness,nil,false,nil,b.ownerId,b.slotIndex,b.first,false,b.shotId,key,b.speed,false)
    b.first=false
   end
   -- After a pierce or bounce it continues from the server's point (.05 past the contact).
   -- The server takes this leg's first step next frame, so this counts as a step here.
   b.at=origin;b.to=finish;b.parked=false;b.heard=now;b.stepped=now
  elseif b then
   if kind=='Land' then
    draw(b.at,origin,'Ranged',b.id,b.thickness,nil,contact,normal,b.ownerId,b.slotIndex,b.first,mobContact,b.shotId,key,b.speed,terminal)
    b.first=false;b.at=origin;b.to=origin;b.parked=true;b.heard=now
   end
   if kind=='Drop' then
    -- Cancellation is still an end-of-flight for a returning visual (the yo-yo). Previously
    -- it lost the server flight without sending the disc its retract transition.
    draw(b.at,origin,'Ranged',b.id,b.thickness,nil,false,nil,b.ownerId,b.slotIndex,false,false,b.shotId,key,b.speed,true)
   end
   if kind=='Drop' or terminal then bullets[key]=nil;fresh[key]=nil end
  end
  return true
 end
 -- After a message's rows: a new bullet draws its first step now, as the old first row did (one
 -- that landed in the same message already drew its whole flight in its Land row).
 function flights.launched(now)
  for key,b in fresh do if bullets[key]==b then advance(key,b,1/F.StepRate,now) end end
  table.clear(fresh)
 end
 -- Every frame. Each bullet steps on its own clock, at most 60 times a second, so one that arrived
 -- mid-frame isn't stepped twice at once. A leg that runs out before its Land row waits at its
 -- end; a bullet that hears nothing for 1 s (its rows went to players near it, and this one left)
 -- is forgotten.
 function flights.step(now)
  for key,b in bullets do
   if now-b.heard>1 or now-b.born>10 then
    draw(b.at,b.at,'Ranged',b.id,b.thickness,nil,false,nil,b.ownerId,b.slotIndex,false,false,b.shotId,key,b.speed,true)
    bullets[key]=nil;fresh[key]=nil
   elseif now-b.stepped>=1/(F.StepRate+1) then advance(key,b,math.min(now-b.stepped,.1),now) end
  end
 end
 return flights
end
return F
