-- Server-only authoritative character builds, practice controls and health economy.
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local Tags=game:GetService('CollectionService')
local combat=game.ReplicatedStorage:WaitForChild('RogueliteCombat')
local Stats=require(combat:WaitForChild('CharacterStats'))
local EnemyCatalog=require(combat:WaitForChild('EnemyCatalog'))
local Skills=require(combat:WaitForChild('SkillTreeConfig'))
local Admin=require(combat:WaitForChild('AdminConfig')) -- sandboxed, like this module
local Pets=require(combat:WaitForChild('PetConfig')) -- sandboxed pet data (PetService runs the abilities)
local playerDamaged=combat:FindFirstChild('PlayerDamaged')
if not playerDamaged then
 playerDamaged=Instance.new('RemoteEvent');playerDamaged.Name='PlayerDamaged'
 playerDamaged.Sandboxed=true
 playerDamaged.Capabilities=SecurityCapabilities.new(Enum.SecurityCapability.Basic,Enum.SecurityCapability.RemoteEvent)
 playerDamaged.Parent=combat
end
assert(playerDamaged:IsA('RemoteEvent'),'RogueliteCombat.PlayerDamaged must be a RemoteEvent')
workspace.Gravity=Stats.Movement.Gravity
local Catalog=require(combat:WaitForChild('WeaponCatalog'))
local Service={states={}}
-- Hooks. Notification hooks take any number of listeners: `Service.onDamaged=fn` adds one, so a
-- second script never silently replaces the first, whatever order they load in. Answer hooks
-- (onPracticeBoss, onPracticeEmeralds) return a result, keep one owner and warn on a takeover.
local hookListeners={onStatsChanged={},onPetShieldPop={},onThorns={},onDamaged={}}
local answerHooks={onPracticeBoss=true,onPracticeEmeralds=true}
setmetatable(Service,{__newindex=function(t,k,v)
 if hookListeners[k] then table.insert(hookListeners[k],v);return end
 if answerHooks[k] and rawget(t,k)~=nil and v~=nil then warn('CharacterService.'..k..' was replaced by a second owner') end
 rawset(t,k,v)
end})
local function notify(name,...)
 for _,fn in hookListeners[name] do local ok,err=pcall(fn,...);if not ok then warn('CharacterService.'..name..' listener failed:',err) end end
end
-- Body bumps (walking into mobs): one mob bumps a player at most every BUMP_GRACE seconds, and the
-- whole crowd at most every BUMP_CROWD_GAP. It was one bump per 0.6 s from all mobs together, so
-- crossing a crowd cost one or two bumps ("i can literally just walk through them", 2026-10-03).
-- Example, wave 1 zombies (bump 3): a half-second walk through a pack is ~3 bumps, ~8 HP after armor.
local BUMP_GRACE=.6
local BUMP_CROWD_GAP=.2
local function humanoid(player) return player.Character and player.Character:FindFirstChildOfClass('Humanoid') end
-- Enemy hits are judged from the player's own screen (2026-10-03). Measured in Studio Play: the
-- server sees a player's body 220 ms late, and the player sees the enemies 200 ms late. Kiting
-- at 22 studs/s from a zombie chasing at 12, the server's distance was ~7 studs shorter than the
-- one on screen, so hits landed after a dodge, on every kind of enemy (user: "if i triggered their
-- hit animation, they are going to hit me regardless if i move away"). So each client reports
-- where its body is (PlayerView, 30 a second, RogueliteCombat.client), and hits use
-- Service.seen(player) against Service.seenEnemy(player, root): where that enemy was on their
-- screen. A report is used only while fresh and near the body here, so it can't carry a player
-- far from where the server has them.
local VIEW_DELAY=.2 -- seconds an enemy shows late on a client (measured 190-205 ms), plus half the ping
local REPORT_FRESH=.3
-- The remote is a Studio instance (RogueliteCombat.PlayerView, an UnreliableRemoteEvent): this
-- sandboxed module may not make one (setting its Sandboxed flag needs CapabilityControl; trying it
-- on 2026-10-03 stopped this module loading, and every script that needs it). Without it, hits
-- use the bodies here, as before.
local reports=setmetatable({},{__mode='k'}) -- player -> {position, at}
local function listen(view)
 view.OnServerEvent:Connect(function(player,position)
  if typeof(position)~='Vector3' or position~=position or position.Magnitude>1e6 then return end
  reports[player]={position=position,at=workspace:GetServerTimeNow()}
 end)
end
local view=combat:FindFirstChild('PlayerView')
if view then listen(view)
elseif combat.ChildAdded then
 local added;added=combat.ChildAdded:Connect(function(c) if c.Name=='PlayerView' then added:Disconnect();listen(c) end end)
end
-- Where `player`'s body is on their own screen: their latest report while it's fresh and within
-- reach of their body here (the server is about their speed x 0.25 s behind), else their body here.
function Service.seen(player,root)
 root=root or (player.Character and player.Character:FindFirstChild('HumanoidRootPart'))
 if not root then return nil end
 local r=reports[player];local here=root.Position
 if r and workspace:GetServerTimeNow()-r.at<REPORT_FRESH then
  local h=humanoid(player);local speed=math.max(h and h.WalkSpeed or 16,16)
  -- For 0.6 s after an approved dash (DashAt, RogueliteMeta) their screen runs up to its length
  -- ahead of the body here, so dashing out of a swing dodges it.
  local dashAt=player:GetAttribute('DashAt')
  local dash=type(dashAt)=='number' and workspace:GetServerTimeNow()-dashAt<.6 and Stats.Dash.Distance or 0
  if (r.position-here).Magnitude<=3+speed*.35+dash then return r.position end
 end
 return here
end
-- Where an enemy (its root) is on `player`'s screen: moved back along its ground velocity by the
-- view delay. Example: a zombie walking at 12 studs/s shows 2.4 studs behind where it is.
function Service.seenEnemy(player,enemyRoot)
 local v=enemyRoot.AssemblyLinearVelocity
 local ok,ping=pcall(player.GetNetworkPing,player)
 return enemyRoot.Position-Vector3.new(v.X,0,v.Z)*(VIEW_DELAY+math.min(.15,(ok and ping or 0)/2))
end
-- Between waves (run phase Shop) a player in the arena is out of play: nothing can damage them and
-- they can't walk or jump until the next wave starts. Players in the Studio lobby aren't in the run.
-- The run state is looked up, never waited on: ShopService creates it after requiring this module.
function Service.inShop(player)
 local run=game.ReplicatedStorage:FindFirstChild('RogueliteRunState')
 return run~=nil and run:GetAttribute('Phase')=='Shop' and player:GetAttribute('LobbyPreviewActive')~=true
end
-- Plan L: a paused run (RunPaused) holds players like the shop does and blocks their damage.
-- A boss entrance (CinematicUntil, BossService.INTRO) holds them the same way for its few seconds.
function Service.frozen(player)
 local held=combat:GetAttribute('RunPaused')==true or (combat:GetAttribute('CinematicUntil') or 0)>workspace:GetServerTimeNow()
 return held and player:GetAttribute('LobbyPreviewActive')~=true
end
-- The air bonus is the player's own client's to apply (RogueliteCombat.client), from the GroundSpeed
-- and AirSpeed set here: the server hears about a jump ~0.2 s late and its WalkSpeed change takes as
-- long to get back, so when it switched the speed itself the bonus missed most of a 0.7 s jump.
-- MovementGuard allows that speed. Always derived from the resolved stat; repeated jumps never stack.
local function applyMoveSpeed(h,s,character)
 h.UseJumpPower=false
 local ground=s.held and 0 or s.stats.MoveSpeed
 if character then character:SetAttribute('GroundSpeed',ground);character:SetAttribute('AirSpeed',ground*Stats.Movement.AirSpeedMultiplier) end
 if s.held then h.WalkSpeed=0;h.JumpHeight=0;return end
 h.JumpHeight=Stats.Movement.JumpHeight
 h.WalkSpeed=ground
end
function Service.refresh(player)
 local s=Service.states[player];if not s then return end
 local count=0
 for _,slot in s.folder:GetChildren() do local d=Catalog.ById[slot:GetAttribute('WeaponId')];if d and d.home==s.class then count+=1 end end
 -- Permanent skill-tree bonuses join the run's item bonuses as flat terms. ProfileSkills is
 -- written only by ProfileService on the server, so clients cannot change it.
 local flat=s.itemBonuses
 local skills=Skills.bonuses(Skills.parse(player:GetAttribute('ProfileSkills')))
 -- Armor set bonuses (lobby and runs) from the server-set ProfileWearing/ProfileArmor, the same
 -- way. Perks are kept on the state: DodgeCrit, RageAttackSpeed, FireThorns, PhoenixBlast.
 local armor,perks=Stats.armorBonus(player:GetAttribute('ProfileWearing'),player:GetAttribute('ProfileArmor') or '')
 s.perks=perks
 -- Viking 4-piece: extra attack speed only while below half health (the HealthChanged hook in
 -- spawned refreshes when health crosses the line).
 local h0=humanoid(player)
 s.raging=perks.RageAttackSpeed~=nil and h0~=nil and h0.Health>0 and h0.Health<h0.MaxHealth*Stats.ArmorPerks.RageBelow
 if s.raging then armor.AttackSpeed=(armor.AttackSpeed or 0)+perks.RageAttackSpeed end
 -- The equipped pet's flat stat (PetConfig by id and tier, from the server-set ProfilePet and
 -- ProfilePets), plus a short pet bonus PetService sets (the Cheetah Cub's speed burst).
 local petId,petTier=Pets.equipped(player:GetAttribute('ProfilePet'),player:GetAttribute('ProfilePets'))
 local pet=petId and Pets.stats(petId,petTier) or {}
 for id,v in s.petTemp or {} do pet[id]=(pet[id] or 0)+v end
 flat=table.clone(s.itemBonuses or {})
 for id,v in skills do flat[id]=(flat[id] or 0)+v end
 for id,v in armor do flat[id]=(flat[id] or 0)+v end
 for id,v in pet do flat[id]=(flat[id] or 0)+v end
 -- Gear power (GEAR_POWER.md) from the starter's owned tier, worn armor and the pet: the GearPower
 -- stat, its damage share in CombatEffectsService.hit and its health share as a max-health percent,
 -- so it multiplies every other health bonus. An admin override of GearPower counts too.
 local weapon=player:GetAttribute('RunWeapon')
 flat.GearPower=Stats.gearPower(function(name) return player:GetAttribute(name) end,type(weapon)=='string' and weapon or Stats.Classes.Brawler.build[1])
 local power=s.overrides.GearPower or flat.GearPower
 local percent=table.clone(s.itemPercent or {})
 percent.MaxHP=(percent.MaxHP or 0)+(Stats.powerHealth(power)-1)*100
 s.stats=Stats.resolve(s.class,count,s.overrides,flat,percent)
 s.folder:SetAttribute('Class',s.class);s.folder:SetAttribute('AffinityCount',count)
 for _,d in Stats.List do
  local value=s.stats[d.id];s.folder:SetAttribute('Stat_'..d.id,value)
  s.folder:SetAttribute('Override_'..d.id,s.overrides[d.id]~=nil)
  if player.Character then player.Character:SetAttribute('Stat_'..d.id,value) end
 end
 local h=humanoid(player)
 if h then
  local missing=h.MaxHealth-h.Health;local alive=h.Health>0
  h.MaxHealth=s.stats.MaxHP;if alive then h.Health=math.clamp(h.MaxHealth-missing,1,h.MaxHealth) end
  applyMoveSpeed(h,s,player.Character)
  player.Character:SetAttribute('CombatClass',s.class)
 end
 notify('onStatsChanged',player)
end
function Service.attach(player,folder)
 local picked=player:GetAttribute('RunClass')
 local s={folder=folder,class=Stats.Classes[picked] and picked or 'Brawler',overrides={},lastRequest=-1e6,lastContact=0,lastBump=0,blocks=1,leech=0,hits=0}
 Service.states[player]=s
 local function spawned(character)
  local h=character:WaitForChild('Humanoid',10);if not h or player.Character~=character then return end
  s.leech=0;s.blocks=1;s.hits=0;s.lastContact=os.clock();s.lastBump=os.clock();s.dodgeCrit=nil
  s.petShield=0;s.petShieldUntil=0;player:SetAttribute('PetShieldUntil',nil)
  s.held=nil;s.holdAt=nil -- the next tick re-checks the shop hold for the new body
  Service.refresh(player);h.Health=h.MaxHealth
  if s.rageConnection then s.rageConnection:Disconnect() end
  s.rageConnection=h.HealthChanged:Connect(function(health)
   if player.Character~=character or Service.states[player]~=s or not (s.perks and s.perks.RageAttackSpeed) then return end
   if (health>0 and health<h.MaxHealth*Stats.ArmorPerks.RageBelow)~=(s.raging==true) then Service.refresh(player) end
  end)
  -- Disable Roblox's implicit regeneration: this game's Recovery/Regeneration own healing.
  local health=character:FindFirstChild('Health');if health and health:IsA('Script') then health.Disabled=true end
 end
 player.CharacterAdded:Connect(spawned)
 if player.Character then task.spawn(spawned,player.Character) end
 for _,slot in folder:GetChildren() do slot:GetAttributeChangedSignal('WeaponId'):Connect(function() Service.refresh(player) end) end
 player:GetAttributeChangedSignal('ProfileSkills'):Connect(function() Service.refresh(player) end)
 player:GetAttributeChangedSignal('ProfileWearing'):Connect(function() Service.refresh(player) end)
 player:GetAttributeChangedSignal('ProfileArmor'):Connect(function() Service.refresh(player) end)
 player:GetAttributeChangedSignal('ProfilePet'):Connect(function() Service.refresh(player) end)
 player:GetAttributeChangedSignal('ProfilePets'):Connect(function() Service.refresh(player) end)
 -- Gear power follows the starter and its owned tier.
 player:GetAttributeChangedSignal('ProfileWeapons'):Connect(function() Service.refresh(player) end)
 player:GetAttributeChangedSignal('RunWeapon'):Connect(function() Service.refresh(player) end)
 Service.refresh(player)
end
-- The class from the player's validated loadout (RunClass). Developer stat overrides stay until clearAdmin.
function Service.setClass(player,class)
 local s=Service.states[player]
 if not s or type(class)~='string' or not Stats.Classes[class] or s.class==class then return end
 s.class=class;Service.refresh(player)
end
-- A new run starts clean (ShopService.resetRun): admin stat edits, class picks, god mode and the
-- Weapons off toggle never carry into a run that pays rewards. Normal play has nothing to clear.
-- The caller refreshes.
function Service.clearAdmin(player)
 local s=Service.states[player];if not s then return end
 s.overrides={}
 local picked=player:GetAttribute('RunClass');s.class=Stats.Classes[picked] and picked or 'Brawler'
 player:SetAttribute('AdminGod',nil)
 s.folder:SetAttribute('WeaponEnabled',true)
end
-- Pet hooks (PetService). setPetTemp: a short flat bonus like {MoveSpeed=6}, nil clears it.
-- givePetShield: one blocked hit for `duration` s (checked before FirstHitBlock; refreshing only
-- resets the timer, it never stacks). The player attribute PetShieldUntil (server time) lets
-- clients draw the bubble.
function Service.setPetTemp(player,bonus)
 local s=Service.states[player];if not s then return end
 s.petTemp=bonus;Service.refresh(player)
end
function Service.givePetShield(player,duration)
 local s=Service.states[player];local h=humanoid(player)
 if not s or not h or h.Health<=0 then return false end
 s.petShield=1;s.petShieldUntil=os.clock()+duration
 player:SetAttribute('PetShieldUntil',workspace:GetServerTimeNow()+duration)
 return true
end
function Service.hasPetShield(player)
 local s=Service.states[player]
 return s~=nil and (s.petShield or 0)>0 and os.clock()<(s.petShieldUntil or 0)
end
function Service.heal(player,amount)
 local s=Service.states[player];local h=humanoid(player)
 if s and h and h.Health>0 then h.Health=math.min(h.MaxHealth,h.Health+math.max(0,amount)*Stats.mult(s.stats.Recovery)) end
end
function Service.leech(player,damage)
 local s=Service.states[player];if not s then return end
 local h=humanoid(player);if not h or h.Health<=0 then return end
 local heal=math.min(damage*s.stats.LifeSteal/100*Stats.mult(s.stats.Recovery),math.max(0,s.stats.LifeStealCap-s.leech))
 s.leech+=heal;h.Health=math.min(h.MaxHealth,h.Health+heal)
end
-- Flat healing that shares the life-steal cap (Vampire Blade hits and wisps, GodlyWeapons).
-- capBonus raises the cap for this heal only (the blade's Tier IV). Returns the HP healed.
function Service.leechFlat(player,amount,capBonus)
 local s=Service.states[player];if not s then return 0 end
 local h=humanoid(player);if not h or h.Health<=0 then return 0 end
 local heal=math.min(math.max(0,amount)*Stats.mult(s.stats.Recovery),math.max(0,s.stats.LifeStealCap+(capBonus or 0)-s.leech))
 s.leech+=heal;h.Health=math.min(h.MaxHealth,h.Health+heal)
 return heal
end
-- attacker: the zombie whose melee hit this is (body contact, swing, slam); nil for projectiles
-- and other sources. It is only used for the Dragon Scale fire thorns.
function Service.contact(player,amount,roll,attacker)
 local s=Service.states[player];local h=humanoid(player)
 -- Admin god mode (AdminGod, set only by AdminService) and the between-wave shop: no damage from
 -- any source. Every player damage path (contact, enemy melee and projectiles, zombie slams, the
 -- boss) comes through here.
 if not s or not h or h.Health<=0 or player.Character:FindFirstChildOfClass('ForceField') or player:GetAttribute('AdminGod')==true or Service.inShop(player) or Service.frozen(player) then return 0 end
 -- Dash i-frames (CharacterStats.Dash.IFrames, 0.35 s from the server's DashAt stamp): every hit in
 -- that window misses, so dashing through a swing or a crowd is safe.
 local dashAt=player:GetAttribute('DashAt')
 if type(dashAt)=='number' and Stats.Dash and workspace:GetServerTimeNow()-dashAt<(Stats.Dash.IFrames or 0) then return 0 end
 -- A pet shell shield (Turtle) blocks the next hit first, then pops.
 if Service.hasPetShield(player) then
  s.petShield=0;s.petShieldUntil=0;player:SetAttribute('PetShieldUntil',nil)
  notify('onPetShieldPop',player)
  return 0
 end
 if s.stats.FirstHitBlock>0 and s.blocks>0 then s.blocks-=1;s.folder:SetAttribute('BlocksRemaining',s.blocks);return 0 end
 if (roll or math.random())<s.stats.Dodge/100 then
  -- Ninja 4-piece: the next direct hit is a guaranteed crit (CombatEffectsService.hit uses it up).
  if s.perks and s.perks.DodgeCrit then s.dodgeCrit=true end
  return 0
 end
 local before=h.Health;local incoming=Stats.incoming(amount,s.stats)
 -- The tutorial (TutorialRun): hits still land and show, but health never goes below 1.
 if combat:GetAttribute('TutorialRun')==true then incoming=math.min(incoming,math.max(0,h.Health-1)) end
 h:TakeDamage(incoming);local actual=before-h.Health
 -- Only the damaged player needs this feedback. The server supplies actual health
 -- lost after armor and health clamping; clients never submit damage values.
 if actual>0 then playerDamaged:FireClient(player,actual) end
 -- Dragon Scale 4-piece fire thorns: a chance to set the attacking zombie on fire (normal burn,
 -- applied by CombatEffectsService through onThorns).
 local thorns=s.perks and s.perks.FireThorns
 if actual>0 and thorns and typeof(attacker)=='Instance' and #hookListeners.onThorns>0 and math.random()<thorns/100 then notify('onThorns',player,attacker) end
 -- Pets react to real damage (the Cheetah Cub's speed burst); analytics remembers the attacker
 -- (nil for projectiles and boss attacks) as a death cause.
 if actual>0 then notify('onDamaged',player,actual,attacker) end
 return actual
end
local remote=combat:FindFirstChild('EditPractice') or Instance.new('RemoteEvent')
remote.Name='EditPractice';remote.Parent=combat
function Service.request(player,action,key,value)
 local s=Service.states[player];local h=humanoid(player);local run=game.ReplicatedStorage:FindFirstChild('RogueliteRunState')
 -- Developer controls (the ADMIN panel's Player tab), usable during combat. Checked by UserId on
 -- every request (AdminConfig), in Studio and on live servers; everyone else gets nothing.
 if not Admin.isAdmin(player) or not s or not h or h.Health<=0 then return false end
 if type(action)~='string' or type(key)=='table' or os.clock()-s.lastRequest<.08 then return false end
 if action=='Stat' then
  if type(key)~='string' or not Stats.valid(key,value) then return false end
  s.overrides[key]=value;Service.refresh(player)
 elseif action=='Class' then
  if type(key)~='string' or not Stats.Classes[key] then return false end
  s.class=key;s.overrides={};Service.refresh(player)
 elseif action=='Build' then
  if run and run:GetAttribute('Phase')~='Practice' then return false end
  local preset=Stats.Classes[s.class].build
  for index,id in preset do if not combat.WeaponTemplates:FindFirstChild(id) then return false end end
  for i=1,6 do
   local slot=s.folder:FindFirstChild('Slot'..i);slot:SetAttribute('WeaponId',preset[i] or '');slot:SetAttribute('Attack',nil) -- the packed attack (ShotBatch.packAttack)
  end
  s.folder:SetAttribute('EquippedCount',#preset);Service.refresh(player)
 elseif action=='Reset' then s.overrides={};Service.refresh(player)
 elseif action=='Heal' then h.Health=h.MaxHealth
 elseif action=='Damage' then Service.contact(player,20)
 elseif action=='Zombies' then
  if type(value)~='number' or value~=value or value%1~=0 or value<0 or value>100 then return false end
  combat:SetAttribute('ZombieCount',value)
  combat:SetAttribute('TestZombieCountOverride',value)
 elseif action=='AutoZombies' then combat:SetAttribute('TestZombieCountOverride',nil)
 elseif action=='Roster' then
  -- Developer mob picker (the remote checks Admin.isAdmin): known catalog IDs only; empty restores the normal wave mix.
  if key~=nil or type(value)~='string' or #value>600 then return false end
  local ids,seen={},{}
  for id in value:gmatch('[^,%s]+') do
   if not EnemyCatalog.ById[id] then return false end
   if not seen[id] then seen[id]=true;table.insert(ids,id) end
  end
  combat:SetAttribute('EnemyRoster',#ids>0 and table.concat(ids,',') or nil)
 elseif action=='SpawnBoss' or action=='RemoveBoss' then
  if key~=nil or value~=nil then return false end
  if not Service.onPracticeBoss or not Service.onPracticeBoss(player,action) then return false end
 elseif action=='Emeralds' then
  -- Developer admin grant (saved profile currency on a live server, in-memory in Studio). key: 'Add' | 'Set'.
  if (key~='Add' and key~='Set') or type(value)~='number' or value~=value or value%1~=0 then return false end
  if (key=='Add' and math.abs(value)>1e6) or (key=='Set' and (value<0 or value>1e7)) then return false end
  if not Service.onPracticeEmeralds or not Service.onPracticeEmeralds(player,key,value) then return false end
 else return false end
 s.lastRequest=os.clock();s.folder:SetAttribute('PracticeRevision',(s.folder:GetAttribute('PracticeRevision') or 0)+1)
 Admin.markTestRun()
 return true
end
remote.OnServerEvent:Connect(function(...) Service.request(...) end)
Players.PlayerRemoving:Connect(function(p)
 local s=Service.states[p]
 if s and s.rageConnection then s.rageConnection:Disconnect() end
 Service.states[p]=nil
end)
-- Body contact (launch audit P10). Each player used to look up every enemy's parts and five
-- attributes 10 times a second: ~18,000 calls a second with 4 players and 65 enemies. Now each
-- enemy's parts and contact numbers are read once (they are set at spawn, before the tag; a
-- change to one drops the record), the tick reads each enemy's position once for all players,
-- and nobody is checked while both of their contact timers are still running. The same enemy
-- is picked as before: the first in tag order in range with a clear line.
local CONTACT_ATTRIBUTES={'ContactDamage','ContactRange','BumpDamage','BumpRange','PracticeTarget'}
local contactRecords=setmetatable({},{__mode='k'})
local watched=setmetatable({},{__mode='k'})
local function contactRecord(npc)
 local r=contactRecords[npc];if r then return r end
 local nr=npc:FindFirstChild('HumanoidRootPart');local nh=npc:FindFirstChildOfClass('Humanoid')
 if not nr or not nh then return nil end -- looked for again next tick
 if not watched[npc] then
  watched[npc]=true
  for _,name in CONTACT_ATTRIBUTES do npc:GetAttributeChangedSignal(name):Connect(function() contactRecords[npc]=nil end) end
 end
 -- Old proximity mobs (ContactDamage > 0) keep their 0.8 s contact timer. Wave mobs set
 -- ContactDamage 0 (their swings own damage) and hurt through BumpDamage/BumpRange instead.
 local damage=npc:GetAttribute('ContactDamage') or 10
 local range=npc:GetAttribute('ContactRange') or 4.5
 local bump=damage<=0
 if bump then damage=npc:GetAttribute('BumpDamage') or 0;range=npc:GetAttribute('BumpRange') or 0 end
 r={root=nr,hum=nh,damage=damage,range=range,bump=bump,practice=npc:GetAttribute('PracticeTarget')}
 contactRecords[npc]=r
 return r
end
-- This tick's enemies that can hurt by contact, in tag order (npcs[i] has records[i]), each
-- record with the enemy's position now.
local function contactList()
 local npcs,records={},{}
 for _,npc in Tags:GetTagged('RogueliteZombie') do
  local r=contactRecord(npc)
  if r and r.damage>0 and not r.practice then r.position=r.root.Position;npcs[#npcs+1]=npc;records[#records+1]=r end
 end
 return {npcs=npcs,records=records}
end
-- The point of the path a->b nearest p, measured on the ground (bumps sweep the path, below).
function Service.nearestOnPath(a,b,p)
 local ab=Vector3.new(b.X-a.X,0,b.Z-a.Z);local len=ab:Dot(ab)
 if len<1e-6 then return b end
 return a+(b-a)*math.clamp(Vector3.new(p.X-a.X,0,p.Z-a.Z):Dot(ab)/len,0,1)
end
local elapsed=0
RunService.Heartbeat:Connect(function(dt)
 elapsed+=dt;if elapsed<.1 then return end;local step=elapsed;elapsed=0
 local now=os.clock()
 local contacts -- built for the first player who can be hit this tick
 for player,s in Service.states do
  local h=humanoid(player);local root=player.Character and player.Character:FindFirstChild('HumanoidRootPart')
  if h and root and h.Health>0 then
   -- Shop hold: stand still from the moment the shop opens until the next wave starts. Anyone who
   -- still drifts a few studs is put back. A long jump is a server move (travel, respawn), so the
   -- hold starts again from there.
   local held=Service.inShop(player) or Service.frozen(player)
   if held~=(s.held==true) then s.held=held;s.holdAt=held and root.Position or nil;applyMoveSpeed(h,s,player.Character) end
   if held and s.holdAt then
    local drift=root.Position-s.holdAt;local flat=Vector2.new(drift.X,drift.Z).Magnitude
    if flat>25 then s.holdAt=root.Position
    elseif flat>3 then player.Character:PivotTo(CFrame.new(s.holdAt)*root.CFrame.Rotation) end
   end
   if not Service.frozen(player) then Service.heal(player,s.stats.Regeneration*step) end
   local second=math.floor(now);if s.leechSecond~=second then s.leechSecond=second;s.leech=0 end
   -- Body overlap only (contactRecord above): each mob once per BUMP_GRACE, the crowd once per
   -- BUMP_CROWD_GAP (one bump a check at most). It
   -- tests the player's path since the last check, as their screen has it (Service.seen), not
   -- just where they are now: a sprint covers ~2.4 studs between checks, and running straight
   -- through a zombie fell between two of them (user, 2026-10-03). A path is one check long
   -- (under 0.25 s and 10 studs); anything else starts over from here.
   local position=Service.seen(player,root)
   local from=s.pathFrom
   if not from or now-(s.pathAt or 0)>.25 or (position-from).Magnitude>10 then from=position end
   s.pathFrom,s.pathAt=position,now
   local bumpReady,contactReady=now-s.lastBump>=BUMP_CROWD_GAP,now-s.lastContact>=.8
   if (bumpReady or contactReady) and combat:GetAttribute('ZombiesEnabled') and combat:GetAttribute('RunPaused')~=true then
    contacts=contacts or contactList()
    local bumped=s.bumped;if not bumped then bumped=setmetatable({},{__mode='k'});s.bumped=bumped end -- mob -> its last bump
    for i,r in contacts.records do
     local npc=contacts.npcs[i]
     local ready=if r.bump then bumpReady and now-(bumped[npc] or -math.huge)>=BUMP_GRACE else contactReady
     local enemy=ready and (r.root.Parent and Service.seenEnemy(player,r.root) or r.position)
     local touch=ready and Service.nearestOnPath(from,position,enemy)
     local delta=ready and touch-enemy
     if ready and math.abs(delta.Y)<4.5 and Vector2.new(delta.X,delta.Z).Magnitude<r.range and r.root.Parent==npc and r.hum.Health>0 then
      local params=RaycastParams.new();params.FilterType=Enum.RaycastFilterType.Exclude;params.FilterDescendantsInstances={npc,player.Character,workspace:FindFirstChild('RogueliteEnemies')}
      if not workspace:Raycast(r.position,touch-r.position,params) then
       if r.bump then s.lastBump=now;bumped[npc]=now else s.lastContact=now end
       Service.contact(player,r.damage,nil,npc);break
      end
     end
    end
   end
  end
 end
end)
local function resetBlocks() for _,s in Service.states do s.blocks=1;s.folder:SetAttribute('BlocksRemaining',1) end end
combat:GetAttributeChangedSignal('ZombieCount'):Connect(resetBlocks)
combat:GetAttributeChangedSignal('ZombiesEnabled'):Connect(resetBlocks)
return Service
