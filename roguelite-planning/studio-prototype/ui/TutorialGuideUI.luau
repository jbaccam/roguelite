-- The tutorial guide's look (plans/2026-10-03-tutorial-design.md; mockup approved from
-- roguelite-planning/previews/tutorial-guide/guide.html): the guide's portrait (Eggbert, the egg
-- merchant) and text box wherever they cover no UI, ONE arrow that glides between targets, and the
-- VICTORY banner. Presentation only: TutorialGuide.client decides what is said and pointed at.
--   G.new(player, assets, name) -> guide   (name: his name tag)
--   guide.say(text, button)   types the line in (button: {label=, onClick=} or nil); same text = no-op
--   guide.hide()              tucks the box away (the arrow too)
--   guide.point(obj)          the arrow glides to a GuiObject (any ScreenGui), or to a Model/BasePart
--                             in the world (a crystal on the ground), and rests there, bobbing;
--                             nil fades it out where it is
--   guide.context(ctx)        where the box may go: ctx.avoid = world Models/BaseParts it must not
--                             cover (the player's own character always counts), ctx.prefer = a
--                             screen rect {x0,y0,x1,y1} to try first, ctx.edges = corners and sides
--                             only (the run: never over the fight)
--   guide.banner(top, big, seconds)
--   guide.Screen, guide.destroy()
-- The arrow is one image: a new target starts a 0.55 s eased curve (a quadratic Bezier bulging to
-- the side) while it turns to its new direction; at rest it keeps following the target (layouts
-- move) and bobs along its pointing line. Below the target pointing up, unless the target sits in
-- the bottom part of the screen (then above, pointing down), so it never covers a card's text.
local GuiService=game:GetService('GuiService')
local RunService=game:GetService('RunService')
local TweenService=game:GetService('TweenService')
local RS=game:GetService('ReplicatedStorage')
local T=require(RS:WaitForChild('UITheme'))
local C=T.Color
local G={}
G.ARROW=112 -- arrow size at scale 1 (design px)
G.TIP=6/256 -- the tip's height in arrow.png (ui/assets/tutorial/make_arrow.py)
G.GLIDE=.55
G.TAG_H=32
-- Two shapes at scale 1, each {size, portrait, box, text, tag, buttons} as {x, y, w, h} inside it:
-- wide (portrait beside a long box, like the reference) and compact (portrait over a short box),
-- for gaps the wide one doesn't fit, like between the chest screen's menu and its chests.
G.Shapes={
 wide={size=Vector2.new(860,300),portrait={0,0,300,300},box={150,120,710,150},text={140,14,530,122,36},
  textWithButton={140,14,330,122,36},tag={290,88},buttons={660,226,190,58},fade=1},
 compact={size=Vector2.new(480,340),portrait={0,0,200,200},box={0,170,480,170},text={24,14,432,142,32},
  textWithButton={24,10,432,90,30},tag={186,130},buttons={270,278,190,52},fade=.35},
}
local CPS=46 -- typed characters per second

local function ease(t) return t<.5 and 4*t*t*t or 1-(-2*t+2)^3/2 end
-- Screen pixels from AbsolutePosition: every GuiObject's AbsolutePosition is measured from under
-- Roblox's top bar, whatever its ScreenGui's insets (a full-screen layer's own top-left reads
-- (0, -58)). Adding the top bar's inset gives the real screen spot for any layer. Until
-- 2026-10-03 full-screen layers got no inset added, and arrows on the level-up cards, chest
-- screen and results sat 58 px too high (into a button, or short of it).
local function inset() return (GuiService:GetGuiInset()) end

function G.new(player,assets,name)
 local o={}
 local screen=T.make('ScreenGui',player:WaitForChild('PlayerGui'),{Name='TutorialGuide',ResetOnSpawn=false,DisplayOrder=95,
  ScreenInsets=Enum.ScreenInsets.None,ZIndexBehavior=Enum.ZIndexBehavior.Sibling})
 o.Screen=screen
 local root=T.frame(screen,'Root',0,0,0,0);root.Size=UDim2.fromScale(1,1)
 local scale=1
 -- The guide: portrait over the left end of a dark box that fades out to the right.
 local guide=T.make('CanvasGroup',root,{Name='Guide',BackgroundTransparency=1,Size=UDim2.fromOffset(860,300),GroupTransparency=1})
 local guideScale=T.make('UIScale',guide,{Scale=1})
 local box=T.make('Frame',guide,{Name='Box',BackgroundColor3=Color3.fromRGB(8,12,10),BackgroundTransparency=.08,BorderSizePixel=0})
 local boxFade=T.make('UIGradient',box,{})
 T.make('Frame',box,{Name='Edge',Size=UDim2.new(0,6,1,0),BackgroundColor3=C.lime,BorderSizePixel=0})
 local text=T.label(box,'Line','',0,0,10,10,36);text.TextXAlignment=Enum.TextXAlignment.Left
 local label=string.upper(name or 'Egg Merchant')
 local tagW=math.clamp(#label*14+28,90,260) -- about 14 px a capital at size 20, plus padding
 local tag=T.make('Frame',guide,{Name='NameTag',Size=UDim2.fromOffset(tagW,G.TAG_H),BackgroundColor3=C.lime,BorderSizePixel=0})
 T.make('UICorner',tag,{CornerRadius=UDim.new(0,4)})
 local tagText=T.label(tag,'Text',label,8,2,tagW-16,28,20,C.ink);tagText.TextStrokeTransparency=1
 local portrait=T.make('ImageLabel',guide,{Name='Portrait',BackgroundTransparency=1,Image=assets.portrait or '',ScaleType=Enum.ScaleType.Fit})
 local buttonHolder=T.frame(guide,'Buttons',0,0,190,58)
 local shapeName,hasButton
 local function setRect(obj,r) obj.Position=UDim2.fromOffset(r[1],r[2]);if r[3] then obj.Size=UDim2.fromOffset(r[3],r[4]) end end
 local function setText()
  local r=G.Shapes[shapeName][hasButton and 'textWithButton' or 'text']
  setRect(text,r);text.TextSize=r[5];text.TextWrapped=true
 end
 local function applyShape(name_)
  if name_==shapeName then return end
  shapeName=name_;local s=G.Shapes[name_]
  guide.Size=UDim2.fromOffset(s.size.X,s.size.Y)
  setRect(portrait,s.portrait);setRect(box,s.box);setRect(tag,s.tag);setRect(buttonHolder,s.buttons)
  buttonHolder.Size=UDim2.fromOffset(s.buttons[3],s.buttons[4])
  boxFade.Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,0),NumberSequenceKeypoint.new(.7,.08),NumberSequenceKeypoint.new(1,s.fade)})
  setText()
 end
 applyShape('wide')
 -- The arrow.
 local arrow=T.make('ImageLabel',root,{Name='Arrow',BackgroundTransparency=1,AnchorPoint=Vector2.new(.5,.5),Size=UDim2.fromOffset(G.ARROW,G.ARROW),
  Image=assets.arrow or '',ImageTransparency=1,ZIndex=5})
 -- The VICTORY banner.
 -- Active: it takes the clicks while it shows (the shop under it must not start another wave).
 local bannerLayer=T.make('Frame',root,{Name='Banner',Size=UDim2.fromScale(1,1),BackgroundColor3=C.shade,BackgroundTransparency=1,BorderSizePixel=0,Visible=false,ZIndex=3,Active=true})
 local bannerScale=T.make('UIScale',bannerLayer,{Scale=1})
 local bannerTop=T.label(bannerLayer,'Top','',0,0,0,0,46,C.white);bannerTop.AnchorPoint=Vector2.new(.5,.5);bannerTop.Position=UDim2.new(.5,0,.5,-110);bannerTop.Size=UDim2.fromOffset(900,60);bannerTop.ZIndex=4
 local bannerBig=T.label(bannerLayer,'Big','',0,0,0,0,150,C.gold);bannerBig.AnchorPoint=Vector2.new(.5,.5);bannerBig.Position=UDim2.fromScale(.5,.5);bannerBig.Size=UDim2.fromOffset(1100,170);bannerBig.ZIndex=4
 bannerBig.TextStrokeTransparency=0
 for i,side in {-1,1} do
  local line=T.make('Frame',bannerLayer,{Name='Line'..i,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.new(.5,side*560,.5,0),Size=UDim2.fromOffset(300,6),BackgroundColor3=C.gold,BorderSizePixel=0,ZIndex=4})
  T.make('UIGradient',line,{Transparency=NumberSequence.new(side<0 and 1 or 0,side<0 and 0 or 1)})
 end

 -- Where the guide sits: spot = {pos (top-left, screen px), s (its scale), shape}; placement moves it.
 local spot={pos=Vector2.zero,s=1,shape='wide'}
 local function layout()
  local v=root.AbsoluteSize;if v.X<=0 then return end
  scale=math.clamp(math.min(v.X/1700,v.Y/950),.42,1.25)
  arrow.Size=UDim2.fromOffset(G.ARROW*scale,G.ARROW*scale)
  bannerScale.Scale=math.clamp(math.min(v.X/1500,v.Y/850),.4,1.3)
 end
 root:GetPropertyChangedSignal('AbsoluteSize'):Connect(layout);layout()
 local function moveGuide(pos,s,shape,instant)
  local reshaped=shape~=spot.shape
  spot={pos=pos,s=s,shape=shape}
  applyShape(shape)
  if instant or reshaped then guide.Position=UDim2.fromOffset(pos.X,pos.Y);guideScale.Scale=s;return end
  local info=TweenInfo.new(.4,Enum.EasingStyle.Quad,Enum.EasingDirection.Out)
  TweenService:Create(guide,info,{Position=UDim2.fromOffset(pos.X,pos.Y)}):Play()
  TweenService:Create(guideScale,info,{Scale=s}):Play()
 end

 -- Placement: the box never covers the game's UI, the arrow's target, the player's character or
 -- what the step says to keep clear (the user, 2026-10-03). Obstacles: every visible button,
 -- panel, picture and text on screen (not backdrops over 60% of it; a piece inside the obstacle
 -- it belongs to counts once, as that obstacle). Hard ones: the target and the world things in
 -- ctx.avoid plus the character, drawn as their screen rects, padded. Spots, in this order, the
 -- wide shape first at each size and then the compact one: inside ctx.prefer (next to the chest
 -- menu), the corners and the middle of each side, then (unless ctx.edges, the run) a grid,
 -- farthest from the screen's centre first. The first spot that covers nothing wins; if none
 -- does, the one that covers least. It stays while its spot is still clear.
 local SKIP={TutorialGuide=true,BossIntro=true}
 local ctx={}
 local function solid(c)
  if c:IsA('TextLabel') or c:IsA('TextButton') or c:IsA('TextBox') then
   if c.Text~='' and c.TextTransparency<.9 then return true end
  end
  if (c:IsA('ImageLabel') or c:IsA('ImageButton')) and c.Image~='' and c.ImageTransparency<.9 then return true end
  return c.BackgroundTransparency<.9 and not c:IsA('CanvasGroup')
 end
 -- The part of rect (p, s) inside clip (nil = no clip), or nil when none of it is.
 local function clipped(p,s,clip)
  if not clip then return p,s end
  local x0,y0=math.max(p.X,clip[1].X),math.max(p.Y,clip[1].Y)
  local x1,y1=math.min(p.X+s.X,clip[1].X+clip[2].X),math.min(p.Y+s.Y,clip[1].Y+clip[2].Y)
  if x1-x0<=0 or y1-y0<=0 then return nil end
  return Vector2.new(x0,y0),Vector2.new(x1-x0,y1-y0)
 end
 local function inside(p,s,o_)
  return o_~=nil and p.X>=o_[1].X-1 and p.Y>=o_[1].Y-1 and p.X+s.X<=o_[1].X+o_[2].X+1 and p.Y+s.Y<=o_[1].Y+o_[2].Y+1
 end
 local function obstacles()
  local list={}
  local full=root.AbsoluteSize;local maxArea=full.X*full.Y*.6 -- bigger = a backdrop or shade
  -- clip: what a scrolling list or clipping frame above shows (rows scrolled out don't count).
  -- owner: the nearest obstacle above; pieces inside it are already covered by it.
  local function walk(obj,off,clip,owner)
   for _,c in obj:GetChildren() do
    if c:IsA('GuiObject') then
     if c.Visible then
      local p,size=clipped(c.AbsolutePosition+off,c.AbsoluteSize,clip)
      local mine=owner
      if p and size.X>4 and size.Y>4 and size.X*size.Y<maxArea and solid(c) and not inside(p,size,owner) then
       mine={p,size};table.insert(list,mine)
      end
      if p or not clip then
       local inner=clip
       if c.ClipsDescendants then inner={c.AbsolutePosition+off,c.AbsoluteSize};if clip then local q,z=clipped(inner[1],inner[2],clip);inner=q and {q,z} or nil end end
       if inner or not c.ClipsDescendants then walk(c,off,inner,mine) end
      end
     end
    elseif c:IsA('Folder') then walk(c,off,clip,owner) end
   end
  end
  local off=inset()
  for _,g in player.PlayerGui:GetChildren() do
   if g:IsA('ScreenGui') and g.Enabled and not SKIP[g.Name] then walk(g,off,nil,nil) end
  end
  return list
 end
 -- A world thing's rect on screen (its bounding box's corners in front of the camera), padded by
 -- a third of its larger side; nil when it's off screen.
 local function worldRect(obj)
  if typeof(obj)~='Instance' or not obj.Parent then return nil end
  local cf,size
  if obj:IsA('Model') then cf,size=obj:GetBoundingBox() elseif obj:IsA('BasePart') then cf,size=obj.CFrame,obj.Size else return nil end
  local cam=workspace.CurrentCamera;local x0,y0,x1,y1=math.huge,math.huge,-math.huge,-math.huge
  for _,sx in {-.5,.5} do for _,sy in {-.5,.5} do for _,sz in {-.5,.5} do
   local v=cam:WorldToViewportPoint(cf*(size*Vector3.new(sx,sy,sz)))
   if v.Z>0 then x0,y0,x1,y1=math.min(x0,v.X),math.min(y0,v.Y),math.max(x1,v.X),math.max(y1,v.Y) end
  end end end
  if x0>x1 then return nil end
  local full=root.AbsoluteSize
  if x1<0 or y1<0 or x0>full.X or y0>full.Y then return nil end
  local pad=math.max(x1-x0,y1-y0)/3
  return {Vector2.new(x0-pad,y0-pad),Vector2.new(x1-x0+pad*2,y1-y0+pad*2)}
 end
 local function overlap(ap,as,bp,bs)
  local w=math.min(ap.X+as.X,bp.X+bs.X)-math.max(ap.X,bp.X)
  local h=math.min(ap.Y+as.Y,bp.Y+bs.Y)-math.max(ap.Y,bp.Y)
  return w>0 and h>0 and w*h or 0
 end
 -- The guide's drawn parts at a spot: the portrait, the text box and the name tag.
 local function parts(pos,s,shape)
  local d=G.Shapes[shape];local q,b,g=d.portrait,d.box,d.tag
  return {{pos+Vector2.new(q[1],q[2])*s,Vector2.new(q[3],q[4])*s},{pos+Vector2.new(b[1],b[2])*s,Vector2.new(b[3],b[4])*s},{pos+Vector2.new(g[1],g[2])*s,Vector2.new(tagW,G.TAG_H)*s}}
 end
 -- Spots for the guide at scale s in a shape (top-left corners), in the order they're tried.
 local function spots(full,top,s,shape)
  local size=G.Shapes[shape].size*s
  local m=18*s;local w,h=size.X,size.Y
  local x0,y0=m,top+56*s
  local x1,y1=math.max(x0,full.X-m-w),math.max(y0,full.Y-m-h)
  local midX,midY=math.clamp((full.X-w)/2,x0,x1),math.clamp((full.Y-h)/2,y0,y1)
  local list={}
  local r=ctx.prefer
  if r then
   -- Inside the preferred area: next to its left side first, then outwards from its middle.
   local px0,py0=math.max(x0,r[1]),math.max(y0,r[2]);local px1,py1=math.min(x1,r[3]-w),math.min(y1,r[4]-h)
   if px1>=px0 and py1>=py0 then
    local mid=(py0+py1)/2;local cells={}
    for i=0,5 do for j=0,5 do table.insert(cells,Vector2.new(px0+(px1-px0)*i/5,py0+(py1-py0)*j/5)) end end
    table.sort(cells,function(a,b) if a.X~=b.X then return a.X<b.X end;return math.abs(a.Y-mid)<math.abs(b.Y-mid) end)
    table.move(cells,1,#cells,1,list)
   end
  end
  for _,v in {Vector2.new(x0,y1),Vector2.new(x0,y0),Vector2.new(x1,y1),Vector2.new(x1,y0),Vector2.new(x0,midY),Vector2.new(x1,midY),Vector2.new(midX,y1),Vector2.new(midX,y0)} do table.insert(list,v) end
  if not ctx.edges then
   local grid,centre={},Vector2.new(full.X-w,full.Y-h)/2 -- a centred guide's corner
   for i=0,9 do for j=0,6 do table.insert(grid,Vector2.new(x0+(x1-x0)*i/9,y0+(y1-y0)*j/6)) end end
   table.sort(grid,function(a,b) return (a-centre).Magnitude>(b-centre).Magnitude end)
   table.move(grid,1,#grid,#list+1,list)
  end
  return list
 end
 local TRIES={{'wide',1},{'wide',.8},{'compact',1},{'compact',.8},{'wide',.66},{'compact',.66},{'wide',.52},{'compact',.52}}
 local placedAt=0
 local placed=false -- placed since it last appeared
 local searchAt=0 -- no new search before this while it stays (a recent one found nothing better)
 local targetRect -- set by the arrow: the target's rect, padded
 -- A different kind of screen (edges only, or another preferred area) looks for a spot at once.
 local function ctxKey(c)
  local r=c.prefer
  return (c.edges and 'edges' or '')..(r and string.format('%d,%d,%d,%d',math.floor(r[1]),math.floor(r[2]),math.floor(r[3]),math.floor(r[4])) or '')
 end
 function o.context(c)
  c=c or {}
  if ctxKey(c)~=ctxKey(ctx) then placed=false;searchAt=0;placedAt=0 end
  ctx=c
 end
 local function place(instant)
  local full=root.AbsoluteSize;if full.X<=0 then return end
  local now=os.clock();placedAt=now
  local list=obstacles()
  local hard={}
  if targetRect then table.insert(hard,targetRect) end
  local things=table.clone(ctx.avoid or {});if player.Character then table.insert(things,player.Character) end
  for _,thing in things do local r=worldRect(thing);if r then table.insert(hard,r) end end
  local top=inset().Y
  local best,bestS,bestShape,bestScore
  -- Overlap in px²; the hard ones far above anything else. A spot that can't beat the best stops early.
  local function try(pos,s,shape)
   local score=0
   for _,part in parts(pos,s,shape) do
    local p,z=part[1],part[2]
    if p.X<0 or p.Y<0 or p.X+z.X>full.X or p.Y+z.Y>full.Y then score+=1e7 end
    for _,h in hard do local o_=overlap(p,z,h[1],h[2]);if o_>0 then score+=1e6+o_*50 end end
    for _,o_ in list do
     score+=overlap(p,z,o_[1],o_[2])
     if bestScore and score>=bestScore then return score end
    end
   end
   if not bestScore or score<bestScore then best,bestS,bestShape,bestScore=pos,s,shape,score end
   return score
  end
  -- Where it is goes first, so staying put wins ties.
  if placed then
   -- Clear at full size and wide with no preferred area: nothing could be better. Otherwise it
   -- looks again at most every 1.2 s (a new target looks at once).
   local here=try(spot.pos,spot.s,spot.shape)
   if here==0 and spot.s>=scale*.99 and spot.shape=='wide' and not ctx.prefer or now<searchAt then return end
  end
  local found=false
  for _,tr in TRIES do
   local s=scale*tr[2]
   for _,pos in spots(full,top,s,tr[1]) do if try(pos,s,tr[1])==0 then found=true;break end end
   if found then break end
  end
  placed=true;searchAt=now+1.2
  if best and ((best-spot.pos).Magnitude>2 or math.abs(bestS-spot.s)>.01 or bestShape~=spot.shape) then moveGuide(best,bestS,bestShape,instant) end
 end

 -- Text box ---------------------------------------------------------------------------------
 local current,shown,typed=nil,false,0
 local function show(on)
  if shown==on then return end;shown=on
  if on then placed=false;searchAt=0;place(true) end -- appear straight in a clear spot
  TweenService:Create(guide,TweenInfo.new(on and .35 or .2,Enum.EasingStyle.Quad),{GroupTransparency=on and 0 or 1}):Play()
 end
 function o.say(line,button)
  if line==current and (button==nil)==(buttonHolder:FindFirstChild('Action')==nil) then show(true);return end
  current=line
  buttonHolder:ClearAllChildren()
  if button then
   local b=T.button(buttonHolder,'Action',button.label,0,0,190,58,button.onClick,button.neutral);b.Caption.TextSize=24
  end
  hasButton=button~=nil;setText() -- room for the button
  text.Text=line or '';text.MaxVisibleGraphemes=0
  typed+=1;local mine=typed
  task.spawn(function()
   local n=utf8.len(text.Text) or #text.Text;local t0=os.clock()
   while mine==typed and text.MaxVisibleGraphemes>=0 and text.MaxVisibleGraphemes<n do
    text.MaxVisibleGraphemes=math.min(n,math.floor((os.clock()-t0)*CPS)+1)
    task.wait()
   end
   if mine==typed then text.MaxVisibleGraphemes=-1 end
  end)
  show(true)
 end
 function o.hide() current=nil;show(false);o.point(nil) end

 -- Arrow ------------------------------------------------------------------------------------
 local A={x=0,y=0,rot=180,shown=false,target=nil,from=nil,ctrl=nil,t0=0,rot0=180,rot1=180}
 -- The arrow tip's spot for a target and its rotation (0 = pointing up, 180 = down), in this
 -- screen's pixels; nil when the target isn't on screen.
 local function aim(obj)
  if typeof(obj)~='Instance' or not obj.Parent then return nil end
  local full=root.AbsoluteSize;local gap=6*scale
  if obj:IsA('Model') or obj:IsA('BasePart') then
   -- A world thing (a crystal on the ground): pointed at from above.
   local pos=obj:IsA('Model') and obj:GetPivot().Position or obj.Position
   local v=workspace.CurrentCamera:WorldToViewportPoint(pos)
   if v.Z<=0 or v.X<0 or v.Y<0 or v.X>full.X or v.Y>full.Y then return nil end
   local size=Vector2.new(36,36)*scale;local at=Vector2.new(v.X,v.Y)-size/2
   return Vector2.new(v.X,at.Y-gap),180,at,size
  end
  if not obj:IsA('GuiObject') then return nil end
  local layer=obj:FindFirstAncestorWhichIsA('LayerCollector')
  if not layer or (layer:IsA('ScreenGui') and not layer.Enabled) then return nil end
  local p=obj
  while p and p~=layer do if p:IsA('GuiObject') and not p.Visible then return nil end;p=p.Parent end
  local size=obj.AbsoluteSize;if size.X<2 or size.Y<2 then return nil end
  local at=obj.AbsolutePosition+inset()
  local cx,cy=at.X+size.X/2,at.Y+size.Y/2
  if cy<full.Y*.62 then return Vector2.new(cx,at.Y+size.Y+gap),0,at,size end
  return Vector2.new(cx,at.Y-gap),180,at,size
 end
 local function setArrow(tip,rot,bob)
  -- The image turns about its centre: put the centre so the tip lands on `tip`.
  local r=math.rad(rot);local dir=Vector2.new(math.sin(r),-math.cos(r)) -- where it points
  local size=G.ARROW*scale
  local tipPoint=tip-dir*bob
  local centre=tipPoint-dir*(size*(.5-G.TIP))
  arrow.Position=UDim2.fromOffset(centre.X,centre.Y);arrow.Rotation=rot
 end
 local fade
 local function fadeArrow(on)
  if fade then fade:Cancel() end
  fade=TweenService:Create(arrow,TweenInfo.new(on and .2 or .3),{ImageTransparency=on and 0 or 1});fade:Play()
 end
 -- A new curve from where the arrow is now to the target's tip spot.
 local function glide(tip,rot)
  if not A.shown then
   -- Appearing: come in from a little way back along its pointing line.
   A.x,A.y=tip.X,tip.Y+(rot==0 and 160 or -160)*scale;A.rot=rot
  end
  A.from=Vector2.new(A.x,A.y);A.t0=os.clock();A.rot0=A.rot;A.rot1=rot
  local d=tip-A.from;local len=math.max(d.Magnitude,1)
  local bulge=math.min(170*scale,len*.32)
  A.ctrl=(A.from+tip)/2+Vector2.new(-d.Y,d.X)/len*bulge-Vector2.new(0,40*scale)
  A.glideTo=A.target;A.lost=nil
  if not A.shown then A.shown=true;fadeArrow(true) end
 end
 function o.point(obj)
  if obj==A.target then return end
  A.target=obj;searchAt=0 -- a new target: move off it at once if the box is on it
  local tip,rot=aim(obj)
  if tip then glide(tip,rot) end -- otherwise frame() picks it up once it shows, or fades the arrow
 end
 local function frame()
  -- Keep the box clear of the UI (place) and of the target and its arrow (targetRect).
  if shown then
   local _,_,at,size=aim(A.shown and A.target or nil)
   if at then local pad=G.ARROW*scale*1.2;targetRect={at-Vector2.new(pad*.4,pad),size+Vector2.new(pad*.8,pad*2)} else targetRect=nil end
   if os.clock()-placedAt>.35 then place(false) end
  end
  if not A.shown and not A.target then return end
  local tip,rot=aim(A.target)
  if not tip then
   -- The target is gone (a screen rebuilt its buttons, or there's nothing to point at): hold
   -- still for a moment so the next target is glided to from here, then fade out.
   if A.shown then
    A.lost=A.lost or os.clock()
    if os.clock()-A.lost>.6 then A.shown=false;A.lost=nil;fadeArrow(false) end
   end
   return
  end
  if A.glideTo~=A.target or A.lost then glide(tip,rot) end
  if rot~=A.rot1 then A.from=Vector2.new(A.x,A.y);A.t0=os.clock();A.rot0=A.rot;A.rot1=rot;A.ctrl=(A.from+tip)/2 end
  local k=math.clamp((os.clock()-A.t0)/G.GLIDE,0,1);local e=ease(k);local u=1-e
  local p=A.from*u*u+A.ctrl*2*u*e+tip*e*e
  local turn=((A.rot1-A.rot0+540)%360)-180
  A.rot=A.rot0+turn*e;A.x,A.y=p.X,p.Y
  local bob=k>=1 and (math.sin(os.clock()*5.8)+1)*5*scale or 0
  setArrow(p,A.rot,bob)
 end
 local conn=RunService.RenderStepped:Connect(frame)
 o.frame=frame -- Edit-mode previews step it by hand (RenderStepped doesn't run there)
 function o.where() return spot.pos,spot.s,spot.shape end -- previews: where the guide sits

 -- Banner -----------------------------------------------------------------------------------
 local bannerToken=0
 function o.banner(top,big,seconds)
  bannerToken+=1;local mine=bannerToken
  bannerTop.Text=top or '';bannerBig.Text=big or ''
  bannerLayer.Visible=true;bannerLayer.BackgroundTransparency=1
  TweenService:Create(bannerLayer,TweenInfo.new(.4),{BackgroundTransparency=.45}):Play()
  local pop=bannerBig:FindFirstChild('Pop') or T.make('UIScale',bannerBig,{Name='Pop',Scale=1})
  pop.Scale=1.6;TweenService:Create(pop,TweenInfo.new(.5,Enum.EasingStyle.Back,Enum.EasingDirection.Out),{Scale=1}):Play()
  T.sound('ui_upgrade')
  task.delay(seconds or 3,function()
   if mine~=bannerToken then return end
   TweenService:Create(bannerLayer,TweenInfo.new(.3),{BackgroundTransparency=1}):Play()
   task.wait(.3);if mine==bannerToken then bannerLayer.Visible=false end
  end)
 end
 function o.destroy() conn:Disconnect();screen:Destroy() end
 return o
end
return G
