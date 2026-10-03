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
-- The nearest entry `can` accepts whose point (measure(e), where it is measured to) is more than
-- .01 and less than `range` from origin and passes clear(point,e), and that point. Candidates are
-- tried nearest first, ties to the earlier entry, so clear runs once per closer blocked enemy.
function G.nearest(grid,origin,range,can,measure,clear)
 local found={}
 for _,e in G.around(grid,origin,range) do
  if can(e) then
   local point=measure(e)
   local distance=(point-origin).Magnitude
   if distance<range and distance>.01 then table.insert(found,{e=e,point=point,distance=distance}) end
  end
 end
 table.sort(found,function(a,b) if a.distance~=b.distance then return a.distance<b.distance end;return a.e.order<b.e.order end)
 for _,f in found do if clear(f.point,f.e) then return f.e,f.point end end
end
return G
