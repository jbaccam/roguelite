-- Pure checks for ShotBatch's packing (launch audit P1-P3): Shot rows for bullet legs, hit
-- batches and the packed attack attribute. Studio Edit, no Play: load ShotBatch's source with
-- loadstring and pass the module in. Returns {passed, checks, notes}.
return function(B)
 local checks=0;local function check(ok,message) checks+=1;assert(ok,message) end
 local rng=Random.new(7)
 local function near(a,b,tolerance) return (a-b).Magnitude<=tolerance end

 -- Shot rows: a bullet's Fly, Land and Drop rows keep their values and their nils.
 local fly={Vector3.new(1,2,3),Vector3.new(4,5,-40),'Fly','07',.24,nil,nil,nil,123456789012,3,true,nil,1759412345.5,17,110}
 local land={Vector3.new(1,2,-9),nil,'Land',nil,nil,nil,true,Vector3.yAxis,nil,nil,nil,true,nil,17,nil,true}
 local drop={Vector3.new(1,2,-9),nil,'Drop',nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,17}
 for _,row in {fly,land,drop} do
  local back=table.pack(B.unpack(B.pack(table.unpack(row,1,16))))
  for i=1,16 do check(back[i]==row[i],'Shot row value '..i..' of '..row[3]) end
 end
 -- The per-frame writer sends one batched message for several rows (no players in Edit: everyone).
 local sent={}
 local fake={FireAllClients=function(_,...) table.insert(sent,table.pack(...)) end,FireClient=function() error('no players in Edit') end}
 local writer=B.writer(fake)
 writer:push(nil,table.unpack(fly,1,16));writer:push(nil,table.unpack(land,1,16));writer:flush()
 check(#sent==1 and sent[1][1]==B.Marker and #sent[1][2]==2,'two rows go out as one batch')
 writer:push(nil,table.unpack(drop,1,16));writer:flush()
 check(#sent==2 and sent[2][3]=='Drop' and sent[2][14]==17,'a lone row keeps the plain format')

 -- Hits: split into messages under the unreliable budget, then decoded exactly.
 local me,them={Name='me'},{Name='them'}
 -- Stand-in enemies: two existing Instances, alternating (nothing is created).
 local npcs={};for i=1,40 do npcs[i]=i%2==0 and workspace or game:GetService('Lighting') end
 local items={}
 -- Each hit's crit, element and turret source (2026-10-10 hit colours) ride in the flags byte's
 -- spare bits. Turrets never crit, so no row asks for both.
 local styles={}
 for i=1,40 do
  local id=({'07','12','Armor','',string.rep('x',30)})[i%5+1]
  local position=Vector3.new(rng:NextNumber(-3000,3000),rng:NextNumber(-50,300),rng:NextNumber(-3000,3000))
  styles[i]={crit=i%5==0 and i%3~=1,element=({false,'Burn','Frost','Poison','Lightning'})[i%5+1] or nil,turret=i%3==1}
  table.insert(items,B.hitItem(i%3==0 and me or them,position,rng:NextNumber(0,250000),npcs[i],i%7==0,i%2==0,i%4==0,id,styles[i].crit,styles[i].element,styles[i].turret))
 end
 local parts=B.splitHits(items);local nextFirst=1;local worst=0
 for _,part in parts do
  check(part[1]==nextFirst and part[2]>=part[1],'hit messages cover every hit in order');nextFirst=part[2]+1
  local budget,bytes=32,0
  for i=part[1],part[2] do budget+=18+#items[i].id+24;bytes+=18+#items[i].id end
  check(bytes==part[3],'buffer size matches the hits');check(budget<=B.HitBytes,'message within the unreliable budget');worst=math.max(worst,budget)
  local buf,list=B.encodeHits(items,part[1],part[2],part[3],me)
  check(buffer.len(buf)==part[3],'buffer filled exactly')
  local count=part[2]-part[1]+1
  -- The client gets the enemies as arguments; one it can't see arrives as nil.
  local args=table.pack(table.unpack(list,1,count));if count>=2 then args[2]=nil end
  local hits=B.readHits(buf,args)
  check(#hits==count,'every hit decoded')
  for k,h in hits do
   local item=items[part[1]+k-1]
   check(near(h.position,item.position,.002*math.max(1,item.position.Magnitude/1000)),'hit position')
   check(h.damage==math.round(item.damage),'hit damage rounded as numbers show it')
   check(h.lethal==bit32.btest(item.flags,1) and h.secondary==bit32.btest(item.flags,2) and h.dot==bit32.btest(item.flags,4),'hit flags')
   check(h.mine==(item.owner==me),'mine is per player')
   check(h.weaponId==(item.id~='' and item.id or nil),'weapon id')
   local style=styles[part[1]+k-1];check(h.crit==style.crit and h.element==style.element and h.turret==style.turret,'crit, element and turret')
   check(h.npc==(k~=2 and item.npc or nil),'each hit keeps its own enemy, and a missing one stays missing')
  end
 end
 check(nextFirst==#items+1 and #parts>=2,'40 hits need more than one message')
 check(#B.readHits(nil,{})==0 and #B.readHits(buffer.create(5),{})==0,'malformed messages read as no hits')

 -- The packed attack: every field the clients read, to the stated precision.
 check(next(B.unpackAttack(nil))==nil,'no attack reads as an empty table')
 local longest=0
 for i=1,300 do
  local yaw=rng:NextNumber(-math.pi,math.pi)
  local root=CFrame.new(rng:NextNumber(-3000,3000),rng:NextNumber(-20,200),rng:NextNumber(-3000,3000))*CFrame.Angles(0,yaw,0)
  local direction=Vector3.new(rng:NextNumber(-1,1),0,rng:NextNumber(-1,1)).Unit
  local a={start=1759412345+rng:NextNumber(0,99999),rate=rng:NextNumber(.4,3),kind=({'Melee','Ranged','Spread','Blast'})[i%4+1],
   style=({'Horizontal','Diagonal','Thrust','Downward','Slap','Reap','FigureEight'})[i%7+1],side=i%2==0 and 1 or -1,hand=i%3==0 and 1 or -1,
   range=rng:NextNumber(3,60),root=root,aim=root.Position+Vector3.new(rng:NextNumber(-30,30),rng:NextNumber(-5,5),rng:NextNumber(-30,30)),
   direction=direction,second=i%2==0 and root.Position+Vector3.new(3,0,4) or nil}
  local raw=B.packAttack(a);longest=math.max(longest,#raw)
  local b=B.unpackAttack(raw)
  check(math.abs(b.start-a.start)<=.0006,'start time to 1 ms')
  check(math.abs(b.rate-a.rate)/a.rate<1e-4 and math.abs(b.range-a.range)/a.range<1e-4,'rate and range')
  check(b.kind==a.kind and b.style==a.style and b.side==a.side and b.hand==a.hand,'kind, style, side, hand')
  check(near(b.root.Position,root.Position,.009),'attack root position')
  check(b.root.LookVector:Dot(root.LookVector)>.99999 and b.root.UpVector:Dot(Vector3.yAxis)>.99999,'attack root faces the same way, upright')
  check(near(b.aim,a.aim,.009) and near(b.direction,direction,2e-4) and math.abs(b.direction.Magnitude-1)<1e-6,'aim and direction')
  check((a.second==nil and b.second==nil) or (b.second and near(b.second,a.second,.009)),'second aim')
 end
 check(longest<200,'packed attack stays short ('..longest..' chars)')
 return {passed=true,checks=checks,notes={hitMessages=#parts,worstHitBudget=worst,longestAttack=longest}}
end
