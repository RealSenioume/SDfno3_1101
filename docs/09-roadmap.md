# 9. Roadmap (living document)

**Status of this document:** the single source of truth for what comes next.
`docs/03-design.md` §14 and `docs/08-report-draft.md` §8 keep a short summary for
their own readers, but when they disagree with this file, this file wins.

*Last updated: 30 October 2026, after v0.3.4.*

| Column | Meaning |
| --- | --- |
| Effort | **S** = under a day, **M** = a few days, **L** = weeks / a research task |
| Status | `now`, `next`, `later`, `blocked`, `done` |
| Target | the release the item is aiming at, or `tbd` |

## 1. Now — v0.3.5

| Item | Why | Effort | Status | Target |
| --- | --- | --- | --- | --- |
| Confirm the scaled-display fix on a second machine | A user reported the wheel appearing offset at 125–200 % scaling; the centre now comes from Qt's pointer. Measured on one machine only. | S | blocked on external hardware | v0.3.5 |
| Bump to v0.3.5 and update the measurement/limitations text | The released 0.3.4 package predates the fix being called "fixed". | S | next | v0.3.5 |
| Keep the README/doc consistency tests green | They caught the stale `0.3.1` / `Retreat` claims; keep them honest. | S | done | — |

## 2. Next — v0.4.x

| Item | Why | Effort | Status | Target |
| --- | --- | --- | --- | --- |
| Fullscreen auto-pause | Overlay cannot draw over exclusive fullscreen; a foreground-window check (`SHQueryUserNotificationState`) would pause instead of misbehave. | M | later | v0.4.0 |
| Application profiles | Different slice sets when presenting, reviewing or tutoring; the eight fixed slots are a deliberate constraint, not a feature. | M | later | v0.4.0 |
| Configurable sector count | 4 / 6 / 8 / 12 slots; the geometry already works on sectors, the UI and defaults do not. | M | later | v0.4.0 |
| Ping history viewer with a heat map | The JSONL log already holds every ping; nothing reads it visually. | M | later | v0.4.1 |
| Accessibility: high-contrast theme, keyboard-only commit, screen-reader announcement | The wheel is mouse-only and colour-dependent today. | M | later | v0.4.1 |
| Localisation (i18n) | The UI is English-only while the documentation is bilingual; the strings are scattered across modules. | M | later | v0.4.1 |
| Installer, auto-update, code signing | A zipped one-folder build with an unsigned exe is fine for testers, not for "download and run". | M | later | tbd |

## 3. Later — research

### 3.1 lolping as a DSH plugin

**Idea.** Turn the wheel from a ping recorder into a *spatial command surface* for
DeepSeek Harness. A committed slice becomes a typed intent — `search`, `analyse`,
`summarise`, `statistics`, `run` — that carries three things a chat box cannot
express: **where** on the screen the user pointed, **what** was on screen at that
point (window title, region), and **which** slice was chosen. DSH consumes the
intent and acts on it.

**Why the wheel is the right input.** A prompt is linear; attention is spatial.
"Look at this part of the log and count the errors" is three facts — region,
action, object — that a radial menu can deliver in one gesture without the user
typing or leaving the application they are looking at.

**Shape of the work.**

1. An intent schema (`lolping.intent/v1`): slice id, action verb, screen point,
   screen region, foreground window, free-text hint, timestamp, confidence.
2. A transport: local socket first (JSON lines), so the plugin and lolping stay
   separate processes and either can crash without taking the other down.
3. A DSH plugin that subscribes to intents, maps verbs to tools (search, file
   read, statistics, screenshot region) and reports progress back.
4. A result channel back to the overlay: a toast/panel that shows what DSH is
   doing, because a silent action triggered by a gesture is unacceptable.
5. Permissions: which verbs may run without confirmation, which need an explicit
   second gesture; an append-only audit log of every dispatched intent.

**Risks.** The plugin API is not frozen; a gesture that can start actions needs a
permission model that is at least as clear as the current "no injection" stance;
the wheel must stay usable when no DSH is listening (today's ping behaviour is
the fallback).

**Effort:** L. **Target:** tbd — after the v0.4.x items, and only if the plugin
API is stable enough to depend on. **Status:** research.

### 3.2 Multi-user DSH collaboration

**Idea.** Several people, each with their own wheel, marking the same shared
surface — a shared screen, a document, a replay — with every intent attributed
and routed into a shared DSH session. The wheel becomes a shared pointing tool:
"this region, look at it" from three people at once, each contributing a
different verb.

**Why.** Reviewing a match or a design together is the natural next step from a
single-user log: the ping list already records *what* was marked, and the point
already records *where*. Attribution and merging are what turn that into
collaboration.

**Shape of the work.**

1. A session service (LAN first): join by code, exchange marks, cursors and
   intent history, no account required.
2. Identity and attribution: every mark carries a peer id and a display name; the
   overlay shows whose mark is whose.
3. Merging: N intents on one region should reach DSH as one grouped request, not
   N duplicates — the same problem as deduplicating pings.
4. Privacy: marks reveal attention; a session must be explicit, visible and easy
   to leave, and nothing is uploaded unless a session is active.
5. A shared result view so participants see the same answer, not five private
   ones.

**Risks.** Transport and NAT traversal, clock skew when ordering marks, and the
social problem of a screen full of other people's marks. Multi-user also multiplies
the permission surface of 3.1: a remote intent must never be able to run an action
that the local user's own gesture could not.

**Effort:** L. **Target:** tbd. **Status:** research.

### 3.3 Everything else

| Item | Why | Effort | Status |
| --- | --- | --- | --- |
| Native input-suppression helper | A tiny C++/Rust helper returning 1 from a low-level hook would remove the "Alt + click is reserved" trade-off. | L | later |
| Per-monitor DPI v2 and a Qt 6 port | Mixed-DPI desktops are only partially handled; the scaling fix solved the coordinate bug, not the awareness model. | L | later |
| Cross-platform (macOS, Linux X11/Wayland) | The overlay is Win32-specific; the geometry and state machine are portable. | L | later |
| Room / team features separated from the core overlay | Explicitly out of scope for the current product; multi-user DSH sessions (3.2) supersede it. | M | later |

## 4. Explicitly out of scope

From `docs/01-proposal.md`: game-memory access, injection, the Riot API, an
in-game HUD, voice, champion or cooldown data, and anything that requires being
inside the game process. A DSH plugin (3.1) stays on the desktop side of that
line: it consumes intents, not the game.

## 5. Recently closed

| Item | Release |
| --- | --- |
| League-inspired `lol` skin, click-to-ping, LoL-aligned sectors, local PNG override | v0.3.2 |
| Pause hotkey (replacing the quit hotkey), settings dialog on start-up | v0.3.3 |
| Trigger on/off switch that mirrors the hotkey and the tray entry | v0.3.4 |
| Wheel centre taken from Qt's pointer, fixing the offset on scaled displays; screen/dpr diagnostics in the log | v0.3.4 hotfix |
| Stale version / default-sector claims in README corrected, with tests that keep them correct | v0.3.4 docs |
