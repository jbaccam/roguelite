-- ProfileLock against a fake store (LOBBY_AND_MATCH_SERVERS.md §7: "the lock logic is tested
-- against a fake store"). Pure: run(L) takes the ProfileLock table, no Studio services needed.
local T={}
local function deepcopy(v) if type(v)~='table' then return v end local c={};for k,x in v do c[k]=deepcopy(x) end;return c end
-- Mimics DataStore UpdateAsync: the transform gets a copy, nil cancels, `fail` throws that many times.
local function fakeStore()
 local s={data={},fail=0,writes=0}
 function s:UpdateAsync(key,fn)
  if self.fail>0 then self.fail-=1;error('fake throttle') end
  local new=fn(deepcopy(self.data[key]))
  if new~=nil then self.data[key]=deepcopy(new);self.writes+=1 end
  return deepcopy(new)
 end
 return s
end
local function clockPair() local t=0;return function() return t end,function(s) t+=s end end
local function fresh() return {emeralds=0} end

function T.run(L)
 local checks,failures=0,{}
 local function check(name,ok) checks+=1;if not ok then table.insert(failures,name) end end

 -- New account: a fresh record, locked by the loader.
 do local store=fakeStore();local clock,sleep=clockPair()
  local d,why=L.claim(store,'u_1','A',{fresh=fresh,clock=clock,sleep=sleep,now=function() return 100 end})
  check('new account loads',d~=nil and why==nil and d.emeralds==0)
  check('new account locked by loader',store.data.u_1.lock.job=='A' and store.data.u_1.lock.at==100)
 end
 -- An old save without a lock keeps its data and gains the lock.
 do local store=fakeStore();store.data.u_2={emeralds=55};local clock,sleep=clockPair()
  local d=L.claim(store,'u_2','A',{fresh=fresh,clock=clock,sleep=sleep})
  check('old save keeps data',d and d.emeralds==55 and store.data.u_2.lock.job=='A')
 end
 -- Another server still holds it, then releases while we wait: we load its final save, no takeover.
 do local store=fakeStore();store.data.u_3={emeralds=10,lock={job='B',at=0}};local clock,sleep=clockPair()
  local slept=0
  local d,why=L.claim(store,'u_3','A',{fresh=fresh,clock=clock,sleep=function(s) slept+=s;sleep(s)
   if slept>=6 then local rec=store.data.u_3;if rec.lock and rec.lock.job=='B' then rec.emeralds=25;rec.lock=nil end end end})
  check('waits for the other server',slept>=6 and slept<L.WAIT)
  check('loads the released save',d and d.emeralds==25 and why==nil and store.data.u_3.lock.job=='A')
 end
 -- Another server never releases: take over after WAIT, and that server can no longer write.
 do local store=fakeStore();store.data.u_4={emeralds=10,lock={job='B',at=0}};local clock,sleep=clockPair()
  local d,why=L.claim(store,'u_4','A',{fresh=fresh,clock=clock,sleep=sleep})
  check('takes over after the wait',d and why=='takeover' and clock()>=L.WAIT and store.data.u_4.lock.job=='A')
  local before=store.writes
  local ok,lost=L.write(store,'u_4','B',{emeralds=999},false)
  check('a server that lost the lock never writes',ok==false and lost==true and store.writes==before and store.data.u_4.emeralds==10)
  d.emeralds=40
  local ok2,lost2=L.write(store,'u_4','A',d,false,function() return 7 end)
  check('the owner writes',ok2 and not lost2 and store.data.u_4.emeralds==40 and store.data.u_4.lock.at==7)
  L.write(store,'u_4','A',d,true)
  check('release clears the lock',store.data.u_4.lock==nil and d.lock==nil)
  local _,why2=L.claim(store,'u_4','B',{fresh=fresh,clock=clock,sleep=sleep})
  check('a released save loads at once',why2==nil and store.data.u_4.lock.job=='B')
 end
 -- The player left while waiting: stop without loading or locking.
 do local store=fakeStore();store.data.u_5={lock={job='B',at=0}};local clock,sleep=clockPair()
  local d,why=L.claim(store,'u_5','A',{fresh=fresh,clock=clock,sleep=sleep,stillWanted=function() return false end})
  check('cancelled when the player left',d==nil and why=='cancelled' and store.data.u_5.lock.job=='B')
 end
 -- Store errors: give up after ATTEMPTS so the profile is never saved over unknown data.
 do local store=fakeStore();store.fail=99;local clock,sleep=clockPair()
  local d,why=L.claim(store,'u_6','A',{fresh=fresh,clock=clock,sleep=sleep})
  check('gives up after store errors',d==nil and why=='error')
  store.fail=1
  local d2=L.claim(store,'u_6','A',{fresh=fresh,clock=clock,sleep=sleep})
  check('retries one store error',d2~=nil)
  store.fail=1
  local ok,lost,err=L.write(store,'u_6','A',d2,false)
  check('a failed write reports it',ok==false and lost==false and err~=nil)
 end
 -- The same server's own lock (a quick rejoin to this server) loads at once.
 do local store=fakeStore();store.data.u_7={emeralds=3,lock={job='A',at=0}};local clock,sleep=clockPair()
  local d,why=L.claim(store,'u_7','A',{fresh=fresh,clock=clock,sleep=sleep})
  check('own lock loads at once',d and d.emeralds==3 and why==nil and clock()==0)
 end
 return checks,failures
end
return T
