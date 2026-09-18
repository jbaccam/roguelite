-- In-memory run economy. No DataStores, Robux, client prices or client-owned inventory.
local RS=game:GetService('ReplicatedStorage')
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local Http=game:GetService('HttpService')
local combat=RS:WaitForChild('RogueliteCombat')
local E=require(combat.EconomyConfig)
local Catalog=require(combat.ShopCatalog)
local Characters=require(script.Parent.CharacterService)
local S={states={},wave=1,phase='Shop'}
local rng=Random.new()
local serial=0
local function token() serial+=1;return tostring(serial) end
local run=RS:FindFirstChild('RogueliteRunState') or Instance.new('Folder')
run.Name='RogueliteRunState';run.Parent=RS
run:SetAttribute('Phase','Shop');run:SetAttribute('Wave',1)
combat:SetAttribute('ZombiesEnabled',false)
local remote=combat:WaitForChild('ShopAction')
local function living(p) local h=p.Character and p.Character:FindFirstChildOfClass('Humanoid');return h and h.Health>0 end
local function slots(p) return Characters.states[p].folder end
local function owned(p)
 local result={}
 for i=1,6 do local f=slots(p)['Slot'..i]
  result[i]={slot=i,id=f:GetAttribute('WeaponId') or '',copy=f:GetAttribute('CopyId') or '',tier=f:GetAttribute('Tier') or 1,paid=f:GetAttribute('FinalPurchasePrice') or 0,basePrice=f:GetAttribute('BasePrice') or 0,wave=f:GetAttribute('WavePurchased') or 0}
 end
 return result
end
function S.publish(p,message)
 local s=S.states[p];if not s or not Characters.states[p] then return end
 local data={gold=s.gold,wave=S.wave,phase=S.phase,rerolls=s.rerolls,rerollPrice=E.reroll(S.wave,s.rerolls),offers=s.offers,items=s.items,weapons=owned(p),ready=s.ready,revision=s.revision,message=message or s.message or '',modifier=E.modifier(Characters.states[p].stats),debug=RunService:IsStudio() and E.DEBUG_CURRENCY_ENABLED}
 s.message=data.message;slots(p):SetAttribute('Gold',s.gold)
 slots(p):SetAttribute('ShopSnapshot',Http:JSONEncode(data))
end
local function reprice(p)
 local s=S.states[p];local modifier=E.modifier(Characters.states[p].stats)
 for _,o in s.offers do if not o.locked and not o.sold then o.price=E.price(Catalog.ById[o.id].basePrice,S.wave,modifier) end end
end
local function roll(p,previous,kind)
 local s=S.states[p];local pool={};local wantWeapon=kind=='Weapon' or (not kind and rng:NextNumber()<.5)
 -- Wave-dependent rarity mix is disclosed, independent of Luck and purchases.
 local n=rng:NextNumber();local tier=n<.55 and 1 or n<.85 and 2 or n<.97 and 3 or 4
 if S.wave>=6 and tier==1 and rng:NextNumber()<.25 then tier=2 end
 for _,entry in Catalog.List do
  if (entry.kind=='Weapon')==wantWeapon and entry.tier==tier and entry.id~=previous then
   local count=0;for _,it in s.items do if it.id==entry.id then count=it.count end end
   if entry.kind=='Weapon' or count<entry.cap then table.insert(pool,entry) end
  end
 end
 if #pool==0 then for _,entry in Catalog.List do if entry.kind=='Weapon' and entry.id~=previous then table.insert(pool,entry) end end end
 local entry=pool[rng:NextInteger(1,#pool)]
 return {id=entry.id,token=token(),price=E.price(entry.basePrice,S.wave,E.modifier(Characters.states[p].stats)),locked=false,sold=false}
end
function S.bonuses(p)
 local s=S.states[p];local cs=Characters.states[p];if not s or not cs then return end
 cs.itemBonuses={};cs.itemPercent={}
 for _,item in s.items do local entry=Catalog.ById[item.id]
  for id,value in entry.modifiers do cs.itemBonuses[id]=(cs.itemBonuses[id] or 0)+value*item.count end
  for id,value in entry.percent do cs.itemPercent[id]=(cs.itemPercent[id] or 0)+value*item.count end
 end
 Characters.refresh(p)
end
function S.attach(p)
 local s={gold=E.STARTING_GOLD,rerolls=0,offers={},items={},ready=false,revision=1,lastRequest=-1e6}
 S.states[p]=s
 for i=1,6 do local f=slots(p)['Slot'..i];f:SetAttribute('Tier',1);f:SetAttribute('FinalPurchasePrice',0);f:SetAttribute('BasePrice',0);f:SetAttribute('WavePurchased',0);f:SetAttribute('CopyId',token()) end
 for i=1,E.OFFER_COUNT do s.offers[i]=roll(p,nil,i==1 and 'Weapon' or i==2 and 'Item' or nil) end
 S.publish(p)
 p.CharacterAdded:Connect(function() task.defer(function() if S.states[p] then s.ready=false;S.publish(p) end end) end)
end
local function beginWave()
 if S.phase~='Shop' then return end
 local count=0
 for p,s in S.states do if living(p) then count+=1;if not s.ready then return end end end
 if count==0 then return end
 S.phase='Combat';run:SetAttribute('Phase','Combat');run:SetAttribute('WaveEndsAt',workspace:GetServerTimeNow()+E.WAVE_SECONDS)
 combat:SetAttribute('ZombieCount',combat:GetAttribute('TestZombieCountOverride') or math.min(100,5+(S.wave-1)*2));combat:SetAttribute('ZombiesEnabled',true)
 for p in S.states do local cs=Characters.states[p];cs.blocks=1;cs.folder:SetAttribute('BlocksRemaining',cs.stats.FirstHitBlock);S.publish(p,'Wave started') end
end
function S.finishWave()
 if S.phase~='Combat' then return false end
 combat:SetAttribute('ZombiesEnabled',false);S.phase='Shop';S.wave+=1
 run:SetAttribute('Phase','Shop');run:SetAttribute('Wave',S.wave);run:SetAttribute('WaveEndsAt',nil)
 for p,s in S.states do
  if living(p) then s.gold=math.min(E.MAX_GOLD,s.gold+E.WAVE_REWARD_BASE+(S.wave-1)*E.WAVE_REWARD_SCALE) end
  s.rerolls=0;s.ready=false;s.revision+=1
  for i,o in s.offers do if not o.locked or o.sold then s.offers[i]=roll(p,o.id) end end
  S.publish(p,'Next shop · reroll cost reset')
 end
 return true
end
function S.request(p,action,revision,arg,extra)
 local s=S.states[p];local cs=Characters.states[p]
 if not s or not cs or not living(p) or type(action)~='string' then return false end
 if os.clock()-s.lastRequest<.12 then return false end;s.lastRequest=os.clock()
 local function fail(msg) S.publish(p,msg);return false end
 if revision~=s.revision then return fail('Shop changed. Please try again.') end
 if action=='Gold' then
  if not RunService:IsStudio() or not E.DEBUG_CURRENCY_ENABLED then return fail('Developer control unavailable') end
  if not E.integer(extra,-E.MAX_GOLD,E.MAX_GOLD) or (arg~='Set' and arg~='Add') then return fail('Enter a whole gold amount') end
  local value=arg=='Set' and extra or s.gold+extra
  if not E.integer(value,0,E.MAX_GOLD) then return fail('Gold must be between 0 and '..E.MAX_GOLD) end
  s.gold=value
 elseif S.phase~='Shop' then return fail('Shop actions are available between waves')
 elseif action=='Buy' or action=='Lock' then
  if not E.integer(arg,1,E.OFFER_COUNT) then return fail('Invalid offer') end
  local o=s.offers[arg];if not o or o.token~=extra or o.sold then return fail('Offer is no longer available') end
  if action=='Lock' then o.locked=not o.locked
  else
   local entry=Catalog.ById[o.id]
   if s.gold<o.price then return fail('Not enough gold') end
   if entry.kind=='Weapon' then
    if not combat.WeaponTemplates:FindFirstChild(entry.weaponId) then return fail('Weapon asset unavailable') end
    local free
    for i=1,6 do if slots(p)['Slot'..i]:GetAttribute('WeaponId')=='' then free=slots(p)['Slot'..i];break end end
    if not free then return fail('All six weapon slots are full. Select and sell a weapon first.') end
    free:SetAttribute('BasePrice',entry.basePrice);free:SetAttribute('FinalPurchasePrice',o.price);free:SetAttribute('PurchasePrice',o.price)
    free:SetAttribute('Tier',entry.tier);free:SetAttribute('WavePurchased',S.wave);free:SetAttribute('CopyId',token());free:SetAttribute('WeaponId',entry.weaponId)
   else
    local existing
    for _,it in s.items do if it.id==entry.id then existing=it end end
    if existing and existing.count>=entry.cap then return fail('Item copy limit reached') end
    if not existing and #s.items>=E.ITEM_CAPACITY then return fail('Item inventory full') end
    if existing then existing.count+=1 else table.insert(s.items,{id=entry.id,count=1}) end
   end
   s.gold-=o.price;o.sold=true;o.locked=false
   S.bonuses(p)
  end
 elseif action=='Reroll' then
  local available=false;for _,o in s.offers do if not o.locked or o.sold then available=true end end
  if not available then return fail('Unlock an offer before rerolling') end
  local price=E.reroll(S.wave,s.rerolls);if s.gold<price then return fail('Not enough gold to reroll') end
  s.gold-=price;s.rerolls+=1
  for i,o in s.offers do if not o.locked or o.sold then s.offers[i]=roll(p,o.id) end end
 elseif action=='Sell' then
  if not E.integer(arg,1,6) then return fail('Invalid weapon slot') end
  local f=slots(p)['Slot'..arg]
  if f:GetAttribute('WeaponId')=='' or f:GetAttribute('CopyId')~=extra then return fail('Weapon changed; select it again') end
  s.gold=math.min(E.MAX_GOLD,s.gold+E.refund(f:GetAttribute('FinalPurchasePrice') or 0))
  f:SetAttribute('WeaponId','');f:SetAttribute('CopyId',token());f:SetAttribute('FinalPurchasePrice',0);f:SetAttribute('PurchasePrice',0);f:SetAttribute('BasePrice',0);f:SetAttribute('Tier',1);f:SetAttribute('WavePurchased',0)
 elseif action=='Start' then s.ready=true
 else return fail('Unknown shop action') end
 if action~='Start' then s.ready=false end
 local count=0;for i=1,6 do if slots(p)['Slot'..i]:GetAttribute('WeaponId')~='' then count+=1 end end;slots(p):SetAttribute('EquippedCount',count)
 s.revision+=1;reprice(p);S.publish(p,action=='Start' and 'Ready · waiting for other living players' or '')
 if action=='Start' then beginWave() end
 return true
end
remote.OnServerEvent:Connect(S.request)
Characters.onStatsChanged=function(p) if S.states[p] then reprice(p);S.states[p].revision+=1;S.publish(p) end end
Characters.onKill=function(p)
 local s=S.states[p];if s and S.phase=='Combat' then s.gold=math.min(E.MAX_GOLD,s.gold+E.KILL_GOLD);S.publish(p) end
end
Players.PlayerRemoving:Connect(function(p) S.states[p]=nil;task.defer(beginWave) end)
local elapsed=0
RunService.Heartbeat:Connect(function(dt)
 elapsed+=dt;if elapsed<.2 then return end;elapsed=0
 if S.phase=='Shop' then beginWave() end
 if S.phase=='Combat' and workspace:GetServerTimeNow()>=(run:GetAttribute('WaveEndsAt') or math.huge) then S.finishWave() end
end)
return S
