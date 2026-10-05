-- Damage numbers and hit flashes, pooled (launch audit F2). Each hit used to build a part, a
-- BillboardGui, labels, three tweens and a Highlight, and destroy them under a second later:
-- ~1,500 objects a second in a horde, with every client drawing all four players' hits.
--  * Hit numbers share 28. When all are showing, a teammate's oldest gives way first, then your
--    own oldest; a teammate's new number is dropped while only yours are showing.
--  * Your own damage taken has 6 of its own and always shows.
--  * Flashes reuse 10 Highlights (Roblox draws at most 31 at once, and other effects need some).
--    A hit on an enemy that is still flashing restarts its flash; past 10, the oldest moves.
-- The motion is the old tweens' (same times and easing, through TweenService:GetValue) in one
-- RenderStepped pass. The pick rules are pure (V.pick, V.pickFlash) for HitFeedbackTests.
local RunService=game:GetService('RunService')
local TweenService=game:GetService('TweenService')
local V={HitNumbers=28,TakenNumbers=6,Flashes=10}
-- Which pooled entry shows a new number: a free one, else 'new' while under `cap`, else a
-- teammate's oldest, else (for your own) your oldest. nil drops it.
function V.pick(pool,cap,mine)
 local free,oldestMine,oldestOther
 for _,e in pool do
  if not e.born then free=free or e
  elseif e.mine then if not oldestMine or e.born<oldestMine.born then oldestMine=e end
  elseif not oldestOther or e.born<oldestOther.born then oldestOther=e end
 end
 if free then return free end
 if #pool<cap then return 'new' end
 return oldestOther or (mine and oldestMine) or nil
end
-- Which flash shows a hit on `npc`: its own if it is still flashing, else a free one, else 'new'
-- while under `cap`, else the oldest.
function V.pickFlash(flashes,cap,npc)
 local free,oldest
 for _,f in flashes do
  if f.born and f.npc==npc then return f end
  if not f.born then free=free or f elseif not oldest or f.born<oldest.born then oldest=f end
 end
 if free then return free end
 if #flashes<cap then return 'new' end
 return oldest
end
local QUAD,BACK,OUT=Enum.EasingStyle.Quad,Enum.EasingStyle.Back,Enum.EasingDirection.Out
-- Slowed enemies (mount, below): ice tints for the 8 nearest, frost patches for the 24 nearest.
V.FrostTints=8;V.FrostPatches=24;V.Ice=Color3.fromRGB(150,220,255);V.IceWhite=Color3.fromRGB(232,248,255)
function V.mount(visuals)
 local anchor=Instance.new('Part');anchor.Name='DamageNumbers';anchor.Size=Vector3.one*.1;anchor.Transparency=1;anchor.Anchored=true
 anchor.CanCollide=false;anchor.CanTouch=false;anchor.CanQuery=false;anchor.CFrame=CFrame.identity;anchor.Parent=visuals
 local hitNumbers,takenNumbers,flashes={},{},{}
 local function newNumber(taken)
  local a=Instance.new('Attachment');a.Name=taken and 'PlayerDamageNumber' or 'DamageNumber';a.Parent=anchor
  local gui=Instance.new('BillboardGui');gui.Size=UDim2.fromOffset(taken and 160 or 100,taken and 90 or 60);gui.AlwaysOnTop=true;gui.MaxDistance=100;gui.Enabled=false;gui.Parent=a
  local text=Instance.new('TextLabel');text.Size=UDim2.fromScale(1,1);text.BackgroundTransparency=1;text.Font=taken and Enum.Font.GothamBlack or Enum.Font.GothamBold;text.TextSize=taken and 44 or 30;text.TextStrokeColor3=Color3.fromRGB(28,22,20);text.Parent=gui
  local outline
  if taken then outline=Instance.new('UIStroke');outline.Thickness=2;outline.Color=Color3.fromRGB(46,10,17);outline.Parent=text end
  local scale=Instance.new('UIScale');scale.Parent=text
  return {attachment=a,gui=gui,text=text,outline=outline,scale=scale,stroke=taken and 1 or .12}
 end
 local api={}
 -- taken: your own damage taken ('-' and red, bigger, always shown). mine: your own hit.
 function api.number(position,damage,color,taken,mine)
  local pool=taken and takenNumbers or hitNumbers
  local e=V.pick(pool,taken and V.TakenNumbers or V.HitNumbers,mine or taken)
  if e=='new' then e=newNumber(taken);table.insert(pool,e) end
  if not e then return end
  e.born=os.clock();e.mine=mine or taken;e.start=position+Vector3.new((math.random()-.5)*.8,0,0)
  e.text.Text=(taken and '-' or '')..tostring(math.round(damage));e.text.TextColor3=color
  e.text.TextTransparency=0;e.text.TextStrokeTransparency=e.stroke;if e.outline then e.outline.Transparency=0 end
  e.scale.Scale=.65;e.attachment.Position=e.start;e.gui.Enabled=true
 end
 function api.flash(npc)
  local f=V.pickFlash(flashes,V.Flashes,npc)
  if f=='new' then
   local h=Instance.new('Highlight');h.Name='WeaponHitFlash';h.FillColor=Color3.new(1,1,1);h.OutlineTransparency=1;h.DepthMode=Enum.HighlightDepthMode.Occluded;h.Enabled=false;h.Parent=visuals
   f={highlight=h};table.insert(flashes,f)
  end
  f.npc=npc;f.born=os.clock();f.highlight.Adornee=npc;f.highlight.FillTransparency=0;f.highlight.Enabled=true
 end
 local function stepNumbers(pool,now)
  for _,e in pool do
   if e.born then
    local t=now-e.born
    if t>=.85 then e.born=nil;e.gui.Enabled=false
    else
     e.attachment.Position=e.start+Vector3.yAxis*2*TweenService:GetValue(math.min(t/.8,1),QUAD,OUT)
     e.scale.Scale=.65+.35*TweenService:GetValue(math.min(t/.13,1),BACK,OUT)
     if t>.42 then
      local f=TweenService:GetValue(math.min((t-.42)/.3,1),QUAD,OUT)
      e.text.TextTransparency=f;e.text.TextStrokeTransparency=e.stroke+(1-e.stroke)*f;if e.outline then e.outline.Transparency=f end
     end
    end
   end
  end
 end
 RunService.RenderStepped:Connect(function()
  local now=os.clock()
  stepNumbers(hitNumbers,now);stepNumbers(takenNumbers,now)
  for _,f in flashes do
   if f.born then
    local t=now-f.born
    if t>=.15 or not f.npc.Parent then f.born=nil;f.npc=nil;f.highlight.Enabled=false;f.highlight.Adornee=nil
    elseif t>.045 then f.highlight.FillTransparency=TweenService:GetValue(math.min((t-.045)/.09,1),QUAD,OUT) end
   end
  end
 end)
 -- Slowed enemies (2026-10-03: nobody noticed Medusa's slow). While an enemy's StatusSlowStrength
 -- (CombatEffectsService, replicated) is above 0 it is tinted ice blue and stands on a flat frost
 -- patch (a pale Neon disc and six frost spikes, turning slowly); a frost ring bursts out when the
 -- slow lands. Only the nearest within 150 studs are drawn: V.FrostTints Highlights (flashes keep
 -- their 10 of the 31 Roblox draws) and V.FrostPatches patches. A white hit flash takes over the
 -- tint for its 0.15 s. Example: a Medusa hit on a zombie walking 12 studs/s shows ice for the
 -- 2 s it crawls at 7.8.
 local Tags=game:GetService('CollectionService')
 local K=require(game:GetService('ReplicatedStorage'):WaitForChild('RogueliteCombat'):WaitForChild('VfxKit'))
 local slowed,watched={},setmetatable({},{__mode='k'})
 local groundCache=setmetatable({},{__mode='k'})
 local groundParams=RaycastParams.new();groundParams.FilterType=Enum.RaycastFilterType.Exclude
 groundParams.IgnoreWater=true;groundParams.RespectCanCollide=true
 local function feet(npc,root)
  -- Sandboxed effects cannot read Humanoid.HipHeight. Probe the actual floor and cache its
  -- height briefly; the bounded frost pool follows the enemy horizontally every frame.
  local now=os.clock();local cached=groundCache[npc]
  if not cached or now>=cached.expires then
   local exclude={npc,visuals};local enemies=workspace:FindFirstChild('RogueliteEnemies')
   if enemies then table.insert(exclude,enemies) end
   for _,player in game:GetService('Players'):GetPlayers() do if player.Character then table.insert(exclude,player.Character) end end
   groundParams.FilterDescendantsInstances=exclude
   local ground=workspace:Raycast(root.Position+Vector3.yAxis*2,-Vector3.yAxis*math.max(24,root.Size.Y*3+8),groundParams)
   cached={y=ground and ground.Position.Y or npc:GetAttribute('BossGroundY') or root.Position.Y-root.Size.Y*.5-2,expires=now+.12}
   groundCache[npc]=cached
  end
  return Vector3.new(root.Position.X,cached.y,root.Position.Z)
 end
 local function patchRadius(root) return math.clamp(math.max(root.Size.X,root.Size.Z)*1.3,2.2,8) end
 local function watch(npc)
  if watched[npc] or not npc:IsA('Model') then return end
  watched[npc]=true
  local function changed()
   local on=(npc:GetAttribute('StatusSlowStrength') or 0)>0
   if on and not slowed[npc] then
    slowed[npc]=os.clock()
    local root=npc:FindFirstChild('HumanoidRootPart')
    if root and K.near(root.Position,120) then
     local r=patchRadius(root)
     K.ring(visuals,CFrame.new(feet(npc,root)+Vector3.yAxis*.12),{radius0=r*.3,radius1=r*1.25,width=.45,duration=.38,color=V.Ice,rim=V.IceWhite,segments=16})
    end
   elseif not on then slowed[npc]=nil end
  end
  npc:GetAttributeChangedSignal('StatusSlowStrength'):Connect(changed);changed()
 end
 Tags:GetInstanceAddedSignal('RogueliteZombie'):Connect(watch)
 Tags:GetInstanceRemovedSignal('RogueliteZombie'):Connect(function(npc) slowed[npc]=nil end)
 for _,npc in Tags:GetTagged('RogueliteZombie') do watch(npc) end
 local patches,tints={},{}
 local function hidePatch(p) p.shown=false;p.disc.Transparency=1;for _,s in p.spikes do s.Transparency=1 end end
 RunService.RenderStepped:Connect(function()
  local list={}
  if next(slowed) then
   local camera=workspace.CurrentCamera;local eye=camera and camera.CFrame.Position or Vector3.zero
   for npc in slowed do
    local root=npc.Parent and npc:FindFirstChild('HumanoidRootPart');local h=npc:FindFirstChildOfClass('Humanoid')
    if not root or not h or h.Health<=0 then slowed[npc]=nil;continue end -- gone or dying
    local distance=(root.Position-eye).Magnitude
    if distance<=150 then table.insert(list,{npc=npc,root=root,distance=distance}) end
   end
   table.sort(list,function(a,b) return a.distance<b.distance end)
  end
  local now=os.clock()
  for i=1,math.max(V.FrostPatches,#patches) do
   local e=i<=V.FrostPatches and list[i];local p=patches[i]
   if e then
    if not p then
     p={disc=K.part(visuals,'FrostPatch',Vector3.new(.05,1,1),V.Ice,1,Enum.Material.Neon,Enum.PartType.Cylinder),spikes={}}
     for k=1,6 do p.spikes[k]=K.part(visuals,'FrostSpike',Vector3.new(.22,.04,1),V.IceWhite,1,Enum.Material.Neon) end
     patches[i]=p
    end
    p.shown=true
    local r=patchRadius(e.root)*(.6+.4*math.min(1,(now-(slowed[e.npc] or now))/.15))
    local at=feet(e.npc,e.root)+Vector3.yAxis*.06
    p.disc.Size=Vector3.new(.05,r*2,r*2);p.disc.CFrame=CFrame.new(at)*CFrame.Angles(0,0,math.pi/2)
    p.disc.Transparency=.62+.08*math.sin(now*5+i)
    for k,s in p.spikes do
     local length=r*(k%2==0 and .75 or 1.05)
     s.Size=Vector3.new(.22,.04,length)
     s.CFrame=CFrame.new(at+Vector3.yAxis*.02)*CFrame.Angles(0,now*.6+i+k*math.pi/3,0)*CFrame.new(0,0,-length*.5)
     s.Transparency=.3
    end
   elseif p and p.shown then hidePatch(p) end
  end
  local flashing={}
  for _,f in flashes do if f.born and f.npc then flashing[f.npc]=true end end
  for i=1,math.max(V.FrostTints,#tints) do
   local e=i<=V.FrostTints and list[i];local h=tints[i]
   if e then
    if not h then
     h=Instance.new('Highlight');h.Name='FrostTint';h.FillColor=V.Ice;h.FillTransparency=.55;h.OutlineColor=V.IceWhite;h.OutlineTransparency=.55
     h.DepthMode=Enum.HighlightDepthMode.Occluded;h.Parent=visuals;tints[i]=h
    end
    h.Adornee=e.npc;h.Enabled=not flashing[e.npc]
   elseif h and h.Enabled then h.Enabled=false;h.Adornee=nil end
  end
 end)
 return api
end
return V
