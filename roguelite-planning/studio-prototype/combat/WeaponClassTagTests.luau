-- Catalog audit against CURRENT_GAME_STRUCTURE.md's approved roster; no instances or rewards.
return function(Weapons)
 local expected={
  ['00']={'Gunner'},['01']={'Brawler'},['02']={'Brawler'},['03']={'Brawler'},
  ['04']={'Juggler','Thrower'},['05']={'Juggler','Handyman'},['06']={'Brawler'},
  ['07']={'Gunner'},['08']={'Gunner','Mage'},['09']={'Gunner'},
  ['10']={'Gunner','Thrower'},['11']={'Gunner','Handyman'},
  ['12']={'Thrower','Juggler'},['13']={'Thrower'},['14']={'Thrower','Mage'},
  ['15']={'Thrower','Juggler'},['16']={'Thrower'},['17']={'Juggler','Thrower'},
  ['18']={'Thrower','Juggler'},['19']={'Brawler','Juggler'},['20']={'Brawler','Handyman'},
  ['21']={'Juggler'},['22']={'Juggler','Thrower'},['23']={'Juggler','Brawler'},
  ['24']={'Handyman','Gunner'},['25']={'Handyman'},['26']={'Handyman','Brawler'},
  ['27']={'Handyman'},['28']={'Handyman'},['29']={'Handyman'},
  ['30']={'Mage'},['31']={'Mage','Thrower'},['32']={'Mage','Brawler'},
  ['33']={'Mage'},['34']={'Mage'},['35']={'Mage'},
 }
 local checks=0
 local function check(ok,message) checks+=1;assert(ok,message) end
 for _,w in Weapons.List do
  local want=expected[w.id]
  if want then
   check(table.concat(w.classes,',')==table.concat(want,','),'class roster: '..w.name)
   check(w.home==want[1],'home class first: '..w.name)
   check(Weapons.classNames(w,' · ')==table.concat(want,' · '),'complete display label: '..w.name)
   for _,class in {'Brawler','Gunner','Thrower','Juggler','Handyman','Mage'} do
    local belongs=table.find(want,class)~=nil
    check(Weapons.inClass(w,class)==belongs,'membership: '..w.name..' / '..class)
    check((table.find(w.tags,class)~=nil)==belongs,'combat tag: '..w.name..' / '..class)
   end
  else
   check(w.godly==true and #w.classes==0,'Godlies have no class restriction: '..w.name)
  end
 end
 check(#Weapons.List==42,'audit covers all 42 weapons')
 return {passed=true,checks=checks}
end
