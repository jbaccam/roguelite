-- Weapon targeting over one tick's enemy snapshot (RogueliteCombat.server, launch audit P4). Pure:
-- no Instances are touched here, so TargetGridTests runs it on made-up enemies.
-- Each player used to rebuild the enemy list every tick, and every slot measured all of it and
-- raycast each enemy closer than its best so far: thousands of raycasts a second in a horde. Now
-- the snapshot is built once per tick, enemies sit in 16-stud X/Z cells, and a slot takes only the
-- cells its range covers, walks them nearest first and stops at the first clear line. That is the
-- same pick as before (the nearest clear enemy, ties to the earlier one in tag order), usually for
-- one raycast. Bosses stay out of the cells and are always checked: they are measured to their
-- nearest side, which can be well inside their root's distance.
-- (EnemySpatialGrid can't serve here: it is unsandboxed and RogueliteCombat is sandboxed.)
local G={Cell=16}
-- entries: in tag order, each with position (its root) and boss (true for a boss). Each gets an
-- order field, its place in the list.
function G.new(entries)
 local grid={list=entries,cells={},bosses={}}
 for order,e in entries do
  e.order=order
  if e.boss then table.insert(grid.bosses,e)
  else
   local x,z=math.floor(e.position.X/G.Cell),math.floor(e.position.Z/G.Cell)
   local column=grid.cells[x];if not column then column={};grid.cells[x]=column end
   local cell=column[z];if not cell then cell={};column[z]=cell end
   table.insert(cell,e)
  end
 end
 return grid
end
-- Every entry whose root may lie within `range` of `origin`, in no particular order. A range that
-- covers more cells than there are entries just takes the whole list.
function G.around(grid,origin,range)
 local x0,x1=math.floor((origin.X-range)/G.Cell),math.floor((origin.X+range)/G.Cell)
 local z0,z1=math.floor((origin.Z-range)/G.Cell),math.floor((origin.Z+range)/G.Cell)
 if (x1-x0+1)*(z1-z0+1)>#grid.list then return grid.list end
 local out={}
 for x=x0,x1 do
  local column=grid.cells[x]
  if column then for z=z0,z1 do local cell=column[z];if cell then table.move(cell,1,#cell,#out+1,out) end end end
 end
 table.move(grid.bosses,1,#grid.bosses,#out+1,out)
 return out
end
function G.byOrder(a,b) return a.order<b.order end
-- Melee reach (2026-10-03, round 2: "bhopping melee weapons won't hit at max height of jump"): flat
-- (X/Z) distance for anything within `allowance` studs above or below; past that, the extra height
-- counts too. No allowance: the plain distance, as before. Example: a zombie 4 studs out and 3
-- across while the player is 9.5 up at a jump's peak is 5 studs away with a 13.5 allowance (10.7 plain).
function G.distance(offset,allowance)
 if not allowance then return offset.Magnitude end
 local over=math.max(0,math.abs(offset.Y)-allowance)
 return math.sqrt(offset.X*offset.X+offset.Z*offset.Z+over*over)
end
-- How high a jump goes: JumpHeight, or JumpPower^2 / (2 x gravity) when UseJumpPower is on.
-- Example: JumpHeight 9.5 at gravity 150 is a 53.4 studs/s take-off, 9.5 up after 0.36 s, 0.71 s
-- in the air. ReachBody, a body's height, is added on top: mob roots sit a few studs below a
-- player's (a crab's is 1 up, a player's 3) or above it (an ogre's), so the allowance is 9.5 + 4 = 13.5.
G.ReachBody=4
function G.jumpHeight(useJumpPower,jumpPower,jumpHeight,gravity)
 if useJumpPower then return (jumpPower or 0)^2/(2*math.max(gravity or 196.2,1)) end
 return jumpHeight or 0
end
-- The nearest entry `can` accepts whose point (measure(e), where it is measured to) is more than
-- .01 and less than `range` from origin and passes clear(point,e), and that point. Candidates are
-- tried nearest first, ties to the earlier entry, so clear runs once per closer blocked enemy.
-- allowance: melee's vertical allowance (G.distance), nil for the plain distance.
function G.nearest(grid,origin,range,can,measure,clear,allowance)
 local found={}
 for _,e in G.around(grid,origin,range) do
  if can(e) then
   local point=measure(e)
   local distance=G.distance(point-origin,allowance)
   if distance<range and distance>.01 then table.insert(found,{e=e,point=point,distance=distance}) end
  end
 end
 table.sort(found,function(a,b) if a.distance~=b.distance then return a.distance<b.distance end;return a.e.order<b.e.order end)
 for _,f in found do if clear(f.point,f.e) then return f.e,f.point end end
end
-- Melee sweeps (launch audit P6). The enemies a swing could still hit this tick: not in `hit`,
-- and a boss (measured to its nearest side) or with its root within `range` of origin. Returns
-- them as a set and how many there are. allowance: as in G.nearest.
function G.open(grid,origin,range,hit,allowance)
 local open,count={},0
 for _,e in grid.list do
  if not hit[e.npc] and (e.boss or G.distance(e.position-origin,allowance)<=range) then open[e.npc]=true;count+=1 end
 end
 return open,count
end
-- One tick of a sweep's hit checks. sample(i) gives the boxes of sample i (0..steps), query(box)
-- the parts touching a box, owner(part) the enemy a part belongs to (nil: none), and judge(npc)
-- checks an enemy and hits it if it can be hit. Nothing moves within a tick, so an enemy's
-- answer is the same for all its parts, boxes and samples: it is judged once, at its first part
-- (the old loop judged every part until one hit). Sampling stops once every enemy in `open` has
-- been judged (open nil: never). Returns the samples and queries made.
function G.sweep(steps,sample,query,owner,judge,open,remaining)
 local judged,samples,queries={},0,0
 for i=0,steps do
  if open and remaining<=0 then break end
  samples+=1
  for _,box in sample(i) do
   queries+=1
   for _,part in query(box) do
    local npc=owner(part)
    if npc and not judged[npc] then
     judged[npc]=true
     if open and open[npc] then remaining-=1 end
     judge(npc)
    end
   end
  end
 end
 return samples,queries
end
return G
