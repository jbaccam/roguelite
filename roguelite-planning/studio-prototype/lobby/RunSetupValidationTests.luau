-- Server validation regressions against ordinary profile snapshots. No profile writes.
local T={}
function T.run(R)
 local checks=0
 local function check(ok,message) checks+=1;assert(ok,message) end
 -- A fresh profile owns Brawler, Gunner and Mage with Baseball Bat, Glock and Magic Staff (2026-10-10).
 local function player(wins,loaded,classes,weapons)
  local a={ProfileLoaded=loaded~=false,ProfileClasses=classes or 'Brawler,Gunner,Mage',ProfileWeapons=weapons or '06:1:0,00:1:0,30:1:0',ProfileMapWins=wins or ''}
  return {GetAttribute=function(_,key) return a[key] end}
 end
 local fresh=player()
 local normalWinner=player('PineValley')
 local hardWinner=player('PineValley,PineValley/Hard')
 check(R.validMap(fresh,'PineValley','Normal'),'Fresh profile can play Normal')
 check(not R.validMap(fresh,'PineValley','Hard'),'Unprogressed party member cannot enter Hard')
 check(R.validMap(normalWinner,'PineValley','Hard'),'Normal winner can play Hard')
 check(not R.validMap(normalWinner,'PineValley','Nightmare'),'Normal win does not unlock Nightmare')
 check(R.validMap(hardWinner,'PineValley','Nightmare'),'Hard winner can play Nightmare')
 check(not R.validMap(fresh,'BeachCove','Normal'),'Locked next map refused')
 check(not R.validMap(fresh,'NotAMap','Normal'),'Unknown map refused')
 check(not R.validMap(fresh,'PineValley','Impossible'),'Unknown difficulty refused')
 check(not R.validMap(player('',false),'PineValley','Normal'),'A loading save cannot enter even default map')
 check(R.validLoadout(fresh,'Brawler','06'),'Owned matching starter accepted (Brawler + Baseball Bat)')
 check(R.validLoadout(fresh,'Gunner','00'),'Gunner + Glock accepted')
 check(not R.validLoadout(fresh,'Gunner','06'),'Wrong-class weapon refused')
 check(not R.validLoadout(fresh,'Chef','01'),'Locked class refused')
 check(not R.validLoadout(fresh,'Brawler','03'),'Unowned starter refused')
 check(not R.validLoadout(fresh,'Brawler','19'),'Unowned Boxing Gloves refused (a Rare, not the default)')
 check(not R.validLoadout(player('',false),'Brawler','06'),'A loading profile cannot lose a pick into temporary defaults')
 check(not R.validLoadout(fresh,{},'06'),'Malformed class refused')
 check(not R.validLoadout(fresh,'Brawler',{}),'Malformed weapon refused')
 -- One starter class per weapon (2026-10-09): the Pan is Chef's, Kusarigama Brawler's, the Nail Gun
 -- only Handyman's; an owned Godly starts with any owned class; Thrower is no class at all.
 local chef=player('',true,'Brawler,Gunner,Chef,Handyman,Mage','06:1:0,00:1:0,01:2:0,04:1:0,24:1:0,30:1:0,36:1:0')
 check(not R.validLoadout(chef,'Brawler','01'),'Brawler + owned Frying Pan refused')
 check(R.validLoadout(chef,'Chef','01'),'Chef + Frying Pan accepted')
 check(R.validLoadout(chef,'Brawler','04'),'Kusarigama starts a Brawler run')
 check(not R.validLoadout(chef,'Gunner','24'),'Nail Gun no longer starts a Gunner run')
 for _,class in {'Brawler','Gunner','Chef','Handyman','Mage'} do check(R.validLoadout(chef,class,'36'),'Owned Godly with '..class) end
 check(not R.validLoadout(fresh,'Brawler','36'),'Unowned Godly refused')
 check(not R.validLoadout(chef,'Thrower','12'),'Thrower is an unknown class')
 local starters=R.starters('Chef',R.progress(chef).weapons)
 check(#starters==2 and starters[1].id=='01' and starters[2].id=='36','Chef starters: owned Chef weapons, then owned Godlies')
 local brawler=R.starters('Brawler',R.progress(fresh).weapons)
 check(#brawler==1 and brawler[1].id=='06','Fresh Brawler starts with only the Bat')
 check(R.ClassUnlock.Chef=='Reach wave 10 on Pine Valley' and R.ClassUnlock.Thrower==nil,'Chef takes the Thrower unlock quest')
 return {passed=checks,failed=0}
end
return T
