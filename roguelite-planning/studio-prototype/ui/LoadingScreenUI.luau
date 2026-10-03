-- Loading screen (ReplicatedFirst.LoadingScreenUI): full-bleed destination art and a bottom plate in
-- the green theme (charcoal panel, stone caps, lime bar). Approved mockup:
-- roguelite-planning/previews/loading-screen-mockup/loading.html (2026-10-02).
-- Lives in ReplicatedFirst so it shows before ReplicatedStorage arrives, so it can't require UITheme:
-- the few theme values it needs are copied here (keep them in step with UITheme's T.Asset/T.Color).
-- Each art is uploaded as two 836x941 halves: Roblox shrinks one 1672x941 image to 1024 px wide,
-- which is blurry on a 1080p screen. The halves sit side by side and are cropped to fill the screen.
local TweenService=game:GetService('TweenService')
local TextService=game:GetService('TextService')
local RunService=game:GetService('RunService')
local LS={}

LS.Asset={panel='rbxassetid://116439058081230',stone='rbxassetid://107387940957948',
 inset='rbxassetid://82653359149627',button='rbxassetid://72732018694626'}
LS.ART_ASPECT=1672/941
-- Destinations: the lobby and the five maps (RunSetupRules ids). going = first step on the way there.
LS.Dest={
 Lobby={name='LOBBY',art={'rbxassetid://76828943197546','rbxassetid://136574378682114'},going='Joining the game',area='Loading the lobby'},
 PineValley={name='PINE VALLEY',art={'rbxassetid://78752628753539','rbxassetid://129262889451329'},going='Traveling to Pine Valley',area='Loading the arena'},
 BeachCove={name='BEACH COVE',art={'rbxassetid://71199992582794','rbxassetid://128591835780790'},going='Traveling to Beach Cove',area='Loading the arena'},
 DesertBasin={name='DESERT BASIN',art={'rbxassetid://115565941214905','rbxassetid://71017141780297'},going='Traveling to Desert Basin',area='Loading the arena'},
 FrozenPass={name='FROZEN PASS',art={'rbxassetid://108881145552072','rbxassetid://133679558574054'},going='Traveling to Frozen Pass',area='Loading the arena'},
 VolcanicCrater={name='VOLCANIC CRATER',art={'rbxassetid://119385297015522','rbxassetid://128024252521009'},going='Traveling to Volcanic Crater',area='Loading the arena'},
}
-- Difficulty chip colours (background, text); only shown on trips to a map.
LS.Chip={Normal={Color3.fromRGB(34,39,43),Color3.fromRGB(248,249,245)},Hard={Color3.fromRGB(168,88,12),Color3.fromRGB(255,241,214)},
 Nightmare={Color3.fromRGB(122,29,42),Color3.fromRGB(255,217,222)}}
LS.Tips={
 'Your weapons attack on their own. Focus on moving.',
 'Clear wave 20 to win, then keep going in Endless.',
 'Downed? You come back when the wave ends.',
 'Leave Run between waves and keep your emeralds.',
 'The shop opens between waves. Spend your shards there.',
}
local C={white=Color3.fromRGB(248,249,245),lime=Color3.fromRGB(145,239,20),cream=Color3.fromRGB(234,221,167),
 track=Color3.fromRGB(22,29,32),edge=Color3.fromRGB(8,10,11),shade=Color3.fromRGB(5,9,10),back=Color3.fromRGB(17,23,26)}
local FONT,BODY=Enum.Font.FredokaOne,Enum.Font.SourceSansBold
local SLICE=Rect.new(48,48,208,208)

function LS.valid(id) return type(id)=='string' and LS.Dest[id]~=nil end

-- UITheme.canvasScale with the same constants: one scale fits 1920x1080; phones are held at .5 on a
-- canvas of at least 1280x640. Example: 844x390 -> .5 (1688x780 canvas); 1024x768 -> .533.
function LS.canvasScale(size)
 local s=math.min(size.X/1920,size.Y/1080)
 if s<.5 then s=math.max(s,math.min(.5,size.X/1280,size.Y/640)) end
 return math.clamp(s,.05,2)
end
-- The art's size so it covers the whole screen (like ScaleType.Crop), centred.
function LS.cover(size)
 if size.X/size.Y>LS.ART_ASPECT then return Vector2.new(size.X,size.X/LS.ART_ASPECT) end
 return Vector2.new(size.Y*LS.ART_ASPECT,size.Y)
end
-- Where the bar sits while a step waits: it creeps from `from` toward `to` and never reaches it,
-- e.g. a save step of .40-.70 shows 60% after 4 s and stops short of 70% until the save is in.
function LS.creep(from,to,elapsed) return from+(to-from)*.9*(1-math.exp(-elapsed/3)) end

local function make(class,parent,props)
 local o=Instance.new(class)
 for k,v in props do o[k]=v end
 o.Parent=parent
 return o
end
local function label(parent,name,text,font,size,color,stroke)
 local l=make('TextLabel',parent,{Name=name,BackgroundTransparency=1,Text=text,Font=font,TextSize=size,TextScaled=true,TextWrapped=true,
  TextColor3=color,TextStrokeColor3=Color3.new(0,0,0),TextStrokeTransparency=stroke or .12})
 make('UITextSizeConstraint',l,{MaxTextSize=size,MinTextSize=math.max(9,math.floor(size*.6))})
 return l
end
local function stone(parent,name,size)
 return make('ImageLabel',parent,{Name=name,BackgroundTransparency=1,AnchorPoint=Vector2.new(.5,.5),Size=UDim2.fromOffset(size,size),Image=LS.Asset.stone,ScaleType=Enum.ScaleType.Fit,ZIndex=5})
end

-- Builds the screen inside `root` (a ScreenGui, or a screen-sized Frame for previews).
-- Returns an object: :step(text,from,to) starts a step, :finish(onDone) fills the bar, fades out
-- and destroys it, :destroy(). The bar moves on its own between those calls.
function LS.new(root,destId,difficulty)
 local dest=LS.Dest[destId] or LS.Dest.Lobby
 local self={destination=LS.valid(destId) and destId or 'Lobby'}
 local frame=make('Frame',root,{Name='LoadingScreen',Size=UDim2.fromScale(1,1),BackgroundColor3=C.back,BorderSizePixel=0,ZIndex=1,Active=true})
 frame:SetAttribute('Destination',self.destination)
 -- Art: two halves inside one frame sized to cover the screen. Charcoal shows until they load.
 -- They start at .995, not 1: Roblox never loads a fully transparent image, so IsLoaded stayed
 -- false and the art only came in at the 20 s fallback (gray screens, 2026-10-03).
 local art=make('Frame',frame,{Name='Art',AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromScale(.5,.5),BackgroundTransparency=1,ZIndex=1})
 local halves={}
 for i,id in dest.art do
  halves[i]=make('ImageLabel',art,{Name=i==1 and 'Left' or 'Right',BackgroundTransparency=1,Position=UDim2.fromScale((i-1)*.5,0),
   Size=UDim2.fromScale(.5,1),Image=id,ImageTransparency=.995,ScaleType=Enum.ScaleType.Stretch,ZIndex=1})
 end
 task.spawn(function()
  local start=os.clock()
  while frame.Parent and os.clock()-start<20 and not (halves[1].IsLoaded and halves[2].IsLoaded) do task.wait(.05) end
  for _,h in halves do if h.Parent then TweenService:Create(h,TweenInfo.new(.35),{ImageTransparency=0}):Play() end end
 end)
 local fade=make('Frame',frame,{Name='Fade',AnchorPoint=Vector2.new(0,1),Position=UDim2.fromScale(0,1),Size=UDim2.fromScale(1,.42),BackgroundColor3=C.shade,BorderSizePixel=0,ZIndex=2})
 make('UIGradient',fade,{Rotation=90,Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,1),NumberSequenceKeypoint.new(.55,.45),NumberSequenceKeypoint.new(1,.14)})})
 -- Plate on a design-pixel canvas.
 local canvas=make('Frame',frame,{Name='Canvas',BackgroundTransparency=1,ZIndex=3})
 local scale=make('UIScale',canvas,{Scale=1})
 local plate=make('ImageLabel',canvas,{Name='Plate',BackgroundTransparency=1,Image=LS.Asset.panel,ScaleType=Enum.ScaleType.Slice,SliceCenter=SLICE,SliceScale=.55,ZIndex=3})
 local titleWidth=TextService:GetTextSize(dest.name,36,FONT,Vector2.new(2000,100)).X+84
 local titlePlate=make('ImageLabel',canvas,{Name='TitlePlate',BackgroundTransparency=1,Image=LS.Asset.panel,ScaleType=Enum.ScaleType.Slice,SliceCenter=SLICE,SliceScale=.55,ZIndex=4})
 -- One line always: scaled down on phones, a wrapped "VOLCANIC / CRATER" spilled out of the plate.
 local title=label(titlePlate,'Title',dest.name,FONT,36,C.white);title.Size=UDim2.new(1,-40,1,0);title.Position=UDim2.fromOffset(20,0)
 title.TextWrapped=false;title.ZIndex=6
 local capL=stone(titlePlate,'LeftStone',44);capL.Position=UDim2.new(0,4,.5,0)
 local capR=stone(titlePlate,'RightStone',44);capR.Position=UDim2.new(1,-4,.5,0)
 local chip
 local colours=destId~='Lobby' and LS.Chip[difficulty]
 if colours then
  chip=make('Frame',canvas,{Name='Difficulty',BackgroundColor3=colours[1],BorderSizePixel=0,ZIndex=4})
  make('UICorner',chip,{CornerRadius=UDim.new(0,8)});make('UIStroke',chip,{Color=C.edge,Thickness=3})
  local t=label(chip,'Text',string.upper(difficulty),FONT,18,colours[2],.4);t.Size=UDim2.fromScale(1,1);t.ZIndex=5
  chip.Size=UDim2.fromOffset(TextService:GetTextSize(string.upper(difficulty),18,FONT,Vector2.new(1000,100)).X+30,34)
 end
 local status=label(canvas,'Status','',BODY,25,C.white,.5);status.TextXAlignment=Enum.TextXAlignment.Left;status.ZIndex=4
 local pct=label(canvas,'Percent','0%',FONT,34,C.lime);pct.TextXAlignment=Enum.TextXAlignment.Right;pct.ZIndex=4
 local track=make('Frame',canvas,{Name='Bar',BackgroundColor3=C.track,BorderSizePixel=0,ClipsDescendants=true,ZIndex=4})
 make('UICorner',track,{CornerRadius=UDim.new(0,8)});make('UIStroke',track,{Color=C.edge,Thickness=3})
 local fill=make('Frame',track,{Name='Fill',Size=UDim2.fromScale(0,1),BackgroundColor3=Color3.new(1,1,1),BorderSizePixel=0,ZIndex=4})
 make('UICorner',fill,{CornerRadius=UDim.new(0,5)})
 make('UIGradient',fill,{Rotation=90,Color=ColorSequence.new({ColorSequenceKeypoint.new(0,Color3.fromRGB(198,255,98)),ColorSequenceKeypoint.new(.45,C.lime),ColorSequenceKeypoint.new(1,Color3.fromRGB(94,166,12))})})
 local shine=make('Frame',fill,{Name='Shine',Position=UDim2.new(0,6,0,3),Size=UDim2.new(1,-12,0,3),BackgroundColor3=Color3.new(1,1,1),BackgroundTransparency=.55,BorderSizePixel=0,ZIndex=5})
 make('UICorner',shine,{CornerRadius=UDim.new(1,0)})
 local barL=stone(canvas,'BarLeftStone',52);local barR=stone(canvas,'BarRightStone',52)
 local tipTag=make('Frame',canvas,{Name='TipTag',BackgroundColor3=C.lime,BorderSizePixel=0,ZIndex=4})
 make('UICorner',tipTag,{CornerRadius=UDim.new(0,7)});make('UIStroke',tipTag,{Color=C.edge,Thickness=3})
 local tagText=label(tipTag,'Text','TIP',FONT,16,Color3.fromRGB(17,34,34),1);tagText.Size=UDim2.fromScale(1,1);tagText.ZIndex=5
 local tip=label(canvas,'Tip','',BODY,22,C.cream,.5);tip.TextXAlignment=Enum.TextXAlignment.Left;tip.ZIndex=4
 local tipIndex=math.random(#LS.Tips);tip.Text=LS.Tips[tipIndex]

 local function layout()
  local size=frame.AbsoluteSize
  if size.X<2 or size.Y<2 then return end
  local c=LS.cover(size);art.Size=UDim2.fromOffset(c.X,c.Y)
  local s=LS.canvasScale(size);local cw,ch=size.X/s,size.Y/s
  scale.Scale=s;canvas.Size=UDim2.fromOffset(cw,ch)
  local pw=math.min(1240,cw-96);local ph=172;local px=(cw-pw)/2;local py=ch-ph-(ch<900 and 30 or 46)
  plate.Position=UDim2.fromOffset(px,py);plate.Size=UDim2.fromOffset(pw,ph)
  titlePlate.Position=UDim2.fromOffset(px+18,py-32);titlePlate.Size=UDim2.fromOffset(titleWidth,62)
  if chip then chip.Position=UDim2.fromOffset(px+18+titleWidth+26,py-18) end
  local ix,iw=px+44,pw-88
  status.Position=UDim2.fromOffset(ix,py+38);status.Size=UDim2.fromOffset(iw-140,34)
  pct.Position=UDim2.fromOffset(ix+iw-140,py+34);pct.Size=UDim2.fromOffset(140,40)
  track.Position=UDim2.fromOffset(ix,py+82);track.Size=UDim2.fromOffset(iw,34)
  barL.Position=UDim2.fromOffset(ix-2,py+99);barR.Position=UDim2.fromOffset(ix+iw+2,py+99)
  tipTag.Position=UDim2.fromOffset(ix,py+130);tipTag.Size=UDim2.fromOffset(52,28)
  tip.Position=UDim2.fromOffset(ix+62,py+128);tip.Size=UDim2.fromOffset(iw-62,32)
 end
 frame:GetPropertyChangedSignal('AbsoluteSize'):Connect(layout)
 layout()

 -- Progress: `shown` eases toward the target; the target creeps inside the current step.
 local shown,stepFrom,stepTo,stepAt,done=0,0,0,os.clock(),false
 local tipAt=os.clock()
 function self:step(text,from,to)
  status.Text=text..'…';stepFrom=math.max(from,shown);stepTo=math.max(to,stepFrom);stepAt=os.clock()
 end
 function self:ratio() return shown end
 local conn
 conn=RunService.Heartbeat:Connect(function(dt)
  if not frame.Parent then conn:Disconnect();return end
  local target=done and 1 or LS.creep(stepFrom,stepTo,os.clock()-stepAt)
  shown=math.min(1,shown+math.max(0,target-shown)*math.min(1,dt*6))
  if done and 1-shown<.004 then shown=1 end
  fill.Size=UDim2.fromScale(shown,1);pct.Text=math.floor(shown*100+1e-6)..'%'
  if os.clock()-tipAt>=6 then tipAt=os.clock();tipIndex=tipIndex%#LS.Tips+1;tip.Text=LS.Tips[tipIndex] end
 end)
 function self:destroy() if conn then conn:Disconnect() end;frame:Destroy() end
 -- Fill to 100%, then fade everything out and destroy.
 function self:finish(onDone)
  if done then return end
  done=true;status.Text='Ready!'
  task.spawn(function()
   local start=os.clock()
   while frame.Parent and shown<1 and os.clock()-start<1.5 do task.wait() end
   task.wait(.25)
   if not frame.Parent then if onDone then onDone() end;return end
   local info=TweenInfo.new(.45,Enum.EasingStyle.Quad,Enum.EasingDirection.In)
   for _,o in frame:GetDescendants() do
    local goal={}
    if o:IsA('ImageLabel') then goal.ImageTransparency=1 end
    if o:IsA('TextLabel') then goal.TextTransparency=1;goal.TextStrokeTransparency=1 end
    if o:IsA('GuiObject') and o.BackgroundTransparency<1 then goal.BackgroundTransparency=1 end
    if o:IsA('UIStroke') then goal.Transparency=1 end
    if next(goal) then TweenService:Create(o,info,goal):Play() end
   end
   TweenService:Create(frame,info,{BackgroundTransparency=1}):Play()
   task.wait(.5)
   self:destroy()
   if onDone then onDone() end
  end)
 end
 return self
end

-- A ScreenGui holding a new screen, above everything (Roblox's top bar included).
function LS.screenGui(destId,difficulty)
 local gui=Instance.new('ScreenGui')
 gui.Name='LoadingScreen';gui.IgnoreGuiInset=true;gui.ResetOnSpawn=false;gui.DisplayOrder=1000
 gui.ZIndexBehavior=Enum.ZIndexBehavior.Sibling
 gui:SetAttribute('Destination',LS.valid(destId) and destId or 'Lobby')
 gui:SetAttribute('Difficulty',difficulty)
 return gui,LS.new(gui,destId,difficulty)
end

return LS
