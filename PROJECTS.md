# Projects in this workspace

This `Roblox` folder is a mixed historical working copy with active tasks. **The games have separate Studio places, and new work should use the dedicated sibling folders below.** The root Rojo project here still builds Copy The Scene only. The `partyati` Git remote attached to this mixed folder does not make its root source the Partyati game.

| Project | Source and planning | Studio target | Build command |
| --- | --- | --- | --- |
| Copy The Scene | `../CopyTheScene/` (dedicated clone of `jbaccam/copy-the-scene`) | Copy The Scene place | From that folder: `rojo build -o build/CopyTheScene.rbxlx` |
| Roguelite | `../roguelite/` (dedicated clone of `jbaccam/roguelite`) | `roguelite` place, ID `107877054949326` | From that folder: `rojo build roguelite-planning/studio-prototype/combat/default.project.json -o build/RogueliteKatanaCombat.rbxlx` |
| Facility blockout | `facility-blockout/` | Its own Studio work | `rojo build facility-blockout/default.project.json -o build/FacilityBlockout.rbxlx` |

## Working boundaries

- Do not run root `rojo serve` against the roguelite place: it serves Copy The Scene. Use the dedicated project paths above.
- Do not use the root Copy The Scene `AGENTS.md` as the roguelite's design brief. The dedicated roguelite folder has its own `AGENTS.md`; identity and plans begin at [Current Game Structure](../roguelite/roguelite-planning/CURRENT_GAME_STRUCTURE.md).
- Roguelite prototype notes begin at [Studio prototype](../roguelite/roguelite-planning/studio-prototype/README.md), and the current icon concept shortlist is [Stat upgrade art direction](../roguelite/roguelite-planning/STAT_UPGRADE_ART_DIRECTION.md).
- The roguelite Rojo project packages its code; the existing Studio map and unrelated instances need to be preserved when syncing.
- `../roguelite-legacy/` preserves an older clone and its untracked files. It is not the current working copy.
- Active uncommitted roguelite code and art work remains in this mixed folder while other agents are editing. A copy exists in the dedicated roguelite folder; reconcile files changed after that copy before removing this historical working tree.
