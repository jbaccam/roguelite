-- Server validation regressions against ordinary profile snapshots. No profile writes.
local T={}
function T.run(R)
 local checks=0
 local function check(ok,message) checks+=1;assert(ok,message) end
 local function player(wins,loaded)
  local a={ProfileLoaded=loaded~=false,ProfileClasses='Brawler,Gunner,Mage',ProfileWeapons='01:1:0,00:1:0,30:1:0',ProfileMapWins=wins or ''}
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
 check(R.validLoadout(fresh,'Brawler','01'),'Owned matching starter accepted')
 check(R.validLoadout(fresh,'Gunner','00'),'Non-pan starter accepted')
 check(not R.validLoadout(fresh,'Gunner','01'),'Wrong-class weapon refused')
 check(not R.validLoadout(fresh,'Thrower','12'),'Locked class refused')
 check(not R.validLoadout(fresh,'Brawler','03'),'Unowned starter refused')
 check(not R.validLoadout(player('',false),'Brawler','01'),'A loading profile cannot lose a pick into temporary defaults')
 check(not R.validLoadout(fresh,{},'01'),'Malformed class refused')
 check(not R.validLoadout(fresh,'Brawler',{}),'Malformed weapon refused')
 return {passed=checks,failed=0}
end
return T
