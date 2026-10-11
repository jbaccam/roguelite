-- Shop Banish (2026-10-10, MONETIZATION_AND_REWARDS.md "Banish"): the run's banned set and the pool
-- one shop slot rolls from (ShopCatalog.banKey / isBanned / offerPool, which ShopService's roll uses).
-- Pure: no Instances, no Play, no rewards. Run with
-- `python roguelite-planning/studio-prototype/combat/run_shop_tests.py build/luau-validation/luau.exe`,
-- or in Studio Edit: print(require(<this module>)(require(C.ShopCatalog))).
-- candidate() below is ShopService's own rule without the build checks (cap, usable, turrets): the
-- kind asked for, owned for weapons, not on show. offerPool must leave banned entries out by itself.
-- Returns the number of checks.
return function(Catalog)
 local checks=0
 local function check(ok,msg) checks+=1;assert(ok,msg) end
 local weapons,items={},{}
 for _,e in Catalog.List do if e.kind=='Weapon' then table.insert(weapons,e) else table.insert(items,e) end end
 check(#weapons>=8 and #items>=8,'catalog has weapons and items')
 local function owns(all) local o={};for _,e in weapons do if all or e.weaponId==weapons[1].weaponId then o[e.weaponId]=true end end;return o end
 local function candidateFor(owned,excluded)
  return function(entry,want) if (entry.kind=='Weapon')~=want or excluded[entry.id] then return false end;if want then return owned[entry.weaponId]==true end;return true end
 end
 local function pool(tier,want,owned,excluded,banned) return Catalog.offerPool(Catalog.List,tier,want,candidateFor(owned,excluded),owned,excluded,banned) end
 local function has(list,fn) for _,e in list do if fn(e) then return true end end;return false end

 -- Keys: items by id; weapons by weapon id, the same for every tier.
 local glock={};for _,e in weapons do if e.weaponId==weapons[1].weaponId then table.insert(glock,e) end end
 check(#glock==4,'a shop weapon has four tiers')
 for _,e in glock do check(Catalog.banKey(e)=='weapon:'..e.weaponId,'weapon key for tier '..e.tier) end
 check(Catalog.banKey(items[1])==items[1].id,'item key is its id')
 check(not Catalog.isBanned(nil,items[1]) and not Catalog.isBanned({},items[1]),'nothing banned: nil or empty set')
 check(Catalog.isBanned({[items[1].id]=true},items[1]) and not Catalog.isBanned({[items[1].id]=true},items[2]),'only the banned item')

 -- A banned weapon never shows in any tier, from any wanted tier; others still do.
 local all=owns(true)
 local wid=weapons[1].weaponId
 local banned={['weapon:'..wid]=true}
 for tier=1,4 do
  local p=pool(tier,true,all,{},banned)
  check(#p>0,'weapon pool at tier '..tier..' still has weapons')
  check(not has(p,function(e) return e.weaponId==wid end),'banned weapon absent at tier '..tier)
  check(has(pool(tier,true,all,{},nil),function(e) return e.weaponId==wid end),'unbanned it is there at tier '..tier)
 end
 -- A banned item never shows; the rolled tier keeps its other items.
 local it=items[1]
 local p=pool(it.tier,false,all,{},{[it.id]=true})
 check(#p>0 and not has(p,function(e) return e.id==it.id end),'banned item absent')
 check(has(pool(it.tier,false,all,{},nil),function(e) return e.id==it.id end),'unbanned item there')
 -- Every item of a tier banned: the roll drops to the next lower tier that has any.
 local tier2={};local any2=false
 for _,e in items do if e.tier==2 then tier2[e.id]=true;any2=true end end
 if any2 then
  local q=pool(2,false,all,{},tier2)
  check(#q>0 and not has(q,function(e) return e.tier==2 end) and has(q,function(e) return e.tier==1 end),'all Tier II items banned: Tier I items instead')
 end
 -- Every item banned on an item roll: an owned weapon fills the slot (any tier), never a banned one.
 local allItems={};for _,e in items do allItems[e.id]=true end
 local owned1=owns(false) -- owns only weapons[1]'s weapon
 local q=pool(3,false,owned1,{},allItems)
 check(#q==4 and not has(q,function(e) return e.kind~='Weapon' or e.weaponId~=wid end),'items all banned: the owned weapon, every tier')
 -- ...and with that weapon banned too: any other weapon (the last resort), still none banned.
 local both=table.clone(allItems);both['weapon:'..wid]=true
 q=pool(3,false,owned1,{},both)
 check(#q>0 and not has(q,function(e) return e.kind~='Weapon' or e.weaponId==wid end),'owned weapon banned too: other weapons')
 -- Everything banned: the slot is still filled (never an empty offer), from weapons not on show.
 local everything=table.clone(allItems);for _,e in weapons do everything['weapon:'..e.weaponId]=true end
 local onShow={[weapons[1].id]=true}
 q=pool(1,true,all,onShow,everything)
 check(#q>0 and not has(q,function(e) return onShow[e.id] end),'everything banned: a slot still fills, never with one on show')
 -- Weapon roll with only banned owned weapons: it falls back to items, as when none is owned.
 q=pool(1,true,owned1,{},{['weapon:'..wid]=true})
 check(#q>0 and q[1].kind~='Weapon','owned weapon banned on a weapon roll: items instead')
 -- Ten rolls in a row with a growing banned set never offer a banned entry (a run of banishes).
 local grow={}
 for n=1,10 do
  local r=pool(((n-1)%4)+1,n%2==0,all,{},grow)
  check(#r>0,'roll '..n..' fills')
  for _,e in r do check(not Catalog.isBanned(grow,e),'roll '..n..': nothing banned offered') end
  grow[Catalog.banKey(r[1])]=true
 end
 return checks
end
