-- Per-boss gameplay numbers for the map-boss runtime (plan F). Clip timings and sampled
-- points come from the generated MapBossTiming; this file owns health, speed, damage,
-- ranges, cooldowns and attack order. Every value is a starting point for play-testing.
local Timing=require(script.Parent:WaitForChild('MapBossTiming'))
local D={}
D.Order={'KingCrab','Pharaoh','FrostCyclops','Dragon'}
D.KingCrab={anim='king-crab',name='Giant King Crab',health=2400,chaseSpeed=13,glowColor=nil,deathSeconds=nil,
 attacks={
  ClawCrush={clip='ClawCrush',range={0,11},cooldown=2.6,damage=28,shape='circle',point='ClawImpact',radius=6.5},
  SidewaysRush={clips={'RushStart','RushLoop','RushEnd'},range={6,40},cooldown=4.5,damage=24,shape='lane',length=38,width=9,speed=30},
  BubbleBarrage={clip='BubbleBarrage',range={8,34},cooldown=4,damage=10,shape='projectiles',point='BubbleOrigin',count=9,spread=math.rad(38),speed=22,radius=1.5,life=2.6,perPlayer=2},
 },order={'ClawCrush','BubbleBarrage','ClawCrush','SidewaysRush'}}
D.Pharaoh={anim='pharaoh',name='The Pharaoh',health=3000,chaseSpeed=12,glowColor=Color3.fromRGB(120,235,255),
 attacks={
  CursedBolts={clip='CursedBolts',range={8,44},cooldown=2.8,damage=22,shape='projectiles',point='BoltOrigin',count=3,spread=math.rad(18),speed=34,radius=1.2,life=2.2,perPlayer=1},
  TombEruption={clip='TombEruption',range={0,60},cooldown=5,damage=30,shape='targets',radius=4.5,maxTargets=5,eruptDelay=0.9},
 },order={'CursedBolts','CursedBolts','TombEruption'}}
D.FrostCyclops={anim='frost-cyclops',name='Frost Cyclops',health=3600,chaseSpeed=11,glowColor=nil,
 attacks={
  GroundSlam={clip='GroundSlam',range={0,10},cooldown=3,damage=32,shape='circle',point='ClubImpact',radius=11,knockdown=0.7},
  Stomp={clip='Stomp',range={6,26},cooldown=4.2,damage=30,shape='wave',point='StompImpact',length=26,width=5,travel=40},
 },order={'GroundSlam','Stomp','GroundSlam','Stomp','Stomp'}}
D.Dragon={anim='dragon',name='Inferno Dragon',health=4500,chaseSpeed=12,glowColor=Color3.fromRGB(255,150,40),
 attacks={
  FireBreath={clip='FireBreath',range={4,20},cooldown=4,damage=12,shape='breath',point='FireOrigin',halfAngle=math.rad(22),length=20,tick=0.4},
  TailWhip={clip='TailWhip',range={0,17},cooldown=3.4,damage=34,shape='sweep',point='SpadeTip',mid='TailMid',radius=3},
  FrontStomp={clip='FrontStomp',range={0,11},cooldown=3.6,damage=38,shape='circle',point='StompCenter',radius=10,knockdown=0.8},
 },order={'FireBreath','FrontStomp','TailWhip','FireBreath','TailWhip'}}
D.ATTACK_CLIPS={['king-crab']={'ClawCrush','RushStart','RushLoop','RushEnd','BubbleBarrage'},['frost-cyclops']={'GroundSlam','Stomp'},['pharaoh']={'CursedBolts','TombEruption'},['dragon']={'FireBreath','TailWhip','FrontStomp'}}
function D.get(id) return D[id] and type(D[id])=='table' and D[id].anim and D[id] or nil end
function D.timing(id) local d=D.get(id);return d and Timing[d.anim] end
function D.isBoss(id) return D.get(id)~=nil end
return D
