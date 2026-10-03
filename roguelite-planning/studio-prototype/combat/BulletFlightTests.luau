-- Pure checks for BulletFlights (launch audit P1): the client turns a bullet's Fly / Land / Drop rows
-- back into the per-step rows the old protocol sent, which the existing visuals draw. Studio Edit,
-- no Play: load its source with loadstring and pass the module in.
return function(F)
 local checks=0;local function check(ok,message) checks+=1;assert(ok,message) end
 local drawn={}
 local function draw(...) table.insert(drawn,table.pack(...)) end
 local function near(a,b) return (a-b).Magnitude<1e-4 end
 local O=Vector3.new(0,5,0);local FORWARD=Vector3.new(0,0,-1)
 -- Fly row: origin, finish, 'Fly', id, thickness, -, -, -, owner, slot, first, -, shotId, key, speed
 local function fly(f,now,key,from,to,first) return f.row(now,from,to,'Fly','00',.14,nil,nil,nil,42,2,first,nil,99,key,120) end
 local function land(f,now,key,at,contact,mob,terminal) return f.row(now,at,nil,'Land',nil,nil,nil,contact,contact and Vector3.yAxis or nil,nil,nil,nil,mob,nil,key,nil,terminal) end

 -- A plain shot that hits an enemy 11 studs out: first step at once, 60 steps a second after.
 local f=F.new(draw)
 check(fly(f,0,1,O,O+FORWARD*40,true)==true,'Fly is a bullet row');f.launched(0)
 check(#drawn==1,'the first step is drawn when the launch arrives')
 local r=drawn[1]
 check(near(r[1],O) and near(r[2],O+FORWARD*2) and r[3]=='Ranged' and r[4]=='00' and r[11]==true and r[14]==1 and r[15]==120 and r[16]==false,'first step: muzzle row, 2 studs at 120 studs/s')
 f.step(1/120);check(#drawn==1,'no second step inside the same 60th of a second')
 f.step(1/60);check(#drawn==2 and near(drawn[2][1],O+FORWARD*2) and drawn[2][11]==false,'steps join end to end, first only once')
 for i=2,5 do f.step(i/60) end
 check(#drawn==6 and near(drawn[6][2],O+FORWARD*12),'six steps by 5/60 s')
 land(f,6/60,1,O+FORWARD*11,true,true,true)
 local last=drawn[#drawn]
 check(near(last[1],O+FORWARD*12) and near(last[2],O+FORWARD*11) and last[7]==true and last[12]==true and last[16]==true,'the Land row ends it at the hit, with its contact flags')
 check(f.bullets[1]==nil,'a terminal Land forgets the bullet')

 -- Hit within its first step: Fly and Land arrive together; one row, both first and terminal.
 drawn={};f=F.new(draw)
 fly(f,0,2,O,O+FORWARD*40,true);land(f,0,2,O+FORWARD*1.2,true,false,true);f.launched(0)
 check(#drawn==1 and drawn[1][11]==true and drawn[1][16]==true and near(drawn[1][2],O+FORWARD*1.2) and drawn[1][7]==true and drawn[1][12]==false,'point-blank wall hit: one first, terminal row')

 -- Pierce: a non-terminal Land parks it at the enemy, the next Fly carries on with no joining row.
 drawn={};f=F.new(draw)
 fly(f,0,3,O,O+FORWARD*40,false);f.launched(0);f.step(1/60)
 land(f,.02,3,O+FORWARD*5,true,true,false)
 check(#drawn==3 and drawn[3][16]==false and drawn[3][7]==true,'pierce contact row, not terminal')
 f.step(.04);check(#drawn==3,'parked at the enemy until the next leg')
 fly(f,.04,3,O+FORWARD*5.05,O+FORWARD*40,false)
 check(#drawn==3,'no joining row after a contact')
 f.step(.04+1/60);check(#drawn==4 and near(drawn[4][1],O+FORWARD*5.05),'the next leg starts at the server point')

 -- Retarget mid-flight: the drawn path joins to where the server turned it.
 drawn={};f=F.new(draw)
 fly(f,0,4,O,O+FORWARD*40,false);f.launched(0)
 local turn=O+FORWARD*2.3
 fly(f,.01,4,turn,turn+Vector3.xAxis*30,false)
 check(#drawn==2 and near(drawn[2][1],O+FORWARD*2) and near(drawn[2][2],turn) and drawn[2][16]==false,'retarget joins the path')
 f.step(.01+1/60);check(near(drawn[3][2],turn+Vector3.xAxis*2),'then flies the new heading')

 -- Drop: cancelled, nothing more drawn.
 local before=#drawn;f.row(.05,turn,nil,'Drop',nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,4)
 f.step(.1);check(#drawn==before and f.bullets[4]==nil,'Drop draws nothing and forgets it')

 -- Range end: it waits at the end of its leg for the Land row; a lost one is forgotten after 1 s.
 drawn={};f=F.new(draw)
 fly(f,0,5,O,O+FORWARD*3,false);f.launched(0);f.step(1/60);f.step(2/60)
 check(#drawn==2 and near(drawn[2][2],O+FORWARD*3),'stops at the end of its range')
 f.step(.5);check(#drawn==2 and f.bullets[5]~=nil,'waits there for its Land row')
 f.step(1.2);check(f.bullets[5]==nil,'forgotten when nothing comes')

 -- Other rows are not bullet rows.
 check(f.row(0,O,O+FORWARD,'Lightning','35')==false and f.row(0,O,O,'Blast','11')==false,'other Shot rows pass through')
 check(f.row(0,O,O,'Land',nil,nil,nil,true,nil,nil,nil,nil,nil,nil,77,nil,true)==true and #drawn==2,'a Land for an unknown bullet is ignored')
 return {passed=true,checks=checks}
end
