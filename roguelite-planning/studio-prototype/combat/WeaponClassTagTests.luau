-- Catalog audit against the 2026-10-09 roster (plans/2026-10-09-chef-roster-weapon-types-design.md):
-- one starter class per ordinary weapon, Godlies classless. No instances or rewards.
return function(Weapons)
 local expected={
  Brawler={'02','03','04','06','19','20'},
  Gunner={'00','07','08','09','10','11'},
  Chef={'01','05','14','15','16','42'},
  Juggler={'12','13','17','18','21','22','23'},
  Handyman={'24','25','26','27','28','29'},
  Mage={'30','31','32','33','34','35'},
 }
 local classOf={};for class,ids in expected do for _,id in ids do classOf[id]=class end end
 local classes={'Brawler','Gunner','Chef','Juggler','Handyman','Mage'}
 local checks=0
 local function check(ok,message) checks+=1;assert(ok,message) end
 for _,w in Weapons.List do
  local want=classOf[w.id]
  if want then
   check(w.class==want and w.home==want,'starter class: '..w.name)
   check(#w.classes==1 and w.classes[1]==want,'one class listed: '..w.name)
   check(Weapons.classNames(w,' · ')==want and Weapons.classNames(w)==want,'display label: '..w.name)
   for _,class in classes do
    check(Weapons.inClass(w,class)==(class==want),'membership: '..w.name..' / '..class)
    check((table.find(w.tags,class)~=nil)==(class==want),'combat tag: '..w.name..' / '..class)
   end
   check(table.find(w.tags,'Thrower')==nil,'no Thrower tag: '..w.name)
  else
   check(w.godly==true and w.class==nil and #w.classes==0 and w.home=='Godly','Godlies have no class restriction: '..w.name)
   for _,class in classes do check(not Weapons.inClass(w,class),'Godly in no class: '..w.name) end
  end
 end
 check(#Weapons.List==43,'audit covers all 43 weapons')
 check(Weapons.ById['42'].name=='Pizza Cutter' and not Weapons.ById['42'].godly,'Pizza Cutter is id 42 and not Godly')
 return {passed=true,checks=checks}
end
