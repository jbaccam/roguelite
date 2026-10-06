# Menu clarity and purchase feedback — 2026-10-06

Applied source-only to roguelite Studio place 107877054949326. All 37 manifest destinations match source. Map and unrelated instances preserved. Built `build/RogueliteKatanaCombat.rbxlx` with the combat Rojo project.

- Choose Class & Starter explains dash eligibility and controls. Dash is now Brawler-only, a class ability. No starter or equipment choice grants dash to another class (October 6 follow-up).
- Class weapon modifiers spell out damage and weapon family. Shop badges say DAMAGE and include a full effect sentence.
- Desktop windows use more of the available screen. Opening tweens are canceled before responsive scale changes. Class details use two columns of modifier sentences on desktop and retain scrolling where content exceeds available height.
- Armory arrows follow the rendered class-grouped grid and active filter. Collection detail removes the rarity-relative count; rarity badge remains.
- Successful Daily Deals animate one icon per server-confirmed copy, with staggered motion and a quantity receipt. Failure/cancellation does not animate rewards.

## Validation actually run

Studio client Play: RunSetupLayoutTests passed 60 viewport/profile cases; ShopLayoutTests passed 10 desktop/phone sizes; ArmoryExperienceTests passed 1,971 assertions; MenuScaleQA passed 27 checks. Final class-column adjustment reran all 60 RunSetup cases successfully. Shop and class UI were visually inspected through Studio captures. Synthetic confirmed-three-Glock reward feedback created three icons and cleaned up correctly; no real purchase was made.

Pure checks: class presentation matrix 831 assertions; DailyDealRewardTests 19 assertions; Armory navigation checks passed. Required Rojo build passed. Final Edit-mode equality check matched all 37 runtime sources. Temporary Studio QA modules removed and Play stopped.

Tests used Studio practice/fixtures. No production DataStores, persistent rewards, or paid purchase flows were exercised. Touch/gamepad input was not manually play-tested.

## Class-only dash follow-up

User requested removing the melee-starter loophole. CharacterStats.dashes now depends only on class (Brawler, the current melee-focused class). Server approval and client eligibility pass only class. Both class screens use the updated explanation.

Four changed runtime sources synchronized to Studio; combat Rojo build passed. Fresh Studio Play checked all 252 class/weapon combinations against the expected Brawler-only rule and selection text on the client. Server checks covered all six classes with melee, ranged, and absent weapon arguments. These are direct module checks, not a manual shop sell-and-dash playthrough. Play stopped after testing.
