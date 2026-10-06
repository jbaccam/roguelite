# Daily Deal item bursts — October 6, 2026

Buying three Glocks now emits three separate Glock icons. They fan upward from the offer, stagger slightly, hang briefly and drift/fade, with a `+3 GLOCK` receipt underneath. The old enlarged source-image pop is skipped for this effect so it does not cover the copies.

`StoreUI` derives the item ID and quantity from the successful `ProfileAction('BuyDeal')` result, whose server-generated result array contains one row per awarded copy. It does not trust the amount displayed before purchase: a daily reset can change the offer during the request. The actual returned ID replaces the snapshot's icon. Failure/cancellation, malformed results and unconfirmed network errors do not emit item icons. Snapshot cleanup also occurs if the store closes before the response.

The server's price checks, purchase grant, persistence and duplicate-claim protection are unchanged. The effect is a scoped `dealItem` branch in the existing `QuestsUI.claimFX`; emerald and chest claim effects keep their behavior. Current daily quantities are at most five. Item particles share one frame callback and the existing 1.7-second cleanup layer; a defensive 24-item effect budget prevents unbounded UI particles.

Validation: nineteen tests execute the actual receipt-selection function for quantities one through five, failures, invalid/mixed IDs, malformed/oversized results and a changed server-awarded ID. Official Luau compilation and diff whitespace checks passed. This agent did not sync or run Studio; parent owns visual QA at normal and scaled window sizes. No real purchase, reward grant or production DataStore was used by the tests.

Production files: `StoreUI.luau`, `QuestsUI.luau`. Test runner: `DailyDealRewardTests.py path/to/luau.exe`.
