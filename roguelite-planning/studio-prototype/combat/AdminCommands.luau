-- Admin chat commands and the Give tab's catalog (2026-10-12, user: "/tempgive user item copies
-- tier ... /give user item ... /god user ... /pause ... what i need to use in arenas so i can give my
-- friends loadouts, pause the game"). Pure: no requires, no Instances. The admin client makes the
-- TextChatCommands and the Give tab from it; AdminService parses and runs the text again itself,
-- so nothing the client sends is trusted. AdminCommandTests checks it offline.
-- Studio: ReplicatedStorage.RogueliteCombat.AdminCommands, Sandboxed = true with CharacterStats'
-- Capabilities (it requires nothing, so any caller may require it).
--   /tempgive <player> <item> [slot] [tier]  this run only. A weapon goes in weapon slot 1-6 (replacing
--                                            what is there), or the next free slot when no slot is
--                                            given. Default Tier I. Run items and turrets have no
--                                            slot: one more copy, and a lone number is the tier
--                                            (for turrets, which turret).
--   /give <player> <item> [tier]             saved for good: weapon, armor piece or set, pet, class
--   /armor <player> <set> [tier] | off       this run only: wears the whole set (visuals, set bonus,
--                                            gear power); their saved armor is untouched and comes
--                                            back in the lobby. Tier left out: the tiers they own.
--   /god [player] [on|off]                   toggles when on/off is left out
--   /ghost [player] [on|off]                 invisible, ignored by every enemy, never hit, weapons
--                                            off (filming with Freecam); toggles like /god
--   /pause                                   holds the wave clock and spawns and freezes every enemy
--   /resume                                  lets them all go again
--   /wave <1-20>                             starts that wave now; paused stays paused
--   /admin                                   this list
-- <player>: me, all, others, or a name or display name (the start is enough when only one fits).
-- <item>: a name, any words of it run together or spaced ("frying pan", "fryingpan", "pan").
-- Example (2026-10-13, user: "not based off copies ... based off of inventory slot"): "/tempgive bob
-- katana 2 3" -> a Tier III Katana in Bob's weapon slot 2; "/tempgive bob katana" -> Tier I in his
-- next free slot; "/tempgive me turret 4" -> a Gatling Rig; "/armor bob dragonscale 4".
-- Tab completion (2026-10-13, user: "if i tab on /armor all _ it will type dragon and if i tab again
-- it will cycle thru the sets ... wy is there spaces in dragon scale"): C.suggest lists what fits the
-- word being typed. Every catalog entry has a one-word `token` ('dragonscale', 'fryingpan') that
-- C.find resolves exactly, so completed commands never hold spaces. Roblox's own chat box can't be
-- read by games, so the admin command bar (;) and the Give tab's box do the completing.
local C={}
-- /pause, /resume and /wave (2026-10-13, user: "pause and set up everyone and then resume and then a
-- /wave number that changes the wave to that").
C.Names={'tempgive','give','armor','god','ghost','pause','resume','wave','admin'}
C.MAX_WAVE=20
C.HELP='/tempgive <player> <item> [slot] [tier] · /give <player> <item> [tier] · /armor <player> <set> [tier] (or off) · /god [player] [on|off] · /ghost [player] [on|off] · /pause · /resume · /wave <1-20>. Player: me, all, others or a name.'
C.SLOTS=6
C.MAX_TEXT=200
-- One line per command for the suggestion list.
C.Usage={tempgive='<player> <item> [slot] [tier] · this run',give='<player> <item> [tier] · saved',armor='<player> <set> [tier] | off · this run',
 god='[player] [on|off]',ghost='[player] [on|off] · invisible, ignored by enemies',pause='hold the clock, spawns and enemies',resume='let them go again',wave='<1-20> · start that wave now',admin='list the commands'}
-- 'Frying Pan!' -> 'fryingpan'.
function C.norm(s) return (string.gsub(string.lower(tostring(s or '')),'[^%w]','')) end
local function words(text) local out={};for w in string.gmatch(text,'%S+') do table.insert(out,w) end;return out end
local function whole(s,lo,hi) local n=tonumber(s);return n and n==math.floor(n) and n>=lo and n<=hi and n or nil end
local ROMAN={i=1,ii=2,iii=3,iv=4}
-- A tier word: 't3', 'tier3' or 'iii' -> 3; anything else nil.
local function tierWord(s)
 s=string.lower(s)
 local n=string.match(s,'^tier([1-4])$') or string.match(s,'^t([1-4])$')
 return n and tonumber(n) or ROMAN[s]
end
local SWITCH={on=true,off=false,['true']=true,['false']=false}

-- text -> {name, player, item, slot, tier, on, off} or nil, reason. Checks the shape only; AdminService
-- finds the player and the item. Example: '/give me katana 4' -> {name='give', player='me',
-- item='katana', tier=4}.
function C.parse(text)
 if type(text)~='string' or #text>C.MAX_TEXT then return nil,'Command too long' end
 local w=words(text)
 local name=w[1] and string.lower(string.gsub(w[1],'^/','')) or ''
 if not table.find(C.Names,name) then return nil,'Unknown command. '..C.HELP end
 local args={table.unpack(w,2)}
 local cmd={name=name}
 if name=='admin' then return cmd end
 if name=='pause' or name=='resume' then
  if #args>0 then return nil,'Usage: /'..name end
  return cmd
 end
 if name=='wave' then
  cmd.wave=#args==1 and whole(args[1],1,C.MAX_WAVE) or nil
  if not cmd.wave then return nil,'Usage: /wave <1-'..C.MAX_WAVE..'>' end
  return cmd
 end
 if name=='god' or name=='ghost' then
  local last=args[#args] and SWITCH[string.lower(args[#args])]
  if last~=nil then cmd.on=last;table.remove(args) end
  if #args>1 then return nil,'Usage: /'..name..' [player] [on|off]' end
  cmd.player=args[1] or 'me'
  return cmd
 end
 -- tempgive / give / armor: <player> <item words...> then trailing numbers.
 local usage={tempgive='Usage: /tempgive <player> <item> [slot] [tier]',give='Usage: /give <player> <item> [tier]',armor='Usage: /armor <player> <set> [tier] (or off)'}
 if #args<2 then return nil,usage[name] end
 cmd.player=table.remove(args,1)
 if name=='armor' and #args==1 and string.lower(args[1])=='off' then cmd.off=true;return cmd end
 if name=='tempgive' then
  -- Up to two trailing numbers: slot then tier. A tier word ('t3', 'iii') may end it instead.
  -- AdminService reads a lone number as the tier for run items and turrets (they have no slot).
  local n=#args
  if n>=2 and tierWord(args[n]) then cmd.tier=tierWord(args[n]);table.remove(args);n-=1 end
  if n>=2 and tonumber(args[n]) then
   if not cmd.tier and n>=3 and tonumber(args[n-1]) then
    cmd.tier=whole(args[n],1,4);if not cmd.tier then return nil,'Tier must be 1-4' end
    table.remove(args);n-=1
   end
   cmd.slot=whole(args[n],1,C.SLOTS);if not cmd.slot then return nil,'Slot must be 1-'..C.SLOTS end
   table.remove(args)
  end
 else
  local n=#args
  if n>=2 and (tonumber(args[n]) or tierWord(args[n])) then
   cmd.tier=whole(args[n],1,4) or tierWord(args[n]);if not cmd.tier then return nil,'Tier must be 1-4' end
   table.remove(args)
  end
 end
 if #args==0 then return nil,'Name an item' end
 cmd.item=table.concat(args,' ')
 return cmd
end

-- The Give catalog: one list for the panel's grid and the commands' item search, built from the
-- catalogs passed in (m.Weapons, m.Items = ShopCatalog, m.Armor, m.Pets, m.Classes = class names in
-- order, m.Signature = class -> weapon id, m.WeaponIcons = weapon id -> image, m.TurretTier = item
-- id -> tier). Each entry: {key, id, name, kind, icon, temp (this run), perm (saved)}. Keys:
-- 'w:<weapon id>', 'i:<item id>', 'a:<Set.Slot>', 's:<set id>', 'p:<pet id>', 'c:<class>'.
C.Kinds={'Weapon','Item','Turret','Armor','Pet','Class'}
function C.entries(m)
 local out={}
 -- token: the one word a command uses for it. Names for weapons, items, turrets and pets
 -- ('fryingpan'); ids for armor and classes ('dragonscale', 'ironhelmet', 'chef').
 local function add(e)
  e.norm=C.norm(e.name);e.idNorm=C.norm(e.id)
  e.token=(e.kind=='Armor' or e.kind=='Class') and e.idNorm or e.norm
  table.insert(out,e)
 end
 for _,w in m.Weapons and m.Weapons.List or {} do
  add({key='w:'..w.id,id=w.id,name=w.name,kind='Weapon',icon=(m.WeaponIcons or {})[w.id],temp=true,perm=true,godly=w.godly==true})
 end
 for _,e in m.Items and m.Items.List or {} do
  if e.kind~='Weapon' then add({key='i:'..e.id,id=e.id,name=e.name,kind=e.turret and 'Turret' or 'Item',icon=e.icon,temp=true,perm=false,tier=e.turret}) end
 end
 for _,s in m.Armor and m.Armor.Sets or {} do
  add({key='s:'..s.id,id=s.id,name=s.name..' Set',kind='Armor',icon=(m.Armor.Icons or {})[s.id..'.Chest'],perm=true,set=true})
  for _,slot in m.Armor.Slots or {} do
   local id=s.id..'.'..slot
   add({key='a:'..id,id=id,name=s.name..' '..slot,kind='Armor',icon=(m.Armor.Icons or {})[id],perm=true})
  end
 end
 for _,d in m.Pets and m.Pets.List or {} do
  add({key='p:'..d.id,id=d.id,name=d.name or d.id,kind='Pet',icon=(m.Pets.Icons or {})[d.id],perm=true})
 end
 for _,class in m.Classes or {} do
  add({key='c:'..class,id=class,name=class..' Class',kind='Class',icon=(m.WeaponIcons or {})[(m.Signature or {})[class] or ''],perm=true})
 end
 return out
end
-- The entry for `query` among those `mode` ('temp' or 'perm') allows, or nil and a reason. Best
-- first: exact name, id or key; then a whole word of the name; then names starting with it; then
-- names containing it. For a turret, `tier` picks which turret ("turret" at Tier III: Quad Nailer). Example: 'pan' ->
-- Frying Pan (a whole word), not Pandora's Box; 'iron' -> Iron Set.
function C.find(entries,query,mode,tier)
 local q=C.norm(query);if q=='' then return nil,'Name an item' end
 -- mode 'armor': whole sets only (/armor).
 local function allowed(e) return (mode=='temp' and e.temp) or (mode=='perm' and e.perm) or (mode=='armor' and e.set) or (mode==nil) end
 local exact,word,starts,contains={},{},{},{}
 local function hasWord(e) for w in string.gmatch(string.lower(e.name),"[%w']+") do if C.norm(w)==q then return true end end;return false end
 for _,e in entries do
  if allowed(e) then
   if e.norm==q or e.idNorm==q or C.norm(e.key)==q then table.insert(exact,e)
   elseif hasWord(e) then table.insert(word,e)
   elseif string.sub(e.norm,1,#q)==q then table.insert(starts,e)
   elseif string.find(e.norm,q,1,true) then table.insert(contains,e) end
  end
 end
 -- A turret's tier is which turret it is: "turret" at Tier III is the Quad Nailer.
 local function turretTier(e)
  if not (tier and e.kind=='Turret' and e.tier~=tier) then return e end
  for _,other in entries do if other.kind=='Turret' and other.tier==tier and allowed(other) then return other end end
  return e
 end
 for _,list in {exact,word,starts,contains} do
  if #list==1 then return turretTier(list[1]) end
  if #list>1 then
   if tier then for _,e in list do if e.kind=='Turret' and e.tier==tier then return e end end end
   -- A whole armor set wins over its pieces ("iron" -> Iron Set when the set is among them).
   for _,e in list do if e.set and C.norm(string.gsub(e.name,' Set$',''))==q then return e end end
   local names={};for i=1,math.min(5,#list) do names[i]=list[i].name end
   return nil,'Did you mean: '..table.concat(names,', ')..(#list>5 and ', ...' or '')
  end
 end
 return nil,'No '..(mode=='perm' and 'saved item' or mode=='temp' and 'run item' or mode=='armor' and 'armor set' or 'item')..' called "'..query..'"'
end
-- Suggestions for the word being typed at the end of `text` (Tab completion). ctx: {entries =
-- C.entries(...), players = {{name, display}}}. Returns {before (the text up to that word), partial
-- (the word so far), options = {{token, label}}}: tokens starting with the word, or when none
-- does, ones whose label contains it. Example: '/armor all ' -> before '/armor all ', options off, iron, ninja,
-- ..., dragonscale; '/armor all dr' -> dragonscale; '/tempgive me katana ' -> slots 1-6.
local ROMAN_OF={'I','II','III','IV'}
function C.suggest(text,ctx)
 text=type(text)=='string' and string.gsub(text,'\t','') or ''
 ctx=ctx or {}
 local tokens=words(text)
 local open=text=='' or string.match(text,'%s$')~=nil
 local index=open and #tokens+1 or #tokens
 local partial=open and '' or tokens[#tokens]
 local before=string.sub(text,1,#text-#partial)
 local cmd=tokens[1] and string.lower((string.gsub(tokens[1],'^/',''))) or ''
 local all={}
 local function add(token,label) table.insert(all,{token=token,label=label or ''}) end
 local function players()
  add('me','yourself');add('all','everyone here');add('others','everyone but you')
  for _,p in ctx.players or {} do add(p.name,p.display~=p.name and p.display or 'player') end
 end
 local function switch() add('on');add('off') end
 local function tiers() for t=1,4 do add(tostring(t),'Tier '..ROMAN_OF[t]) end end
 if index==1 then for _,n in C.Names do add('/'..n,C.Usage[n]) end
 elseif not table.find(C.Names,cmd) then
 elseif cmd=='pause' or cmd=='resume' then
 elseif cmd=='wave' then if index==2 then for n=1,C.MAX_WAVE do add(tostring(n),'wave '..n) end end
 elseif cmd=='god' or cmd=='ghost' then if index==2 then players();switch() elseif index==3 then switch() end
 elseif cmd~='admin' then
  if index==2 then players()
  elseif index==3 then
   if cmd=='armor' then add('off','back to their saved armor') end
   for _,e in ctx.entries or {} do
    if (cmd=='armor' and e.set) or (cmd=='tempgive' and e.temp) or (cmd=='give' and e.perm) then add(e.token,e.name..' · '..e.kind) end
   end
  elseif cmd=='tempgive' and index==4 then for n=1,C.SLOTS do add(tostring(n),'slot '..n..' (weapons) · tier for items') end
  elseif (cmd=='tempgive' and index==5) or ((cmd=='give' or cmd=='armor') and index==4) then tiers() end
 end
 local q=string.lower(partial)
 local starts,contains={},{}
 for _,o in all do
  if string.sub(string.lower(o.token),1,#q)==q then table.insert(starts,o)
  elseif q~='' and string.find(C.norm(o.label),C.norm(q),1,true) then table.insert(contains,o) end
 end
 return {before=before,partial=partial,options=#starts>0 and starts or contains}
end
-- The players `query` names. list: {name, display, userId, player}. me / all / others, else a
-- name or display name: exact first, then the only one starting with it. Example: 'bo' with Bob and
-- Bonnie -> nil, 'Bob or Bonnie?'.
function C.players(query,list,selfId)
 local q=string.lower(tostring(query or 'me'))
 local out={}
 if q=='me' then for _,p in list do if p.userId==selfId then table.insert(out,p) end end;return out end
 if q=='all' or q=='everyone' then return table.clone(list) end
 if q=='others' then for _,p in list do if p.userId~=selfId then table.insert(out,p) end end;return out end
 local starts={}
 for _,p in list do
  local n,d=string.lower(p.name),string.lower(p.display or p.name)
  if n==q or d==q then return {p} end
  if string.sub(n,1,#q)==q or string.sub(d,1,#q)==q then table.insert(starts,p) end
 end
 if #starts==1 then return starts end
 if #starts>1 then local names={};for i,p in starts do names[i]=p.name end;return nil,table.concat(names,' or ')..'?' end
 return nil,'No player called "'..tostring(query)..'"'
end
return C
