# Plan E: Economy numbers and Armory cleanup (RARITY_GODLY_ARMOR.md, step 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chests give a handful of items instead of a flood, upgrades and daily deals follow the approved rarity tables, Mjolnir becomes Legendary, the Godly rarity exists (but never rolls until step 4 adds Godly weapons), and the Armory stops talking about pet eggs.

**Architecture:**
- `ChestConfig` (unsandboxed, `RS.RogueliteCombat`) holds every number and every pure rule: the chest table, `rollCounts`, a new `open` (one chest with both pity counters), `summary`/`odds` for the UI, a new `percent` formatter and a new `rollDeal`. Keeping the rules pure makes them testable in Edit without booting `ProfileService`.
- `ProfileService` (unsandboxed, `SSS`) keeps the saved state and calls those rules: `openChest` uses `Chests.open`, `dealList` uses `Chests.rollDeal`, saves gain `pity.Godly`.
- UI (`ChestScreenUI`, `LobbyUI`, `ArmoryUI`) reads row counts and colours from `ChestConfig` instead of assuming four rarities.

**Tech stack:** Roblox Luau, Studio MCP (`execute_luau`, `start_stop_play`, `get_console_output`, plain `screen_capture`), the local Python file server for syncing repo files into Studio, stylua for parse checks.

**Spec:** `roguelite-planning/RARITY_GODLY_ARMOR.md` sections 1–3 and 12, build-order "Step 1" (user-approved 2026-09-28).

**Decision made here (not in the spec):** `pity.Godly` only counts chests where a Godly can drop (a pity chest while the Godly pool is non-empty). Until step 4 it stays 0. Counting now would hand every long-time player a guaranteed Godly the day Godly weapons launch.

---

## Conventions

Everything in the "Conventions" section of `plans/2026-09-28-D-admin-panel.md` applies: paths, the Studio helper block (`pull`, `same`, `sync`, `create`, `fresh`, `testsFolder`), `serverCheck`, the shared-Studio rules, parse checks and commits. Extra rows for this plan:

| Repo file | Studio instance | Sandboxed |
|---|---|---|
| `studio-prototype/combat/ChestConfig.luau` | `RS.RogueliteCombat.ChestConfig` | no |
| `studio-prototype/combat/ChestConfigTests.luau` (new) | `ServerStorage.RogueliteTests.ChestConfigTests` | no |
| `studio-prototype/combat/ProfileService.luau` | `SSS.ProfileService` | no |
| `studio-prototype/ui/ChestScreenUI.luau` | `RS.ChestScreenUI` | no |
| `studio-prototype/ui/LobbyUI.luau` | `RS.LobbyUI` | no |
| `studio-prototype/ui/ArmoryUI.luau` | `RS.ArmoryUI` | no |

No new `require` edges. `ChestConfig` requires nothing.

**Other sessions' uncommitted edits.** When this plan was written, `ChestScreenUI`, `LobbyUI` and `ArmoryUI` carried other sessions' uncommitted hunks (sound cues, practice-dummy button). Never revert them. To commit only this plan's hunks:

```bash
# before editing: snapshot the working copy
cp studio-prototype/ui/X.luau "$SCRATCH/X.before"
# after editing: my hunks = before -> now; apply them to the index only
diff -u "$SCRATCH/X.before" studio-prototype/ui/X.luau | sed '1,2c --- a/roguelite-planning/studio-prototype/ui/X.luau\n+++ b/roguelite-planning/studio-prototype/ui/X.luau' > "$SCRATCH/X.patch"
git apply --cached --unidiff-zero "$SCRATCH/X.patch"
```

If `git apply --cached` refuses because a hunk touches their lines, stop and tell the user instead of staging their work.

---

### Task 0: Pre-flight

- [ ] **Step 1:** `git status --short` on the six files above. Note which carry other sessions' hunks (expected: the three UI files) and snapshot those three into the scratchpad.
- [ ] **Step 2:** Start the file server (plan D Conventions) and check `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8765/RARITY_GODLY_ARMOR.md` → `200`.
- [ ] **Step 3:** `list_sessions` + `get_studio_state`. Edit work only while Studio is in Edit; if it is in Play and this session didn't start it, wait.
- [ ] **Step 4:** In Edit, `same()` for all five existing files. Expected `true` for each. A `false` means an unsynced edit on one side: stop and ask.

---

### Task 1: ChestConfig numbers and pure rules (TDD)

**Files:**
- Create: `studio-prototype/combat/ChestConfigTests.luau`
- Modify: `studio-prototype/combat/ChestConfig.luau` (whole file)

Studio stays working after this task: `rollCounts(kind,rng,forceLegendary)` keeps its old call shape, `summary` still returns four rows while Godly is off, and no UI reads the new fields yet.

- [ ] **Step 1: Write the failing test** `studio-prototype/combat/ChestConfigTests.luau`:

```lua
-- ChestConfig checks (RARITY_GODLY_ARMOR.md step 1): chest table, item counts, odds against a
-- simulation, both pity counters, upgrade and spare-copy tables, deal prices and rarity pools.
-- Run in Studio Edit on a fresh copy of ChestConfig. The Godly checks give that copy a temporary
-- three-weapon Godly pool and empty it again. `rolls` = simulated chests per chest kind.
return function(Chests, rolls)
	rolls = rolls or 100000
	local checks = 0
	local function check(condition, message)
		assert(condition, message)
		checks += 1
	end
	local rng = Random.new(20260928)

	-- Pools, rarities, colours
	local sizes = { Common = 12, Rare = 12, Epic = 5, Legendary = 7, Godly = 0 }
	for r, n in sizes do
		check(#Chests.Pool[r] == n, r .. " pool has " .. n .. " weapons, found " .. #Chests.Pool[r])
		check(typeof(Chests.RarityColor[r]) == "Color3", r .. " has a colour")
	end
	check(#Chests.Rarities == 5 and Chests.Rarities[5] == "Godly", "Godly is the fifth rarity")
	check(Chests.RarityOf["31"] == "Legendary", "Mjolnir is Legendary")
	check(not Chests.godlyEnabled(), "Godly is off while its pool is empty")

	-- Section 1: the chest table {emeralds, items, rare, epic, legendary, godly, pity}
	local want = {
		Wooden = { 60, 3, 0.25, 0.02, 0.002, 0, false },
		Silver = { 160, 6, 1, 0.08, 0.008, 0.0005, true },
		Gold = { 300, 10, 2, 0.25, 0.03, 0.002, true },
		Magical = { 700, 18, 4, 1, 0.1, 0.006, true },
		Legendary = { nil, 8, 3, 1, 1, 0.02, true },
	}
	for kind, w in want do
		local d = Chests.ById[kind]
		check(
			d.emeralds == w[1]
				and d.copies == w[2]
				and d.rare == w[3]
				and d.epic == w[4]
				and d.legendary == w[5]
				and d.godly == w[6]
				and d.pity == w[7],
			kind .. " matches the section 1 table"
		)
	end
	check(Chests.LegendaryPity == 50 and Chests.GodlyPity == 150, "Pity is 50 Legendary / 150 Godly")

	-- Section 2: upgrade costs and spare-copy emeralds
	local upgrades = {
		Common = { 2, 6, 15 },
		Rare = { 2, 4, 8 },
		Epic = { 1, 2, 4 },
		Legendary = { 1, 2, 3 },
		Godly = { 1, 1, 2 },
	}
	local spare = { Common = 2, Rare = 5, Epic = 20, Legendary = 60, Godly = 200 }
	for r, costs in upgrades do
		for t = 1, 3 do
			check(Chests.UpgradeByRarity[r][t] == costs[t], r .. " tier " .. t .. " costs " .. costs[t])
		end
		check(Chests.OverflowByRarity[r] == spare[r], r .. " spare copy is " .. spare[r] .. " emeralds")
	end
	check(Chests.upgradeCost("31", 2) == 2 and Chests.overflow("31") == 60, "Mjolnir upgrades and cashes in as a Legendary")
	check(Chests.upgradeCost("00", 3) == 15, "Glock III -> IV costs 15")

	-- The UI's text
	for x, text in { [0.25] = "25%", [0.02] = "2%", [0.002] = "0.2%", [0.0005] = "0.05%", [0.006] = "0.6%", [0.1] = "10%" } do
		check(Chests.percent(x) == text, "percent(" .. x .. ") = " .. text .. ", got " .. Chests.percent(x))
	end
	local function rows(kind)
		local out = {}
		for _, row in Chests.summary(kind) do
			table.insert(out, row.rarity .. "=" .. row.text)
		end
		return table.concat(out, " ")
	end
	local summaries = {
		Wooden = "Common=×0–3 Rare=25% Epic=2% Legendary=0.2%",
		Silver = "Common=×3–5 Rare=×1 Epic=8% Legendary=0.8%",
		Gold = "Common=×6–8 Rare=×2 Epic=25% Legendary=3%",
		Magical = "Common=×12–13 Rare=×4 Epic=×1 Legendary=10%",
		Legendary = "Common=×3 Rare=×3 Epic=×1 Legendary=×1",
	}
	for kind, text in summaries do
		check(rows(kind) == text, kind .. " summary: " .. rows(kind))
	end

	-- Item counts are conserved by rollCounts and group
	local function conserved(kind, n)
		local d = Chests.ById[kind]
		for _ = 1, n do
			local counts = Chests.rollCounts(kind, rng)
			local total = 0
			for _, r in Chests.Rarities do
				total += counts[r]
				assert(counts[r] >= 0, kind .. " negative " .. r)
			end
			assert(total == d.copies, kind .. " rolled " .. total .. " items, not " .. d.copies)
			local tally, grouped = {}, 0
			for _, r in Chests.Rarities do
				Chests.group(r, counts[r], rng, tally)
			end
			for _, c in tally do
				grouped += c
			end
			assert(grouped == total, kind .. " grouped " .. grouped .. " of " .. total .. " items")
			if not Chests.godlyEnabled() then
				assert(counts.Godly == 0, kind .. " rolled a Godly while Godly is off")
			end
		end
		checks += 1
	end
	for _, kind in Chests.Order do
		conserved(kind, 5000)
	end

	-- odds() matches a simulation (4.5 standard deviations per weapon)
	local function compare(kind, n)
		local seen, sim = {}, Random.new(7)
		for _ = 1, n do
			local counts = Chests.rollCounts(kind, sim)
			local tally = {}
			for _, r in Chests.Rarities do
				Chests.group(r, counts[r], sim, tally)
			end
			for id in tally do
				seen[id] = (seen[id] or 0) + 1
			end
		end
		local listed = 0
		for _, o in Chests.odds(kind) do
			listed += 1
			local p, got = o.chance / 100, (seen[o.id] or 0) / n
			local sigma = math.sqrt(p * (1 - p) / n)
			assert(
				math.abs(got - p) <= 4.5 * sigma + 1e-9,
				string.format("%s %s: odds say %.4f%%, simulation %.4f%%", kind, o.id, p * 100, got * 100)
			)
		end
		local pooled = 0
		for _, r in Chests.Rarities do
			pooled += #Chests.Pool[r]
		end
		check(listed == pooled, kind .. " odds list every pooled weapon once")
	end
	for _, kind in Chests.Order do
		compare(kind, rolls)
	end

	-- Legendary pity
	local pity = { Legendary = Chests.LegendaryPity - 1, Godly = 0 }
	local counts = Chests.open("Silver", rng, pity)
	check(counts.Legendary == 1 and pity.Legendary == 0, "The 50th pity chest has a Legendary and resets the counter")
	pity = { Legendary = 10, Godly = 0 }
	Chests.open("Wooden", rng, pity)
	check(pity.Legendary == 10 and pity.Godly == 0, "Wooden chests don't count toward pity")
	pity = { Legendary = 0, Godly = 0 }
	local gap, worst = 0, 0
	for _ = 1, 20000 do
		local c = Chests.open("Silver", rng, pity)
		gap += 1
		if c.Legendary > 0 then
			worst = math.max(worst, gap)
			gap = 0
		end
	end
	check(worst == Chests.LegendaryPity, "Over 20,000 Silver chests the longest Legendary wait is exactly 50, got " .. worst)
	-- Godly off: never rolls, never counts
	pity = { Legendary = 0, Godly = Chests.GodlyPity - 1 }
	counts = Chests.open("Gold", rng, pity)
	check(counts.Godly == 0 and pity.Godly == Chests.GodlyPity - 1, "No Godly and no Godly pity while Godly is off")

	-- Godly on (temporary pool on this copy only)
	Chests.Pool.Godly = { "G1", "G2", "G3" }
	check(Chests.godlyEnabled(), "A Godly pool turns Godly on")
	check(rows("Gold") == "Common=×5–8 Rare=×2 Epic=25% Legendary=3% Godly=0.2%", "Gold summary with Godly: " .. rows("Gold"))
	check(not rows("Wooden"):find("Godly"), "Wooden never shows Godly")
	pity = { Legendary = 0, Godly = Chests.GodlyPity - 1 }
	counts = Chests.open("Gold", rng, pity)
	check(counts.Godly == 1 and pity.Godly == 0, "The 150th pity chest has a Godly and resets the counter")
	pity = { Legendary = 0, Godly = 5 }
	Chests.open("Wooden", rng, pity)
	check(pity.Godly == 5, "Wooden chests don't count toward Godly pity")
	pity = { Legendary = 0, Godly = 0 }
	gap, worst = 0, 0
	for _ = 1, 6000 do
		local c = Chests.open("Silver", rng, pity)
		gap += 1
		if c.Godly > 0 then
			worst = math.max(worst, gap)
			gap = 0
		end
	end
	check(worst == Chests.GodlyPity, "Over 6,000 Silver chests the longest Godly wait is exactly 150, got " .. worst)
	for _, kind in Chests.Order do
		conserved(kind, 2000)
	end
	compare("Gold", rolls)
	compare("Legendary", rolls)
	Chests.Pool.Godly = {}
	check(not Chests.godlyEnabled(), "Godly is off again")

	-- Section 3: daily deals
	for _, o in Chests.DealOdds do
		check(o[1] ~= "Godly", "Deals never offer Godly")
		check(
			Chests.DealPrice[o[1]] > Chests.OverflowByRarity[o[1]],
			o[1] .. " deal price per copy is above its spare-copy value"
		)
	end
	local mix, drng, n = {}, Random.new(99), 20000
	for _ = 1, n do
		local deal = Chests.rollDeal(drng)
		local a = Chests.DealAmount[deal.rarity]
		assert(Chests.RarityOf[deal.id] == deal.rarity, "deal weapon " .. deal.id .. " is " .. deal.rarity)
		assert(deal.amount >= a[1] and deal.amount <= a[2], "deal amount in range")
		assert(deal.each == Chests.DealPrice[deal.rarity] and deal.price == deal.amount * deal.each, "deal price")
		assert(deal.each > Chests.overflow(deal.id), "deal price per copy beats cashing in")
		mix[deal.rarity] = (mix[deal.rarity] or 0) + 1
	end
	checks += 1
	for _, o in Chests.DealOdds do
		local got = (mix[o[1]] or 0) / n * 100
		check(math.abs(got - o[2]) < 1.5, string.format("%s deals %.1f%% (want %d%%)", o[1], got, o[2]))
	end
	return { passed = checks }
end
```

- [ ] **Step 2: Run it against today's ChestConfig and watch it fail.** In Edit (helper block first):

```lua
local t=create('ModuleScript','ChestConfigTests',testsFolder(),'studio-prototype/combat/ChestConfigTests.luau')
local ok,r=pcall(fresh(t),fresh(RS.RogueliteCombat.ChestConfig),2000)
return ok and ('passed '..r.passed) or ('FAIL '..tostring(r))
```

  Expected: `FAIL … Godly pool has 0 weapons` (or another missing-field error). A pass here means the test isn't testing anything.

- [ ] **Step 3: Replace `studio-prototype/combat/ChestConfig.luau`** with:

```lua
-- Chest tiers, weapon rarities and odds, shared by the server (rolls) and the UI (odds shown
-- before opening). Numbers: roguelite-planning/RARITY_GODLY_ARMOR.md sections 1-3.
-- A chest holds a handful of weapon copies. Rare and Epic amounts are whole copies plus a chance
-- of one more (.25 = a 25% chance of one, 1 = exactly one); Legendary and Godly are a chance of
-- one copy (1 = always). Commons fill the rest. Copies of one rarity are grouped into 1-3 weapons
-- (e.g. ×5 Frying Pan, ×2 Egg).
local C={Order={},ById={}}

C.Rarities={'Common','Rare','Epic','Legendary','Godly'}
C.RarityColor={
 Common=Color3.fromRGB(214,222,226),Rare=Color3.fromRGB(79,183,245),
 Epic=Color3.fromRGB(192,116,249),Legendary=Color3.fromRGB(255,196,60),
 Godly=Color3.fromRGB(226,34,64),
}
-- Fixed rarity per weapon id (WeaponCatalog). Every class signature weapon is Common.
-- Godly weapons arrive in step 4; until then the Godly pool is empty and Godly never rolls.
local RARITY={
 Common={'01','05','00','08','12','15','19','17','24','26','30','35'},
 Rare={'02','06','09','07','13','16','23','21','27','29','34','33'},
 Epic={'04','10','14','20','28'},
 Legendary={'03','11','18','22','25','32','31'},
 Godly={},
}
C.Pool={};C.RarityOf={}
for _,r in C.Rarities do
 C.Pool[r]=table.clone(RARITY[r])
 for _,id in RARITY[r] do C.RarityOf[id]=r end
end
-- A Godly roll with no Godly weapon would turn into a missing item, so Godly waits for its pool.
function C.godlyEnabled() return #C.Pool.Godly>0 end

-- Copies spent to raise a weapon's starting tier (I->II, II->III, III->IV).
C.UpgradeByRarity={Common={2,6,15},Rare={2,4,8},Epic={1,2,4},Legendary={1,2,3},Godly={1,1,2}}
C.UpgradeCost=C.UpgradeByRarity.Common -- fallback for unknown ids
function C.upgradeCost(id,tier)
 local costs=C.UpgradeByRarity[C.RarityOf[id] or 'Common']
 return costs[tier]
end
-- Copies past Tier IV turn into this many emeralds each.
C.OverflowByRarity={Common=2,Rare=5,Epic=20,Legendary=60,Godly=200}
function C.overflow(id) return C.OverflowByRarity[C.RarityOf[id] or 'Common'] end

-- Pity, on chests with pity=true: a Legendary within 50 chests, a Godly within 150.
C.LegendaryPity=50
C.GodlyPity=150
-- Chests bought or opened at once.
C.Amounts={1,10,100}
function C.validAmount(n) return table.find(C.Amounts,n)~=nil end

-- aura: the chest's glow and opening colour. emeralds=nil: not sold for emeralds (the Legendary
-- Chest comes from Robux packs and rewards).
local function add(d) C.ById[d.id]=d;table.insert(C.Order,d.id) end
add({id='Wooden',icon='rbxassetid://107136053285951',name='Wooden Chest',emeralds=60,copies=3,rare=.25,epic=.02,legendary=.002,godly=0,pity=false,
 aura=Color3.fromRGB(120,235,70),glow=Color3.fromRGB(255,190,80)})
add({id='Silver',icon='rbxassetid://103320236733137',name='Silver Chest',emeralds=160,copies=6,rare=1,epic=.08,legendary=.008,godly=.0005,pity=true,
 aura=Color3.fromRGB(70,170,255),glow=Color3.fromRGB(110,195,255)})
add({id='Gold',icon='rbxassetid://88627612681717',name='Gold Chest',emeralds=300,copies=10,rare=2,epic=.25,legendary=.03,godly=.002,pity=true,
 aura=Color3.fromRGB(255,200,50),glow=Color3.fromRGB(255,206,90)})
add({id='Magical',icon='rbxassetid://92681366357642',name='Magical Chest',emeralds=700,copies=18,rare=4,epic=1,legendary=.1,godly=.006,pity=true,
 aura=Color3.fromRGB(176,90,255),glow=Color3.fromRGB(110,180,255)})
add({id='Legendary',icon='rbxassetid://81753880209961',name='Legendary Chest',emeralds=nil,copies=8,rare=3,epic=1,legendary=1,godly=.02,pity=true,
 aura=Color3.fromRGB(255,110,40),glow=Color3.fromRGB(255,176,60),accent=Color3.fromRGB(120,255,232)})
-- Old saves: class chests become Wooden, the Royal Chest becomes Legendary (same Robux packs).
C.Legacy={Brawler='Wooden',Gunner='Wooden',Thrower='Wooden',Juggler='Wooden',Handyman='Wooden',Mage='Wooden',Royal='Legendary'}

-- How many stacks a rarity's copies are grouped into.
local function stacks(copies) return copies<=0 and 0 or copies==1 and 1 or copies<=3 and 2 or 3 end
-- Whole copies, plus one more with the fraction's chance (.25 -> 0 or 1; 1 -> 1).
local function amount(rng,x) return math.floor(x)+(rng:NextNumber()<x%1 and 1 or 0) end

-- Copies per rarity for one chest (forceLegendary / forceGodly = pity).
function C.rollCounts(kind,rng,forceLegendary,forceGodly)
 local d=C.ById[kind]
 local rare=amount(rng,d.rare)
 local epic=amount(rng,d.epic)
 local legendary=(forceLegendary or rng:NextNumber()<d.legendary) and 1 or 0
 local godly=C.godlyEnabled() and (forceGodly or rng:NextNumber()<d.godly) and 1 or 0
 return {Common=math.max(0,d.copies-rare-epic-legendary-godly),Rare=rare,Epic=epic,Legendary=legendary,Godly=godly}
end

-- One chest with pity. `pity` (the saved {Legendary=n, Godly=n}) is updated in place. Only pity
-- chests count, and Godly pity only counts once a Godly can drop.
function C.open(kind,rng,pity)
 local d=C.ById[kind]
 local godlyCounts=d.pity and C.godlyEnabled()
 local counts=C.rollCounts(kind,rng,
  d.pity and (pity.Legendary or 0)>=C.LegendaryPity-1,
  godlyCounts and (pity.Godly or 0)>=C.GodlyPity-1)
 if d.pity then pity.Legendary=counts.Legendary>0 and 0 or (pity.Legendary or 0)+1 end
 if godlyCounts then pity.Godly=counts.Godly>0 and 0 or (pity.Godly or 0)+1 end
 return counts
end

-- Split `copies` of one rarity over 1-3 different weapons. Returns {id=count}.
function C.group(rarity,copies,rng,into)
 into=into or {}
 local pool=table.clone(C.Pool[rarity]);local n=math.min(stacks(copies),#pool)
 if n==0 then return into end
 -- Distinct weapons; the first stack is the biggest (like ×5 / ×3 / ×1).
 local picked={}
 for i=1,n do table.insert(picked,table.remove(pool,rng:NextInteger(1,#pool))) end
 local shares={}
 local left=copies-n
 for i=1,n do shares[i]=1 end
 for _=1,left do local i=rng:NextNumber()<.55 and 1 or rng:NextInteger(1,n);shares[i]+=1 end
 table.sort(shares,function(a,b) return a>b end)
 for i,id in picked do into[id]=(into[id] or 0)+shares[i] end
 return into
end

-- 0.25 -> '25%', 0.002 -> '0.2%', 0.0005 -> '0.05%'.
function C.percent(x)
 local p=x*100
 local s=p>=10 and string.format('%.0f',p) or p>=1 and string.format('%.1f',p) or p>=.1 and string.format('%.2f',p) or string.format('%.3f',p)
 if s:find('%.') then s=s:gsub('0+$',''):gsub('%.$','') end
 return s..'%'
end
-- '×2', '25%' or '×1 + 25%'; nil when it can't drop.
local function amountText(x)
 local whole,frac=math.floor(x),x%1
 if whole>0 and frac>0 then return '×'..whole..' + '..C.percent(frac) end
 if whole>0 then return '×'..whole end
 if frac>0 then return C.percent(frac) end
 return nil
end

-- Rarity summary for the chest screen. Rarities this chest can't drop are left out (Godly until
-- Godly weapons exist).
function C.summary(kind)
 local d=C.ById[kind];local out={}
 local godly=C.godlyEnabled() and d.godly or 0
 local most=d.copies-math.floor(d.rare)-math.floor(d.epic)-math.floor(d.legendary)-math.floor(godly)
 local least=math.max(0,d.copies-math.ceil(d.rare)-math.ceil(d.epic)-math.ceil(d.legendary)-math.ceil(godly))
 table.insert(out,{rarity='Common',text=least==most and ('×'..most) or ('×'..least..'–'..most)})
 for _,r in {{'Rare',d.rare},{'Epic',d.epic},{'Legendary',d.legendary},{'Godly',godly}} do
  local text=amountText(r[2])
  if text then table.insert(out,{rarity=r[1],text=text}) end
 end
 return out
end

-- Chance (percent) that one chest includes at least one copy of each weapon, grouped by
-- rarity. Exact for the rules above (stacks are distinct weapons picked uniformly).
function C.odds(kind)
 local d=C.ById[kind];if not d then return {} end
 local godly=C.godlyEnabled() and d.godly or 0
 -- {count, probability} cases for each rarity's roll.
 local function split(x) local w,f=math.floor(x),x%1;return f>0 and {{w,1-f},{w+1,f}} or {{w,1}} end
 local function once(p) return p>=1 and {{1,1}} or p>0 and {{1,p},{0,1-p}} or {{0,1}} end
 local dist={Rare=split(d.rare),Epic=split(d.epic),Legendary=once(d.legendary),Godly=once(godly),Common={}}
 -- Commons are whatever the other rolls leave.
 for _,r in dist.Rare do for _,e in dist.Epic do for _,l in dist.Legendary do for _,g in dist.Godly do
  table.insert(dist.Common,{d.copies-r[1]-e[1]-l[1]-g[1],r[2]*e[2]*l[2]*g[2]})
 end end end end
 local out={}
 for _,r in C.Rarities do
  local pool=#C.Pool[r]
  if pool>0 then
   local p=0
   for _,c in dist[r] do p+=c[2]*math.min(stacks(math.max(0,c[1])),pool)/pool end
   for _,id in C.Pool[r] do table.insert(out,{id=id,rarity=r,chance=p*100}) end
  end
 end
 return out
end

-- Daily deals (the "item shop sale"): each paid slot picks a rarity, then a weapon of it. Never
-- Godly. Every price per copy is well above that rarity's spare-copy value, so buying a deal to
-- cash the copies in never pays.
C.DealOdds={{'Common',55},{'Rare',35},{'Epic',8},{'Legendary',2}}
C.DealPrice={Common=15,Rare=40,Epic=150,Legendary=500} -- emeralds per copy
C.DealAmount={Common={2,5},Rare={1,3},Epic={1,1},Legendary={1,1}}
function C.rollDeal(rng)
 local roll=rng:NextNumber()*100;local rarity=C.DealOdds[#C.DealOdds][1]
 for _,o in C.DealOdds do if roll<o[2] then rarity=o[1];break end;roll-=o[2] end
 local pool=C.Pool[rarity];local id=pool[rng:NextInteger(1,#pool)]
 local a=C.DealAmount[rarity];local n=rng:NextInteger(a[1],a[2])
 return {kind='Weapon',id=id,rarity=rarity,amount=n,each=C.DealPrice[rarity],currency='Emeralds',price=n*C.DealPrice[rarity]}
end
return C
```

- [ ] **Step 4: Parse check** both files (Conventions command). Expected `ok` twice.
- [ ] **Step 5: Sync and run the tests.** In Edit:

```lua
sync(RS.RogueliteCombat.ChestConfig,'studio-prototype/combat/ChestConfig.luau')
local t=create('ModuleScript','ChestConfigTests',testsFolder(),'studio-prototype/combat/ChestConfigTests.luau')
local t0=os.clock()
local ok,r=pcall(fresh(t),fresh(RS.RogueliteCombat.ChestConfig))
return (ok and ('PASS '..r.passed..' checks') or ('FAIL '..tostring(r)))..string.format(' in %.1fs',os.clock()-t0)
```

  Expected: `PASS <n> checks`. If the 100,000-roll run times out the MCP call, rerun with `rolls=30000` and record which count ran.
- [ ] **Step 6: Commit** `ChestConfig.luau` + `ChestConfigTests.luau`: "Chests: fewer items, rarity-based upgrades, Godly rarity (off), Mjolnir Legendary".

---

### Task 2: ProfileService uses the new rules

**Files:** Modify `studio-prototype/combat/ProfileService.luau`.

- [ ] **Step 1:** In Edit `same(SSS.ProfileService,'studio-prototype/combat/ProfileService.luau')` → `true`.
- [ ] **Step 2: Replace** the pity migration line

```lua
 if data.pity.Legendary==nil then data.pity={Legendary=0} end
```
with
```lua
 if data.pity.Legendary==nil then data.pity={Legendary=0} end
 if data.pity.Godly==nil then data.pity.Godly=0 end -- Godly pity (2026-09-28); old saves start at 0
```

- [ ] **Step 3: Replace** `local RANK={Common=1,Rare=2,Epic=3,Legendary=4}` with `local RANK={Common=1,Rare=2,Epic=3,Legendary=4,Godly=5}`.
- [ ] **Step 4: Replace** the roll loop in `P.openChest`

```lua
 for _=1,n do
  local forced=chest.pity and (d.pity.Legendary or 0)>=Chests.LegendaryPity-1
  local counts=Chests.rollCounts(kind,rng,forced)
  if chest.pity then d.pity.Legendary=counts.Legendary>0 and 0 or (d.pity.Legendary or 0)+1 end
  for _,r in Chests.Rarities do Chests.group(r,counts[r],rng,tally) end
 end
```
with
```lua
 for _=1,n do
  local counts=Chests.open(kind,rng,d.pity) -- rolls with both pity counters and updates them
  for _,r in Chests.Rarities do Chests.group(r,counts[r],rng,tally) end
 end
```

- [ ] **Step 5: Replace** `dealList`'s loop

```lua
 for _=2,Money.DailyDealSlots do
  local w=Weapons.List[r:NextInteger(1,#Weapons.List)]
  local amount=r:NextInteger(2,5)
  table.insert(list,{kind='Weapon',id=w.id,amount=amount,currency='Emeralds',price=amount*15})
 end
```
with
```lua
 -- Each paid slot: a rarity, then a weapon of it, priced per copy by rarity (ChestConfig.rollDeal).
 for _=2,Money.DailyDealSlots do table.insert(list,Chests.rollDeal(r)) end
```
and the comment above it with `-- Daily deals: same 5 deals for a player all day, new ones at UTC midnight. Never Godly.`

- [ ] **Step 6:** Parse check, `sync(SSS.ProfileService,…)`.
- [ ] **Step 7: Play check (server).** Only when `get_studio_state` is Edit and no other session is in Play: start Play, then run with `serverCheck`:

```lua
local P=require(game.ServerScriptService.ProfileService)
local Chests=require(game.ReplicatedStorage.RogueliteCombat.ChestConfig)
local player=game.Players:GetPlayers()[1]
local t0=os.clock();while not P.get(player) and os.clock()-t0<10 do task.wait(.2) end
local d=P.get(player)
add(d.pity.Legendary~=nil and d.pity.Godly==0,'profile has pity.Legendary and pity.Godly=0')
P.grant(player,{chests={Wooden=11,Silver=11,Gold=11,Magical=11,Legendary=11}})
local before=d.pity.Legendary
local ok,_,res=P.openChest(player,'Gold',10)
local total=0;for _,r in res do total+=r.count end
add(ok and total==100,'10 Gold Chests give 100 items, got '..total)
add(d.pity.Legendary<=before+10 and d.pity.Godly==0,'Legendary pity moved, Godly pity stayed 0')
add(tostring(player:GetAttribute('ProfilePity')):find('Godly:0')~=nil,'ProfilePity publishes Godly:0')
local view=P.dailyView(player)
for i,deal in view.deals do if i>1 then
 add(deal.rarity~='Godly' and deal.each==Chests.DealPrice[deal.rarity] and deal.price==deal.amount*deal.each and deal.each>Chests.overflow(deal.id),'deal '..i..' '..deal.rarity..' ×'..deal.amount..' for '..deal.price)
end end
```

  Expected: every line `PASS`. Leave Play running for Task 3's checks if they follow immediately; otherwise stop Play.
- [ ] **Step 8: Commit** `ProfileService.luau`: "Profiles: Godly pity counter, chests roll through ChestConfig.open, rarity-based daily deals".

---

### Task 3: Chest screen reads rows and colours from ChestConfig

**Files:** Modify `studio-prototype/ui/ChestScreenUI.luau` (other sessions' hunks present: stage only this task's hunks).

- [ ] **Step 1:** `same(RS.ChestScreenUI,…)` → `true`; snapshot the file.
- [ ] **Step 2: Replace** `local RANK={Common=1,Rare=2,Epic=3,Legendary=4}` with `local RANK={Common=1,Rare=2,Epic=3,Legendary=4,Godly=5}`.
- [ ] **Step 3: Replace** `rarityBars` so the row count comes from `summary`:

```lua
 local function rarityBars(parent,id,y)
  local rows=Chests.summary(id)
  for i,row in rows do
```
…and its last line `return y+4*(RAR_H+6)` with `return y+#rows*(RAR_H+6)`.

- [ ] **Step 4: Add** after `rarityBars`:

```lua
 -- Pity reminders under the selected chest (the Godly line only once Godly weapons exist).
 local function pityLines(def)
  local out={}
  if not def.pity then return out end
  local function line(rarity,limit)
   local n=math.max(1,limit-(profile.pity[rarity] or 0))
   table.insert(out,rarity..' guaranteed within <b>'..n..'</b> chest'..(n>1 and 's' or ''))
  end
  line('Legendary',Chests.LegendaryPity)
  if Chests.godlyEnabled() and (def.godly or 0)>0 then line('Godly',Chests.GodlyPity) end
  return out
 end
```

- [ ] **Step 5: In `drawList`, replace**
  - `local rowH=ROW_H+(sel and (4*(RAR_H+6)+(def.pity and 44 or 10)) or 0)` → `local rowH=ROW_H+(sel and (#Chests.summary(id)*(RAR_H+6)+10+#pityLines(def)*34) or 0)`
  - the Sub text's `('Legendary '..(math.floor(def.legendary*1000+.5)/10)..'%')` → `('Legendary '..Chests.percent(def.legendary))`
  - the pity block
```lua
    if def.pity then
     local left_=math.max(1,Chests.LegendaryPity-(profile.pity.Legendary or 0))
     local p=left(T.text(row,'Pity','Legendary guaranteed within <b>'..left_..'</b> chest'..(left_>1 and 's' or ''),18,yy+2,LIST_W-36,30,20,C.limeSoft));p.ZIndex=row.ZIndex+2
    end
```
  with
```lua
    for i,text in pityLines(def) do
     local p=left(T.text(row,i==1 and 'Pity' or 'Pity'..i,text,18,yy+2+(i-1)*34,LIST_W-36,30,20,C.limeSoft));p.ZIndex=row.ZIndex+2
    end
```

- [ ] **Step 6: In `openOdds`**, compute the odds before the panel and size the panel by the rarities that have weapons:

```lua
  local odds=Chests.odds(id)
  local byR={};for _,o in odds do byR[o.rarity]=byR[o.rarity] or {};table.insert(byR[o.rarity],o) end
  local shown={};for _,r in Chests.Rarities do if byR[r] then table.insert(shown,r) end end
  local W,H=1340,math.max(740,130+#shown*144)
```
  (removing the later `local odds=…` / `local byR=…` lines and the old `local W,H=1340,740`), and loop `for _,r in shown do local list=byR[r]` instead of `for _,r in Chests.Rarities do local list=byR[r] or {}`.
- [ ] **Step 7: Reveal:** in `card()` replace `RANK[r.rarity]==4 and 40 or 22` with `RANK[r.rarity]>=4 and 40 or 22`; in `showResults` replace the four `rank==4` with `rank>=4`. (The full Godly reveal is step 4's job.)
- [ ] **Step 8:** Parse check, `sync(RS.ChestScreenUI,…)`, commit only this task's hunks: "Chest screen: rows, pity lines and odds panel sized from ChestConfig; Godly-ready".

---

### Task 4: Daily-deal cards show rarity and price per copy

**Files:** Modify `studio-prototype/ui/LobbyUI.luau` (other sessions' hunks present).

- [ ] **Step 1:** `same(RS.LobbyUI,…)` → `true`; snapshot.
- [ ] **Step 2: Replace** the deal card block in `tabs.Daily` (from `local n=math.max(1,#deals);local cw=(SW-(n-1)*12)/n;local ch=270` through the `if deal.kind=='Weapon' then … end` block) with:

```lua
   local n=math.max(1,#deals);local cw=(SW-(n-1)*12)/n;local ch=292
   for i,deal in deals do
    local x=(i-1)*(cw+12)
    local free=deal.kind=='Emeralds'
    local rarity=deal.rarity or 'Common'
    local card=T.panel(list,'Deal'..i,x,y,cw,ch,'panel');T.setTier(card,free and 4 or 2)
    -- Weapon deals wear their rarity's colour (ChestConfig.RarityColor), like chest reveal cards.
    local color=free and C.emerald or Chests.RarityColor[rarity]
    if not free and card:FindFirstChild('RarityCorners') then card.RarityCorners.ImageColor3=color end
    art(card,free and 'emerald' or WeaponIcons[deal.id],cw/2,104,92,color,150)
    local amt=T.label(card,'Amount',(free and '+' or '×')..deal.amount,0,22,cw,34,32,free and C.emerald or C.gold);amt.TextXAlignment=Enum.TextXAlignment.Center;amt.ZIndex=3
    local name=free and 'Emeralds' or Weapons.ById[deal.id].name
    local nm=T.text(card,'Name',name,10,156,cw-20,22,18);nm.TextXAlignment=Enum.TextXAlignment.Center
    if deal.kind=='Weapon' then
     local rl=T.text(card,'Rarity',string.upper(rarity)..'  ·  '..(deal.each or deal.price)..' each',10,180,cw-20,20,15,color);rl.TextXAlignment=Enum.TextXAlignment.Center
     local rec=profile.weapons[deal.id]
     if rec then T.upgradeBar(card,'Bar',14,204,cw-28,18,rec.have,L.need(rec)) else local l=T.text(card,'New','NEW WEAPON',14,202,cw-28,20,15,C.gold);l.TextXAlignment=Enum.TextXAlignment.Center end
    end
```
  (the Buy button below already sits at `ch-64`).
- [ ] **Step 3:** Parse check, `sync(RS.LobbyUI,…)`, commit only this task's hunks: "Store: daily-deal cards show rarity colour and price per copy".

---

### Task 5: Armory cleanup (section 12)

**Files:** Modify `studio-prototype/ui/ArmoryUI.luau` (other sessions' hunks present).

- [ ] **Step 1:** `same(RS.ArmoryUI,…)` → `true`; snapshot.
- [ ] **Step 2: Look first.** In Play (lobby), open the Armory through `PlayerGui.RogueliteLobbyUI.TestOpenWindow:Fire('Armory', tab)` for Weapons, Armor and Pets; select a weapon, the pet slot and an armor slot; plain `screen_capture` each and run `UILayoutAudit` on `PlayerGui.Armory`. Write down what's cluttered or confusing.
- [ ] **Step 3: Pet wording.** Replace the header comment (lines 39–40) with `-- Armor is worn as four pieces; 2 and 4 pieces of one set give set bonuses. Pets come from the Pet\n-- Chest (pets only). Neither exists yet, so their slots and tabs say what is coming.`; the Pets tab body with `"Pets come from the Pet Chest and follow you into runs. Each one has its own strong suit."` and the first line with `"From the Pet Chest (pets only)"`; the pet detail sub with `"PET SLOT  ·  COMING WITH THE PET CHEST"`.
- [ ] **Step 4: Fix what Step 2 found** (expected candidates: the long "coming" panels and their detail text; show the weapon's rarity in its rarity colour in the detail header so rarity reads at a glance). Record each change in the commit message.
- [ ] **Step 5:** Parse check, sync, re-run Step 2's captures and `UILayoutAudit` (expected: 0 problems), commit only this task's hunks.

---

### Task 6: Full Play verification, docs, push

- [ ] **Step 1:** Studio idle check, start Play. Grant chests with `serverCheck` (`P.grant(player,{chests={Wooden=11,Silver=11,Gold=11,Magical=11,Legendary=11}})`).
- [ ] **Step 2:** From the Client, for each chest kind: `ChestScreen.TestChest:Fire('Open',kind)`, `SetAmount 1`, `Begin`, `Advance`×3, wait for results, count cards and sum `×n` (expected: that chest's item count); `Claim`; then the same with `SetAmount 10` (expected 10× the item count). Capture one ×1 and one ×10 result screen.
- [ ] **Step 3:** Open the odds grid for Wooden and Magical and capture it; check the percentages against `ChestConfig.odds`.
- [ ] **Step 4:** Open Store → Daily; capture; check each deal's rarity label matches `ChestConfig.RarityOf[id]` and the price is `amount × DealPrice`.
- [ ] **Step 5:** `UILayoutAudit` on `PlayerGui.ChestScreen` (browse, odds, results) and the Store's Daily tab. Expected: 0 problems.
- [ ] **Step 6:** `get_console_output`: no new errors. Stop Play.
- [ ] **Step 7:** Paste the real pass counts into `RARITY_GODLY_ARMOR.md` under step 1, commit, push `origin main`.
- [ ] **Step 8:** Show the user; wait before step 2.

**Can't be tested in Studio:** DataStore migration of real saves (Studio profiles are in memory), Robux Legendary Chest purchases, PolicyService-restricted accounts.
