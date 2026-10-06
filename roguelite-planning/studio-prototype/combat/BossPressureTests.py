"""Test actual boss population, live-boss detection and no-reward trimming with Luau CLI."""
from pathlib import Path
import subprocess
import sys
import tempfile

PRELUDE = r'''
local attributes={ZombieCount=65}
local combat={GetAttribute=function(_,key) return attributes[key] end}
local alive=1
local function playersUp() return alive end
local endlessBoss=nil
local Timeline={MaxAlive=100}
local function timelineMode() return false end
local children={}
local folder={GetChildren=function() return children end}
local function npc(values,hp)
 local object={Parent=folder,values=values or {},humanoid={Health=hp or 10}}
 function object:GetAttribute(key) return self.values[key] end
 function object:FindFirstChildOfClass() return self.humanoid end
 function object:Destroy() self.destroyed=true;self.Parent=nil end
 table.insert(children,object)
 return object
end
'''
CHECKS = r'''
assert(spawnCount()==100,'ordinary count changed')
local boss=npc({IsBoss=true},100)
liveBosses[boss]=true
for n=1,4 do alive=n;assert(spawnCount()==20*n,'boss cap mismatch') end
alive=1
for i=1,100 do npc({SpawnIndex=i}) end
local admin=npc({SpawnIndex=99,AdminSpawn=true})
trimBossPopulation()
local kept=0
for _,object in children do
 assert(object.humanoid.Health>0,'trim killed an enemy')
 if object.values.SpawnIndex and not object.values.AdminSpawn and not object.destroyed then kept+=1 end
end
assert(kept==20 and not boss.destroyed and not admin.destroyed,'trim touched wrong enemies')
attributes.TestZombieCountOverride=65
assert(not bossPressure() and spawnCount()==65,'explicit override changed')
attributes.TestZombieCountOverride=nil
attributes.TutorialRun=true
assert(not bossPressure() and spawnCount()==65,'tutorial count changed')
attributes.TutorialRun=nil;attributes.WaveNoRespawn=true
assert(not bossPressure() and spawnCount()==65,'fixed count changed')
attributes.WaveNoRespawn=nil
boss.humanoid.Health=0
assert(not bossPressure() and spawnCount()==100,'dead boss retained cap')
boss.humanoid.Health=100;boss.values.DeathPopped=true
assert(not bossPressure(),'cosmetic boss retained cap')
boss.values.DeathPopped=nil;boss.Parent=nil
assert(not bossPressure(),'removed boss retained cap')
assert(Population.bossPopulation(0,4)==0 and Population.bossPopulation(5,1)==12,'boss cap increased small/empty wave')
assert(Population.bossPopulation(100,99)==80,'multiplayer cap exceeded')
print('PASS: boss population 20/40/60/80; safe trim; alive/dead/removed detection; tutorial/fixed/override exclusions; ordinary count restored')
'''
base=Path(__file__).resolve().parent
source=(base.parent/'RogueliteZombieChase.server.luau').read_text()
scheduler=(base/'EnemyScheduler.luau').read_text()
pressure=source[source.index('local liveBosses = {}'):source.index('local function playersUp()')]
count=source[source.index('local function spawnCount()'):source.index('local COLLISION_GROUP')]
trim=source[source.index('local function trimBossPopulation()'):source.index('folder.ChildAdded:Connect(function(npc)')]
with tempfile.TemporaryDirectory(prefix='roguelite-boss-pressure-') as directory:
    path=Path(directory)/'BossPressureTests.luau'
    path.write_text('local Population=(function()\n'+scheduler+'\nend)()\n'+PRELUDE+pressure+count+trim+CHECKS)
    subprocess.run([sys.argv[1],str(path)],check=True)
