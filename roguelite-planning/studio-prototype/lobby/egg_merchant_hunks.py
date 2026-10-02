"""The egg merchant's small additions to shared scripts, as anchored inserts.

Several sessions edit ProfileService, RogueliteMeta and LobbyUI at once, and Studio often runs an
older or newer copy than the repo. So the egg merchant never pushes those whole files: it adds
these exact hunks next to stable anchor lines, in the repo and in Studio alike.

  python egg_merchant_hunks.py           apply to the repo files (skips hunks already there)
  python egg_merchant_hunks.py --json    also write egg-merchant-hunks.json for SyncEggMerchant.luau
  python egg_merchant_hunks.py --check   report which hunks each repo file has, change nothing

Each hunk: (repo file, Studio path, anchor, where, text). `where` is 'after' or 'before' the
anchor line; `text` is inserted as whole lines. A hunk is "present" when its text is in the file.
"""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent          # studio-prototype/lobby
ROOT = HERE.parent                              # studio-prototype

HUNKS = [
    # --- ProfileService: owned eggs, buying and hatching -----------------------------------
    ("combat/ProfileService.luau", "ServerScriptService.ProfileService",
     "local Pets=require(combat:WaitForChild('PetConfig')) -- sandboxed data", "after",
     "local Eggs=require(combat:WaitForChild('EggConfig')) -- pet eggs; unsandboxed data like ChestConfig"),
    ("combat/ProfileService.luau", "ServerScriptService.ProfileService",
     " player:SetAttribute('ProfileChests',csv(d.chests,function(k,v) return k..':'..v end))", "after",
     " player:SetAttribute('ProfileEggs',d.eggs or 0) -- unhatched pet eggs (EggConfig)"),
    ("combat/ProfileService.luau", "ServerScriptService.ProfileService",
     "-- One tier up for a weapon, an armor piece or a pet: spends its copies AND emeralds (both tables", "before",
     """-- Pet eggs (EggConfig, the egg merchant): bought into the inventory, then hatched. Like chests,
-- where paid random items are restricted only emeralds earned in play can buy them.
function P.buyEgg(player,count,restricted)
 local d=P.profiles[player]
 if not d then return false,'Profile still loading' end
 if not Eggs.validAmount(count) then return false,'Invalid amount' end
 local price=Eggs.price(count)
 if not canSpend(d,price,restricted) then
  if restricted and d.emeralds>=price then return false,'Only emeralds earned in runs can buy eggs in your region' end
  return false,'Need '..(price-(restricted and d.emeralds-d.bought or d.emeralds))..' more emeralds'
 end
 spend(d,price,restricted)
 d.eggs=(d.eggs or 0)+count
 P.publish(player)
 return true,count>1 and ('Bought '..count..'× '..Eggs.Name) or ('Bought a '..Eggs.Name)
end
-- Hatch owned eggs (up to count): one pet per egg, rolled here. The reply has one entry per pet,
-- {id, count, rarity, new, tier, have, emeralds}, rarest first (the same shape as openChest).
function P.openEgg(player,count)
 local d=P.profiles[player]
 if not d then return false,'Profile still loading' end
 if not Eggs.validAmount(count) then return false,'Invalid amount' end
 local n=math.min(count,d.eggs or 0)
 if n<=0 then return false,'No '..Eggs.Name..' to hatch' end
 d.eggs-=n
 local tally={}
 for _=1,n do local id=Eggs.roll(rng);tally[id]=(tally[id] or 0)+1 end
 local results={}
 for id,c in tally do
  local r=P.addCopies(d,id,c);r.count=c;r.rarity=Pets.ById[id].rarity
  table.insert(results,r)
 end
 table.sort(results,function(a,b)
  if RANK[a.rarity]~=RANK[b.rarity] then return RANK[a.rarity]>RANK[b.rarity] end
  if a.count~=b.count then return a.count>b.count end
  return a.id<b.id
 end)
 P.publish(player)
 return true,n>1 and ('Hatched '..n..' eggs') or 'Hatched an egg',results
end"""),
    # --- RogueliteMeta: the two remote actions ---------------------------------------------
    ("combat/RogueliteMeta.server.luau", "ServerScriptService.RogueliteMeta",
     " elseif action=='BuyChest' and type(a)=='string' and type(b)=='number' then ok,message=Profiles.buyChest(p,a,b,restricted[p])", "after",
     """ elseif action=='BuyEgg' and type(a)=='number' then ok,message=Profiles.buyEgg(p,a,restricted[p])
 elseif action=='OpenEgg' and type(a)=='number' then ok,message,results=Profiles.openEgg(p,a)"""),
    # --- LobbyUI: the egg screen as the "Eggs" window ----------------------------------------
    ("ui/LobbyUI.luau", "ReplicatedStorage.LobbyUI",
     "local ChestScreenUI=require(RS:WaitForChild('ChestScreenUI'))", "after",
     """-- The egg merchant's screen, protected: a fault in it must never take the lobby HUD down.
local eggsOk,EggScreenUI=pcall(require,RS:WaitForChild('EggScreenUI'))
if not eggsOk then warn('LobbyUI: EggScreenUI failed to load:',EggScreenUI);EggScreenUI=nil end"""),
    ("ui/LobbyUI.luau", "ReplicatedStorage.LobbyUI",
     " builders.Chests=function(kind) return chestScreen.Open(kind) end", "after",
     """ -- Egg merchant (quest-board island): full-screen egg screen over the egg pedestal (EggScreenUI
 -- + EggStage); the walk-up ring in front of the merchant opens it. Replaces the HUD while open.
 if EggScreenUI then
  local ok,eggScreen=pcall(EggScreenUI.new,player,{
   profile=function() profile=L.profile(player);return profile end,
   need=L.need,
   openWindow=function(name,arg) task.defer(open,name,arg) end,
   onVisible=function(visible) hud.Visible=visible end,
  })
  if ok then self.EggScreen=eggScreen;builders.Eggs=function() return eggScreen.Open() end
  else warn('LobbyUI: egg screen failed:',eggScreen) end
 end"""),
    # --- StationApproach: the merchant's walk-up ring ---------------------------------------
    ("ui/StationApproach.luau", "ReplicatedStorage.StationApproach",
     '\tQuests = { route = "Quests", icon = "quests", label = "QUESTS" },', "after",
     '\tEggs = { route = "Eggs", label = "EGGS" }, -- icon: the stand\'s Icon attribute (the egg merchant)'),
    ("ui/StationApproach.luau", "ReplicatedStorage.StationApproach",
     '\ticon.Image = T.Asset[info.icon] or ""', "after",
     '\tif icon.Image == "" then\n\t\ticon.Image = stand:GetAttribute("Icon") or ""\n\tend'),
    # --- Rojo project (repo only; Studio path None): the new modules ---------------------------
    ("combat/default.project.json", None,
     '        "ChestConfig": {', "before",
     '        "EggConfig": {\n          "$path": "EggConfig.luau"\n        },'),
    ("combat/default.project.json", None,
     '      "ChestScreenUI": {', "before",
     '      "EggMerchant": {\n        "$path": "../ui/EggMerchant.luau"\n      },\n'
     '      "EggStage": {\n        "$path": "../ui/EggStage.luau"\n      },\n'
     '      "EggScreenUI": {\n        "$path": "../ui/EggScreenUI.luau"\n      },'),
]


def apply(text, anchor, where, ins):
    if ins in text.replace(chr(13) + chr(10), chr(10)):
        return text, "present"
    lines = text.split("\n")
    hits = [i for i, l in enumerate(lines) if l.rstrip("\r") == anchor]
    if len(hits) != 1:
        return text, f"anchor found {len(hits)} times"
    i = hits[0]
    crlf = lines[i].endswith("\r")
    new = [l + ("\r" if crlf else "") for l in ins.split("\n")]
    lines[i + 1:i + 1] = new if where == "after" else []
    if where == "before":
        lines[i:i] = new
    return "\n".join(lines), "applied"


def stage_on_head():
    """Stage HEAD + these hunks (and nothing else) for each shared file, so a commit never takes
    other sessions' uncommitted edits in the same files."""
    import subprocess
    repo = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    prefix = subprocess.run(["git", "rev-parse", "--show-prefix"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    for path in sorted({h[0] for h in HUNKS}):
        gp = prefix + path
        text = subprocess.run(["git", "show", "HEAD:" + gp], cwd=repo, capture_output=True, check=True).stdout.decode("utf-8")
        for p, _, anchor, where, ins in HUNKS:
            if p == path:
                text, status = apply(text, anchor, where, ins)
                assert status in ("applied", "present"), f"{path}: {status}"
        sha = subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=repo, input=text.encode("utf-8"), capture_output=True, check=True).stdout.decode().strip()
        subprocess.run(["git", "update-index", "--cacheinfo", f"100644,{sha},{gp}"], cwd=repo, check=True)
        print("staged HEAD + hunks:", gp)


def main():
    check = "--check" in sys.argv
    files = {}
    for path, studio, anchor, where, ins in HUNKS:
        p = ROOT / path
        text = files.get(path) or p.read_bytes().decode("utf-8")
        new, status = apply(text, anchor, where, ins)
        files[path] = new
        print(f"{status:22s} {path}: {ins.splitlines()[0][:70]}")
    if not check:
        for path, text in files.items():
            p = ROOT / path
            if text != p.read_bytes().decode("utf-8"):
                p.write_bytes(text.encode("utf-8"))
    if "--stage" in sys.argv:
        stage_on_head()
    if "--json" in sys.argv:
        out = [{"repo": p, "studio": s, "anchor": a, "where": w, "text": t} for p, s, a, w, t in HUNKS]
        (HERE / "egg-merchant-hunks.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
        print("wrote egg-merchant-hunks.json")


if __name__ == "__main__":
    main()
