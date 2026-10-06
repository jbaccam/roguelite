# Admin difficulty tabs — October 6, 2026

Mobs and Waves now both show Normal, Hard and Nightmare tabs using the existing tab styling. They read the same server-owned `RogueliteCombat.RunDifficulty` attribute and redraw when it changes. Difficulty affects new manual spawns, subsequent Keep N alive replacements and scheduled wave enemies/bosses. Existing enemies retain their spawn stats; selecting a new difficulty does not heal or recreate them. Start the desired wave again for a complete wave at the new difficulty.

The new `Difficulty` AdminAction accepts only the three exact difficulty IDs and no second argument. It uses the existing developer check, rate limit, shared-server gate and test-run marking. Lobby-only servers and active tutorials reject the action. Testing cannot award persistent run rewards.

Three production sources changed: AdminConfig, AdminService and AdminPanelUI. Synced into place **107877054949326** with source-only backups; no map/assets replaced or place published. The required combat Rojo build passed. Final running Studio sources matched **32/32** manifest destinations.

Verification:

- AdminConfig suite: 139 assertions passed during initial Edit validation. The first Play exposed a forbidden sandboxed-to-unsandboxed module require; removing that dependency fixed startup while preserving the same strict allowlist. Final runtime validator checked ten valid/invalid argument cases.
- Live client mounted both panels; all six difficulty buttons were present with nonzero dimensions and content separated below the row. Eighteen selected/unselected-state assertions passed across all three choices and both tabs. An initial selection test incorrectly compared the transparent button background; the corrected test reads the theme's `Neutral` state.
- Actual AdminAction calls changed difficulty and rejected an invalid ID. Pine Valley Sandbox Hard regular zombie spawned with **5 HP / speed 14**. After selecting Nightmare and starting wave 1, scheduled regular zombies had **8 HP / speed 14**. The run was marked AdminTestRun.
- Final console contained only the Studio Assistant camera-restoration diagnostic. No full run or multiplayer admin session was tested. The final live selector check restored Normal; Play remained active.
