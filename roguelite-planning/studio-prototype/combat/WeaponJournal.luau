-- Bounded lifetime records and encyclopedia data. No remotes or storage calls.
local Weapons=require(script.Parent.WeaponCatalog)
local Items=require(script.Parent.ShopCatalog)
local Stats=require(script.Parent.CharacterStats)
local J={MAX=9e12,Since='October 4, 2026'}
J.Items={};J.ItemById={};J.WeaponIds={}
for _,w in Weapons.List do table.insert(J.WeaponIds,w.id) end
for _,e in Items.List do if not e.weaponId then table.insert(J.Items,e);J.ItemById[e.id]=e end end
table.sort(J.Items,function(a,b) return a.name<b.name end)
local function number(n)
 return type(n)=='number' and n==n and n<math.huge and n>=0
end
local function cleanCount(n,integer)
 if not number(n) then return 0 end
 n=math.min(J.MAX,n);return integer and math.floor(n) or n
end
function J.clean(raw)
 local out={version=1,weapons={},items={}}
 if type(raw)~='table' then return out end
 local weapons=type(raw.weapons)=='table' and raw.weapons or {}
 for _,w in Weapons.List do
  local r=weapons[w.id]
  if type(r)=='table' then
   local damage,kills=cleanCount(r.damage),cleanCount(r.kills,true)
   if damage>0 or kills>0 then out.weapons[w.id]={damage=damage,kills=kills} end
  end
 end
 local items=type(raw.items)=='table' and raw.items or {}
 for _,e in J.Items do local n=cleanCount(items[e.id],true);if n>0 then out.items[e.id]=n end end
 return out
end
function J.hit(data,id,damage,lethal)
 if not Weapons.ById[id] or not number(damage) or damage<=0 or damage>J.MAX then return false end
 local r=data.weapons[id] or {damage=0,kills=0};data.weapons[id]=r
 r.damage=math.min(J.MAX,r.damage+damage)
 if lethal==true then r.kills=math.min(J.MAX,r.kills+1) end
 return true
end
function J.bought(data,id)
 if not J.ItemById[id] then return false end
 data.items[id]=math.min(J.MAX,(data.items[id] or 0)+1);return true
end
function J.view(data)
 local out=J.clean(data)
 for _,r in out.weapons do r.damage=math.floor(r.damage*10+.5)/10 end
 return out
end
-- Base compatibility plus explicit conditional lightning support. Uses the same policy as shop.
function J.compatibility(item)
 local neutral={};for _,s in Stats.List do neutral[s.id]=s.base end
 local ids=Items.worksWith(item,J.WeaponIds,neutral)
 return ids or table.clone(J.WeaponIds),ids==nil
end
return J
