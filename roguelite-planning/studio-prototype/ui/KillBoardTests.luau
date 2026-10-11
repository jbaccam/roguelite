-- Pure checks for KillBoard (ui/run_kill_board_tests.py runs them with luau.exe; in Studio Edit,
-- call this with require(ReplicatedStorage.KillBoard)). Returns the number of checks.
-- The HUD rects below follow RogueliteUI layout() (health, timer, build strip with its three
-- reserved item rows, PAUSE/SETTINGS launchers, boss bar slot, touch zones) and Round10Hud's
-- objective panel, so the sweep checks the board against every HUD element on each screen size.
return function(K)
 local count=0
 local function check(ok,msg) count+=1;assert(ok,msg) end
 local function near(a,b,msg) check(math.abs(a-b)<.01,msg..' ('..tostring(a)..' vs '..tostring(b)..')') end

 -- Ranking: most kills first; ties share a rank and sort by name; your row is marked.
 local r=K.rank({{userId=1,name='Ana',kills=12},{userId=2,name='Ben',kills=30},{userId=3,name='Cy',kills=12},{userId=4,name='Abe',kills=0}},3)
 check(r[1].userId==2 and r[1].rank==1,'most kills is first')
 check(r[2].userId==1 and r[3].userId==3,'a tie sorts by name')
 check(r[2].rank==2 and r[3].rank==2,'a tie shares the rank')
 check(r[4].rank==4 and r[4].kills==0,'after a two-way tie for 2nd comes 4th')
 check(r[3].mine and not r[1].mine,'your row is marked')
 r=K.rank({{userId=1,name='A',kills=0},{userId=2,name='B',kills=0}},1)
 check(r[1].rank==1 and r[2].rank==1,'wave start: everyone ties for 1st')
 r=K.rank({{userId=1,name='A',kills=-3},{userId=2,name='B',kills=2.7},{userId=3,name='C'}},9)
 check(r[1].kills==2 and r[2].kills==0 and r[3].kills==0,'bad values clamp to whole non-negative kills')
 check(not r[1].mine and not r[2].mine,'no local player in the list')

 -- Rows: at most 4; when you are lower, your row replaces the 4th.
 local six={};for i=1,6 do six[i]={userId=i,name='P'..i,kills=100-i*10} end
 local rows=K.rows(K.rank(six,6),4)
 check(#rows==4 and rows[1].userId==1 and rows[3].userId==3,'top three kept')
 check(rows[4].userId==6 and rows[4].rank==6 and rows[4].mine,'your 6th place replaces the 4th row')
 rows=K.rows(K.rank(six,2),4)
 check(#rows==4 and rows[4].userId==4,'already shown: no swap')
 check(#K.rows(K.rank({six[1],six[2]},1),4)==2,'two players, two rows')

 -- Visible only with 2+ run members, while you are one and your run has not ended.
 check(not K.visible(1,true,false),'solo: hidden')
 check(K.visible(2,true,false),'two players: shown')
 check(K.visible(4,true,false),'four players: shown')
 check(not K.visible(3,false,false),'not in the run (lobby): hidden')
 check(not K.visible(3,true,true),'your run ended (results screen): hidden')

 -- Numbers.
 for _,c in {{0,'0'},{7,'7'},{999,'999'},{1000,'1,000'},{1234,'1,234'},{9999,'9,999'},{10000,'10K'},{12345,'12.3K'},{999949,'999.9K'},{1290000,'1.2M'},{999999,'999.9K'},{-5,'0'}} do
  check(K.format(c[1])==c[2],'format '..c[1]..' -> '..c[2]..', got '..K.format(c[1]))
 end
 check(K.signature(K.rank({{userId=1,name='A',kills=1}},1))~=K.signature(K.rank({{userId=1,name='A',kills=2}},1)),'a kill changes the signature')
 check(K.signature(K.rank({{userId=1,name='A',kills=1}},1))==K.signature(K.rank({{userId=1,name='A',kills=1}},1)),'same board, same signature')
 near(K.height(2),108,'2 rows: 108 design px');near(K.height(4),176,'4 rows: 176 design px')

 -- Placement against the HUD, RogueliteUI layout() for a w x h HUD frame (CoreUISafeInsets), plus
 -- the DASH button (RogueliteCombat.client layout) and, on keyboard screens, the chat window that
 -- RogueliteHUD moves to the centre left in a run. Its size is Roblox's; 340 x 250 is an estimate
 -- (the game reads the real ChatWindowConfiguration rect), and every size is also checked without it.
 local function hud(w,h,touch,withBoss,withChat)
  local s=math.clamp(math.min(w/1100,h/620),.55,1)
  s=math.min(math.max(s,.55),(w/2-24)/510.5)
  local bs=math.max(s*.9,math.min(s,.55));local ms=math.clamp(s,.7,1.1)
  local health={12,12,12+382*s,12+234*s}
  local timer={w/2-112.5*s,14,w/2+112.5*s,14+112*s}
  local build={w-12-330*bs,12,w-12,12+210*bs}
  local small=math.min(w,h)<=500
  local jump=small and {w-95,h-90,w-25,h-20} or {w-170,h-210,w-50,h-90}
  local zones=touch and {jump,small and {0,h-150,170,h} or {0,h-260,260,h}} or {}
  local function clear(rc) if rc[4]>h-8 then return false end;for _,z in zones do if K.overlaps(rc,z,8) then return false end end;return true end
  local n=2 -- PAUSE, SETTINGS
  local top=math.max(.52*h-150*ms,build[4]+10)
  local menu={w-10-76*ms,top,w-10,top+(80*n+6*(n-1))*ms}
  local vertical=clear(menu)
  if not vertical then top=build[4]+10;local width=58*n+44*(n-1);menu={w-10-18*ms-width*ms,top,w-10,top+80*ms} end
  local healthRight,buildLeft=health[3],build[1]
  local function topSlot()
   local y=14+112*s+6;local half=math.min(350*s,w/2-healthRight-10,buildLeft-10-w/2)
   if not vertical and menu[2]<y+96*s then half=math.min(half,menu[1]-10-w/2) end
   return {half,{w/2-half,y,w/2+half,y+96*s}}
  end
  local function bottomSlot()
   local half=math.min(350*s,w/2-16);local y0,y1=h-24-96*s,h-24
   for _,z in zones do if z[2]<y1 and z[4]>y0 then if z[1]+z[3]<w then half=math.min(half,w/2-z[3]-10) else half=math.min(half,z[1]-10-w/2) end end end
   if menu[4]>y0 then half=math.min(half,menu[1]-10-w/2) end
   return {half,{w/2-half,y0,w/2+half,y1}}
  end
  local first,second=topSlot(),bottomSlot()
  if h>=500 then first,second=second,first end
  local boss=((first[1]*2>=240 or first[1]>=second[1]) and first or second)[2]
  if not withBoss then boss={-100,-100,-90,-90} end
  -- Round 10 objective panel (Round10Hud place): under the timer, or under a top-slot boss bar.
  local ry=14+65*s+8+26*s;if boss[2]<h/2 and boss[2]>=ry-4 then ry=boss[4]+6 end
  local rs=math.min(s,math.max(240,w-2*(12+384*s)-20)/420)
  local r10={w/2-210*rs,ry,w/2+210*rs,ry+136*rs}
  -- DASH: left of the jump button on touch, bottom right otherwise.
  local dash
  if touch then local J=jump[3]-jump[1];local size=math.clamp(J*.8,52,96);local cx,cy=jump[1]-10-size/2,(jump[2]+jump[4])/2-J*.35;dash={cx-size/2,cy-size/2,cx+size/2,cy+size/2}
  else local ds=math.clamp(math.min(w/1100,h/620),.7,1.1);dash={w-16-76*ds,h-16-76*ds,w-16,h-16} end
  -- The boss bar and the round 10 panel are the busy case (withBoss); ordinary waves have neither.
  local blocks={health,timer,build,menu,dash};if withBoss then table.insert(blocks,boss);table.insert(blocks,r10) end
  for _,z in zones do table.insert(blocks,z) end
  local chat
  if withChat and not touch then chat={8,h/2-125,348,h/2+125};table.insert(blocks,chat) end
  return s,{health=health,build=build,menu=menu,chat=chat,blocks=blocks}
 end
 local function placeOn(w,h,touch,n,withBoss,withChat)
  local s,rects=hud(w,h,touch,withBoss,withChat)
  local compact=math.min(w,h)<=500
  local x,y,sc,clear=K.place(w,h,s,rects,n,compact)
  return {x,y,x+K.width(compact)*sc,y+K.height(n)*sc},sc,clear,rects
 end
 -- The documented examples. Desktops: the left edge under the health block (12 + 234 + 10).
 local b,sc=placeOn(1920,1022,false,4)
 near(b[1],12,'1080p desktop: left edge');near(b[2],256,'1080p desktop: under the health block');near(sc,1,'desktop scale 1')
 b=placeOn(1920,1022,false,2,false,true)
 near(b[1],12,'1080p, 2 players, chat: left');near(b[2],256,'2 players fit between the health block and the chat')
 b=placeOn(1920,1022,false,4,false,true)
 near(b[1],12,'1080p, 4 players, chat: left');near(b[2],511+125+10,'4 players go under the chat window')
 b=placeOn(1366,710,false,4,true,true)
 near(b[1],12,'1366x710 laptop, chat, boss: left');near(b[2],355+125+10,'laptop: under the chat window too')
 b,sc=placeOn(1024,712,true,4)
 near(b[1],12,'tablet: left edge');near(b[2],12+234*sc+10,'tablet: under the health block, above the thumbstick')
 b,sc=placeOn(750,311,true,2)
 near(b[2],137.5,'750x311 phone: under the weapon strip');near(b[3],750-10-12.6-112-8,'phone: left of PAUSE/SETTINGS');near(sc,.55,'phone scale .55')
 near(b[3]-b[1],K.WC*.55,'phone: compact, no names')
 b=placeOn(750,311,true,4)
 near(b[3],750-133-28-8,'750x311 phone, 4 players: left of DASH')
 -- Every screen size, 2-4 players, with and without the boss bar and the chat window: on screen and
 -- clear of every HUD element; prints where nothing fits (the board hides there).
 local sizes={
  {568,270,true},{640,300,true},{667,311,true},{750,311,true},{812,340,true},{844,350,true},{926,390,true},{1024,712,true},{1180,770,true},{1366,980,true},
  {1100,620,false},{1280,662,false},{1366,710,false},{1440,842,false},{1536,806,false},{1920,1022,false},{2560,1382,false},{3440,1382,false},{1024,712,false},
 }
 for _,size in sizes do
  local w,h,touch=size[1],size[2],size[3]
  for n=2,4 do for _,withBoss in {false,true} do for _,withChat in {false,true} do
   local rect,_,clear,rects=placeOn(w,h,touch,n,withBoss,withChat)
   local where=w..'x'..h..(touch and ' touch' or '')..' n='..n..(withBoss and ' boss' or '')..(withChat and not touch and ' chat' or '')
   if not clear then print('  no clear spot (hidden): '..where) end
   if clear then
    check(rect[1]>=0 and rect[2]>=0 and rect[3]<=w and rect[4]<=h,'on screen: '..where)
    for i,block in rects.blocks do check(not K.overlaps(rect,block,0),'clear of HUD element '..i..': '..where) end
    if not touch then check(rect[1]==12,'keyboard screens: left edge: '..where) end
   end
  end end end
 end
 -- Desktops never shrink it.
 for _,size in {{1366,710},{1920,1022},{2560,1382}} do local _,sc2=placeOn(size[1],size[2],false,4,true,true);near(sc2,1,'full size on '..size[1]..'x'..size[2]) end
 return count
end
