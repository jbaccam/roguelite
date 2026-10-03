"""Plan M's anchored edits to shared scripts: feats, weekly quests and win records
(plans/2026-10-02-M-feats-weekly-roads.md). QuestConfig, QuestService and QuestsUI are whole modules.
    python plan_m_hunks.py [--check] [--stage] [--json]   (see tools/hunks.py)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from hunks import run  # noqa: E402

META = "combat/RogueliteMeta.server.luau"
META_S = "ServerScriptService.RogueliteMeta"
PROFILE = "combat/ProfileService.luau"
PROFILE_S = "ServerScriptService.ProfileService"

HUNKS = [
    # --- RogueliteMeta: who died / had company this stint, the win record, wave 25, two claims -----
    (META, META_S,
     "local runInfo={} -- player -> {stint,prevBest,firstWin}", "after",
     "-- Plan M feats: the stint a player last died in (any death, even one a revive or a phoenix\n"
     "-- undoes) and the last stint that cleared a wave with company. Solo and no-down need neither.\n"
     "local wentDown,soloBroken={},{}"),
    (META, META_S,
     " if not m or not Shop.states[p] or down[p] then return end", "after",
     " wentDown[p]=m.stint -- plan M: before the phoenix check, so a phoenix save still counts"),
    (META, META_S,
     " local map=runMap();local index=RunSetupRules.MapIndex[map]", "after",
     " if Shop.memberCount()>1 then for p,m in Shop.members do soloBroken[p]=m.stint end end -- plan M: not solo"),
    (META, META_S,
     "  if wavesPassed==10 then questEvent(p,'deepRuns',1) end -- Reach Wave 10 in One Run", "after",
     "  if wavesPassed==25 then questEvent(p,'wave25Runs',1) end -- plan M: Reach Wave 25 in One Run\n"
     "  -- Plan M: the win's record for feats and weekly quests. Solo and no-down count from wave 1 only.\n"
     "  if wavesPassed==RunSetupRules.WinWave and Profiles.questWin then\n"
     "   local cs=Characters.states[p]\n"
     "   Profiles.questWin(p,{diff=difficulty(),solo=m.joined==1 and soloBroken[p]~=m.stint,\n"
     "    flawless=m.joined==1 and wentDown[p]~=m.stint,class=cs and cs.class})\n"
     "  end"),
    (META, META_S,
     " RunPause.forget(pause,p);pausedWeapons[p]=nil;lastPauseAction[p]=nil;runKills[p]=nil;runDamage[p]=nil;statStint[p]=nil -- plan L",
     "after",
     " wentDown[p]=nil;soloBroken[p]=nil -- plan M"),
    (META, META_S,
     " elseif action=='ClaimUnlock' and Profiles.claimUnlock and type(a)=='string' and #a<=40 then ok,message=Profiles.claimUnlock(p,a)",
     "after",
     " elseif action=='ClaimWeekly' and Profiles.claimWeekly and type(a)=='number' then ok,message=Profiles.claimWeekly(p,a) -- plan M\n"
     " elseif action=='ClaimFeat' and Profiles.claimFeat and type(a)=='string' and #a<=40 then ok,message=Profiles.claimFeat(p,a) -- plan M"),
    # --- ProfileService: the win record and the two new claims ----------------------------------
    (PROFILE, PROFILE_S,
     "-- Daily deals: same 5 deals for a player all day, new ones at UTC midnight. Never Godly.", "before",
     "-- Plan M: a map win's record (difficulty, solo, no-down, class) for feats and weekly quests,\n"
     "-- and their claims. A test run counts nothing, like questEvent.\n"
     "function P.questWin(player,info)\n"
     " local d=P.profiles[player];if not d or Admin.isTestRun() then return end\n"
     " if quest('win',d,Money.day(),player.UserId,info) then questDirty[player]=true end\n"
     "end\n"
     "function P.claimWeekly(player,index)\n"
     " local d=P.profiles[player];if not d then return false,'Profile loading' end\n"
     " return questGrant(player,quest('claimWeekly',d,Money.day(),player.UserId,index))\n"
     "end\n"
     "function P.claimFeat(player,id)\n"
     " local d=P.profiles[player];if not d then return false,'Profile loading' end\n"
     " return questGrant(player,quest('claimFeat',d,Money.day(),player.UserId,id))\n"
     "end\n"),
]

MODULES = [
    {"path": "combat/QuestConfig.luau", "parent": "ReplicatedStorage.RogueliteCombat", "name": "QuestConfig"},
    {"path": "combat/QuestService.luau", "parent": "ServerScriptService", "name": "QuestService"},
    {"path": "ui/QuestsUI.luau", "parent": "ReplicatedStorage", "name": "QuestsUI"},
]
BASE = "db73bbf"  # Studio holds the plan M build (db73bbf); e28f1c7 for the first sync

if __name__ == "__main__":
    run(HUNKS, MODULES, "combat/plan-m-sync.json", BASE)
