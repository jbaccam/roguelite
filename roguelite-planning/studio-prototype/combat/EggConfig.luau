-- Pet eggs (user, 2026-10-02): the egg merchant on the quest-board island sells one kind of egg.
-- Every egg hatches exactly ONE pet. The roll picks a rarity by E.Odds, then one pet of that rarity
-- evenly. Example: Common is 50% and there are 4 Common pets, so each is 12.5%; the Baby Dragon is
-- the only Legendary, so it gets the whole 5%. Copies upgrade a pet like a weapon
-- (ProfileService.addCopies). Pets come from eggs only (the planned Pet Chest was dropped).
-- Shared by the server (ProfileService rolls) and the client (EggScreenUI shows the odds).
-- Studio: RS.RogueliteCombat.EggConfig, an UNSANDBOXED ModuleScript like ChestConfig (only
-- unsandboxed scripts require it; requiring the sandboxed PetConfig from here is fine).
local Pets=require(script.Parent:WaitForChild('PetConfig'))
local E={}

E.Id='PetEgg'
E.Name='Pet Egg'
E.Icon='' -- UI icon (blender-egg-merchant-kit previews/icon-egg.png, uploaded); set by the installer step
E.Emeralds=250 -- per egg (user pick: between a Silver Chest, 160, and a Gold Chest, 300)
E.Amounts={1,3,10} -- bought or hatched at once
E.Rarities={'Common','Rare','Epic','Legendary'}
-- Percent per rarity ("generous", user pick). Rarer pets are flashier, not stronger (PetConfig),
-- so generous odds don't hand out power. If a pet ever tunes out stronger, make it rarer.
E.Odds={Common=50,Rare=30,Epic=15,Legendary=5}
-- Presentation colours: the teal of the egg's spots, and the warm light from its cracks.
E.Aura=Color3.fromRGB(86,214,206)
E.Glow=Color3.fromRGB(255,214,120)
-- Burst size for one hatch animation (×3 and ×10 are one bigger burst, like chests).
function E.burstScale(n) return n>=10 and 2.4 or n>=3 and 1.6 or 1 end

function E.validAmount(n) return type(n)=='number' and table.find(E.Amounts,n)~=nil end
function E.price(n) return E.Emeralds*n end

-- Pets of each rarity, in PetConfig order.
E.ByRarity={}
for _,r in E.Rarities do E.ByRarity[r]={} end
for _,pet in Pets.List do
 local list=E.ByRarity[pet.rarity]
 if list then table.insert(list,pet.id) end
end

-- One hatch: returns pet id, rarity. A rarity with no pets falls through to the next roll.
function E.roll(rng)
 local x=rng:NextNumber()*100
 local rarity=E.Rarities[1]
 for _,r in E.Rarities do
  if x<E.Odds[r] then rarity=r;break end
  x-=E.Odds[r]
 end
 local list=E.ByRarity[rarity]
 if #list==0 then list=E.ByRarity.Common end
 return list[rng:NextInteger(1,#list)],rarity
end

-- Every pet's chance (percent) from one egg, rarest last within PetConfig order:
-- {{id, rarity, chance}, ...}. Sums to 100.
function E.odds()
 local out={}
 for _,r in E.Rarities do
  local list=E.ByRarity[r]
  for _,id in list do table.insert(out,{id=id,rarity=r,chance=E.Odds[r]/#list}) end
 end
 return out
end

return E
