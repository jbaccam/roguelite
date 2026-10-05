// Plan L pause screen. Positions and sizes are the ones ui/PauseUI.luau computes, in canvas pixels:
// a 1920x1080 PC is a 1920x1080 canvas at scale 1; an 844x390 phone is a 1688x780 canvas at .5, with
// Roblox's 58 px top bar covering the top 116 of it.
function glass(parent,x,y,w,h){const g=$(`<div class="abs" style="left:${x}px;top:${y}px;width:${w}px;height:${h}px;border-radius:16px;background:rgba(7,9,10,.5);border:2px solid rgba(0,0,0,.55);overflow:hidden"></div>`);parent.appendChild(g);return g}
// With a note, the title keeps the left 55% and the note the rest (narrow phone panels).
function section(p,y,w,title,right){txt(p,24,y,right?Math.floor(w*.55)-32:w-48,32,title,24,'#fff','left','o2');if(right)txt(p,Math.floor(w*.55),y+6,Math.ceil(w*.45)-24,24,right,16,'var(--muted)','right','o1 body');p.appendChild($(`<div class="rule" style="left:24px;top:${y+38}px;width:${w-48}px;height:2px;background:linear-gradient(90deg,var(--lime),transparent)"></div>`))}
// A list taller than its panel scrolls (phones): show where the scroll bar sits.
function scrollHint(g,h,contentH){if(contentH>h)g.appendChild($(`<div class="scrollbar" style="top:8px;height:${Math.max(30,(h-16)*h/contentH)}px"></div>`))}
const ALL_ITEMS=['magnet','protein','shoes','hotsauce','glasses','bandage','crown','potlid','alien','antlers','backpack','ballchain','battery','bouncy','bubble','cheese'];
const RARS=['Common','Rare','Epic','Legendary'];
const ALL_UPS=['Damage','AttackSpeed','MaxHP','Luck','MoveSpeed','Armor','CritChance','MeleeDamage','RangedDamage','ElementalDamage','UtilityPower','Dodge','Regeneration','LifeSteal','PickupRadius','AttackRange'];
// Party of 4: you, one paused, one still playing, one downed (downed players don't count).
const PARTY4=[['EggaRowls','paused'],['xX_DragonSlayer99_Xx','paused'],['SuperLongName_12345A','playing'],['Hyper_kaiju','down']];

// A name on one line; past 13 px (11 on a phone) it ends in "…" (PauseUI fitName).
function fitName(c,text,x,y,w,h,size,color){
 const chars=[...text],min=Math.max(11,Math.floor(13*S));let n=chars.length;
 const shown=k=>chars.slice(0,k).join('')+(k<chars.length?'…':'');
 while(n>1&&textWidth(shown(n),min,"'Fredoka One'")>(w-4)*S) n--;
 return txt(c,x,y,w,h,shown(n),size,color);
}

// L: {w,h,s,top} canvas size, scale and top-bar height; touch hides "or press P".
function pauseView(s,mode,L){
 const late=mode.late,w=L.w,h=L.h;
 const members=mode.members||[['EggaRowls','paused']];
 const solo=members.length<=1;
 const living=members.filter(m=>m[1]!=='down').length,count=members.filter(m=>m[1]==='paused').length,many=living>1;
 const frozen=mode.frozen;
 const tight=h-L.top<800; // phones: plate and map line share a row, buttons close up
 // The run stays visible behind a darker see-through veil.
 s.appendChild($(`<div class="abs" style="inset:0;background:rgba(4,7,8,.66)"></div>`));
 if(L.phone) s.appendChild($(`<div class="topbar" style="height:${L.top}px;font-size:26px">Roblox top bar</div>`));
 // Title plate, map · difficulty · wave, status pill, party strip.
 let y=L.top+(tight?4:12);
 const map=late?'VOLCANIC CRATER':'PINE VALLEY',diff=late?'NIGHTMARE':'HARD',wave=late?'ENDLESS WAVE 63':'WAVE 7';
 // Phones: the map line sits right of the plate on its middle, and the pair is centred on the screen.
 const iw=tight?Math.min(w-440,textWidth(`${map}  ·  ${diff}  ·  ${wave}`,Math.min(22,Math.floor(30*L.s)),"'Fredoka One'")/L.s+8):w;
 const px=tight?w/2-(350+iw)/2+18:w/2-150; // the left stone pokes 18 out of the plate
 const plate=$(`<div class="abs panel" style="left:${px}px;top:${y}px;width:300px;height:66px"></div>`);s.appendChild(plate);
 for(const sx of [4,296]) plate.appendChild($(`<div class="abs icon" style="left:${sx-22}px;top:11px;width:44px;height:44px;background-image:url(img/stone.png)"></div>`));
 plate.appendChild($(`<div class="abs icon" style="left:40px;top:11px;width:44px;height:44px;background-image:url(img/pause.png)"></div>`));
 txt(plate,92,8,180,50,'PAUSED',40,'#fff','left','o3');
 if(!tight) y+=74;
 const info=`${map}  ·  <span style="color:${late?'#ff6969':'#ffcb40'}">${diff}</span>  ·  ${wave}`;
 if(tight) txt(s,px+332,y+18,iw,30,info,22,'#fff','center','o2'); else txt(s,0,y,w,30,info,22,'#fff','center','o2');
 y+=tight?74:40;
 // Shorter words on phones; the pill grows to fit them on one line at full size.
 const status=frozen?(many?'EVERYONE PAUSED  ·  GAME FROZEN':'GAME FROZEN'):(many?`${count} / ${living} PAUSED  ·  ${tight?'GAME KEEPS GOING UNTIL ALL PAUSE':'THE GAME KEEPS GOING UNTIL EVERYONE PAUSES'}`:'PAUSING…');
 const pw=Math.min(w-80,Math.max(frozen?(many?560:360):(many?820:300),textWidth(status,Math.min(frozen?22:19,Math.floor(38*L.s)),"'Fredoka One'")/L.s+48));
 const pill=$(`<div class="abs" style="left:${w/2-pw/2}px;top:${y}px;width:${pw}px;height:46px;border-radius:23px;border:3px solid var(--ink);background:${frozen?'#2f5f0e':'#6e4a0a'}"></div>`);s.appendChild(pill);
 txt(pill,9,1,pw-24,38,status,frozen?22:19,frozen?'#d2ffa1':'#ffd98a','center','o2');
 y+=56;
 if(!solo){
  // One card per member, you first: headshot, name, then ✓ paused / playing / down.
  const n=members.length,cw=Math.min(tight?340:300,Math.floor((w-64-(n-1)*12)/n)),x0=w/2-(n*cw+(n-1)*12)/2;
  members.forEach((m,i)=>{
   const down=m[1]==='down',paused=m[1]==='paused',you=i===0;
   const c=$(`<div class="abs" style="left:${x0+i*(cw+12)}px;top:${y}px;width:${cw}px;height:54px;border-radius:12px;background:rgba(7,9,10,${down?.38:.55});${you?'box-shadow:0 0 0 2px rgba(145,239,20,.75)':''}"></div>`);s.appendChild(c);
   c.appendChild($(`<div class="abs icon" style="left:6px;top:6px;width:42px;height:42px;border-radius:50%;background-color:#3b4a52;background-image:url(img/profile.png);opacity:${down?.45:1}"></div>`));
   fitName(c,m[0],54,4,cw-60,24,18,down?'var(--muted)':'#fff');
   let sx=54;
   if(paused){check(c,54,31,18);sx=78}
   txt(c,sx,29,cw-sx-10,22,(down?'down':paused?'paused':'playing')+(you?'  ·  you':''),15,down?'var(--negative)':paused?'var(--limeSoft)':'var(--gold)','left','o1 body');
  });
  y+=66;
 }
 // Three columns: stats | buttons | build.
 const top=y+(tight?0:10),panelH=h-top-(tight?12:24);
 const side=Math.min(520,Math.max(300,Math.floor((w-400-160)/2))),gap=Math.floor((w-2*side-400)/4);
 const lx=gap,mx=gap*2+side,rx=gap*3+side+400;
 // Left: stats (the totals already include every item and level-up).
 const Lp=glass(s,lx,top,side,panelH);
 section(Lp,14,side,'STATS');
 const v=late?{d:'+410%',as:'+160%',cc:'48%',cd:'240%',md:'+95%',rd:'+60%',hp:'2,840 HP',ar:'38',dg:'42%',rg:'14 HP/s',ls:'12%',ms:'34',pr:'28',lk:'85',lv:'64',k:'18,340',dd:'21.6M'}
  :{d:'+35%',as:'+20%',cc:'12%',cd:'175%',md:'+10%',rd:'0%',hp:'180 HP',ar:'6',dg:'5%',rg:'2 HP/s',ls:'4%',ms:'26',pr:'10',lk:'12',lv:'9',k:'412',dd:'38.4K'};
 const groups=[['OFFENSE',[['Damage',v.d],['Attack speed',v.as],['Critical chance',v.cc],['Critical damage',v.cd],['Melee damage',v.md],['Ranged damage',v.rd]]],
  ['DEFENSE',[['Max health',v.hp],['Armor',v.ar],['Dodge',v.dg]]],
  ['RECOVERY',[['Regeneration',v.rg],['Life steal',v.ls]]],
  ['UTILITY',[['Movement speed',v.ms],['Pickup radius',v.pr],['Luck',v.lk]]],
  ['THIS RUN',[['Level',v.lv],['Kills',v.k],['Damage dealt',v.dd]]]];
 let sy=62;
 groups.forEach(g=>{txt(Lp,24,sy,side-48,22,g[0],15,'var(--lime)','left','o1');sy+=26;
  g[1].forEach(r=>{txt(Lp,36,sy,side*.6-36,26,r[0],18,'#c9d1d3','left','o1 body');txt(Lp,side*.55,sy,side*.45-24,26,r[1],20,'#fff','right','o2');sy+=27});sy+=8});
 scrollHint(Lp,panelH,sy+16);
 // Centre: actions. Phones keep every button 72 tall (36 px, the tap minimum), one short line per
 // note with room above the next button, and a party's RESTART says SOLO ONLY on the button.
 const bh=tight?72:70;let by=top+(tight?0:44);
 btn(s,mx,by,400,tight?80:86,'RESUME',{size:34});
 if(!L.touch) txt(s,mx,by+(tight?84:90),400,22,'or press P',15,'var(--muted)','center','o1 body');
 by+=tight?118:132;
 btn(s,mx,by,400,bh,'SETTINGS',{neutral:1,size:26});
 by+=bh+(tight?12:20);
 btn(s,mx,by,400,bh,tight&&!solo?'RESTART  ·  SOLO ONLY':'RESTART',{neutral:1,size:26,off:!solo});
 if(!solo&&!tight) txt(s,mx,by+bh+2,400,22,'Restart is for solo runs',14,'var(--muted)','center','o1 body');
 by+=bh+(tight?12:40);
 btn(s,mx,by,400,bh,'<span style="color:#ff6969">LEAVE RUN</span>',{neutral:1,size:26});
 txt(s,mx,by+bh+(tight?8:6),400,tight?22:44,tight?'You keep the emeralds earned so far':'Leaving keeps the emeralds you earned so far',15,'var(--muted)','center','o1 body',tight?'':'white-space:normal;text-align:center');
 // Right: build. Weapons (max 6), items (max 16 kinds, copies stack ×5), level-up picks (16 kinds, stack).
 const R=glass(s,rx,top,side,panelH);
 section(R,14,side,'WEAPONS',late?'6 / 6':'4 / 6');
 const wcell=Math.min(80,Math.floor((side-48-5*8)/6)),cell=Math.floor((side-48-7*6)/8);
 const ws=late?[['w01','IV','Legendary'],['w00','IV','Legendary'],['w03','III','Epic'],['w05','IV','Legendary'],['w06','III','Epic'],['w07','IV','Legendary']]
  :[['w01','I','Common'],['w00','II','Rare'],['w03','I','Common'],['w05','III','Epic'],null,null];
 let ry=62;
 ws.forEach((wp,i)=>{const x=24+i*(wcell+8);
  if(!wp){R.appendChild($(`<div class="abs" style="left:${x}px;top:${ry}px;width:${wcell}px;height:${Math.floor(wcell*1.08)}px;border-radius:12px;border:2px solid rgba(255,255,255,.18)"></div>`));return}
  const t=tile(R,x,ry,wcell,'img/'+wp[0]+'.png','',wp[2]);
  t.appendChild($(`<div class="abs o1" style="left:4px;top:4px;padding:0 5px;height:19px;border-radius:5px;background:#1d2427;border:2px solid var(--ink);font-size:12px;display:flex;align-items:center">${wp[1]}</div>`));
 });
 ry+=Math.floor(wcell*1.08)+20;
 const items=late?ALL_ITEMS.map((n,i)=>[n,['×5','×3','×5','×2','×5','','×4','×5','×1','×5','×3','×2','×5','×5','×4','×3'][i],RARS[i%4]])
  :[['magnet','×2','Rare'],['protein','','Common'],['shoes','','Rare'],['hotsauce','×3','Epic'],['glasses','','Common'],['bandage','','Common']];
 section(R,ry,side,'ITEMS',items.length+' / 16');ry+=48;
 items.forEach((it,i)=>tile(R,24+(i%8)*(cell+6),ry+Math.floor(i/8)*(Math.floor(cell*1.08)+6),cell,'img/shop-'+it[0]+'.png','',it[2],it[1]));
 ry+=Math.ceil(items.length/8)*(Math.floor(cell*1.08)+6)+14;
 const ups=late?ALL_UPS.map((n,i)=>[n,'×'+[14,12,11,9,8,8,7,6,6,5,4,4,3,3,2,1][i]])
  :[['Damage','×3'],['AttackSpeed','×2'],['MaxHP','×2'],['Luck','×1'],['MoveSpeed','×1']];
 section(R,ry,side,'LEVEL-UPS',side<450?(late?'103 picks':'9 picks'):(late?'level 64  ·  103 picks':'level 9  ·  9 picks'));ry+=48; // narrow: THIS RUN shows the level
 ups.forEach((u,i)=>{const x=24+(i%8)*(cell+6),yy=ry+Math.floor(i/8)*(cell+12);
  const c=$(`<div class="abs" style="left:${x}px;top:${yy}px;width:${cell}px;height:${cell+6}px;border-radius:10px;background:rgba(255,255,255,.06);border:2px solid rgba(0,0,0,.5)"></div>`);R.appendChild(c);
  c.appendChild($(`<div class="abs icon" style="left:${Math.floor(cell*.12)}px;top:3px;width:${Math.floor(cell*.76)}px;height:${Math.floor(cell*.76)}px;background-image:url(img/up-${u[0]}.png)"></div>`));
  txt(c,2,cell-16,cell-6,20,u[1],15,'var(--lime)','right','o2');
 });
 ry+=Math.ceil(ups.length/8)*(cell+12)+6;
 txt(R,24,ry,side-48,40,'Level-ups are the stat cards you pick each time you level up. Their effect is already in STATS.',15,'var(--muted)','left','o1 body','white-space:normal');
 scrollHint(R,panelH,ry+56);
}
// Canvas for a screen size: PauseUI's T.canvas (1920x1080 design, phones held at scale .5) with
// Roblox's 58 px top bar.
function canvasFor(sw,sh,touch){
 let s=Math.min(sw/1920,sh/1080);
 if(s<.5) s=Math.max(s,Math.min(.5,sw/1280,sh/640));
 return {sw,sh,s,w:sw/s,h:sh/s,top:Math.max(58,36)/s,phone:touch,touch};
}
const PC=canvasFor(1920,1080,false),PHONE=canvasFor(844,390,true),SMALL_PHONE=canvasFor(667,375,true);
const VIEWS=[
 ['Solo',PC,{frozen:true},'<b>Solo:</b> P, Esc or the pause button freezes everything. Background is the run, darker but see-through. Stats on the left, build on the right.'],
 ['Late game (maxed)',PC,{frozen:true,late:true},'<b>Late game / Endless:</b> the most a run can hold. 6 weapons, all 16 item kinds (copies stack ×5) and all 16 level-up cards (they stack, ×14). Numbers grow, the grids don\'t.'],
 ['Party of 4: waiting',PC,{members:PARTY4,frozen:false},'<b>Party of 4, not everyone paused:</b> the menu opens but the game <b>keeps going</b>. One card per player, you first (lime edge): ✓ paused, <b>playing</b> or <b>down</b>. Downed players don\'t count, so it says 2 / 3, and they never block a freeze. Long names (up to 20 characters) fit; a wider one ends in "…". Restart is solo-only.'],
 ['Party of 4: all paused',PC,{members:PARTY4.map(m=>m[1]==='playing'?[m[0],'paused']:m),frozen:true},'<b>Party of 4, everyone alive has paused:</b> the game freezes for everyone (the downed player isn\'t waited for) until anyone presses Resume.'],
 ['Party of 4 on a phone',PHONE,{members:PARTY4,frozen:false},'<b>Phone (844×390):</b> the same screen at the phone\'s scale, under Roblox\'s top bar. The plate and map line share one centred row, the pill uses shorter words and grows to keep them on one line, cards are wider so long names stay readable, and the buttons close up (still 36 px tall for thumbs) with one short line under LEAVE RUN. RESTART says SOLO ONLY on the button. The side panels scroll. No "or press P" on touch.'],
 ['Small phone (667×375)',SMALL_PHONE,{members:PARTY4,frozen:false},'<b>Small phone (667×375, iPhone SE):</b> the narrowest phone canvas. Cards get a little narrower, so the longest names can end in "…" (in Studio, "xX_DragonSlayer99_Xx" still fits at 11 px and "SuperLongName_12345A" ends in "…").'],
];
let cur=0;
function render(){
 const v=VIEWS[cur],L=v[1],st=document.getElementById('stage');
 S=L.s;st.innerHTML='';st.style.width=L.w+'px';st.style.height=L.h+'px';
 pauseView(st,v[2],L);
 document.getElementById('note').innerHTML=v[3];
 document.querySelectorAll('.top button').forEach((b,i)=>b.classList.toggle('on',i==cur));
 fit();
}
// PC fills the page width; the phone sits in a bezel, up to 1.5x its real size.
function fit(){
 const L=VIEWS[cur][1],vp=document.getElementById('vp'),fr=document.getElementById('frame'),st=document.getElementById('stage');
 const bez=L.phone?18:0,k=L.phone?Math.min(1.5,(vp.clientWidth-40)/(L.sw+2*bez)):vp.clientWidth/L.sw;
 fr.className='frame'+(L.phone?' phone':'');
 fr.style.width=(L.sw*k+2*bez*k)+'px';fr.style.height=(L.sh*k+2*bez*k)+'px';fr.style.borderWidth=(bez*k)+'px';
 st.style.transform=`scale(${L.s*k})`;
}
const tb=document.getElementById('tabs');VIEWS.forEach((v,i)=>{const b=document.createElement('button');b.textContent=v[0];b.onclick=()=>{location.hash=i};tb.appendChild(b)});
addEventListener('resize',fit);
if(location.hash)cur=+location.hash.slice(1)||0;
addEventListener('hashchange',()=>{cur=+location.hash.slice(1)||0;render()});
// Text fitting measures real glyphs: draw again once the fonts are in.
render();document.fonts.ready.then(render);
