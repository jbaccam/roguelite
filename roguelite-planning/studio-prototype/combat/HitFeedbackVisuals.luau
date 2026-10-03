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
 return api
end
return V
