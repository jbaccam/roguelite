-- Pure checks of the tutorial guide's placement maths (TutorialGuideUI: G.toLocal, G.clip,
-- G.placeArrow, G.scrollInto, G.spots, G.placeBox, G.fitText). Offline: python
-- ui/run_tutorial_guide_tests.py build/luau-validation/luau.exe (from the repo root). 2026-10-16,
-- after the user's report that Eggbert's box and arrows were off on phones. Returns the check count.
return function(G)
 local n=0
 local function check(ok,msg) if not ok then error(msg,2) end;n+=1 end
 local V=Vector2.new
 local function near(a,b,eps) return math.abs(a-b)<=(eps or .01) end
 local function inRect(p,s,r) return p.X>=r.x0-.5 and p.Y>=r.y0-.5 and p.X+s.X<=r.x1+.5 and p.Y+s.Y<=r.y1+.5 end

 -- 1. Guide pixels from AbsolutePositions, whatever the device reserves. AbsolutePosition is
 -- measured from the CoreUISafeInsets corner; the guide root (ScreenInsets None) is the screen's
 -- own top-left, which reads as minus that corner.
 for _,dev in {{name='pc',top=58,notch=0},{name='no inset',top=0,notch=0},{name='notched phone',top=58,notch=47}} do
  local corner=V(dev.notch,dev.top) -- where AbsolutePosition (0, 0) is on screen
  local rootAbs=V(0,0)-corner
  local screenSpot=V(147,158)
  local abs=screenSpot-corner -- a HUD button there
  local here=G.toLocal(abs,rootAbs)
  check(near(here.X,screenSpot.X) and near(here.Y,screenSpot.Y),dev.name..': guide px = the screen spot')
  -- The old rule, AbsolutePosition + GetGuiInset() (the top bar only), misses a notch.
  local old=abs+V(0,dev.top)
  check(near(old.X,screenSpot.X)==(dev.notch==0),dev.name..': the old rule was off by the notch only')
 end

 -- 2. Arrows on targets drawn under a UIScale (a phone's shop at .6 to 1): AbsoluteSize already holds
 -- the scale, so the tip lands on the target's edge, centred, at every scale and inset.
 for _,inset in {0,58} do
  for _,k in {.6,.7,.8,.9,1} do
   local full=V(844,390);local rootAbs=V(0,-inset)
   local canvasAt=V(40,70) -- the scaled canvas's top-left on screen
   local screenP=canvasAt+V(300,180)*k;local s=V(200,60)*k -- a 200x60 Buy at design (300, 180)
   local p=G.toLocal(screenP-V(0,inset),rootAbs)
   local tip,rot=G.placeArrow(p,s,full,112*.42,6*.42)
   check(near(tip.X,screenP.X+s.X/2),'scale '..k..' inset '..inset..': tip centred on the target')
   if rot==0 then check(near(tip.Y,screenP.Y+s.Y+6*.42),'tip just under the target')
   else check(near(tip.Y,screenP.Y-6*.42),'tip just over the target') end
  end
 end

 -- 3. Up or down on short screens.
 do
  local full=V(667,375);local size,gap=112*.42,6*.42
  local _,rot=G.placeArrow(V(500,300),V(140,40),full,size,gap)
  check(rot==180,'GO at the bottom: the arrow is over it, pointing down')
  local _,rot2=G.placeArrow(V(200,70),V(120,40),full,size,gap)
  check(rot2==0,'a button near the top: the arrow is under it, pointing up')
  -- In the top 62% but no room under it: over it.
  local _,rot3=G.placeArrow(V(100,150),V(200,200),full,size,gap)
  check(rot3==180,'no room under a tall card: the arrow goes over it')
  -- No room either way: the side with more room.
  local tip4,rot4=G.placeArrow(V(100,40),V(200,300),V(667,375),112,6)
  check(rot4==180 and near(tip4.Y,34),'no room either way: over it (34 px) beats under it (29 px)')
 end
 do
  -- Near a side the tip stays on the target, at its edge if it must.
  local tip=G.placeArrow(V(0,100),V(20,40),V(844,390),47,2.5)
  check(tip.X>=0 and tip.X<=20,'a target at the left edge keeps the tip on it')
  local tip2=G.placeArrow(V(830,100),V(14,40),V(844,390),47,2.5)
  check(tip2.X>=830 and tip2.X<=844,'a target at the right edge keeps the tip on it')
  local tip3=G.placeArrow(V(300,100),V(100,40),V(844,390),47,2.5)
  check(near(tip3.X,350),'a target in the open: centred')
 end

 -- 4. A target in a sideways-scrolling offer row (the phone shop since 2026-10-16), inside the shop's
 -- vertical column.
 do
  local k=.6;local winP,winS=V(20,120),V(480,180) -- the row's window on screen
  local cardW,gapW=300,12;local canvasW=4*cardW+3*gapW -- 1236 design px
  local max=V(canvasW-winS.X/k,0)
  local canvas=V(0,0)
  local function card(i,cv) return winP+V(((i-1)*(cardW+gapW)-cv.X)*k,10*k),V(cardW,250)*k end
  local p,s=card(4,canvas)
  check(G.clip(p,s,{winP,winS})==nil,'card 4 starts scrolled out of the row')
  local to=G.scrollInto(p,s,winP,winS,canvas,k,max,'X')
  check(to~=nil and to.Y==0,'it scrolls the row sideways only')
  check(near(to.X,max.X),'card 4 is the last: the row stops at its end ('..to.X..')')
  local p2,s2=card(4,to)
  check(p2.X>=winP.X-.5 and p2.X+s2.X<=winP.X+winS.X+.5,'after scrolling card 4 shows whole')
  check(G.scrollInto(p2,s2,winP,winS,to,k,max,'X')==nil,'a card that shows needs no scroll')
  -- Card 2 half scrolled out: the arrow points at the part that shows.
  local half=V(((cardW+gapW)+cardW/2)-winS.X/k,0) -- card 2's middle at the window's right edge
  local p3,s3=card(2,half)
  local vp,vs=G.clip(p3,s3,{winP,winS})
  check(vp~=nil and near(vs.X,cardW*k/2),'half of card 2 shows')
  local tip=G.placeArrow(vp,vs,V(667,375),47,2.5)
  check(tip.X>=winP.X and tip.X<=winP.X+winS.X,'the arrow points inside the row, at the part that shows')
  check(near(tip.X,vp.X+vs.X/2),'at the middle of what shows')
  -- A centred card: card 3, partly out at the start, lands in the middle of the window.
  local p4,s4=card(3,canvas)
  local to4=G.scrollInto(p4,s4,winP,winS,canvas,k,max,'X')
  check(to4~=nil,'card 3 sticks out: it scrolls')
  local p5,s5=card(3,to4)
  check(near(p5.X+s5.X/2,winP.X+winS.X/2,.6),'card 3 is centred in the row')
  -- The column around the row scrolls up and down only; a row below the fold comes up.
  local col=G.scrollInto(V(20,420),V(480,180),V(10,62),V(500,300),V(0,0),k,V(0,400),'Y')
  check(col~=nil and col.X==0 and col.Y>0,'the shop column scrolls down to the row')
  check(G.scrollInto(V(20,420),V(480,180),V(10,62),V(500,300),V(0,0),k,V(0,400),'X')==nil,'a sideways list never scrolls up or down')
 end

 -- 5. The box on phones: inside the safe area, never on the target, the offers or GO.
 local tagW=124
 -- A phone shop like ShopUI's: 4 px under the top bar to 32 px off the bottom, a stats column 23%
 -- wide on the right with LEAVE RUN and GO under it, the header, two offer cards on the left.
 local function phoneShop(full,safe)
  local x0,x1=safe.x0+math.floor(full.X*.02),safe.x1-math.floor(full.X*.02)
  local y0,y1=safe.y0+4,full.Y-32
  local w=x1-x0;local side=math.floor(w*.23);local sx=x1-side
  local goH,leaveH=40,38
  local list,keep={},{}
  local function add(p,s,wt,isKeep) local r={p,s,wt};table.insert(list,r);if isKeep then table.insert(keep,r) end;return r end
  add(V(20,16),V(170,70),1) -- the HUD's health block, under the shop
  add(V(sx,y0+6),V(side,y1-y0-goH-leaveH-24),1) -- the stats panel
  add(V(sx,y1-goH-leaveH-12),V(side,leaveH),3) -- LEAVE RUN
  local go=add(V(sx,y1-goH),V(side,goH),3,true) -- GO
  add(V(x0+6,y0+6),V(120,36),1) -- SHOP title
  add(V(x0+140,y0+6),V(90,36),1) -- crystals
  add(V(sx-150,y0+6),V(120,36),3) -- reroll
  local cw=(sx-16-x0-12)/2
  local cards={}
  for i=1,2 do cards[i]=add(V(x0+(i-1)*(cw+12),y0+50),V(cw,y1-(y0+50)),1,true) end
  for _,c in keep do table.insert(list,{c[1],c[2],G.KEEP or 25}) end
  return list,keep,cards,go
 end
 local phones={{667,375,0},{740,360,24},{812,375,44},{844,390,47},{932,430,59}}
 for _,ph in phones do
  local full=V(ph[1],ph[2]);local notch=ph[3]
  local safe={x0=notch,y0=58,x1=full.X-notch,y1=full.Y-(notch>0 and 21 or 0)}
  local s=math.clamp(math.min(full.X/1700,full.Y/950),.42,1.25)
  local list,keep,cards,go=phoneShop(full,safe)
  -- The target: the first card's BUY (hard), padded for the arrow like targetArea.
  local buy={cards[1][1]+V(10,cards[1][2].Y-50),V(cards[1][2].X-20,40)}
  local pad=112*s*1.2
  local hard={{buy[1]-V(pad*.4,pad),buy[2]+V(pad*.8,pad*2)}}
  local pos,shape,score=G.placeBox({full=full,safe=safe,s=s,shapes=G.TRIES,list=list,hard=hard,tagW=tagW})
  local tag=ph[1]..'x'..ph[2]
  check(pos~=nil,tag..': a spot')
  local covered=0
  for _,part in G.parts(pos,s,shape,tagW) do
   check(inRect(part[1],part[2],safe),tag..': '..shape..' stays in the safe area')
   check(G.overlap(part[1],part[2],hard[1][1],hard[1][2])==0,tag..': not on the target')
   for _,k in keep do covered+=G.overlap(part[1],part[2],k[1],k[2]) end
  end
  check(covered==0,tag..': '..shape..' covers no offer or GO ('..covered..' px²)')
  -- The fight on the same phone: corners and sides only, off the health block, the joystick and
  -- the jump button.
  local hud={{V(safe.x0+12,safe.y0+8),V(170,64),G.KEEP or 25},{V(safe.x1-180,safe.y0+8),V(170,50),1},
   {V(safe.x0,full.Y*.45),V(full.X*.4,full.Y*.55),1},{V(safe.x1-110,full.Y-130),V(90,90),3}}
  local fpos,fshape=G.placeBox({full=full,safe=safe,s=s,shapes=G.TRIES,list=hud,hard={},edges=true,tagW=tagW})
  local fc=0
  for _,part in G.parts(fpos,s,fshape,tagW) do
   check(inRect(part[1],part[2],safe),tag..' fight: in the safe area')
   fc+=G.overlap(part[1],part[2],hud[1][1],hud[1][2])
  end
  check(fc==0,tag..' fight: off the health block')
 end

 -- 6. Every spot keeps every shape inside the safe area when it fits there.
 for _,ph in phones do
  local full=V(ph[1],ph[2]);local safe={x0=ph[3],y0=58,x1=ph[1]-ph[3],y1=ph[2]}
  local s=.42
  for _,shape in G.TRIES do
   local size=G.Shapes[shape].size*s
   if size.X<=safe.x1-safe.x0-16 and size.Y<=safe.y1-safe.y0-16 then
    for _,p in G.spots(full,safe,s,shape,nil,false) do check(inRect(p,size,safe),ph[1]..'x'..ph[2]..' '..shape..' spot in the safe area') end
   end
  end
 end

 -- 7. It holds still: a clear spot stays, its shape is kept, and UI under it moves it.
 do
  local full,safe=V(1920,1080),{x0=0,y0=58,x1=1920,y1=1080}
  local list={{V(0,980),V(1920,100),1}} -- a bottom bar
  local pos,shape,score=G.placeBox({full=full,safe=safe,s=1,shapes=G.TRIES,list=list,tagW=tagW})
  check(score==0 and shape=='wide','a PC with room: the wide box, clear')
  local here={pos=pos,shape=shape}
  local p2=G.placeBox({full=full,safe=safe,s=1,shapes=G.TRIES,list={{V(1500,100),V(300,300),1}},tagW=tagW,here=here})
  check(p2==pos,'UI elsewhere: it stays')
  local p3,_,s3=G.placeBox({full=full,safe=safe,s=1,shapes=G.TRIES,list={{pos,V(400,300),1}},tagW=tagW,here=here})
  check(p3~=pos and s3==0,'UI under it: it moves to a clear spot')
  -- Compact first (its own shape): a clear compact spot wins over a clear wide one.
  local _,sh=G.placeBox({full=full,safe=safe,s=1,shapes={'compact','wide','strip','column'},list=list,tagW=tagW})
  check(sh=='compact','its own shape is kept while it has a clear spot')
 end

 -- 8. Text sizes: the line's own fixed size when it fits, smaller (never under 60%) when not.
 do
  local function measure(line,z,w) -- about half an em a character, wrapped
   local perLine=math.max(1,math.floor(w/(z*.5)));local lines=math.ceil(#line/perLine)
   return V(math.min(w,#line*z*.5),lines*z)
  end
  check(G.fitText(measure,'Red circle = move!',530,122,36)==36,'a short line keeps 36')
  local long=string.rep('Crystals pay for the shop. ',8)
  local z=G.fitText(measure,long,530,122,36)
  check(z<36 and z>=21,'a long line shrinks, to 60% at most ('..z..')')
  local b=measure(long,z,530-8)
  check(b.Y<=122-4 or z==21,'and fits (or is at the floor)')
 end
 return n
end
