-- Pure regression: return require(testModule).run(require(WeaponJournal)).
local Tests={}
function Tests.run(J)
 local checks=0
 local function check(value,message) checks+=1;assert(value,message) end
 local d=J.clean({weapons={['00']={damage=42.25,kills=2},unknown={damage=1e30},['01']={damage=0/0,kills=-1}},items={soup=3,unknown=20}})
 check(d.weapons['00'].damage==42.25 and d.weapons['00'].kills==2,'migration keeps valid counters')
 check(d.weapons.unknown==nil and d.weapons['01']==nil and d.items.unknown==nil,'migration rejects invalid data')
 check(d.items.soup==3,'item history survives migration')
 for _,bad in {-1,0,0/0,math.huge,-math.huge,'100'} do check(not J.hit(d,'00',bad,true),'invalid damage rejected') end
 check(not J.hit(d,'Pet',12,true),'nonweapon source rejected')
 check(J.hit(d,'00',7.75,true) and d.weapons['00'].damage==50 and d.weapons['00'].kills==3,'confirmed lethal hit')
 check(J.hit(d,'00',1,false) and d.weapons['00'].kills==3,'nonlethal never adds kill')
 check(not J.bought(d,'weapon_00_1'),'weapon purchases do not count as passive items')
 check(J.bought(d,'soup') and d.items.soup==4,'item purchase adds one')
 d.weapons['00']={damage=J.MAX,kills=J.MAX};J.hit(d,'00',100,true)
 check(d.weapons['00'].damage==J.MAX and d.weapons['00'].kills==J.MAX,'counters saturate')
 local view=J.view(d);view.weapons['00'].damage=0;check(d.weapons['00'].damage==J.MAX,'view cannot mutate save')
 check(#J.WeaponIds==42,'all 42 weapons indexed')
 for _,item in J.Items do
  local ids=J.compatibility(item);local seen={}
  for _,id in ids do check(table.find(J.WeaponIds,id)~=nil and not seen[id],'valid unique compatibility '..item.id);seen[id]=true end
 end
 local ids=J.compatibility(J.ItemById.straws)
 check(not table.find(ids,'01') and table.find(ids,'00')~=nil,'extra projectiles do not claim to help pan')
 return {passed=true,checks=checks,weapons=#J.WeaponIds,items=#J.Items}
end
return Tests
