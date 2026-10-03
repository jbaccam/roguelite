"""The tutorial's anchored edits to shared scripts (plans/2026-10-03-tutorial-build-steps.md).
TutorialConfig, TutorialDirector, TutorialGuideUI, TutorialGuide and BossIntro are whole files.
    python tutorial_hunks.py [--check] [--stage] [--json]   (see tools/hunks.py)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from hunks import run  # noqa: E402

ECON = "combat/EconomyConfig.luau"
ECON_S = "ReplicatedStorage.RogueliteCombat.EconomyConfig"

HUNKS = [
    # --- EconomyConfig: the shared-crystal split ------------------------------------------------
    (ECON, ECON_S,
     "return E", "before",
     "-- Shared drops (a boss's crystal shower): which of `count` players gets the nth one. Round-robin,\n"
     "-- so 50 across 3 players is 17 / 17 / 16 (TutorialTests).\n"
     "function E.shareIndex(n,count) return (n-1)%math.max(1,count)+1 end"),
]

MODULES = []

if __name__ == "__main__":
    run(HUNKS, MODULES, manifest="combat/tutorial-sync.json", base=None)
