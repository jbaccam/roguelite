CHEST AND PET EGG ICONS - 2026-10-02 v1

Six separate 512x512 RGBA PNGs, generated individually with the built-in image-generation tool. Source render and two existing style icons were attached to EVERY request. No source assets or UI code were overwritten. This is a local-source configuration audit, not a live Studio/published-place audit.

PROJECT DESTINATION
roguelite-planning/studio-prototype/ui/assets/chests-pet-egg-2026-10-02-v1/

FILE -> GAME ENTRY / REUSE MAPPING
chest-wooden.png -> ChestConfig.ById.Wooden; free daily Wooden chest and Wooden selection/owned entries in ChestScreenUI. Optional shared generic chest activity art for QuestConfig.Icons.chests (Chests daily task and Collector road); those count all chest types, not specifically Wooden. No current Wooden quest reward in QuestConfig.
chest-silver.png -> ChestConfig.ById.Silver; 160-emerald chest purchase; Boss daily quest reward; streak day 3; achievement road reward tiers 2 and 3. Reuse for all quantities.
chest-gold.png -> ChestConfig.ById.Gold; 300-emerald chest purchase; StoreUI VIP daily Gold chest claim and VIP benefit tile; streak days 7 and 15; achievement road reward tiers 4 and 5.
chest-magical.png -> ChestConfig.ById.Magical; 700-emerald chest purchase; streak day 20; achievement road reward tiers 6 and 7.
chest-legendary.png -> ChestConfig.ById.Legendary; StoreUI Legendary packs Royal1 / Royal5 / Royal12 (1/5/12 of the SAME chest), StarterPack (2), GodlyStarter (3), MegaBundle (30), UltimateBundle (100), owned/open entries; streak day 30; achievement road reward tiers 8, 9 and 10. Do not generate different physical chests for pack size or bundle name.
pet-egg.png -> EggConfig.Id = PetEgg and EggConfig.Icon; wandering merchant egg purchase and EggScreenUI, quantities 1/3/10; QuestConfig.Icons.eggs for Hatch daily task and Hatcher achievement road. One kind of egg, 250 emeralds, one random pet per egg. Egg + attached straw nest only; no merchant or wooden pedestal.

SCOPE AND SOURCE EVIDENCE
Read repository-root AGENTS.md; no nested AGENTS.md found under roguelite-planning, including hidden files.
Current authoritative configs: studio-prototype/combat/ChestConfig.luau (Order/ById/Legacy), EggConfig.luau, QuestConfig.luau, MonetizationConfig.luau, ShopCatalog.luau.
UI inspected: ShopUI.luau, StoreUI.luau, QuestsUI.luau, ChestScreenUI.luau, EggStage.luau.
ShopCatalog/ShopUI describe the in-run item shop; physical lobby chest purchases and packs are represented by ChestConfig, ChestScreenUI and StoreUI.
Five active chest IDs are Wooden, Silver, Gold, Magical, Legendary. Royal is a legacy alias to Legendary; Brawler/Gunner/Thrower/Juggler/Handyman/Mage legacy chest IDs map to Wooden. Godly is a reward rarity, not a sixth chest. The stale 'Pet Chest' comment in ChestConfig does not define an active chest; EggConfig defines the current pet container.
The chest-kit README still lists a 60-emerald Wooden price; current ChestConfig makes Wooden free daily. Current configuration took precedence.

PHYSICAL REFERENCES
blender-chest-kit/previews/{wooden,silver,gold,magical,legendary}-closed.png, inspected individually.
blender-egg-merchant-kit/previews/egg-closed.png and icon-egg.png, both inspected; icon-egg.png attached for generation. Current EggConfig explicitly names that icon. The egg README says the old concept's belt and paw medallion were intentionally removed. build_egg.py explicitly hides the pedestal for its icon and keeps the nest. These built assets supersede the original merchant concept for this task.
Style: studio-prototype/ui/assets/upgrades/Armor.png and supplemental-v1/Calendar.png, both inspected and attached to each generation request. Also read upgrades/GENERATED_PROMPTS.md.
No missing physical reference among the six active designs.

VALIDATION AND HONEST DESIGN LIMITS
Generated artwork was resampled and centered without artistic repainting. Framing uses source alpha >8/255 to ignore nearly invisible stray pixels outside the subject; retained pixels preserve generated alpha. Each final is exactly 512x512 with genuine alpha, transparent outer padding, and approximately 83% coverage along its longest visible dimension. See validation.json for measured alpha bounds, transparent/partially transparent/opaque pixel counts and SHA256 hashes. Preview sheet contains checkerboard large previews and actual 64/32 px samples on dark background; the checkerboard is only in the preview sheet.
All chests are closed and show their front plus left side; egg is intact. No scenery, floor shadows, characters, frames, badges, text or loose props in individual icons. Gold's seam coins and Magical's skull/chain are attached model details.
Fidelity limits: illustrated interpretations, not exact model renders. Stronger facets/contours and saturation match existing icon art. Gold and Legendary keyholes became dark instead of warm gold; Gold's coin edges and scrollwork are simplified. Magical skull/teeth/horns are somewhat enlarged and more saturated; tiny stitch/chain topology differs. Legendary crenellations and small gem spacing are simplified. Egg spots preserve the main arrangement but have harder facet borders and slightly altered shapes; straw strands are consolidated. At 32 px the distinct colors and silhouettes remain the primary cues; small bolts, stitches, scrolls and keyholes cannot be expected to resolve.
No Roblox import, asset upload, live Studio test or UI wiring performed. No gameplay changes were made, so gameplay packaging/tests were not run. Existing unrelated work was left in place.

PACKAGE CONTENTS
Six item PNGs; preview-sheet.png; README.txt; validation.json; generation-prompts-and-references.json (complete prompts and source paths). ZIP contains these same files.
