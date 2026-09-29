-- Developer accounts and request rules for the ADMIN panel (ADMIN_PANEL.md).
-- Shared: clients only use isAdmin to show or hide the ADMIN button. The server checks isAdmin
-- and check() on every admin request. By UserId, never by name, because names can change.
-- Sandboxed (Capabilities copied from CharacterStats): CharacterService, ShopService and the
-- RogueliteCombat scripts require it, so everything it requires must be sandboxed too.
local RS=game:GetService('ReplicatedStorage')
local RunService=game:GetService('RunService')
local combat=RS:WaitForChild('RogueliteCombat')
local Enemies=require(combat:WaitForChild('EnemyCatalog'))
local Items=require(combat:WaitForChild('ShopCatalog'))
local Maps=require(combat:WaitForChild('MapConfig'))
local E=require(combat:WaitForChild('EconomyConfig'))
local XP=require(combat:WaitForChild('RunXP'))
local A={UserIds={341854066},BossId='Hammer'} -- 341854066: EggaRowls
local admins={};for _,id in A.UserIds do admins[id]=true end
function A.isAdminId(id) return type(id)=='number' and admins[id]==true end
function A.isAdmin(player) return typeof(player)=='Instance' and player:IsA('Player') and A.isAdminId(player.UserId) end

-- Test runs: the first admin action of a run sets RogueliteRunState.AdminTestRun, and
-- ShopService.resetRun clears it. While it is set, reward code grants nothing. The folder is
-- looked up lazily: ShopService creates it after requiring this module.
function A.isTestRun(runState)
 runState=runState or RS:FindFirstChild('RogueliteRunState')
 return typeof(runState)=='Instance' and runState:GetAttribute('AdminTestRun')==true
end
function A.markTestRun()
 local run=RunService:IsServer() and RS:FindFirstChild('RogueliteRunState')
 if run then run:SetAttribute('AdminTestRun',true) end
end

-- Argument rules for every AdminAction request. Nothing a client sends is trusted.
local function int(v,lo,hi) return type(v)=='number' and v==v and v%1==0 and v>=lo and v<=hi end
local function flag(a,b) return type(a)=='boolean' and b==nil end
local function none(a,b) return a==nil and b==nil end
-- Comma list of EnemyCatalog ids; '' means the map's own mix.
local function enemyList(v)
 if type(v)~='string' or #v>600 then return false end
 for id in v:gmatch('[^,%s]+') do if not Enemies.ById[id] then return false end end
 return true
end
local rules={
 Travel=function(a,b) return b==nil and (a=='Lobby' or Maps.valid(a)) end,
 Spawn=function(a,b) return (a==A.BossId or (type(a)=='string' and Enemies.ById[a]~=nil)) and int(b,1,50) end,
 KeepAlive=function(a,b) return int(a,0,100) and enemyList(b) end,
 ClearMobs=none,Freeze=flag,
 Sandbox=none,Waves=none,EndWave=none,Pause=flag,
 JumpWave=function(a,b) return int(a,1,20) and b==nil end,
 God=flag,Weapons=flag,
 GiveItem=function(a,b) local e=type(a)=='string' and Items.ById[a];return e and e.kind~='Weapon' and b==nil end,
 Shards=function(a,b) return (a=='Add' and int(b,-E.MAX_SHARDS,E.MAX_SHARDS)) or (a=='Set' and int(b,0,E.MAX_SHARDS)) end,
 Level=function(a,b) return (a=='Add' and int(b,1,100)) or (a=='Set' and int(b,1,XP.MAX_LEVEL)) end,
}
A.Actions={};for name in rules do table.insert(A.Actions,name) end;table.sort(A.Actions)
-- true only for a known action with valid arguments.
function A.check(action,a,b)
 local rule=type(action)=='string' and rules[action] or nil
 return rule~=nil and rule(a,b)==true
end
return A
