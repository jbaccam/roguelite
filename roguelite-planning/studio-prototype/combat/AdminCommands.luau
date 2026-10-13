-- Admin chat commands and the Give tab's catalog (2026-10-12, user: "/tempgive user item copies
-- tier ... /give user item ... /god user ... /pause ... what i need to use in arenas so i can give my
-- friends loadouts, pause the game"). Pure: no requires, no Instances. The admin client makes the
-- TextChatCommands and the Give tab from it; AdminService parses and runs the text again itself,
-- so nothing the client sends is trusted. AdminCommandTests checks it offline.
-- Studio: ReplicatedStorage.RogueliteCombat.AdminCommands, Sandboxed = true with CharacterStats'
-- Capabilities (it requires nothing, so any caller may require it).
--   /tempgive <player> <item> [copies] [tier]  this run only: weapons fill free slots, items and
--                                              turrets stack. Default 1 copy, Tier I.
--   /give <player> <item> [tier]               saved for good: weapon, armor piece or set, pet, class
--   /god [player] [on|off]                     toggles when on/off is left out
--   /pause [on|off]                            the wave clock, spawns and every enemy
--   /admin                                     this list
-- <player>: me, all, others, or a name or display name (the start is enough when only one fits).
-- <item>: a name, any words of it run together or spaced ("frying pan", "fryingpan", "pan").
-- Example: "/tempgive bob katana 2 3" -> 2 Katanas at Tier III in Bob's free weapon slots.
local C={}
C.Names={'tempgive','give','god','pause','admin'}
C.HELP='/tempgive <player> <item> [copies] [tier] · /give <player> <item> [tier] · /god [player] [on|off] · /pause [on|off]. Player: me, all, others or a name.'
C.MAX_COPIES=10
C.MAX_TEXT=200
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

-- text -> {name, player, item, copies, tier, on} or nil, reason. Checks the shape only; AdminService
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
 if name=='pause' then
  if #args>1 or (args[1] and SWITCH[string.lower(args[1])]==nil) then return nil,'Usage: /pause [on|off]' end
  if args[1] then cmd.on=SWITCH[string.lower(args[1])] end
  return cmd
 end
 if name=='god' then
  local last=args[#args] and SWITCH[string.lower(args[#args])]
  if last~=nil then cmd.on=last;table.remove(args) end
  if #args>1 then return nil,'Usage: /god [player] [on|off]' end
  cmd.player=args[1] or 'me'
  return cmd
 end
 -- tempgive / give: <player> <item words...> then trailing numbers.
 if #args<2 then return nil,name=='tempgive' and 'Usage: /tempgive <player> <item> [copies] [tier]' or 'Usage: /give <player> <item> [tier]' end
 cmd.player=table.remove(args,1)
 if name=='tempgive' then
  -- Up to two trailing numbers: copies then tier. A tier word ('t3', 'iii') may end it instead.
  local n=#args
  if n>=2 and tierWord(args[n]) then cmd.tier=tierWord(args[n]);table.remove(args);n-=1 end
  if n>=2 and tonumber(args[n]) then
   if not cmd.tier and n>=3 and tonumber(args[n-1]) then
    cmd.tier=whole(args[n],1,4);if not cmd.tier then return nil,'Tier must be 1-4' end
    table.remove(args);n-=1
   end
   cmd.copies=whole(args[n],1,C.MAX_COPIES);if not cmd.copies then return nil,'Copies must be 1-'..C.MAX_COPIES end
   table.remove(args)
  end
  cmd.copies=cmd.copies or 1;cmd.tier=cmd.tier or 1
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
 local function add(e) e.norm=C.norm(e.name);e.idNorm=C.norm(e.id);table.insert(out,e) end
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
 local function allowed(e) return (mode=='temp' and e.temp) or (mode=='perm' and e.perm) or (mode==nil) end
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
 return nil,'No '..(mode=='perm' and 'saved ' or mode=='temp' and 'run ' or '')..'item called "'..query..'"'
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
