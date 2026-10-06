-- Shared green UI theme: charcoal nine-slice panels with lime corners, lime buttons,
-- faceted stone end caps and FredokaOne type. Presentation only; no gameplay authority.
local TweenService=game:GetService('TweenService')
local Players=game:GetService('Players')
local T={}

T.Color={
 white=Color3.fromRGB(248,249,245), muted=Color3.fromRGB(174,183,185), dim=Color3.fromRGB(120,128,131),
 lime=Color3.fromRGB(145,239,20), limeSoft=Color3.fromRGB(210,255,161), limeDark=Color3.fromRGB(58,112,12),
 red=Color3.fromRGB(239,35,47), negative=Color3.fromRGB(255,105,105), gold=Color3.fromRGB(255,203,64),
 cyan=Color3.fromRGB(100,220,255), cream=Color3.fromRGB(234,221,167), emerald=Color3.fromRGB(70,226,120),
 well=Color3.fromRGB(34,39,43), track=Color3.fromRGB(22,29,32), shade=Color3.fromRGB(5,9,10), ink=Color3.fromRGB(10,14,8),
}
-- Rarity: common, rare, epic, legendary. Used as accent strips and name colours only.
T.Tier={Color3.fromRGB(218,224,228),Color3.fromRGB(79,183,245),Color3.fromRGB(192,116,249),Color3.fromRGB(248,88,99)}
T.Roman={'I','II','III','IV'}
T.Font=Enum.Font.FredokaOne
T.Body=Enum.Font.SourceSansBold

T.Asset={
 panel='rbxassetid://116439058081230', inset='rbxassetid://82653359149627', button='rbxassetid://72732018694626',
 stone='rbxassetid://107387940957948', heart='rbxassetid://101432943753406', gem='rbxassetid://102213113777434',
 bag='rbxassetid://82818131570338', shard='rbxassetid://119781825571908', xp='rbxassetid://101475186887359',
 teeth='rbxassetid://113971691535704', shoulders='rbxassetid://103758481309908', pan='rbxassetid://120727496371371',
 duck='rbxassetid://72853007735977', staff='rbxassetid://102427273904664',
 -- User-generated HUD icons (ui/assets/hud/asset-ids.json).
 play='rbxassetid://119231770241307', chest='rbxassetid://128369126123154', armory='rbxassetid://128990045041232',
 loadout='rbxassetid://73755136987218', store='rbxassetid://113789432822588', quests='rbxassetid://85014504299735',
 achievements='rbxassetid://79366861483753', profile='rbxassetid://138623258102251', party='rbxassetid://83985140371877',
 settings='rbxassetid://127804812980101',
 -- Rarity (build_assets.py): `panel` without accents, plus white corner accents to tint.
 panelPlain='rbxassetid://105310886449973', corners='rbxassetid://122511819290059',
 -- build_assets.py `lock`: steel shackle, brass body.
 lock='rbxassetid://89513131203273',
 -- User-supplied art: premium currency and the run's shard bag.
 emerald='rbxassetid://107205947937384', shardBag='rbxassetid://129322350142524',
}
-- The supplied shard art sits inside a larger atlas; crop to the crystal.
T.ShardRect={offset=Vector2.new(280,130),size=Vector2.new(460,780)}
local SLICE=Rect.new(48,48,208,208)

function T.make(class,parent,props)
 local o=Instance.new(class)
 for k,v in props do o[k]=v end
 o.Parent=parent
 return o
end
local make=T.make

function T.frame(parent,name,x,y,w,h)
 return make('Frame',parent,{Name=name,BackgroundTransparency=1,BorderSizePixel=0,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(w,h)})
end
-- Shared, sandbox-safe check. ShopUI cannot require the unsandboxed lobby StoreFX module.
function T.check(parent,x,y,size)
 local c=make('Frame',parent,{Name='Check',Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(size,size),BackgroundColor3=T.Color.lime,BorderSizePixel=0})
 make('UICorner',c,{CornerRadius=UDim.new(1,0)})
 make('UIStroke',c,{Color=T.Color.ink,Thickness=math.max(1,size*.08)})
 for _,b in {{.375,.5625,.333,45},{.604,.479,.5,-50}} do
  local line=make('Frame',c,{Name='Mark',AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromScale(b[1],b[2]),Size=UDim2.fromScale(b[3],.146),Rotation=b[4],BackgroundColor3=T.Color.white,BorderSizePixel=0})
  make('UICorner',line,{CornerRadius=UDim.new(1,0)})
 end
 return c
end
-- kind: 'panel' (lime corners), 'inset' (plain dark well) or 'button' (lime face).
function T.panel(parent,name,x,y,w,h,kind)
 return make('ImageLabel',parent,{Name=name,BackgroundTransparency=1,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(w,h),Image=T.Asset[kind or 'panel'],ScaleType=Enum.ScaleType.Slice,SliceCenter=SLICE,SliceScale=.55})
end
function T.icon(parent,name,x,y,size,asset)
 local i=make('ImageLabel',parent,{Name=name,BackgroundTransparency=1,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(size,size),Image=T.Asset[asset] or asset or '',ScaleType=Enum.ScaleType.Fit})
 if asset=='shard' then i.ImageRectOffset=T.ShardRect.offset;i.ImageRectSize=T.ShardRect.size end
 return i
end
-- Chunky outlined headline text at TextSize; wraps inside its box. Text that would not fit (a long
-- name, a big number, a narrow screen layout) shrinks to fit instead of spilling out, down to 60%
-- of its size. Setting TextSize later moves the cap with it. A caller that adds its own
-- UITextSizeConstraint replaces this one.
function T.label(parent,name,text,x,y,w,h,size,color)
 size=size or 24
 local l=make('TextLabel',parent,{Name=name,BackgroundTransparency=1,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(w,h),Text=text,TextColor3=color or T.Color.white,Font=T.Font,TextSize=size,TextScaled=true,TextWrapped=true,TextStrokeColor3=Color3.new(0,0,0),TextStrokeTransparency=.12})
 -- Named FitText so callers' own `.UITextSizeConstraint` lookups always find theirs.
 local fit=make('UITextSizeConstraint',l,{Name='FitText',MaxTextSize=size,MinTextSize=math.min(size,math.max(9,math.floor(size*.6)))})
 l:GetPropertyChangedSignal('TextSize'):Connect(function()
  if fit.Parent then fit.MaxTextSize=l.TextSize;fit.MinTextSize=math.min(l.TextSize,math.max(9,math.floor(l.TextSize*.6))) end
 end)
 l.ChildAdded:Connect(function(c) if c~=fit and c:IsA('UITextSizeConstraint') then fit:Destroy() end end)
 return l
end
-- Body copy: left aligned, shrinks to fit between 9px and `size`.
function T.text(parent,name,text,x,y,w,h,size,color)
 local l=make('TextLabel',parent,{Name=name,BackgroundTransparency=1,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(w,h),Text=text,TextColor3=color or T.Color.white,Font=T.Body,TextSize=size or 16,TextScaled=true,TextWrapped=true,RichText=true,TextXAlignment=Enum.TextXAlignment.Left,TextStrokeColor3=Color3.new(0,0,0),TextStrokeTransparency=.55})
 make('UITextSizeConstraint',l,{MinTextSize=9,MaxTextSize=size or 16})
 return l
end
function T.hex(color) return string.format('#%02X%02X%02X',math.round(color.R*255),math.round(color.G*255),math.round(color.B*255)) end

-- Buttons: lime face by default, charcoal panel when `neutral`. Interactable=false dims them.
function T.button(parent,name,text,x,y,w,h,callback,neutral)
 local b=make('ImageButton',parent,{Name=name,BackgroundTransparency=1,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(w,h),Image=T.Asset[neutral and 'panel' or 'button'],ScaleType=Enum.ScaleType.Slice,SliceCenter=SLICE,SliceScale=.5,AutoButtonColor=false,Selectable=true})
 b:SetAttribute('Neutral',neutral==true)
 local t=T.label(b,'Caption',text,8,4,w-16,h-8,22);t.Size=UDim2.new(1,-16,1,-8)
 local over=false
 local function paint()
  local enabled=b.Interactable
  local tier=b:GetAttribute('Tier') or 1
  if tier>1 then
   -- Same charcoal panel; only the corner accents (RarityCorners child) carry the colour.
   b.Image=T.Asset.panelPlain
   b.ImageColor3=not enabled and Color3.fromRGB(150,150,150) or over and Color3.fromRGB(215,222,228) or Color3.new(1,1,1)
  else
   b.Image=T.Asset[(b:GetAttribute('Neutral') or not enabled) and 'panel' or 'button']
   b.ImageColor3=not enabled and Color3.fromRGB(150,150,150) or over and T.Color.limeSoft or Color3.new(1,1,1)
  end
  t.TextTransparency=enabled and 0 or .4
 end
 b.MouseEnter:Connect(function() over=true;paint() end)
 b.MouseLeave:Connect(function() over=false;paint() end)
 b.SelectionGained:Connect(function() over=true;paint() end)
 b.SelectionLost:Connect(function() over=false;paint() end)
 b:GetPropertyChangedSignal('Interactable'):Connect(paint)
 b:GetAttributeChangedSignal('Neutral'):Connect(paint)
 b:GetAttributeChangedSignal('Tier'):Connect(paint)
 if callback then b.Activated:Connect(callback) end
 paint()
 return b
end
-- Switch an existing button between lime (selected/primary) and charcoal.
function T.setPrimary(b,primary) b:SetAttribute('Neutral',not primary) end

-- Rarity: same panel, corner accents recoloured (II blue, III purple, IV red). Common (I)
-- keeps the lime corners. Works on labels and buttons (buttons repaint through hover).
function T.setTier(obj,tier)
 tier=tier or 1
 obj:SetAttribute('Tier',tier)
 local corners=obj:FindFirstChild('RarityCorners')
 if tier>1 then
  if not obj:IsA('GuiButton') then obj.Image=T.Asset.panelPlain;obj.ImageColor3=Color3.new(1,1,1) end
  if not corners then
   corners=make('ImageLabel',obj,{Name='RarityCorners',BackgroundTransparency=1,Size=UDim2.fromScale(1,1),Image=T.Asset.corners,ScaleType=Enum.ScaleType.Slice,SliceCenter=SLICE,SliceScale=obj.SliceScale,ZIndex=obj.ZIndex})
  end
  corners.ImageColor3=T.Tier[tier]
 elseif corners then corners:Destroy() end
 return obj
end
function T.rarityPanel(parent,name,x,y,w,h,tier)
 return T.setTier(T.panel(parent,name,x,y,w,h,'panel'),tier)
end
-- Solid rarity pill with the tier numeral (I-IV). Anchored by its top-left unless given.
T.TierFill={Color3.fromRGB(96,104,108),Color3.fromRGB(34,122,190),Color3.fromRGB(128,62,196),Color3.fromRGB(196,44,56)}
function T.tierBadge(parent,tier,x,y,anchor)
 tier=math.clamp(tier or 1,1,4)
 local b=make('Frame',parent,{Name='TierBadge',Position=UDim2.fromOffset(x,y),AnchorPoint=anchor or Vector2.zero,Size=UDim2.fromOffset(tier==1 and 22 or 18+#T.Roman[tier]*8,20),BackgroundColor3=T.TierFill[tier],BorderSizePixel=0,ZIndex=4})
 make('UICorner',b,{CornerRadius=UDim.new(0,5)})
 make('UIStroke',b,{Color=Color3.fromRGB(8,10,11),Thickness=2})
 local l=T.label(b,'Tier',T.Roman[tier],0,0,0,0,15);l.Size=UDim2.fromScale(1,1);l.ZIndex=5;l.TextStrokeTransparency=.3
 return b
end
-- Upgrade progress: "have / need" printed inside a lime bar. need=nil means max tier.
function T.upgradeBar(parent,name,x,y,w,h,have,need)
 local fill,track=T.bar(parent,name,x,y,w,h,need and have>=need and T.Color.gold or T.Color.lime)
 T.setBar(fill,need and have/need or 1)
 local l=T.label(track,'Count',need and (have..' / '..need) or 'MAX',0,0,0,0,math.min(16,h),T.Color.white);l.Size=UDim2.fromScale(1,1);l.ZIndex=3;l.TextStrokeTransparency=0
 return track
end
-- Faceted stone end caps on either side of a header panel.
function T.caps(parent,size)
 size=size or 40
 local l=T.icon(parent,'LeftStone',0,0,size,'stone');l.AnchorPoint=Vector2.new(.5,.5);l.Position=UDim2.new(0,4,.5,0)
 local r=T.icon(parent,'RightStone',0,0,size,'stone');r.AnchorPoint=Vector2.new(.5,.5);r.Position=UDim2.new(1,-4,.5,0)
 return l,r
end
-- Progress bar in a dark inset well. Returns the fill frame; call T.setBar(fill,ratio).
function T.bar(parent,name,x,y,w,h,color)
 local track=make('Frame',parent,{Name=name,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(w,h),BackgroundColor3=T.Color.track,BorderSizePixel=0,ClipsDescendants=true})
 make('UICorner',track,{CornerRadius=UDim.new(0,4)})
 make('UIStroke',track,{Color=Color3.fromRGB(8,10,11),Thickness=2})
 local fill=make('Frame',track,{Name='Fill',Size=UDim2.fromScale(0,1),BackgroundColor3=color or T.Color.lime,BorderSizePixel=0})
 make('UICorner',fill,{CornerRadius=UDim.new(0,4)})
 make('UIGradient',fill,{Rotation=90,Color=ColorSequence.new(Color3.new(1,1,1),Color3.fromRGB(165,165,165))})
 return fill,track
end
function T.setBar(fill,ratio,animate)
 ratio=math.clamp(ratio or 0,0,1)
 if animate then TweenService:Create(fill,TweenInfo.new(.22,Enum.EasingStyle.Quad,Enum.EasingDirection.Out),{Size=UDim2.fromScale(ratio,1)}):Play()
 else fill.Size=UDim2.fromScale(ratio,1) end
end
-- Red notification pill in a corner. Text '' or nil hides it.
function T.badge(parent,text)
 local b=parent:FindFirstChild('Badge')
 if not b then
  b=make('Frame',parent,{Name='Badge',AnchorPoint=Vector2.new(.5,.5),Position=UDim2.new(1,-8,0,8),Size=UDim2.fromOffset(28,28),BackgroundColor3=Color3.fromRGB(214,38,46),BorderSizePixel=0,ZIndex=5})
  make('UICorner',b,{CornerRadius=UDim.new(1,0)})
  make('UIStroke',b,{Color=Color3.fromRGB(20,10,10),Thickness=2.5})
  local l=T.label(b,'Count','',0,0,28,28,17);l.Size=UDim2.fromScale(1,1);l.ZIndex=6
 end
 b.Visible=text~=nil and text~=''
 b.Count.Text=text or ''
 b.Size=UDim2.fromOffset(math.max(28,12+#(text or '')*11),28)
 return b
end
-- Large icon-with-caption launcher (lobby bar, HUD menu). Grows slightly on hover.
function T.iconButton(parent,name,asset,caption,size,callback)
 local b=make('ImageButton',parent,{Name=name,BackgroundTransparency=1,Image='',Size=UDim2.fromOffset(size,size+(caption~='' and 22 or 0)),AutoButtonColor=false,Selectable=true})
 local scale=make('UIScale',b,{Scale=1})
 local art=T.icon(b,'Icon',0,0,size,asset)
 local l
 if caption~='' then l=T.label(b,'Caption',caption,-20,size-10,size+40,30,math.clamp(math.floor(size*.3),14,24));l.TextWrapped=false end
 local function to(v) TweenService:Create(scale,TweenInfo.new(.12,Enum.EasingStyle.Back,Enum.EasingDirection.Out),{Scale=v}):Play() end
 b.MouseEnter:Connect(function() to(1.08) end);b.MouseLeave:Connect(function() to(1) end)
 b.SelectionGained:Connect(function() to(1.08) end);b.SelectionLost:Connect(function() to(1) end)
 b.MouseButton1Down:Connect(function() to(.94) end);b.MouseButton1Up:Connect(function() to(1.08) end)
 if callback then b.Activated:Connect(callback) end
 return b,art,l
end
-- Row of tab buttons. The selected tab is lime; the rest charcoal.
function T.tabs(parent,x,y,w,h,list,selected,callback)
 local gap=8;local bw=(w-gap*(#list-1))/#list;local out={}
 for i,id in list do
  local b=T.button(parent,'Tab_'..id,id,x+(i-1)*(bw+gap),y,bw,h,function() callback(id) end,id~=selected)
  b.Caption.TextSize=math.min(20,h-14);out[id]=b
 end
 return out
end
function T.scroll(parent,name,x,y,w,h)
 return make('ScrollingFrame',parent,{Name=name,BackgroundTransparency=1,BorderSizePixel=0,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(w,h),CanvasSize=UDim2.new(),ScrollBarThickness=6,ScrollBarImageColor3=T.Color.lime,ScrollingDirection=Enum.ScrollingDirection.Y,VerticalScrollBarInset=Enum.ScrollBarInset.ScrollBar})
end
-- Small rounded chip, e.g. PREVIEW / LOCKED / OWNED.
function T.chip(parent,name,text,x,y,color,textColor)
 local size=game:GetService('TextService'):GetTextSize(text,14,T.Font,Vector2.new(1000,100))
 local c=make('Frame',parent,{Name=name,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(size.X+16,22),BackgroundColor3=color or T.Color.well,BorderSizePixel=0})
 make('UICorner',c,{CornerRadius=UDim.new(0,6)})
 make('UIStroke',c,{Color=Color3.fromRGB(8,10,11),Thickness=1.5})
 local l=T.label(c,'Text',text,0,0,0,0,14,textColor);l.Size=UDim2.fromScale(1,1);l.TextStrokeTransparency=.6
 return c
end
-- Rounded tag with an optional icon on the left, e.g. a weapon's class and type on cards:
-- [pan icon] BRAWLER   [MELEE]. o: icon, color (background), textColor, h (28), size (15), maxW
-- (the text shrinks to fit).
-- Returns the tag and its width, so callers can line several up.
function T.tag(parent,name,text,x,y,o)
 o=o or {}
 local h=o.h or 28;local size=o.size or 15;local iconW=o.icon and h-6 or 0
 -- Text measured at design size draws a little wider at small canvas scales: 12% slack.
 local tw=game:GetService('TextService'):GetTextSize(text,size,T.Font,Vector2.new(1000,100)).X*1.12
 local w=math.ceil(tw)+(o.icon and iconW+14 or 20)
 if o.maxW and w>o.maxW then tw=tw-(w-o.maxW);w=o.maxW end
 local c=make('Frame',parent,{Name=name,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(w,h),BackgroundColor3=o.color or Color3.fromRGB(42,50,54),BorderSizePixel=0})
 make('UICorner',c,{CornerRadius=UDim.new(0,7)})
 make('UIStroke',c,{Color=Color3.fromRGB(8,10,11),Thickness=2})
 if o.icon then T.icon(c,'Icon',4,3,iconW,o.icon) end
 local l=T.label(c,'Text',text,o.icon and iconW+7 or 7,0,math.ceil(tw)+6,h,size,o.textColor);l.TextStrokeTransparency=.5
 l.FitText.MinTextSize=9 -- may shrink to the 9 px floor in scaled-down screens (run shop on phones)
 if text=='' then l.Visible=false;w=iconW+8;c.Size=UDim2.fromOffset(w,h) end
 return c,w
end

-- Class weapon fit (CharacterStats.ClassFit): one colour per number, the same on every screen.
-- Your class +15 lime; 0 cream (no change); -5 pale red; -10 red; -15 deep red.
function T.fitColor(p)
 if p>0 then return T.Color.lime elseif p==0 then return T.Color.cream
 elseif p>=-5 then return Color3.fromRGB(255,176,168) elseif p>=-10 then return T.Color.negative end
 return Color3.fromRGB(255,74,84)
end
function T.fitText(p) return (p>0 and '+' or '')..p..'%' end
-- Section heading: cream caps with a fading rule to the right, plus an optional muted note.
-- Returns the height used.
function T.section(parent,name,text,x,y,w,size,note)
 size=size or 19
 local TS=game:GetService('TextService')
 local tw=math.ceil(TS:GetTextSize(text,size,T.Font,Vector2.new(1000,100)).X*1.12)
 local l=T.label(parent,name,text,x,y,tw+8,size+6,size,T.Color.cream);l.TextXAlignment=Enum.TextXAlignment.Left;l.TextStrokeTransparency=.5
 l.FitText.MinTextSize=9 -- at phone scale (.5) a heading must shrink below 60% to stay in its box
 local after=x+tw+12
 if note then
  local nw=math.ceil(TS:GetTextSize(note,size-5,T.Body,Vector2.new(1000,100)).X*1.12)
  T.text(parent,name..'Note',note,after,y+2,math.min(nw+8,x+w-after),size+2,size-5,T.Color.muted)
  after+=nw+14
 end
 if after<x+w-10 then
  local rule=make('Frame',parent,{Name=name..'Rule',Position=UDim2.fromOffset(after,y+math.floor((size+6)/2)),Size=UDim2.fromOffset(x+w-after,2),BackgroundColor3=T.Color.cream,BorderSizePixel=0})
  make('UIGradient',rule,{Transparency=NumberSequence.new(.5,1)})
 end
 return size+6
end
-- A class's always-on stats in an inset: BUFFS (lime) and DRAWBACKS (red) side by side, or one
-- above the other with o.stack (narrow phone columns). good/bad: CharacterStats.classLines.
-- o.size: row text size (18). Returns the inset and its height.
function T.statColumns(parent,name,x,y,w,good,bad,o)
 o=o or {}
 local size=o.size or 18;local rowH=math.floor(size*1.4);local headH=math.floor(size*.75)+8;local pad=8
 local valW=math.floor(size*3.3)
 local box=T.panel(parent,name,x,y,w,0,'inset')
 local function column(key,cx,cy,cw,title,list,color)
  local head=T.label(box,key..'Head',title,cx,cy,cw,headH,math.floor(size*.75),color)
  head.TextXAlignment=Enum.TextXAlignment.Left;head.TextStrokeTransparency=.5
  if #list==0 then list={{value=nil,label='None'}} end
  for i,l in list do
   local ry=cy+headH+(i-1)*rowH
   if l.value then
    local v=T.label(box,key..'Value'..i,(l.value>0 and '+' or '')..l.value..l.unit,cx,ry,valW,rowH,size,color)
    v.TextXAlignment=Enum.TextXAlignment.Right;v.TextStrokeTransparency=.4
   end
   local t=T.text(box,key..'Label'..i,l.label,cx+(l.value and valW+8 or 0),ry,cw-(l.value and valW+8 or 0),rowH,size-1,l.value and T.Color.white or T.Color.dim)
   t.TextYAlignment=Enum.TextYAlignment.Center
  end
  return headH+#list*rowH
 end
 local h
 if o.stack then
  local a=column('Buffs',14,pad,w-24,'BUFFS',good,T.Color.lime)
  make('Frame',box,{Name='Divider',Position=UDim2.fromOffset(10,pad+a+5),Size=UDim2.fromOffset(w-20,2),BackgroundColor3=Color3.new(0,0,0),BackgroundTransparency=.45,BorderSizePixel=0})
  local b=column('Drawbacks',14,pad+a+12,w-24,'DRAWBACKS',bad,T.Color.negative)
  h=pad+a+12+b+pad
 else
  -- Each column gets room in proportion to what it holds: value + its longest label.
  local TS=game:GetService('TextService')
  local function need(list)
   local m=0
   for _,l in list do m=math.max(m,TS:GetTextSize(l.label,size-1,T.Body,Vector2.new(1000,100)).X) end
   return valW+8+m*1.12
  end
  local ng,nb=need(good),need(bad)
  local lw=math.floor(math.clamp((w-8)*ng/(ng+nb),(w-8)*.4,(w-8)*.6))
  local a=column('Buffs',12,pad,lw-16,'BUFFS',good,T.Color.lime)
  local b=column('Drawbacks',lw+12,pad,w-lw-24,'DRAWBACKS',bad,T.Color.negative)
  h=pad+math.max(a,b)+pad
  make('Frame',box,{Name='Divider',Position=UDim2.fromOffset(lw,8),Size=UDim2.fromOffset(2,h-16),BackgroundColor3=Color3.new(0,0,0),BackgroundTransparency=.45,BorderSizePixel=0})
 end
 box.Size=UDim2.fromOffset(w,h)
 return box,h
end
-- Home weapon bonus rows: {{n=2,text='+15% Melee damage ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· +2 Armor'},{n=4,text='also +5% Life steal'}}.
-- Diamond pips count the weapons. The label sits in its own column (o.labelW) so wrapped text
-- lines up, or above the text with o.stack. Returns the inset and its height.
function T.homeRows(parent,name,x,y,w,rows,o)
 o=o or {}
 local size=o.size or 17;local labelW=o.labelW or 136;local TS=game:GetService('TextService')
 local box=T.panel(parent,name,x,y,w,0,'inset')
 local cy=4
 for i,r in rows do
  if not o.stack then labelW=math.max(labelW,math.ceil(TS:GetTextSize(r.n..' HOME WEAPONS',size-2,T.Font,Vector2.new(1000,100)).X*1.12)+12) end
  local tx=12+30+(o.stack and 0 or labelW)
  local textW=w-tx-12
  local th=math.ceil(TS:GetTextSize(r.text,size,T.Body,Vector2.new(textW,1000)).Y)
  local labelH=size+2
  local rh=o.stack and labelH+th+12 or math.max(size+18,th+14)
  if i>1 then make('Frame',box,{Name='Divider'..i,Position=UDim2.fromOffset(10,cy-1),Size=UDim2.fromOffset(w-20,2),BackgroundColor3=Color3.new(0,0,0),BackgroundTransparency=.45,BorderSizePixel=0}) end
  for k=1,4 do
   local p=make('Frame',box,{Name='Pip'..i..'_'..k,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromOffset(19+((k-1)%2)*13,cy+rh/2-6+math.floor((k-1)/2)*13),Size=UDim2.fromOffset(9,9),Rotation=45,BorderSizePixel=0,BackgroundColor3=k<=r.n and T.Color.lime or Color3.fromRGB(58,66,70)})
   make('UIStroke',p,{Color=Color3.fromRGB(8,10,11),Thickness=1.5})
  end
  local label=T.label(box,'Label'..i,r.n..' HOME WEAPONS',42,o.stack and cy+6 or cy+math.floor((rh-labelH)/2),o.stack and textW+labelW or labelW-8,labelH,size-2,T.Color.cream)
  label.TextXAlignment=Enum.TextXAlignment.Left;label.TextStrokeTransparency=.5
  local t=T.text(box,'Text'..i,r.text,tx,o.stack and cy+6+labelH or cy+math.floor((rh-th)/2),textW,th+2,size,T.Color.white)
  t.TextYAlignment=Enum.TextYAlignment.Top
  cy+=rh
 end
 box.Size=UDim2.fromOffset(w,cy+4)
 return box,cy+4
end
-- One tile per class: its signature weapon icon, name and fit number. entries:
-- {{name=,image=,pct=,own=true (lime frame),you=true (YOU tag above)}}. o: icon (44), h (tile
-- height), gap (8), nameSize (13), pctSize (21), youSize (12), cols (all in one row; 3 gives a
-- 3x2 grid where tiles would be too narrow for the names). Returns the frame and its height.
function T.fitTiles(parent,name,x,y,w,entries,o)
 o=o or {}
 local gap=o.gap or 8;local icon=o.icon or 44;local nameSize=o.nameSize or 13;local pctSize=o.pctSize or 21;local youSize=o.youSize or 12
 local n=#entries;local cols=o.cols or n;local rows=math.ceil(n/cols)
 local tw=math.floor((w-(cols-1)*gap)/cols);local th=o.h or (icon+nameSize+pctSize+22)
 local rowGap=gap+10 -- room for a YOU tag on the row below
 local total=rows*th+(rows-1)*rowGap
 local row=T.frame(parent,name,x,y,w,total)
 for i,e in entries do
  local tile=make('Frame',row,{Name='Tile_'..e.name,Position=UDim2.fromOffset(((i-1)%cols)*(tw+gap),math.floor((i-1)/cols)*(th+rowGap)),Size=UDim2.fromOffset(tw,th),BackgroundColor3=e.own and Color3.fromRGB(32,48,24) or Color3.fromRGB(26,32,36),BorderSizePixel=0})
  make('UICorner',tile,{CornerRadius=UDim.new(0,9)})
  make('UIStroke',tile,{Color=e.own and T.Color.lime or Color3.fromRGB(8,10,11),Thickness=2})
  T.icon(tile,'Icon',(tw-icon)/2,5,icon,e.image)
  local nl=T.text(tile,'Name',e.name,2,icon+6,tw-4,nameSize+6,nameSize,T.Color.muted);nl.TextXAlignment=Enum.TextXAlignment.Center
  T.label(tile,'Pct',T.fitText(e.pct),0,icon+nameSize+12,tw,pctSize+6,pctSize,T.fitColor(e.pct))
  if e.you then
   local yh=youSize+10
   local you=T.tag(tile,'You','YOU',0,0,{h=yh,size=youSize,color=T.Color.lime,textColor=T.Color.ink})
   you.Position=UDim2.new(.5,-you.Size.X.Offset/2,0,-math.floor(yh*.6));you.ZIndex=3;you.Text.ZIndex=4;you.Text.TextStrokeTransparency=1
  end
 end
 return row,total
end
-- The shop's fit badge: the number big, one word under it (YOUR CLASS / SIMILAR / OFF-CLASS), or
-- both on one line with inline=true ('+15%  ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â·  YOUR CLASS').
function T.fitBadge(parent,name,x,y,w,h,pct,word,inline)
 local top,bottom,textColor
 if pct>0 then top,bottom,textColor=Color3.fromRGB(63,125,16),Color3.fromRGB(36,77,8),Color3.fromRGB(234,255,208)
 elseif pct==0 then top,bottom,textColor=Color3.fromRGB(74,69,53),Color3.fromRGB(44,42,32),T.Color.cream
 else top,bottom,textColor=Color3.fromRGB(109,30,36),Color3.fromRGB(67,18,22),Color3.fromRGB(255,212,212) end
 local b=make('Frame',parent,{Name=name,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(w,h),BackgroundColor3=Color3.new(1,1,1),BorderSizePixel=0})
 make('UICorner',b,{CornerRadius=UDim.new(0,9)})
 make('UIStroke',b,{Color=Color3.fromRGB(8,10,11),Thickness=2})
 make('UIGradient',b,{Rotation=90,Color=ColorSequence.new(top,bottom)})
 if inline then
  local text=T.fitText(pct)..(word=='DMG' and ' DMG' or ' DAMAGE'..(word and ' · '..word or ''))
  T.label(b,'Pct',text,6,0,w-12,h,math.floor(h*.62),textColor).FitText.MinTextSize=9
  return b
 end
 local pctH=word and math.floor(h*.58) or h
 T.label(b,'Pct',T.fitText(pct)..(word=='DMG' and '' or ' DAMAGE'),2,word and 3 or 0,w-4,pctH,math.floor(pctH*.82),textColor)
 if word then
  local l=T.label(b,'Word',word,2,pctH,w-4,h-pctH-3,math.max(10,math.floor(h*.22)),textColor);l.TextStrokeTransparency=.6
 end
 return b
end

-- rbxthumb content goes through the normal image cache: no web call each time a window opens,
-- and AssetPreloader warms the local player's portrait at join.
function T.headshotId(userId) return 'rbxthumb://type=AvatarHeadShot&id='..userId..'&w=150&h=150' end
function T.headshot(image,userId) image.Image=T.headshotId(userId) end

-- Full-screen screens (Armory, Skill Tree, Chests, Run Setup) lay out on a canvas in design pixels:
-- the screen size divided by one scale, so panels, slots and text keep their proportions on every
-- screen. The scale fits DESIGN (1920x1080). On small screens (phones) it is raised to
-- READABLE_SCALE while the canvas stays at least MIN_CANVAS, so text stays readable and the screen
-- lays itself out on the smaller canvas (lists and details scroll) instead of shrinking further.
-- Example: a 1366x768 laptop gets scale .71 on a 1920x1080 canvas; an 844x390 phone gets .5 on a
-- 1688x780 canvas; a 2560x1080 ultrawide gets 1 on a 2560x1080 canvas.
T.DESIGN=Vector2.new(1920,1080);T.MIN_CANVAS=Vector2.new(1280,640);T.READABLE_SCALE=.5;T.MAX_SCALE=2
function T.canvasScale(size,design,min)
 design=design or T.DESIGN;min=min or T.MIN_CANVAS
 local s=math.min(size.X/design.X,size.Y/design.Y)
 if s<T.READABLE_SCALE then s=math.max(s,math.min(T.READABLE_SCALE,size.X/min.X,size.Y/min.Y)) end
 return math.clamp(s,.05,T.MAX_SCALE)
end
-- A canvas filling `root` (a frame the size of the screen; tests resize it to preview other
-- screens). onLayout(L,canvas) runs now and whenever the size changes: L.s scale, L.w/L.h canvas size and
-- L.top the band at the top covered by Roblox's menu buttons, all in canvas pixels.
-- Returns the canvas frame and an update() to call when the layout should be recomputed.
function T.canvas(root,onLayout,opts)
 local canvas=T.frame(root,'Canvas',0,0,0,0)
 local scale=make('UIScale',canvas,{Scale=1})
 local last
 local function update()
  if not canvas.Parent then return end
  local size=root.AbsoluteSize
  if size.X<2 or size.Y<2 then pcall(function() size=workspace.CurrentCamera.ViewportSize end) end
  if size.X<2 or size.Y<2 then return end
  local s=T.canvasScale(size,opts and opts.design,opts and opts.min)
  local inset=0
  pcall(function() inset=game:GetService('GuiService'):GetGuiInset().Y end)
  local L={s=s,w=size.X/s,h=size.Y/s,top=math.max(inset,36)/s}
  local key=string.format('%.2f %.2f %.3f %.5f',L.w,L.h,L.top,L.s)
  if key==last then return end
  last=key
  canvas.Size=UDim2.fromOffset(L.w,L.h);scale.Scale=s
  onLayout(L,canvas)
 end
 root:GetPropertyChangedSignal('AbsoluteSize'):Connect(update)
 update()
 return canvas,function() last=nil;update() end
end

-- Gamepad: when a menu opens, put the selection on its first button so a controller can drive it
-- (mouse and touch players see no change). Deferred so the caller can finish building it first.
-- All selection calls are protected: a sandboxed caller without the capability just skips them.
function T.gamepadSelect(parent)
 task.defer(function()
  if not parent.Parent then return end
  pcall(function()
   if not game:GetService('UserInputService'):GetLastInputType().Name:find('^Gamepad') then return end
   game:GetService('GuiService'):Select(parent)
  end)
 end)
end
-- Screens that rebuild themselves (Armory, Skill Tree) keep the controller's selection across a
-- redraw: remember the selected button's path under `root` before, reselect it after.
function T.selectionPath(root)
 local ok,sel=pcall(function() return game:GetService('GuiService').SelectedObject end)
 if not (ok and sel and sel:IsDescendantOf(root)) then return nil end
 local path={};local o=sel
 while o and o~=root do table.insert(path,1,o.Name);o=o.Parent end
 return path
end
function T.restoreSelection(root,path)
 if not path then return end
 local o=root
 for _,name in path do o=o and o:FindFirstChild(name) end
 if o and o:IsA('GuiObject') and o.Selectable then pcall(function() game:GetService('GuiService').SelectedObject=o end)
 else T.gamepadSelect(root) end
end

-- Full-screen screens hide the touch thumbstick and jump button while open, so neither can cover
-- a button (the jump button sits bottom-right, over the details panels). Keyed per screen.
local touchHiders={}
function T.hideTouchControls(key,hide)
 touchHiders[key]=hide or nil
 pcall(function() game:GetService('GuiService').TouchControlsEnabled=next(touchHiders)==nil end)
end

-- The regular camera (2026-10-03, "camera should always be regular"): Custom, following your own
-- Humanoid, FOV 70. Camera stages (chest island, egg pedestal, Armory hall, map-select islands, boss
-- intro, asset warm-up) take it by key like hideTouchControls, and the last one out always hands back
-- this constant, never a value saved at open: a chest opened during the station walk-up's FOV punch
-- saved 62, gave back 62, and the next visit went 62 -> 54 (the narrow "isometric" view players saw).
-- Only the first take keeps the player's view, so overlapping stages (chests -> eggs) never stack.
T.CAMERA_FOV=70
local cameraHolders,cameraAlive={},{} -- keys oldest first (the newest drives); key -> still-shown check
local cameraBack,cameraTween,cameraFollow
local function stopCameraTween() if cameraTween then cameraTween:Cancel();cameraTween=nil end end
local function dropHolder(key)
 local at=table.find(cameraHolders,key);if at then table.remove(cameraHolders,at) end
 cameraAlive[key]=nil
end
function T.cameraOwner() return cameraHolders[#cameraHolders] end
-- `alive` (optional): the stage's IsShown, so a stage that broke without Hide can't block self-heal.
-- Returns the player's own view from before the first stage (to fly back to).
function T.cameraTake(key,alive)
 local camera=workspace.CurrentCamera
 stopCameraTween()
 if #cameraHolders==0 then cameraBack=camera and camera.CFrame end
 dropHolder(key);table.insert(cameraHolders,key);cameraAlive[key]=alive
 return cameraBack
end
-- Back to the regular camera now. `look`: face that way again when a stage left it Scriptable.
function T.cameraHome(look)
 local camera=workspace.CurrentCamera;if not camera then return end
 stopCameraTween()
 local c=Players.LocalPlayer and Players.LocalPlayer.Character
 local h=cameraFollow and cameraFollow.Parent and cameraFollow or c and c:FindFirstChildOfClass('Humanoid')
 if h then camera.CameraSubject=h end
 if look and camera.CameraType==Enum.CameraType.Scriptable then camera.CFrame=look end
 camera.CameraType=Enum.CameraType.Custom
 camera.FieldOfView=T.CAMERA_FOV
end
function T.cameraRelease(key)
 dropHolder(key)
 if #cameraHolders==0 then local back=cameraBack;cameraBack=nil;T.cameraHome(back) end
end
-- Self-heal (spawn, arrival, a window closing): the regular camera unless a shown stage holds it.
function T.cameraHeal()
 for i=#cameraHolders,1,-1 do
  local key=cameraHolders[i];local alive=cameraAlive[key]
  if alive and not alive() then dropHolder(key) end
 end
 if #cameraHolders==0 then T.cameraHome() end
end
-- Spectating (death screen) follows a teammate's Humanoid; nil goes back to your own.
function T.cameraFollow(humanoid) cameraFollow=humanoid;T.cameraHeal() end

-- Full-screen results own a free cursor while shown. A one-time Default assignment loses
-- to the standard first-person/shift-lock camera on its next render. Release ownership when
-- hidden/destroyed; gameplay and other camera stages retain their normal controls afterward.
local cursorSerial=0
function T.freeMenuCursor(screen)
 cursorSerial+=1
 local Run=game:GetService('RunService')
 local Input=game:GetService('UserInputService')
 local Gui=game:GetService('GuiService')
 local key='RogueliteMenuCursor_'..cursorSerial
 local bound,disposed=false,false
 local links={}
 local modal=T.make('TextButton',screen,{Name='MenuCursor',Text='',BackgroundTransparency=1,Size=UDim2.fromOffset(1,1),Modal=true,Selectable=false,Active=false,AutoButtonColor=false})
 local function free()
  Input.MouseBehavior=Enum.MouseBehavior.Default
  Input.MouseIconEnabled=true
 end
 local function release()
  if not bound then return end
  bound=false;Run:UnbindFromRenderStep(key)
  local selected=Gui.SelectedObject
  if selected and selected:IsDescendantOf(screen) then Gui.SelectedObject=nil end
  free();T.cameraHeal()
 end
 local function refresh()
  local visible=not disposed and screen.Parent~=nil and screen.Enabled
  modal.Modal=visible
  if visible and not bound then
   bound=true;free()
   Run:BindToRenderStep(key,Enum.RenderPriority.Camera.Value+1,function()
    if screen.Parent and screen.Enabled then free() else release() end
   end)
  elseif not visible then release() end
 end
 local function dispose()
  if disposed then return end
  disposed=true;modal.Modal=false;release()
  for _,link in links do link:Disconnect() end
 end
 table.insert(links,screen:GetPropertyChangedSignal('Enabled'):Connect(refresh))
 table.insert(links,screen.AncestryChanged:Connect(refresh))
 table.insert(links,screen.Destroying:Connect(dispose))
 refresh()
 return dispose
end
-- An FOV tween on the regular camera (the station walk-up punch). One at a time; skipped while a
-- stage holds the camera, and any take or home cancels it so a finishing tween can't undo them.
function T.cameraFov(fov,info)
 stopCameraTween()
 local camera=workspace.CurrentCamera
 if #cameraHolders>0 or not camera or camera.CameraType~=Enum.CameraType.Custom then return end
 cameraTween=TweenService:Create(camera,info,{FieldOfView=fov});cameraTween:Play()
end

-- Modal window: dimmed backdrop, lime-cornered frame, title with stone caps, close button.
-- `w`/`h` is the content layout size; the frame adds WINDOW_MARGIN of breathing room on every
-- side. Scales to fit the viewport, up to WINDOW_MAX_SCALE on large screens.
-- Returns an object with Body (content frame, w-36 wide) and Close().
-- opts.large: content-heavy windows (Store) centre on screen and use nearly the full height
-- instead of leaving room for the lobby HUD, which the backdrop dims anyway.
T.WINDOW_MARGIN=22;T.WINDOW_MAX_SCALE=1.35;T.LARGE_WINDOW_MAX_SCALE=1.45
function T.window(screen,name,title,w,h,onClose,opts)
 local large=opts and opts.large
 local m=T.WINDOW_MARGIN;w+=m*2;h+=m*2
 -- Extends above the safe area so the dim also covers Roblox's top bar strip.
 local backdrop=make('TextButton',screen,{Name=name,Text='',AutoButtonColor=false,Active=true,Modal=true,Position=UDim2.fromOffset(0,-120),Size=UDim2.new(1,0,1,120),BackgroundColor3=T.Color.shade,BackgroundTransparency=.35,BorderSizePixel=0,ZIndex=20,Selectable=false})
 local holder=T.frame(backdrop,'Window',0,0,w,h);holder.AnchorPoint=Vector2.new(.5,.5)
 -- Backdrop starts 120 px above the screen: +76 puts the frame centre 16 px below screen centre,
 -- which centres frame + title plate together.
 holder.Position=large and UDim2.new(.5,0,.5,76) or UDim2.new(.5,0,.53,60)
 local scale=make('UIScale',holder,{Scale=1})
 local frame=T.panel(holder,'Frame',0,0,w,h,'panel');frame.Size=UDim2.fromScale(1,1);frame.Active=true
 if opts and opts.seeThrough then frame.ImageTransparency=opts.seeThrough end -- e.g. Quests (plan K): the world shows through a little
 local head=T.panel(holder,'TitlePlate',18,-30,0,56,'panel')
 local titleSize=game:GetService('TextService'):GetTextSize(title,32,T.Font,Vector2.new(2000,100)).X
 head.Size=UDim2.fromOffset(titleSize+76,56);head.Active=true
 T.caps(head,40)
 local titleLabel=T.label(head,'Title',title,0,0,0,0,32);titleLabel.Size=UDim2.fromScale(1,1)
 local body=T.frame(holder,'Body',18+m,40+m,w-36-m*2,h-58-m*2)
 local self={Root=backdrop,Holder=holder,Body=body,Title=titleLabel,Scale=scale}
 -- Red-cornered close button with a red X so it reads as 'close' at a glance.
 local close=T.button(holder,'Close','X',w-62,-22,58,58,nil,true);T.setTier(close,4);close.Caption.TextColor3=T.Color.negative;close.Caption.TextSize=34
 -- A window that would have to shrink below READABLE_SCALE+.05 to fit (phones) stays at that scale
 -- instead: it gets as tall as the screen allows and its body scrolls. Example: Settings on an
 -- 844x390 phone was scale .22 (22 px titles drawn 5 px tall); now .55 with a scrolling body.
 local scroller,openingTween
 local function fit()
  local v=screen.AbsoluteSize
  if v.X<=0 then return end
  -- Desktop menus use more of the available screen. Preserve compact-screen spacing.
  local desktop=v.X>=1000 and v.Y>=650
  local reserve=large and 40 or desktop and math.clamp(v.Y*.08,40,88) or math.clamp(v.Y*.17,24,184)
  local s=math.min(large and T.LARGE_WINDOW_MAX_SCALE or T.WINDOW_MAX_SCALE,(v.X-(large and 32 or 24))/w,(v.Y-reserve)/(h+34))
  local readable=math.min(opts and opts.minScale or T.READABLE_SCALE+.05,(v.X-24)/w)
  local vh=h
  if s<readable then s=readable;vh=math.clamp(math.floor((v.Y-16)/s-34),math.min(h,240),h) end
  if openingTween then openingTween:Cancel();openingTween=nil end
  scale.Scale=s
  holder.Size=UDim2.fromOffset(w,vh)
  if vh<h then
   -- Centred exactly (the backdrop starts 120 px above the screen; the title plate pokes 30 up).
   holder.Position=UDim2.new(.5,0,0,120+v.Y/2+15*s)
   scroller=scroller or T.scroll(holder,'BodyScroll',0,0,0,0)
   scroller.Position=UDim2.fromOffset(18+m,40+m);scroller.Size=UDim2.fromOffset(w-36-m*2+12,vh-58-m*2)
   scroller.CanvasSize=UDim2.fromOffset(0,h-58-m*2)
   body.Position=UDim2.new();body.Parent=scroller
  else
   holder.Position=large and UDim2.new(.5,0,.5,76) or UDim2.new(.5,0,.53,60)
   if scroller then body.Parent=holder;body.Position=UDim2.fromOffset(18+m,40+m);scroller:Destroy();scroller=nil end
  end
 end
 local conn=screen:GetPropertyChangedSignal('AbsoluteSize'):Connect(fit);fit()
 function self.Close()
  if not backdrop.Parent then return end
  if openingTween then openingTween:Cancel();openingTween=nil end
  conn:Disconnect();backdrop:Destroy()
  if onClose then onClose() end
 end
 close.Activated:Connect(self.Close)
 backdrop.Activated:Connect(self.Close)
 T.gamepadSelect(body)
 scale.Scale*=.92;openingTween=TweenService:Create(scale,TweenInfo.new(.14,Enum.EasingStyle.Back,Enum.EasingDirection.Out),{Scale=scale.Scale/.92});openingTween:Play()
 return self
end

-- Named sound cue (ui_equip, ui_purchase, ui_upgrade, ui_error). Sandboxed modules can't play
-- audio, so StarterPlayerScripts.RogueliteSounds plays it. The cue is a sandboxed BindableEvent
-- saved in ReplicatedStorage (audio/InstallSoundCue.luau). Protected: a sound problem must never
-- stop the purchase, equip or message that follows the call.
function T.sound(name)
 pcall(function()
  local cue=game:GetService('ReplicatedStorage'):FindFirstChild('RogueliteSoundCue');if cue then cue:Fire(name) end
 end)
end

-- Short message near the top of a screen (purchase results, errors). Replaces any previous one.
-- A red (negative) message is a failure and plays the error sound.
function T.toast(screen,text,color)
 if color==T.Color.negative then T.sound('ui_error') end
 local old=screen:FindFirstChild('Toast');if old then old:Destroy() end
 local size=game:GetService('TextService'):GetTextSize(text,20,T.Font,Vector2.new(900,100))
 -- Never wider than the screen (phones): the text wraps or shrinks inside instead.
 local maxW=screen.AbsoluteSize.X>0 and screen.AbsoluteSize.X-24 or 900
 local t=T.panel(screen,'Toast',0,0,math.min(size.X+60,maxW),52,'panel');t.AnchorPoint=Vector2.new(.5,0);t.Position=UDim2.new(.5,0,0,96);t.ZIndex=50
 local l=T.label(t,'Text',text,12,4,0,0,20,color or T.Color.white);l.Size=UDim2.new(1,-24,1,-8);l.ZIndex=51
 task.delay(2.6,function()
  if not t.Parent then return end
  TweenService:Create(t,TweenInfo.new(.3),{ImageTransparency=1}):Play()
  TweenService:Create(l,TweenInfo.new(.3),{TextTransparency=1,TextStrokeTransparency=1}):Play()
  task.delay(.3,function() t:Destroy() end)
 end)
 return t
end

-- Local presentation settings, stored as LocalPlayer attributes. SettingsSync.client saves changes
-- with the profile, and ProfileService sets them again when the next server loads it.
-- Combat presentation reads Setting_ScreenShake and Setting_DamageNumbers; RogueliteSounds and
-- RogueliteMusic apply Setting_SfxVolume and Setting_MusicVolume (0-1) to their SoundGroups.
T.SettingDefaults={VisualQuality='Auto',HudScale=1,ScreenShake=true,DamageNumbers=true,MusicVolume=1,SfxVolume=1}
function T.setting(key)
 local v=Players.LocalPlayer:GetAttribute('Setting_'..key)
 if v==nil then return T.SettingDefaults[key] end
 return v
end
function T.setSetting(key,value) Players.LocalPlayer:SetAttribute('Setting_'..key,value) end
-- Drag bar for a 0-1 value in 5% steps with a live percent label; onChange(value) while dragging.
function T.slider(parent,name,x,y,w,value,onChange)
 local UIS=game:GetService('UserInputService')
 local track=T.make('Frame',parent,{Name=name,Position=UDim2.fromOffset(x,y+16),Size=UDim2.fromOffset(w-72,12),BackgroundColor3=T.Color.track,BorderSizePixel=0})
 T.make('UICorner',track,{CornerRadius=UDim.new(1,0)})
 local fill=T.make('Frame',track,{Name='Fill',Size=UDim2.fromScale(value,1),BackgroundColor3=T.Color.lime,BorderSizePixel=0})
 T.make('UICorner',fill,{CornerRadius=UDim.new(1,0)})
 local knob=T.make('Frame',track,{Name='Knob',AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromScale(value,.5),Size=UDim2.fromOffset(26,26),BackgroundColor3=T.Color.white,BorderSizePixel=0,ZIndex=3})
 T.make('UICorner',knob,{CornerRadius=UDim.new(1,0)})
 local label=T.label(parent,name..'Value',math.round(value*100)..'%',x+w-64,y+4,64,36,20)
 local hit=T.make('TextButton',track,{Name='Hit',Text='',AutoButtonColor=false,BackgroundTransparency=1,Position=UDim2.fromOffset(-14,-16),Size=UDim2.new(1,28,0,44),ZIndex=4})
 hit:SetAttribute('NoClickSound',true)
 local dragging=false
 local function set(px)
  local v=math.round(math.clamp((px-track.AbsolutePosition.X)/track.AbsoluteSize.X,0,1)*20)/20
  fill.Size=UDim2.fromScale(v,1);knob.Position=UDim2.fromScale(v,.5);label.Text=math.round(v*100)..'%'
  onChange(v)
 end
 local function pointer(input) return input.UserInputType==Enum.UserInputType.MouseButton1 or input.UserInputType==Enum.UserInputType.Touch end
 hit.InputBegan:Connect(function(input) if pointer(input) then dragging=true;set(input.Position.X) end end)
 local moved=UIS.InputChanged:Connect(function(input)
  if dragging and (input.UserInputType==Enum.UserInputType.MouseMovement or input.UserInputType==Enum.UserInputType.Touch) then set(input.Position.X) end
 end)
 local ended=UIS.InputEnded:Connect(function(input) if pointer(input) then dragging=false end end)
 track.Destroying:Connect(function() moved:Disconnect();ended:Disconnect() end)
 return track
end
-- `extras`: optional ON/OFF rows owned by the caller, {key,title,help,get(),toggle()}.
-- The caller calls win.Redraw() when its value changes (e.g. after a server reply).
function T.settingsWindow(screen,extras)
 extras=extras or {}
 local viewport=screen.AbsoluteSize
 local narrow=math.min(viewport.X,viewport.Y)<500
 local width=narrow and 320 or 520
 local stride=narrow and 130 or 84
 local win=T.window(screen,'SettingsWindow','Settings',width,100+(6+#extras)*stride,nil,{minScale=.9})
 local body=win.Body;local w=width-36
 local controlX=narrow and 14 or w*.5
 local controlW=narrow and w-28 or w*.5-6
 local function row(i,title,help)
  local y=16+i*stride
  local textW=narrow and w-28 or w*.5-10
  T.label(body,title..'Title',title,14,y,textW,30,22).TextXAlignment=Enum.TextXAlignment.Left
  local l=T.text(body,title..'Help',help,14,y+30,textW,40,15,T.Color.muted);l.TextYAlignment=Enum.TextYAlignment.Top
  l.UITextSizeConstraint.MinTextSize=12
  return y+(narrow and 70 or 2)
 end
 local function draw()
  for _,c in body:GetChildren() do c:Destroy() end
  local y=row(0,'HUD size','Scales the in-run HUD.')
  local current=T.setting('HudScale')
  for i,opt in {{'Small',.85},{'Normal',1},{'Large',1.15}} do
   T.button(body,'Scale'..opt[1],opt[1],controlX+(i-1)*controlW/3,y,controlW/3-6,52,function() T.setSetting('HudScale',opt[2]);draw() end,math.abs(current-opt[2])>.01).Caption.TextSize=18
  end
  for i,opt in {{'ScreenShake','Screen shake','Camera shake when you take damage.'},{'DamageNumbers','Damage numbers','Numbers above enemies you hit.'}} do
   y=row(i,opt[2],opt[3])
   local on=T.setting(opt[1])
   T.button(body,opt[1],on and 'ON' or 'OFF',controlX+controlW/2,y,controlW/2-6,52,function() T.setSetting(opt[1],not T.setting(opt[1]));draw() end,not on).Caption.TextSize=20
  end
  for i,opt in {{'MusicVolume','Music','Background music in runs.'},{'SfxVolume','Sound effects','Weapons, hits, pickups and menus.'}} do
   y=row(2+i,opt[2],opt[3])
   T.slider(body,opt[1],controlX,y,controlW,T.setting(opt[1]),function(v) T.setSetting(opt[1],v) end)
  end
  y=row(5,'Visual quality','Auto adapts effects. Low also removes shadows.')
  for i,mode in {'Auto','Low','Full'} do
   T.button(body,'Quality'..mode,mode,controlX+(i-1)*controlW/3,y,controlW/3-6,52,function() T.setSetting('VisualQuality',mode);draw() end,T.setting('VisualQuality')~=mode).Caption.TextSize=18
  end
  for i,extra in extras do
   y=row(5+i,extra.title,extra.help)
   local on=extra.get()
   T.button(body,extra.key,on and 'ON' or 'OFF',controlX+controlW/2,y,controlW/2-6,52,extra.toggle,not on).Caption.TextSize=20
  end
  T.text(body,'Note','Settings are saved with your profile.',14,20+(6+#extras)*stride,w-28,20,14,T.Color.dim)
 end
 draw()
 win.Redraw=function() if win.Root.Parent then draw() end end
 return win
end

-- Leaving a run (2026-10-03 friends play-test: LEAVE RUN in the pause menu froze a player).
-- T.requestLeave sends RunAction LeaveRun (or LeaveParty) and calls done(true) once the run has
-- ended for this player (RunResult / RunMember, both server-set), or done(false, why) on the
-- server's refusal (RunAction 'LeaveResult', echoing this request's number) or after 6 s with no
-- answer. Callers keep their screen up until then, so nobody is left behind a menu that closed.
local leaveSerial=0
function T.requestLeave(withParty,done)
 local player=Players.LocalPlayer
 local combat=game:GetService('ReplicatedStorage'):FindFirstChild('RogueliteCombat')
 local remote=combat and combat:FindFirstChild('RunAction')
 if not remote then done(false,'You are not in a run');return end
 leaveSerial+=1
 local id,over,conns=leaveSerial,false,{}
 local function finish(ok,why)
  if over then return end
  over=true
  for _,c in conns do c:Disconnect() end
  done(ok,why)
 end
 pcall(function()
  table.insert(conns,remote.OnClientEvent:Connect(function(kind,ok,why,token)
   if kind=='LeaveResult' and token==id and ok~=true then finish(false,type(why)=='string' and why or "You can't leave right now") end
  end))
 end)
 for _,a in {'RunResult','RunMember'} do
  table.insert(conns,player:GetAttributeChangedSignal(a):Connect(function()
   if player:GetAttribute('RunResult') or not player:GetAttribute('RunMember') then finish(true) end
  end))
 end
 remote:FireServer(withParty and 'LeaveParty' or 'LeaveRun',id)
 task.delay(6,function() finish(false,'No answer from the server. Try again') end)
end
-- The Leave Run popup: one confirm behind every LEAVE RUN button (pause menu, shop, death screen)
-- and the wave-20 victory panel. "Leave the run? You keep 340 emeralds." with STAY / LEAVE. A
-- private party's leader (RunLeader on RogueliteCombat, MatchService; the server checks it again)
-- also gets LEAVE WITH PARTY: the run ends for the whole party, each keeping what they earned. A
-- refusal shows its reason here and the buttons work again. It closes itself when the run ends for
-- this player, or when a signal in opts.closeOn fires and opts.closeIf() (if given) says so.
-- opts: keep (emeralds when RunEmeralds isn't set), closeOn, closeIf, onClose, and victory=true for
-- the wave-20 panel (opts.sub under YOU WON!, LEAVE to collect, KEEP GOING into Endless).
function T.leaveConfirm(screen,opts)
 opts=opts or {}
 local C=T.Color
 local player=Players.LocalPlayer
 local combat=game:GetService('ReplicatedStorage'):FindFirstChild('RogueliteCombat')
 local others=0
 for _,q in Players:GetPlayers() do if q~=player and q:GetAttribute('RunMember') then others+=1 end end
 local leader=others>0 and combat~=nil and combat:GetAttribute('RunLeader')==player.UserId
 local victory=opts.victory==true
 -- Rows, top to bottom (design px, body 484 wide): question, the victory line, what you keep, a
 -- note, the refusal line, the buttons (with notes on the victory panel), then LEAVE WITH PARTY.
 local BW=484;local qH=victory and 64 or 48
 local H=4+qH+(victory and 30 or 0)+32+26+26+6+70+(victory and 26 or 0)+(leader and 82 or 0)+4
 local conns={}
 local win
 win=T.window(screen,victory and 'Victory' or 'LeaveConfirm',victory and 'Run Complete' or 'Leave Run',BW+36,H+58,function()
  for _,c in conns do c:Disconnect() end
  if opts.onClose then opts.onClose() end
 end)
 local body=win.Body
 local function centre(l) l.TextXAlignment=Enum.TextXAlignment.Center;return l end
 local y=4
 centre(T.label(body,'Question',victory and 'YOU WON!' or 'Leave the run?',0,y,BW,qH,victory and 56 or 36,victory and C.gold or C.white));y+=qH
 if victory then centre(T.label(body,'Sub',opts.sub or 'RUN COMPLETE',0,y,BW,28,20,C.muted));y+=30 end
 local keep=centre(T.text(body,'Keep','',0,y,BW,30,22));y+=32
 local function paintKeep()
  local n=tonumber(player:GetAttribute('RunEmeralds')) or tonumber(opts.keep) or 0
  local amount=('<font color="%s">%d emerald%s</font>'):format(T.hex(C.emerald),math.floor(n),n==1 and '' or 's')
  keep.Text=victory and ('Your '..amount..(n==1 and ' is' or ' are')..' safe either way.') or ('You keep '..amount..'.')
 end
 paintKeep()
 local note=leader and 'LEAVE WITH PARTY ends it for everyone; each keeps what they earned'
  or others>0 and (victory and 'Each player chooses for themselves' or 'Your teammates keep playing')
  or (victory and 'Endless goes on until you fall or leave' or 'You see your results, then go back to the lobby')
 centre(T.text(body,'Note',note,0,y,BW,24,17,C.muted));y+=26
 local why=centre(T.text(body,'Why','',0,y,BW,24,17,C.negative));y+=32
 local half=(BW-16)/2
 local buttons={}
 local busy=false
 local function go(withParty,b,caption)
  if busy then return end
  busy=true;why.Text='';b.Caption.Text='LEAVING...'
  for _,x in buttons do x.Interactable=false end
  T.requestLeave(withParty,function(ok,reason)
   if ok then win.Close();return end
   busy=false
   if not b.Parent then return end
   b.Caption.Text=caption;why.Text=reason or ''
   for _,x in buttons do x.Interactable=true end
   T.sound('ui_error')
  end)
 end
 local leaveButton,stayButton
 if victory then
  leaveButton=T.button(body,'Leave','LEAVE',0,y,half,70,function() go(false,leaveButton,'LEAVE') end)
  stayButton=T.button(body,'KeepGoing','KEEP GOING',half+16,y,half,70,function() win.Close() end,true)
  centre(T.text(body,'LeaveNote','Collect your rewards',0,y+74,half,22,16,C.muted))
  centre(T.text(body,'KeepGoingNote','Endless: harder waves, more emeralds',half+16,y+74,half,22,16,C.muted))
  y+=70+26
 else
  stayButton=T.button(body,'Stay','STAY',0,y,half,70,function() win.Close() end)
  leaveButton=T.button(body,'Leave','LEAVE',half+16,y,half,70,function() go(false,leaveButton,'LEAVE') end,true)
  leaveButton.Caption.TextColor3=C.negative
  y+=70
 end
 stayButton.Caption.TextSize=28;leaveButton.Caption.TextSize=28
 buttons={stayButton,leaveButton}
 if leader then
  local party
  party=T.button(body,'LeaveParty','LEAVE WITH PARTY',0,y+12,BW,70,function() go(true,party,'LEAVE WITH PARTY') end,true)
  party.Caption.TextSize=26;party.Caption.TextColor3=C.negative
  table.insert(buttons,party)
 end
 table.insert(conns,player:GetAttributeChangedSignal('RunEmeralds'):Connect(paintKeep))
 table.insert(conns,player:GetAttributeChangedSignal('RunResult'):Connect(function() if player:GetAttribute('RunResult') then win.Close() end end))
 for _,signal in opts.closeOn or {} do
  table.insert(conns,signal:Connect(function() if not opts.closeIf or opts.closeIf() then win.Close() end end))
 end
 -- A controller starts on the choice that keeps playing (STAY, KEEP GOING), never on a leave.
 task.delay(.05,function() pcall(function()
  if stayButton.Parent and game:GetService('UserInputService'):GetLastInputType().Name:find('^Gamepad') then game:GetService('GuiService').SelectedObject=stayButton end
 end) end)
 return win
end

return T
