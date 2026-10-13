# Wavebreaker Discord Server Layout

**Status:** Draft, 2026-10-13. Nothing created in Discord yet.

The community server for Wavebreaker: Survive the Swarm. It covers news and patch notes, reveals, chat and voice, feedback and bug reports, a private playtest area, and staff/dev rooms.

Emoji prefixes are only for looks and can be removed. Squad voice channels are capped at 4 because a run holds up to 4 players (see `LOBBY_AND_MATCH_SERVERS.md`).

## Tooling

- **MCP server:** [PaSympa/discord-mcp](https://github.com/pasympa/discord-mcp), added to Claude Code with `npx`. The bot token goes in the MCP config and never in this repo, because the repo is public.
- **Lock it to one server:** set `DISCORD_ALLOWED_GUILDS=<server id>`. Deletes then default to a dry-run preview.
- **Bot invite permissions:** Manage Channels, Manage Roles, View Channels, Send Messages, Manage Webhooks, Manage Events. Do not grant Administrator.
- **Your part:** create the empty server, turn on Community (Server Settings > Enable Community), and drag the bot's role to just under Owner. The bot can only manage roles below its own.

## Roles (top to bottom)

| Role | Colour | Who | Key permissions |
|---|---|---|---|
| Owner | red `#E5484D` | you | Administrator |
| Wavebreaker Bot | (auto) | the MCP bot | Manage Channels, Manage Roles, Webhooks, Events |
| Developer | lime `#8BD94A` | devs/artists | Manage Messages, Manage Threads, Manage Events, Mention @everyone |
| Moderator | blue `#3E8EF7` | trusted mods | Timeout, Kick, Ban, Manage Messages, Manage Threads, View Audit Log |
| Helper | teal `#2EC4B6` | trial mods | Manage Threads (tag/close bug and help posts), Timeout |
| Content Creator | purple `#9B6BFF` | YouTubers/streamers | Posts in #content-creators, Embed Links |
| Playtester | orange `#F59E0B` | Roblox Playtesters list | Sees the Playtesting category |
| Server Booster | pink (auto) | Discord creates it | Image perms in #general |
| Verified | grey `#9AA4B2` | linked Roblox via Bloxlink (optional) | Giveaway entry, nickname synced to Roblox name |

**Ping roles**, which members pick themselves in Discord Onboarding and which have no permissions: `Announcements Ping`, `Update Ping`, `Sneak Peek Ping`, `Event Ping`, `Playtest Ping` (only offered to Playtesters).

@everyone can chat after accepting the rules in Discord's built-in Rules Screening. Linking a Roblox account is optional. That keeps the path from a Roblox page click to the first message short.

## Channels

### 📌 START HERE (read-only)
| Channel | Type | Purpose |
|---|---|---|
| welcome | text | What the game is, play link, how the server works |
| rules | text | Server rules (also used by Rules Screening) |
| faq | text | Common questions: chests, emeralds, classes, Gear Power |
| link-roblox | text | Bloxlink `/verify` (optional) |

Discord's own "Channels & Roles" page (from Onboarding) handles ping roles, so there is no #roles channel.

### 📢 NEWS (read-only; Developer posts)
| Channel | Type | Purpose |
|---|---|---|
| announcements | announcement | Big news, releases, milestones. Pings `Announcements Ping` |
| changelog | announcement | Patch notes for every update. Pings `Update Ping` |
| sneak-peeks | announcement | Reveals: new weapons, mobs, maps, bosses. Pings `Sneak Peek Ping` |
| events | text | In-game events, double-emerald weekends, giveaways. Pings `Event Ping` |

Announcement channels let other servers "Follow" them, so fan servers get your posts automatically.

### 💬 COMMUNITY
| Channel | Type | Purpose |
|---|---|---|
| general | text | Anything (slowmode 3s) |
| game-chat | text | Talking about Wavebreaker |
| builds | forum | Share runs and builds. Tags: class, map, weapon type, "Wave 20 clear" |
| looking-for-group | forum | Find a squad of up to 4. Tags: map, difficulty, region |
| media | text | Screenshots and clips (needs attachments) |
| fan-art | text | Art of the game |
| content-creators | text | Videos/streams, only Content Creator can post |
| bot-commands | text | Bloxlink and other bot commands |

### 💡 FEEDBACK & SUPPORT
| Channel | Type | Purpose |
|---|---|---|
| bug-reports | forum | One post per bug. Template below |
| suggestions | forum | One post per idea, sorted by reactions |
| known-issues | text (read-only) | Staff-kept list so people don't re-report |
| help | forum | Gameplay questions. Helpers mark answered posts |
| feedback | text | General opinions on balance, difficulty, feel |

**bug-reports tags:** Combat, Shop, Chests, UI, Lobby, Pets, Mobile, Crash · status tags (mods only): Open, Need Info, Can't Reproduce, Fixed Next Update, Fixed.

**bug-reports post guidelines** (pinned as the forum's guidelines):
> What happened? · What did you expect? · Steps to make it happen again · Device (PC/phone/tablet/console) · Map, wave and class · Clip or screenshot if you have one

**suggestions tags:** Weapons, Mobs & Bosses, Maps, Items, UI, Balance, Quality of Life · status tags (mods only): Under Review, Planned, Added, Not Planned.

### 🧪 PLAYTESTING (Playtester, staff only)
| Channel | Type | Purpose |
|---|---|---|
| playtest-info | text (read-only) | How to join (Roblox Playtesters list), session times, test build notes. Pings `Playtest Ping` |
| playtest-chat | text | Talking during sessions |
| playtest-feedback | forum | Bugs and feedback on unreleased builds. Kept here so unreleased content doesn't leak into public forums |
| 🔊 Playtest VC | voice | Live sessions |

This matches the friends-first launch plan: friends play-test through Audience Limited > Playtesters before ads.

### 🔊 VOICE
| Channel | Type | Purpose |
|---|---|---|
| Lounge | voice | Hang out |
| Squad 1 / Squad 2 / Squad 3 | voice, limit 4 | Play together |
| Reveal Stage | stage | Live reveals and dev Q&A, paired with a Discord Scheduled Event |
| AFK | voice | Server AFK channel (5 min) |

### 🛡️ STAFF (Helper and above)
| Channel | Type | Purpose |
|---|---|---|
| staff-chat | text | Mod discussion |
| staff-notices | text | Rule changes, staff to-dos |
| mod-log | text | AutoMod alerts and Discord's Community/safety updates |
| bug-triage | text | Mods pass confirmed bugs to devs with links to forum posts |
| 🔊 Staff VC | voice | |

### 🔒 DEV (Owner and Developer only)
| Channel | Type | Purpose |
|---|---|---|
| dev-chat | text | Dev talk |
| reveal-planning | text | Reveal calendar and draft posts before they go to #sneak-peeks |
| announcement-drafts | text | Patch notes and announcement drafts |
| github-feed | text | Webhook from the repo's commits |
| 🔊 Dev VC | voice | |

## How a reveal goes out

For example, the Pizza Cutter weapon:

1. Draft the post and image in **#reveal-planning**.
2. Playtesters try it first in **#playtest-info** / **#playtest-feedback**.
3. Teaser in **#sneak-peeks** a week before, pinging `Sneak Peek Ping`.
4. Optional **Reveal Stage** Q&A as a Scheduled Event.
5. Release day: **#announcements** (headline) and **#changelog** (full patch notes), pinging `Update Ping`.
6. Bug posts tagged `Fixed Next Update` get a mention in the next changelog.

## Server settings

- **Community:** on (needed for announcement channels, forums, stage, Onboarding, Rules Screening).
- **Default notifications:** Only @mentions. Without this, every message pings everyone and people mute or leave.
- **Verification level:** Medium (account older than 5 minutes).
- **Explicit media filter:** all members.
- **AutoMod:** block slurs/profanity, mention spam (5+), suspected spam, and links in #general except for Verified and above. Alerts go to #mod-log.
- **Moderation 2FA:** required for staff.
- **Onboarding questions:** "What pings do you want?" (the ping roles) and "Do you make videos?" (points to #content-creators).
- **Roblox side:** add the invite link to the experience's Social Links in Creator Hub.

## Open later

- Ticket bot (private mod-mail) if public bug forums aren't enough for account/purchase problems.
- Separate language channels if a non-English group grows.
