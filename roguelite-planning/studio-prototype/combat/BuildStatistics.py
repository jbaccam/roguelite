"""Deterministic source-based build census; no game state or balance mutations.
Run: python BuildStatistics.py build/luau-validation/luau.exe
"""
import csv, math, statistics, subprocess, sys, tempfile, html
from pathlib import Path
from functools import lru_cache
root=Path(__file__).resolve().parent
# Reuse the existing pure-source adapter, without executing its test/CLI tail.
adapter=(root/'run_enemy_scaling_tests.py').read_text(encoding='utf-8-sig')
namespace={'__file__':str(root/'run_enemy_scaling_tests.py')}
exec(adapter.split('source += module("Tests",')[0],namespace)
source=namespace['source']+r"""
local slots={1,3,5,6}
local bonuses={0,15,30,50}
for section=1,4 do
 for _,profile in {'NoItems','DamageUpgrades'} do
  for _,w in Weapons.List do
   if w.godly then continue end
   local bonus=profile=='DamageUpgrades' and bonuses[section] or 0
   local s=Stats.resolve(w.home,slots[section],nil,{Damage=bonus})
   local d=Stats.weapon(w,s,w.home,section)
   local unit=d.damage
   local label='direct hit'
   if w.id=='18' then unit/=3;label='card' end
   if w.id=='09' then label='pellet' end
   if w.id=='28' or w.id=='29' then unit*=.12/d.cooldown;label='0.12s stream tick' end
   print(string.format('W|%d|%s|%s|%s|%s|%.12f|%.12f|%.12f|%.12f|%s',section,profile,w.home,w.id,w.name,unit,s.CritChance/100,s.CritDamage/100,d.cooldown,label))
  end
 end
end
for _,map in Rules.Maps do
 for wave=1,20 do
  local count=Scheduler.population(math.min(100,8+(wave-1)*3),1,0)
  local mix={}
  for slot=1,count do local id=Catalog.forSlot(slot,wave,Playable.Maps[map.id].roster);mix[id]=(mix[id] or 0)+1 end
  for _,diff in Rules.Difficulties do
   local _,scale=Rules.enemyScale(map.id,diff.id)
   for id,n in mix do
    print(string.format('E|%s|%d|%s|%s|%d|%d|%.12f',map.id,wave,diff.id,id,n,math.ceil(Catalog.scaled(id,wave).health*scale),Stats.powerDamage(map.power)))
   end
  end
 end
end
"""
with tempfile.TemporaryDirectory() as td:
 p=Path(td)/'census.luau';p.write_text(source,encoding='utf-8')
 output=subprocess.run([str(Path(sys.argv[1]).resolve()),str(p)],check=True,capture_output=True,text=True).stdout
weapons=[];enemies={}
for line in output.splitlines():
 a=line.split('|')
 if a[0]=='W':
  _,section,profile,cls,wid,name,damage,crit,mult,cooldown,unit=a
  weapons.append(dict(section=int(section),profile=profile,cls=cls,id=wid,name=name,damage=float(damage),crit=float(crit),mult=float(mult),cooldown=float(cooldown),unit=unit))
 elif a[0]=='E':
  _,mapid,wave,diff,eid,count,hp,power=a
  enemies.setdefault((mapid,int(wave),diff),[]).append((eid,int(count),int(hp),float(power)))
@lru_cache(None)
def expected_hits(hp,damage,crit,mult):
 # E[N] = sum P(N>n); survival after n hits is the binomial number of crits.
 max_hits=math.ceil((hp-1e-9)/damage)
 result=0.
 for n in range(max_hits):
  if crit<=0 or mult<=1:
   result+=1.;continue
  needed=(hp-n*damage)/(damage*(mult-1))
  largest=min(n,math.ceil(needed-1e-9)-1)
  if largest<0: continue
  if largest>=n: result+=1.;continue
  prob=(1-crit)**n;cdf=prob
  for k in range(largest):
   prob*=((n-k)/(k+1))*(crit/(1-crit));cdf+=prob
  result+=cdf
 return result
# Check exact analytic stopping rules, independent of game tuning.
assert expected_hits(10,10,.05,1.5)==1
assert abs(expected_hits(15,10,.2,2)-1.8)<1e-9
assert expected_hits(21,10,0,1.5)==3
assert len(weapons)==36*4*2
rows=[]
for w in weapons:
 for mapid in ['PineValley','BeachCove','DesertBasin','FrozenPass','VolcanicCrater']:
  record={**w,'map':mapid}
  for diff in ['Normal','Hard','Nightmare']:
   means=[];heavy=[]
   for wave in range((w['section']-1)*5+1,w['section']*5+1):
    mix=enemies[(mapid,wave,diff)];total=sum(x[1] for x in mix)
    mean=sum(n/total*expected_hits(hp,w['damage']*power,w['crit'],w['mult']) for _,n,hp,power in mix)
    means.append(mean)
    if mapid=='PineValley':
     for eid,n,hp,power in mix:
      if eid=='tank-zombie': heavy.append(expected_hits(hp,w['damage']*power,w['crit'],w['mult']))
   record[diff]=statistics.mean(means)
   record[diff+'Tank']=statistics.mean(heavy) if heavy else 0
  record['mean_damage']=w['damage']*(1+w['crit']*(w['mult']-1))
  rows.append(record)
classes=['Brawler','Gunner','Thrower','Juggler','Handyman','Mage']
def aggregate(group):
 return {k:statistics.mean(r[k] for r in group) for k in ['mean_damage','Normal','Hard','Nightmare','NormalTank','HardTank','NightmareTank']}
out=Path('build/build-statistics').resolve();out.mkdir(parents=True,exist_ok=True)
with (out/'per_weapon_builds.csv').open('w',newline='',encoding='utf-8') as f:
 writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
summary=[]
for mapid in ['PineValley','BeachCove','DesertBasin','FrozenPass','VolcanicCrater']:
 for profile in ['NoItems','DamageUpgrades']:
  for section in range(1,5):
   for cls in classes+['All classes']:
    group=[r for r in rows if r['map']==mapid and r['profile']==profile and r['section']==section and (cls=='All classes' or r['cls']==cls)]
    r=dict(map=mapid,profile=profile,section=section,cls=cls,**aggregate(group))
    r['NormalMedian']=statistics.median(x['Normal'] for x in group)
    r['NormalMin']=min(x['Normal'] for x in group);r['NormalMax']=max(x['Normal'] for x in group)
    summary.append(r)
with (out/'class_summary.csv').open('w',newline='',encoding='utf-8') as f:
 writer=csv.DictWriter(f,fieldnames=list(summary[0]));writer.writeheader();writer.writerows(summary)
text=[]
for profile in ['NoItems','DamageUpgrades']:
 text.append(profile)
 for r in summary:
  if r['map']=='PineValley' and r['profile']==profile and (r['cls']=='All classes' or r['section']==4):
   text.append(f"W{r['section']} {r['cls']}: dmg {r['mean_damage']:.2f}, hits {r['Normal']:.2f}/{r['Hard']:.2f}/{r['Nightmare']:.2f}, normal median/range {r['NormalMedian']:.2f} [{r['NormalMin']:.2f},{r['NormalMax']:.2f}], tank {r['NormalTank']:.2f}/{r['HardTank']:.2f}/{r['NightmareTank']:.2f}")
print('\n'.join(text))
method="""<p>This is a deterministic balance census, not player telemetry or a prediction of the average player. Each class is equally weighted across its six home weapons; each benchmark build repeats one weapon. Counts/tiers are assumed: W1–5 one Tier I; W6–10 three Tier II; W11–15 five Tier III; W16–20 six Tier IV. Counts activate real class affinity bonuses; more weapons increase throughput, not an individual hit's damage.</p>
<p>NoItems includes class/affinity and native crit only. DamageUpgrades adds raw Damage bonuses 0/15/30/50 by section through Stats.resolve (including class gain modifiers); these are hypothetical upgrades, not observed shopping outcomes. Class compatibility remains applied. Gear Power matches each map recommendation. Damage columns are normalized to Power 1 for comparison; multiply by the map's power-damage factor for actual damage.</p>
<p>A hit means one initial direct damage event: a pellet, card (one third of listed card-volley damage), melee contact, throw contact, blast or 0.12-second stream tick. Includes native random crit in both expected damage and exact expected stopping hit count. Excludes missed attacks, target overkill, pierce/bounce falloff, zones, status damage, secondary chains, legendary moves, pets, turrets, Godlies and bosses. Thus this is direct-hit endurance, not total DPS, trigger pulls, time-to-kill or whole-build clear speed. Especially fire/gas/utility builds benefit from effects outside this model.</p>
<p>Expected hit count is computed for each weapon, enemy and wave BEFORE averaging. Within each wave enemies are weighted by actual authored spawn-slot mix using EnemyCatalog.forSlot and EnemyScheduler.population; waves are equally weighted within each section. This is population composition, not kill-frequency weighting: fast-dying types may respawn more often. Then six home-weapon builds and six classes receive equal weight. Exact calculation averages random critical-hit sequences using binomial survival probabilities. No Monte Carlo sampling error; uncertainty comes from the benchmark assumptions.</p>
<p>Normal is the requested easy mode; Hard and Nightmare use current source multipliers. No gameplay values or Studio state were changed. Pine Valley tank averages condition on waves where tanks naturally appear (wave 8 onward).</p>"""
parts=['<!doctype html><meta charset="utf-8"><title>Wavebreaker build statistics</title><style>body{font:15px system-ui;max-width:1200px;margin:36px auto;padding:0 22px;color:#17202a}table{border-collapse:collapse;width:100%;margin:18px 0 36px}td,th{padding:8px;border-bottom:1px solid #ddd;text-align:right}td:first-child,th:first-child{text-align:left}th{background:#eaf3ec}p{line-height:1.6}h1,h2{color:#17683b}</style><h1>Wavebreaker: damage and hits-to-kill</h1><p>Source census · October 5, 2026 · 36 weapon builds × 4 sections × 2 upgrade scenarios × 5 maps × 3 difficulties.</p>',method]
for mapid in ['PineValley','BeachCove','DesertBasin','FrozenPass','VolcanicCrater']:
 for profile in ['NoItems','DamageUpgrades']:
  parts.append(f'<h2>{mapid} — {profile}</h2><table><tr><th>Class / waves</th><th>Mean damage/hit</th><th>Normal hits</th><th>Hard hits</th><th>Nightmare hits</th><th>Normal build range</th></tr>')
  for r in summary:
   if r['map']!=mapid or r['profile']!=profile: continue
   parts.append(f"<tr><td>{r['cls']} · {(r['section']-1)*5+1}–{r['section']*5}</td><td>{r['mean_damage']:.2f}</td><td>{r['Normal']:.2f}</td><td>{r['Hard']:.2f}</td><td>{r['Nightmare']:.2f}</td><td>{r['NormalMin']:.2f}–{r['NormalMax']:.2f}</td></tr>")
  parts.append('</table>')
parts.append('<p>CSV files alongside this report contain every weapon build and class summary.</p>')
(out/'report.html').write_text(''.join(parts),encoding='utf-8')
print('OUTPUT '+str(out))
