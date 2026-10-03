-- The tutorial guide's look (plans/2026-10-03-tutorial-design.md; mockup approved from
-- roguelite-planning/previews/tutorial-guide/guide.html): the Egg Merchant's portrait and text box
-- bottom-left, ONE arrow that glides between targets, and the VICTORY banner. Presentation only:
-- TutorialGuide.client decides what is said and pointed at.
--   G.new(player, assets) -> guide
--   guide.say(text, button)   types the line in (button: {label=, onClick=} or nil); same text = no-op
--   guide.hide()              tucks the box away (the arrow too)
--   guide.point(obj)          the arrow glides to a GuiObject (any ScreenGui) and rests there,
--                             bobbing; nil fades it out where it is
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
G.BOX_W,G.BOX_H=860,300 -- the guide (portrait + box) at scale 1
local CPS=46 -- typed characters per second

local function ease(t) return t<.5 and 4*t*t*t or 1-(-2*t+2)^3/2 end
-- Where a ScreenGui's (0,0) is on the real screen: GuiObject.AbsolutePosition is relative to its
-- own layer, which insets move. Device insets (phone notches, landscape) are the same left and
-- right; the core UI inset is the top bar.
local function origin(layer,full)
 if not layer or not layer:IsA('ScreenGui') then return Vector2.zero end
 local mode=layer.ScreenInsets
 if mode==Enum.ScreenInsets.None or layer.IgnoreGuiInset and mode==Enum.ScreenInsets.CoreUISafeInsets then return Vector2.zero end
 local size=layer.AbsoluteSize
 local x=math.max(0,(full.X-size.X)/2)
 if mode==Enum.ScreenInsets.DeviceSafeInsets then return Vector2.new(x,0) end
 local topLeft=GuiService:GetGuiInset()
 return Vector2.new(math.max(x,topLeft.X),topLeft.Y)
end

function G.new(player,assets)
 local o={}
 local screen=T.make('ScreenGui',player:WaitForChild('PlayerGui'),{Name='TutorialGuide',ResetOnSpawn=false,DisplayOrder=95,
  ScreenInsets=Enum.ScreenInsets.None,ZIndexBehavior=Enum.ZIndexBehavior.Sibling})
 o.Screen=screen
 local root=T.frame(screen,'Root',0,0,0,0);root.Size=UDim2.fromScale(1,1)
 local scale=1
 -- The guide: portrait over the left end of a dark box that fades out to the right.
 local guide=T.make('CanvasGroup',root,{Name='Guide',BackgroundTransparency=1,Size=UDim2.fromOffset(G.BOX_W,G.BOX_H),GroupTransparency=1})
 local guideScale=T.make('UIScale',guide,{Scale=1})
 local box=T.make('Frame',guide,{Name='Box',Position=UDim2.fromOffset(150,G.BOX_H-180),Size=UDim2.fromOffset(G.BOX_W-150,150),BackgroundColor3=Color3.fromRGB(8,12,10),BackgroundTransparency=.08,BorderSizePixel=0})
 T.make('UIGradient',box,{Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,0),NumberSequenceKeypoint.new(.7,.08),NumberSequenceKeypoint.new(1,1)})})
 T.make('Frame',box,{Name='Edge',Size=UDim2.new(0,6,1,0),BackgroundColor3=C.lime,BorderSizePixel=0})
 local text=T.label(box,'Line','',140,14,G.BOX_W-150-180,122,36);text.TextXAlignment=Enum.TextXAlignment.Left
 local tag=T.make('Frame',guide,{Name='NameTag',Position=UDim2.fromOffset(290,G.BOX_H-212),Size=UDim2.fromOffset(196,32),BackgroundColor3=C.lime,BorderSizePixel=0})
 T.make('UICorner',tag,{CornerRadius=UDim.new(0,4)})
 local tagText=T.label(tag,'Text','EGG MERCHANT',8,2,180,28,20,C.ink);tagText.TextStrokeTransparency=1
 local portrait=T.make('ImageLabel',guide,{Name='Portrait',BackgroundTransparency=1,Position=UDim2.fromOffset(0,0),Size=UDim2.fromOffset(300,300),Image=assets.portrait or '',ScaleType=Enum.ScaleType.Fit})
 local buttonHolder=T.frame(guide,'Buttons',G.BOX_W-200,G.BOX_H-74,190,58)
 -- The arrow.
 local arrow=T.make('ImageLabel',root,{Name='Arrow',BackgroundTransparency=1,AnchorPoint=Vector2.new(.5,.5),Size=UDim2.fromOffset(G.ARROW,G.ARROW),
  Image=assets.arrow or '',ImageTransparency=1,ZIndex=5})
 -- The VICTORY banner.
 local bannerLayer=T.make('Frame',root,{Name='Banner',Size=UDim2.fromScale(1,1),BackgroundColor3=C.shade,BackgroundTransparency=1,BorderSizePixel=0,Visible=false,ZIndex=3})
 local bannerScale=T.make('UIScale',bannerLayer,{Scale=1})
 local bannerTop=T.label(bannerLayer,'Top','',0,0,0,0,46,C.white);bannerTop.AnchorPoint=Vector2.new(.5,.5);bannerTop.Position=UDim2.new(.5,0,.5,-110);bannerTop.Size=UDim2.fromOffset(900,60);bannerTop.ZIndex=4
 local bannerBig=T.label(bannerLayer,'Big','',0,0,0,0,150,C.gold);bannerBig.AnchorPoint=Vector2.new(.5,.5);bannerBig.Position=UDim2.fromScale(.5,.5);bannerBig.Size=UDim2.fromOffset(1100,170);bannerBig.ZIndex=4
 bannerBig.TextStrokeTransparency=0
 for i,side in {-1,1} do
  local line=T.make('Frame',bannerLayer,{Name='Line'..i,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.new(.5,side*560,.5,0),Size=UDim2.fromOffset(300,6),BackgroundColor3=C.gold,BorderSizePixel=0,ZIndex=4})
  T.make('UIGradient',line,{Transparency=NumberSequence.new(side<0 and 1 or 0,side<0 and 0 or 1)})
 end

 -- Where the guide sits: spot = {pos (top-left, screen px), s (its scale)}; placement below moves it.
 local spot={pos=Vector2.zero,s=1}
 local function layout()
  local v=root.AbsoluteSize;if v.X<=0 then return end
  scale=math.clamp(math.min(v.X/1700,v.Y/950),.42,1.25)
  arrow.Size=UDim2.fromOffset(G.ARROW*scale,G.ARROW*scale)
  bannerScale.Scale=math.clamp(math.min(v.X/1500,v.Y/850),.4,1.3)
 end
 root:GetPropertyChangedSignal('AbsoluteSize'):Connect(layout);layout()
 local function moveGuide(pos,s,instant)
  spot={pos=pos,s=s}
  if instant then guide.Position=UDim2.fromOffset(pos.X,pos.Y);guideScale.Scale=s;return end
  local info=TweenInfo.new(.4,Enum.EasingStyle.Quad,Enum.EasingDirection.Out)
  TweenService:Create(guide,info,{Position=UDim2.fromOffset(pos.X,pos.Y)}):Play()
  TweenService:Create(guideScale,info,{Scale=s}):Play()
 end

 -- Placement: the box never covers the game's UI (the user, 2026-10-03). Every visible button,
 -- panel, picture and text on screen (other than backdrops over 60% of it) is an obstacle. The
 -- guide takes the first spot that covers none of them, trying a smaller size before giving up:
 -- bottom-left, top-left, bottom-right, top-right, middle-left. If every spot covers something it
 -- takes the one that covers the least, and never the arrow's target. Checked a few times a
 -- second while it's showing; it glides to a new spot.
 local SKIP={TutorialGuide=true,BossIntro=true}
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
 local function obstacles()
  local list={}
  local full=root.AbsoluteSize;local maxArea=full.X*full.Y*.6 -- bigger = a backdrop or shade
  -- clip: what a scrolling list or clipping frame above shows (rows scrolled out don't count).
  local function walk(obj,off,clip)
   for _,c in obj:GetChildren() do
    if c:IsA('GuiObject') then
     if c.Visible then
      local p,size=clipped(c.AbsolutePosition+off,c.AbsoluteSize,clip)
      if p and size.X>4 and size.Y>4 and size.X*size.Y<maxArea and solid(c) then table.insert(list,{p,size}) end
      if p or not clip then
       local inner=clip
       if c.ClipsDescendants then inner={c.AbsolutePosition+off,c.AbsoluteSize};if clip then local q,z=clipped(inner[1],inner[2],clip);inner=q and {q,z} or nil end end
       if inner or not c.ClipsDescendants then walk(c,off,inner) end
      end
     end
    elseif c:IsA('Folder') then walk(c,off,clip) end
   end
  end
  for _,g in player.PlayerGui:GetChildren() do
   if g:IsA('ScreenGui') and g.Enabled and not SKIP[g.Name] then walk(g,origin(g,full),nil) end
  end
  return list
 end
 local function overlap(ap,as,bp,bs)
  local w=math.min(ap.X+as.X,bp.X+bs.X)-math.max(ap.X,bp.X)
  local h=math.min(ap.Y+as.Y,bp.Y+bs.Y)-math.max(ap.Y,bp.Y)
  return w>0 and h>0 and w*h or 0
 end
 -- The guide's drawn parts at a spot: the portrait, the text box and the name tag.
 local function parts(pos,s)
  return {{pos,Vector2.new(300,300)*s},{pos+Vector2.new(150,G.BOX_H-180)*s,Vector2.new(G.BOX_W-150,150)*s},{pos+Vector2.new(290,G.BOX_H-212)*s,Vector2.new(196,32)*s}}
 end
 local placedAt=0
 local targetRect -- set by the arrow: the target's rect, padded (never covered)
 local function place(instant)
  local full=root.AbsoluteSize;if full.X<=0 then return end
  local list=obstacles()
  local top=(GuiService:GetGuiInset()).Y
  local best,bestS,bestScore
  -- Staying put wins ties, so the box doesn't hop between equally good spots.
  local function try(pos,s)
   local score=0
   for _,part in parts(pos,s) do
    if part[1].X<0 or part[1].Y<0 or part[1].X+part[2].X>full.X or part[1].Y+part[2].Y>full.Y then score+=1e7 end
    for _,o in list do score+=overlap(part[1],part[2],o[1],o[2]) end
    if targetRect then score+=overlap(part[1],part[2],targetRect[1],targetRect[2])*50 end
   end
   if not bestScore or score<bestScore then best,bestS,bestScore=pos,s,score end
   return score==0
  end
  if not (placedAt>0 and spot.s>=scale*.99 and try(spot.pos,spot.s)) then
   for _,k in {1,.8,.66,.52} do
    local s=scale*k;local m=18*s;local w,h=G.BOX_W*s,G.BOX_H*s
    local found=false
    for _,pos in {Vector2.new(m,full.Y-m-h),Vector2.new(m,top+56*s),Vector2.new(full.X-m-w,full.Y-m-h),Vector2.new(full.X-m-w,top+56*s),Vector2.new(m,(full.Y-h)/2)} do
     if try(pos,s) then found=true;break end
    end
    if found then break end
   end
  end
  if best and ((best-spot.pos).Magnitude>2 or math.abs(bestS-spot.s)>.01) then moveGuide(best,bestS,instant) end
  placedAt=os.clock()
 end

 -- Text box ---------------------------------------------------------------------------------
 local current,shown,typed=nil,false,0
 local function show(on)
  if shown==on then return end;shown=on
  if on then placedAt=0;place(true) end -- appear straight in a clear spot
  TweenService:Create(guide,TweenInfo.new(on and .35 or .2,Enum.EasingStyle.Quad),{GroupTransparency=on and 0 or 1}):Play()
 end
 function o.say(line,button)
  if line==current and (button==nil)==(buttonHolder:FindFirstChild('Action')==nil) then show(true);return end
  current=line
  buttonHolder:ClearAllChildren()
  if button then
   local b=T.button(buttonHolder,'Action',button.label,0,0,190,58,button.onClick,button.neutral);b.Caption.TextSize=24
  end
  text.Size=UDim2.fromOffset(button and 330 or G.BOX_W-150-180,122) -- room for the button
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
  if not obj or not obj.Parent or not obj:IsA('GuiObject') then return nil end
  local layer=obj:FindFirstAncestorWhichIsA('LayerCollector')
  if not layer or (layer:IsA('ScreenGui') and not layer.Enabled) then return nil end
  local p=obj
  while p and p~=layer do if p:IsA('GuiObject') and not p.Visible then return nil end;p=p.Parent end
  local size=obj.AbsoluteSize;if size.X<2 or size.Y<2 then return nil end
  local full=root.AbsoluteSize
  local at=obj.AbsolutePosition+origin(layer,full)
  local cx,cy=at.X+size.X/2,at.Y+size.Y/2
  local gap=6*scale
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
 function o.point(obj)
  if obj==A.target then return end
  A.target=obj
  local tip,rot=aim(obj)
  if not tip then if A.shown then A.shown=false;fadeArrow(false) end;return end
  if not A.shown then
   -- Appearing: come in from a little way back along its pointing line.
   A.x,A.y=tip.X,tip.Y+(rot==0 and 160 or -160)*scale;A.rot=rot
  end
  A.from=Vector2.new(A.x,A.y);A.t0=os.clock();A.rot0=A.rot;A.rot1=rot
  local d=tip-A.from;local len=math.max(d.Magnitude,1)
  local bulge=math.min(170*scale,len*.32)
  A.ctrl=(A.from+tip)/2+Vector2.new(-d.Y,d.X)/len*bulge-Vector2.new(0,40*scale)
  A.shown=true;fadeArrow(true)
 end
 local function frame()
  -- Keep the box clear of the UI (place) and of the target and its arrow (targetRect).
  if shown then
   local _,_,at,size=aim(A.shown and A.target or nil)
   if at then local pad=G.ARROW*scale*1.2;targetRect={at-Vector2.new(pad*.4,pad),size+Vector2.new(pad*.8,pad*2)} else targetRect=nil end
   if os.clock()-placedAt>.35 then place(false) end
  end
  if not A.shown or not A.target then return end
  local tip,rot=aim(A.target)
  if not tip then A.shown=false;fadeArrow(false);return end
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
