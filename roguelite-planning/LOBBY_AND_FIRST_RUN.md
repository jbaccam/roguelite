# Lobby and first-run flow

Updated: 2026-09-26. Planning only; no gameplay implementation implied. Progression rules (maps, keys, chests, starting tiers, armor): [PROGRESSION_AND_SESSION_FLOW.md](PROGRESSION_AND_SESSION_FLOW.md).

## Confirmed first-join direction

On first join, automatically spawn the player into a guided game as a base character. Introduce features step by step, let them kill mobs across a few waves, then defeat an easy boss. After finishing, send them to the lobby where they can select their setup and queue normally. This supersedes the earlier lobby introduction and class selection before the tutorial.

The base character remains the player's Roblox avatar. The exact tutorial weapon and whether the tutorial uses a neutral class or a predefined starter class remain open.

## Recommended lobby flow — proposed

**Confirmed queue direction, 2026-09-24:** Multiple physical portals support independent simultaneous queues so separate groups can prepare runs at the same time. Target four portals. The revised concept places four separate queue pads around the main plaza, clear of through-traffic. Each portal needs independent membership and departure state; chapter selection, party privacy, capacity, and countdown behavior remain to be designed. See [four-portal concept](lobby-concepts/circular-floating-lobby-v2-four-portals.png).

**Confirmed visual direction, 2026-09-24:** Use the user's grassy floating-island reference with rocky cliffs, trees, and wooden bridges, redesigned into a circular connected route with no dead end. See [3D lobby concept](lobby-concepts/README.md). Exact island count and station placement remain proposed.

- Returning players spawn directly into a compact social lobby; no separate mandatory title-screen Play click.
- Select class, an owned class starter weapon (showing its saved tier), and an owned armor set in the lobby through a Loadout button or matching world station. Both open the same interface. Remember the last valid selection.
- Play opens a compact run setup with an unlocked map, supported solo/party mode, and a visible class/weapon/armor summary with Change. Selection happens before queueing, not after matchmaking.

**Queue screen, confirmed 2026-09-27** (modelled on the supplied reference selectors):

1. **Map step (host only):** the chosen map's mini island sits blurred behind the screen, seen from its approved hero camera. `<` `>` slide the camera to the neighbouring island. A locked map fades to a dark silhouette with its unlock rule. Below the map name: Normal / Hard / Nightmare tabs (locked tabs show a padlock and "Beat Normal to unlock Hard"), a line spelling out the enemy buff and key multiplier, the 0 → 20 wave track (elite 5, horde 10, elite 15, boss 20) filled to the best wave on that difficulty, and reward tiles (keys by wave 20, first-win bonus, Endless).
2. **Class step (everyone):** class cards, class details and the starting-weapon grid over the same island. The host also picks Open (up to 4) or Solo.
3. **Stepping onto a pad** opens the map step for the first player (host) and the class step with READY for everyone after. **PLAY away from the pads** opens the same screens; START claims the first empty pad and moves the player onto it as host (no walking or guide beam). The countdown only starts after the host presses START.
4. **Joiners must have the map and difficulty unlocked themselves.** READY is refused otherwise, and anyone who still lacks it at launch stays in the lobby with the reason.
5. **Since 2026-10-03:** READY is now LOCK IN, Solo is now Private, and everyone put on a pad (including party members pulled on after START) gets the class step. The countdown waits up to 20 s for each LOCK IN. Rules: [LOBBY_AND_MATCH_SERVERS.md](LOBBY_AND_MATCH_SERVERS.md), "Leaving, party pads and bigger waves".
- Queue/Ready confirms the setup. Freeze it when committed; changing it requires leaving the queue or clearing ready status. Party members choose their own loadouts; the leader chooses the shared destination. Do not require unique classes.
- First lobby visit briefly introduces Loadout and Play and guides the first chest opening. Reveal other systems (Armory, achievements, quests) as relevant instead of touring every station or opening several reward panels.

**Implemented preview, 2026-09-27:** The Studio lobby HUD and its Loadout, Play (map, portal guide beam, queue banner with Leave), Chests, Armory, Quests, Store, Profile, Party and Settings windows exist as presentation over the real catalogs. Progression values show a fresh-account PREVIEW until a profile service publishes them. See [UI implementation](studio-prototype/ui/README.md).

## Tutorial — approved 2026-10-03

**Superseded:** the approved design is [plans/2026-10-03-tutorial-design.md](plans/2026-10-03-tutorial-design.md). It has 3 waves with the boss on wave 3, Eggbert the egg merchant as guide, a suggested Glock buy (any pick counts), a 650 HP boss with a super-jump intro, and a reward of 3 Silver Chests + 100 emeralds, then the guided chests → Armory → Play. The older proposal below is kept for history; it predates emeralds replacing keys.

### Earlier proposal (2026-09-26)

Target roughly 3–4 minutes with three short waves and an easy boss. Start with one fixed, readable weapon; defer class comparison until the first lobby visit.

1. Move and defeat a few slow mobs. Explain that the weapon attacks automatically using one short prompt.
2. Collect XP and crystal shards; teach one stat choice during a safe intermission.
3. Make one guided weapon purchase, then fight a slightly larger group so the improvement is visible. Teach combining only if this remains brief; otherwise guide it on the first normal run.
4. Defeat a forgiving boss with one clearly telegraphed attack and generous recovery windows.
5. Show a short result that grants enough keys for one chest, and return to the lobby. Explain that the temporary build resets while keys, weapons and armor stay, then guide the first chest, class/starter/armor selection and Play.

Advance prompts when the player performs the action. Pause combat for menu explanations. Use checkpoints and a quick free retry on tutorial defeat; never show a paid revive in onboarding. Save completion only after success, support resume after disconnect, and allow replay from Help. Only the first completion grants keys; retries and replays must not farm persistent rewards. Studio practice still grants no persistent rewards and DataStores remain disabled by default.

## Decisions still open

- Tutorial starter weapon and base-class behavior.
- Exact wave lengths and boss.
- Skip behavior, particularly for experienced players joining friends.
- Whether in-run combining fits onboarding or should move to the first normal run.

Validate first-time comprehension, time to first kill, time to first normal queue, and mobile/controller usability before treating proposed timings as final.
