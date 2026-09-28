local RS=game:GetService('ReplicatedStorage')
local combat=RS:WaitForChild('RogueliteCombat')
local Stats=require(combat:WaitForChild('CharacterStats'))
local Catalog=require(combat.WeaponCatalog)
local EnemyCatalog=require(combat:WaitForChild('EnemyCatalog'))
local T=require(RS:WaitForChild('UITheme'))
local M={}
function M.new(player,helpers)
 local panel,label,button=helpers.panel,helpers.label,helpers.button
 local state=combat.PlayerStates:WaitForChild(tostring(player.UserId))
 local remote=combat:WaitForChild('EditPractice')
 local self={state=state,refreshers={}}
 local function update() for _,fn in self.refreshers do fn() end end
 state.AttributeChanged:Connect(update);combat:GetAttributeChangedSignal('ZombieCount'):Connect(update);combat:GetAttributeChangedSignal('EnemyRoster'):Connect(update);combat:GetAttributeChangedSignal('ZombiesEnabled'):Connect(update);combat:GetAttributeChangedSignal('PracticeBossStatus'):Connect(update)
 local function send(action,key,value) remote:FireServer(action,key,value) end
 local function small(parent,name,text,x,y,w,callback)
  local b=button(parent,name,text,x,y,w,34,callback,true);b.Caption.TextSize=15;return b
 end
 function self:render(content,width)
  self.refreshers={}
  local usable=math.min(width,1200);local x=(width-usable)/2
  local extra=usable<600 and 70 or 0
  local classBox=panel(content,'ClassPanel',x,0,usable,268+extra)
  local heading=label(classBox,'Title','Character build',12,8,usable-24,30,26)
  local columns=usable<600 and 3 or 6;local cw=(usable-24)/columns
  local classButtons={}
  for i,name in Stats.ClassOrder do
   classButtons[name]=small(classBox,'Class_'..name,name,12+((i-1)%columns)*cw,44+math.floor((i-1)/columns)*40,cw-5,function() send('Class',name) end)
  end
  local y=columns==3 and 128 or 88
  local description=label(classBox,'Description','',12,y,usable-24,48,16);description.TextWrapped=true
  local affinity=label(classBox,'Affinity','',12,y+49,usable-24,35,15);affinity.TextWrapped=true
  small(classBox,'SuggestedBuild','Class build (practice only)',12,220+extra,(usable-38)/2,function() send('Build') end)
  small(classBox,'ResetStats','Reset stat edits',26+(usable-38)/2,220+extra,(usable-38)/2,function() send('Reset') end)
  local buffs=label(classBox,'Buffs','',12,180+extra,usable-24,36,13);buffs.TextWrapped=true;buffs.RichText=true
  table.insert(self.refreshers,function()
   local class=state:GetAttribute('Class') or 'Brawler';heading.Text='Character build · '..class
   for name,b in classButtons do T.setPrimary(b,name==class) end
   description.Text=Stats.Classes[class].description
   local values={};for _,d in Stats.List do local v=Stats.Classes[class].buffs[d.id];if v then table.insert(values,'<font color="'..(v>0 and '#91ef14' or '#ff6969')..'">'..d.label..' '..(v>0 and '+' or '')..v..d.unit..'</font>') end end;buffs.Text=table.concat(values,'  |  ')
   affinity.Text=string.format('%d home weapons · Bonuses at 2 and 4 · Changing class clears stat edits',state:GetAttribute('AffinityCount') or 0)
  end)
  local mobCols=usable<600 and 3 or 6;local mobRows=math.ceil(#EnemyCatalog.List/mobCols)
  local zombieH=282+mobRows*38;local zextra=zombieH-238
  local zombies=panel(content,'ZombieControls',x,280+extra,usable,zombieH)
  local count=label(zombies,'Count','',12,6,usable-24,32,23)
  local function zombieCount() return combat:GetAttribute('ZombieCount') or 5 end
  table.insert(self.refreshers,function() count.Text='Zombies · '..tostring(zombieCount())..' / 100'..(combat:GetAttribute('ZombiesEnabled') and ' · ON' or ' · OFF [Z]') end)
  local zw=(usable-44)/5
  for i,amount in {-10,-1,0,1,10} do
   if amount~=0 then
    small(zombies,'Count'..tostring(amount),(amount>0 and '+' or '')..amount,12+(i-1)*(zw+5),44,zw,function() send('Zombies','',math.clamp(zombieCount()+amount,0,100)) end)
   end
  end
  local countBox=Instance.new('TextBox');countBox.Name='CountValue';countBox.Position=UDim2.fromOffset(12+2*(zw+5),44);countBox.Size=UDim2.fromOffset(zw,34)
  countBox.BackgroundColor3=Color3.fromRGB(36,41,43);countBox.TextColor3=Color3.fromRGB(200,224,167);countBox.Font=Enum.Font.GothamBold;countBox.TextSize=17;countBox.ClearTextOnFocus=false;countBox.Parent=zombies
  table.insert(self.refreshers,function() if not countBox:IsFocused() then countBox.Text=tostring(zombieCount()) end end)
  countBox.FocusLost:Connect(function()
   local v=tonumber(countBox.Text)
   if v and v%1==0 and v>=0 and v<=100 and v~=zombieCount() then send('Zombies','',v) else countBox.Text=tostring(zombieCount()) end
  end)
  -- Mob picker: selected IDs become the server's EnemyRoster, cycled by spawn slot.
  local function roster()
   local ids,set={},{}
   for id in (combat:GetAttribute('EnemyRoster') or ''):gmatch('[^,%s]+') do table.insert(ids,id);set[id]=true end
   return ids,set
  end
  local mobTitle=label(zombies,'MobsTitle','',12,238,usable-174,30,17);mobTitle.TextXAlignment=Enum.TextXAlignment.Left
  small(zombies,'WaveMix','Use wave mix',usable-150,236,138,function() send('Roster',nil,'') end)
  table.insert(self.refreshers,function()
   local ids=roster();mobTitle.Text=#ids>0 and ('Mobs · '..#ids..' selected · cycles by slot') or 'Mobs · wave mix (tanks from wave 8)'
  end)
  local mw=(usable-24)/mobCols
  for i,d in EnemyCatalog.List do
   local b=small(zombies,'Mob_'..d.id,d.name,12+((i-1)%mobCols)*mw,276+math.floor((i-1)/mobCols)*38,mw-5,function()
    local ids,set=roster()
    if set[d.id] then table.remove(ids,table.find(ids,d.id)) else table.insert(ids,d.id) end
    send('Roster',nil,table.concat(ids,','))
   end)
   b.Caption.TextSize=13
   table.insert(self.refreshers,function() local _,set=roster();b.Caption.Text=(set[d.id] and '✓ ' or '')..d.name end)
  end
  label(zombies,'Hint','Studio population override persists across waves. Defeated zombies return after 3s.',12,81,usable-168,52,13).TextWrapped=true
  small(zombies,'AutoCount','Use wave count',usable-150,96,138,function() send('AutoZombies') end)
  small(zombies,'SpawnBoss','Spawn boss',12,144,(usable-36)/2,function() send('SpawnBoss') end)
  small(zombies,'RemoveBoss','Remove boss',24+(usable-36)/2,144,(usable-36)/2,function() send('RemoveBoss') end)
  local bossStatus=label(zombies,'BossStatus','',12,183,usable-24,48,13);bossStatus.TextWrapped=true
  table.insert(self.refreshers,function() bossStatus.Text=combat:GetAttribute('PracticeBossStatus') or 'Spawn one practice boss nearby · Enables zombies · No boss rewards' end)
  extra+=zextra
  small(content,'Heal','Heal to full',x,530+extra,(usable-12)/2,function() send('Heal') end)
  small(content,'TestDamage','Test 20 contact damage',x+(usable+12)/2,530+extra,(usable-12)/2,function() send('Damage') end)
  -- Emeralds (saved currency): quick grants plus an exact value. Studio only, never saved.
  local gems=panel(content,'Emeralds',x,574+extra,usable,52,'inset')
  local Theme=require(RS:WaitForChild('UITheme'))
  local gemIcon=Instance.new('ImageLabel');gemIcon.Name='Icon';gemIcon.BackgroundTransparency=1;gemIcon.Image=Theme.Asset.emerald;gemIcon.Position=UDim2.fromOffset(10,6);gemIcon.Size=UDim2.fromOffset(40,40);gemIcon.ScaleType=Enum.ScaleType.Fit;gemIcon.Parent=gems
  local gemTitle=label(gems,'Title','',56,10,150,32,20);gemTitle.TextXAlignment=Enum.TextXAlignment.Left
  local gemBox=Instance.new('TextBox');gemBox.Name='Value';gemBox.Position=UDim2.fromOffset(210,10);gemBox.Size=UDim2.fromOffset(110,32)
  gemBox.BackgroundColor3=Color3.fromRGB(36,41,43);gemBox.TextColor3=Theme.Color.emerald;gemBox.Font=Enum.Font.GothamBold;gemBox.TextSize=17;gemBox.ClearTextOnFocus=false;gemBox.Parent=gems
  local function gemCount() return player:GetAttribute('ProfileGems') or 0 end
  local function gemRefresh() gemTitle.Text='Emeralds';if not gemBox:IsFocused() then gemBox.Text=tostring(gemCount()) end end
  table.insert(self.refreshers,gemRefresh)
  local gemConn=player:GetAttributeChangedSignal('ProfileGems'):Connect(gemRefresh)
  gems.Destroying:Connect(function() gemConn:Disconnect() end)
  gemBox.FocusLost:Connect(function()
   local v=tonumber(gemBox.Text)
   if v and v%1==0 and v>=0 and v<=1e7 and v~=gemCount() then send('Emeralds','Set',v) else gemBox.Text=tostring(gemCount()) end
  end)
  local gw=math.max(60,(usable-340-3*6)/3)
  for i,amount in {100,1000,10000} do
   small(gems,'AddEmeralds'..amount,'+'..(amount>=1000 and (amount//1000)..'K' or tostring(amount)),330+(i-1)*(gw+6),9,gw,function() send('Emeralds','Add',amount) end)
  end
  label(content,'EditHelp','Studio edits work during waves · Type a value and press Enter or click away, or use − / +.',x,634+extra,usable,50,17).TextWrapped=true
  local cols=usable>=850 and 2 or 1;local cardW=(usable-(cols-1)*12)/cols
  local top=696+extra;local cardH=128
  for i,d in Stats.List do
   local cx=x+((i-1)%cols)*(cardW+12);local cy=top+math.floor((i-1)/cols)*(cardH+10)
   local row=panel(content,'Stat_'..d.id,cx,cy,cardW,cardH,'inset')
   local title=label(row,'Name',d.label,12,6,cardW-24,26,20);title.TextXAlignment=Enum.TextXAlignment.Left
   local box=Instance.new('TextBox');box.Name='Value';box.Position=UDim2.fromOffset(60,37);box.Size=UDim2.fromOffset(cardW-120,30)
   box.BackgroundColor3=Color3.fromRGB(36,41,43);box.TextColor3=Color3.fromRGB(200,224,167);box.Font=Enum.Font.GothamBold;box.TextSize=17;box.ClearTextOnFocus=false;box.Parent=row
   local function value() return state:GetAttribute('Stat_'..d.id) or d.base end
   local function refresh() if not box:IsFocused() then box.Text=tostring(value()) end;box.TextColor3=require(RS.ShopUI).statColor(d.id,value(),d.base);title.Text=d.label..(state:GetAttribute('Override_'..d.id) and ' *' or '') end
   table.insert(self.refreshers,refresh)
   small(row,'Minus','−',12,36,38,function() send('Stat',d.id,math.clamp(value()-d.step,d.min,d.max)) end)
   small(row,'Plus','+',cardW-50,36,38,function() send('Stat',d.id,math.clamp(value()+d.step,d.min,d.max)) end)
   box.FocusLost:Connect(function()
    local v=tonumber(box.Text)
    if Stats.valid(d.id,v) and v~=value() then send('Stat',d.id,v) else box.Text=tostring(value()) end
   end)
   label(row,'Hint',d.unit..' · '..d.help,12,73,cardW-24,48,13).TextWrapped=true

  end
  local bottom=top+math.ceil(#Stats.List/cols)*(cardH+10)
  local weapons=panel(content,'EffectiveWeapons',x,bottom,usable,260)
  label(weapons,'Title','Equipped weapon values',12,8,usable-24,30,24)
  for i=1,6 do
   local text=label(weapons,'Weapon'..i,'',12,44+(i-1)*32,usable-24,30,15);text.TextXAlignment=Enum.TextXAlignment.Left
   table.insert(self.refreshers,function()
    local slot=state:FindFirstChild('Slot'..i);local base=slot and Catalog.ById[slot:GetAttribute('WeaponId')]
    if base then local d=Stats.weapon(base,Stats.read(state),state:GetAttribute('Class'),slot:GetAttribute('Tier'));text.Text=string.format('%d · %s · %.1f damage · %.2fs · %.1f range',i,d.name,d.damage,d.cooldown,d.range) else text.Text=i..' · Empty' end
   end)
  end
  if not game:GetService('RunService'):IsStudio() then
   for _,o in content:GetDescendants() do if o:IsA('GuiButton') then o.Interactable=false elseif o:IsA('TextBox') then o.TextEditable=false end end
  end
  update();return bottom+274
 end
 function self:drawSummary(parent,x,y,width)
  local outer=panel(parent,'Stats',x,y,width,380)
  label(outer,'Title','All character stats',12,10,width-24,32,22)
  local scroll=Instance.new('ScrollingFrame');scroll.Name='AllStats';scroll.Position=UDim2.fromOffset(8,50);scroll.Size=UDim2.new(1,-16,1,-60);scroll.BackgroundTransparency=1;scroll.BorderSizePixel=0;scroll.ScrollBarThickness=4;scroll.CanvasSize=UDim2.fromOffset(0,#Stats.List*30);scroll.Parent=outer
  for i,d in Stats.List do
   local name=label(scroll,d.id,d.label,4,(i-1)*30,width-105,28,13);name.TextXAlignment=Enum.TextXAlignment.Left
   local v=label(scroll,d.id..'Value','',width-100,(i-1)*30,70,28,13)
   local function refresh() if v.Parent then v.Text=Stats.format(d,state:GetAttribute('Stat_'..d.id) or d.base) end end
   refresh();local connection=state:GetAttributeChangedSignal('Stat_'..d.id):Connect(refresh)
   v.Destroying:Connect(function() connection:Disconnect() end)
  end
  return 394
 end
 return self
end
return M
