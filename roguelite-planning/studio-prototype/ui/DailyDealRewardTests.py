"""Exercise actual StoreUI receipt-to-effect selection without Roblox or a purchase."""
from pathlib import Path
import subprocess,sys,tempfile
base=Path(__file__).resolve().parent
source=(base/'StoreUI.luau').read_text()
selection=source[source.index('function S.dailyReward(result)'):source.index('S.Tabs=')]
checks=r'''
local checks=0
local function check(ok,label) checks+=1;assert(ok,label) end
for count=1,5 do
 local results={};for i=1,count do results[i]={id='00',tier=1,have=i} end
 local reward=S.dailyReward({ok=true,results=results})
 check(reward and reward.id=='00' and reward.amount==count,'exact confirmed Glock quantity '..count)
 check(S.dailyReward({ok=false,results=results})==nil,'failed/cancelled purchase cannot emit icons')
end
for _,r in {{},{ok=true},{ok=true,results={}},{ok=true,results=table.create(6,{id='00'})},{ok=true,results={{id='bad'}}},{ok=true,results={{id='00'},{id='07'}}},{ok=true,results={1}}} do
 check(S.dailyReward(r)==nil,'invalid receipt must not guess quantity or identity')
end
check(S.dailyReward(nil)==nil,'nil receipt is not success')
local reward=S.dailyReward({ok=true,results={{id='07'},{id='07'},{id='07'}}})
check(reward.id=='07' and reward.amount==3,'server awarded ID replaces stale displayed offer ID')
print('DailyDealRewardTests: '..checks..' assertions passed')
'''
harness="local S={}\nlocal Chests={DealAmount={Common={2,5},Rare={1,3},Epic={1,1},Legendary={1,1}}}\nlocal Weapons={ById={['00']={name='Glock'},['07']={name='Draco'}}}\n"+selection+checks
with tempfile.TemporaryDirectory(prefix='daily-deal-reward-') as directory:
    path=Path(directory)/'tests.luau';path.write_text(harness)
    subprocess.run([str(Path(sys.argv[1]).resolve()),str(path)],check=True)
