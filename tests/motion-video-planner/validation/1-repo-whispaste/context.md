# Video context: WhisPaste (2026-10-20)

## Sources and coverage
- Mode: repository
- Inventory: 3003 files (`git ls-files`, .gitignore respected); JSON at `/private/tmp/claude-501/-Users-silvio-Documents-Projekte-skills/169b11c3-fcdb-418e-92da-63425fb3e425/scratchpad/inv-whispaste.json`. Excluded by the walk: `.dart_tool/`, `build/`, `dist/`. Classified: 1102 code, 1111 tests, 244 docs, 281 images, 38 audio, 6 video, 12 generated, 10 lockfiles.
- Read (targeted): `README.md`; `AGENTS.md` (points to `.jules/GUIDANCE.md`, read: applies to automated PRs, not to planning); `CHANGELOG.md` (section "Unreleased" and 1.4.2, 1.4.1, 1.4.0 head); `store/en-US/features.txt`; `fastlane/metadata/en-US/{description,subtitle,promotional_text}.txt`; `store/microsoft-store-long-description.md` (grep); `docs/zielgruppe.md` (first ~3.5 KB); `docs/landingpage-story.md` (first ~3 KB); `CONTEXT.md` §7 Anti-Vokabular (excerpt); `NETWORK.md` (first ~2 KB); `CLAUDE.md` (grep only); `design-tokens/README.md` (head); `website/src/data/brand-glossary.ts` (head); website `index.astro` (head).
- Code checks (grep, existence only, not read in full): spoken line breaks (`lib/core/config/settings_sections.dart`, `lib/features/settings/sections/text_processing_section.dart`), providers OpenAI/Deepgram (`lib/core/config/settings_enums.dart`, `secure_key_store.dart`), snippets (`lib/features/snippets/snippets_page.dart`), time-saved estimate (`lib/features/analytics/analytics_page.dart`).
- External sources: none supplied. The Chrome/website was not opened.
- Gaps: `CLAUDE.md` (15.7 KB) only grepped; `docs/store-release.md`, `ARCHITECTURE.md`, `CONTEXT.md` mostly unread; the public roadmap lives on Votepit (external, not in the repo, not read); the store copy for de-DE/other languages not read; no test files read (existence only); no runtime check of any feature. Two shipped-claim checks ("offline after model download", "no account") are documented, not verified by a test read.

## Product in one paragraph
WhisPaste is a free, open-source (MIT) desktop dictation tool for Windows, macOS and Linux: press a global hotkey, speak, and the transcript is pasted at the cursor in any app. Offline by default with local Whisper or Parakeet engines; cloud providers (OpenAI, Deepgram) are optional with the user's own key. Positioned as "Press. Speak. Done." / "Speak where you usually type." One-time purchase on the Mac App Store and Microsoft Store; the GitHub release is free. Target audience (docs/zielgruppe.md): people who write a lot on their own desktop (knowledge workers, developers, support staff, students, freelancers, people with RSI). Desktop only; the app is not mobile (the website must work on phones).

## Verified facts (usable in the video)
- Global hotkey, push-to-talk or toggle, text pasted at cursor — evidence: README "How It Works"; store/en-US/features.txt; the auto-paste feature is named in CONTEXT.md §2 (canonical).
- Two local engines, Whisper (up to 99 languages) and Parakeet (~25 languages) — evidence: store/en-US/features.txt line 2; README "Transcription".
- Optional cloud transcription via OpenAI or Deepgram with own key — evidence: store/en-US/features.txt line 4; provider enums in `lib/core/config/settings_enums.dart`.
- Voice Snippets (spoken trigger → text, incl. multi-field templates) — evidence: store/en-US/features.txt; `lib/features/snippets/snippets_page.dart` exists.
- Spoken line breaks ("new paragraph" / "new line") — evidence: store/en-US/features.txt line 7; grep hit in `lib/core/config/settings_sections.dart` and `lib/features/settings/sections/text_processing_section.dart`.
- Smart Mode (clean up / shorten / translate) — evidence: store/en-US/features.txt line 5 (not read in code).
- Searchable history with tags, pins (now "Favorit" per CONTEXT.md terminology), archive, export TXT/MD/JSON/CSV/DOCX — evidence: store/en-US/features.txt line 6 + 10. The UI term is "Favorit"; do not say "pin" as UI label.
- One-time purchase, no subscription, no account, open source MIT — evidence: store/en-US/features.txt last line; fastlane description. "No account": grep found no account/login code in lib (not fully verified).
- Time saved is shown as an estimate — evidence: CHANGELOG 'Unreleased' (Statistics) and `lib/features/analytics/analytics_page.dart`. Must be phrased as estimate.
- Two telemetry defaults are on (opt-out): anonymous usage statistics and crash reports — evidence: NETWORK.md. Relevant if the video mentions privacy: must not say "zero data sent" without qualification.
- Platforms: Windows, macOS, Linux (Ubuntu) — evidence: README badges; store copy.
- Interface languages (app): EN, DE, HE, RU, ES, PT — evidence: CHANGELOG 1.4.0 and README. Website: 8 languages (de, en, es, pt, it, ru, zh, fr) — evidence: docs/landingpage-story.md.
- Apple Silicon Metal speed-up: "about 2.6 times faster than CPU alone with the compact model" — evidence: store/microsoft-store-long-description.md (benchmark, specific model). Only usable with the qualifier.

## Documented but unverified
- "Parakeet ... several times faster" — source: README.md line 60; status: needs check (no benchmark result for Parakeet vs Whisper was read; only the Metal 2.6x claim is sourced). Reworded to: "the faster Parakeet engine" (store wording), no multiplier.
- Smart Mode "translate into 7 languages" — source: README.md; status: needs check (not read in code).
- "Works in emails, chat apps, code editors, browsers, terminals" — source: README; status: documented, general claim; keep generic.
- "Offline after one-time model download" — source: store copy, NETWORK.md (cloud optional); status: documented; consistent with NETWORK.md, not yet tested.
- "Audio never leaves your Mac/PC" — source: Mac store description ("never leaves your Mac"), Windows store ("stays on your PC"). Only true with cloud provider off; wording must carry the condition.

## Roadmap / not shipped (never claim as current)
- Everything under CHANGELOG "## Unreleased": redesigned main window (sidebar, dock), import of audio files by drag and drop (MP3/FLAC/M4A/Ogg), Notes with images and version history, App profiles, Dictionary and Snippets pages, Undo Smart Mode, Linux Wayland auto-paste check, help hub/feedback form, double-tap hands-free recording, flat dialogs. Status: unreleased on dev; not yet in a store build.
- Known issue (Unreleased): Flatpak import of Ogg/FLAC/M4A not verified.
- Public roadmap / idea board: Votepit (external). Not read; no roadmap items in the repo were verified.
- Growth/social features (Teilen, Weiterempfehlung): a growth-reviewer agent exists (CLAUDE.md, `.claude/agents/growth-reviewer.md`); no share feature in the app was found. Do not promise a share feature in the video.

## Assumptions
- The video is for the desktop app and its download page / stores; no mobile app.
- "Teilen wollen" = a clip people post because it is funny, surprising or useful to watch; the product does not offer sharing. Assumption, to be confirmed in the interview.
- The brand palette and font (Hanken Grotesk / Bricolage Grotesque, from `website/src/styles/global.css`) are the current brand; the design-tokens README says the site consumes them.

## Audiences and use cases
- Writers and knowledge workers: recognize writing a reply in mail or chat; pain: typing is slow and interrupts thought; change: say it, it lands at the cursor.
- Developers: recognize code comments and GitHub replies; the terminal and editor case in the README.
- People with RSI or typing fatigue: recognize pain from long typing; change: speak instead of type (phrase as an option, no medical claim).
- Power users: automation via the local automation API (AUTOMATION_API.md, opt-in) — only mention if verified.

## Differentiation and limits
- Differs by: runs locally by default, global (any app), open source (MIT), one-time purchase with no subscription — evidence: store copy, CONTEXT.md, README.
- Limits and honest caveats: GPU speed depends on hardware; Parakeet CPU-only by design (Microsoft store copy); Whisper 99 languages but Parakeet ~25; Linux auto-paste on Wayland needs a one-time setup (README); Flatpak import issue (Unreleased).

## Brand sources
- Logo: `assets/icons/logo-dark.svg` and `logo-light.svg` (SVG, 1024x1024), plus PNG variants up to 320 px; wordmark PNG variants `assets/icons/wordmark-*.png` (no SVG wordmark found). App icon `resources/app-icon mit bg.png`.
- Colors: navy stage, glacier, amber accents; tokens in `design-tokens/primitives.tokens.json` (e.g. `#0b122a` navy base in website global.css, `#0baacc` cyan, `#ffb547` amber). Role names: "Glacier + Amber" (design-tokens/README.md). Source `design-tokens/README.md`.
- Fonts: Hanken Grotesk Variable (body), Bricolage Grotesque Variable (display) — source `website/src/styles/global.css`; font files: not checked in this pass (license not checked).
- Voice and tone: calm, plain, precise. Example (en store copy): "Press a hotkey, speak, and your text appears at your cursor in any app." Brand glossary forbids the word "Spende"/donation across the site (use "Unterstützung"/"Sponsoring" in any copy).
- Design rule (docs/zielgruppe.md, landingpage-story): flat, calm surface, no glass, no glow, continuous motion instead of hard state changes; motion components already exist as inline SVG/CSS on the site (`website/src/components/motion/`).
- Recurring element candidates: the waveform of the recording overlay (live waveform, shown in README and the overlay); the hotkey keycap (`Ctrl+Shift+D` default); the text cursor where text lands.

## Usable assets
| Path | Kind | Size | Usable for |
|---|---|---|---|
| `assets/icons/logo-dark.svg` | logo (SVG) | 1024x1024 | logo end card (vector, scalable) |
| `assets/icons/logo-light.svg` | logo (SVG) | 1024x1024 | light-background variant |
| `assets/icons/wordmark-dark.png` | wordmark PNG | 199x64 (1x) to 798x256 (4x) | end card; use the 4x |
| `assets/icons/4.0x/logo-dark.png` | logo PNG | 320x320 | fallback |
| `resources/app-icon mit bg.png` | app icon | ? | end card |
| `resources/screenshots/history-overview-dark.png` | app screenshot (dark) | ? (not read) | UI reference; check pixel size before use |
| `resources/screenshots/history-detail-dark.png` | app screenshot (dark) | ? (not read) | UI reference |
| `fastlane/screenshots/en-US/01_hero.png` | store screenshot | 1440x900 | UI reference; Windows/Mac framing rules apply for store only |
| `assets/feature_spotlight/side_panel.webp` | image | 18 KB | UI reference (side panel) |
| `assets/onboarding/beat_1_loop_dark.webp` | loop | 747 KB | not checked, possibly an existing animation (inspect before reuse) |
| `website/public/og-image.png` | OG card | ? | brand reference |
| `website/scripts/og-card/og-card-en.html` | HTML card | 5.4 KB | layout reference |

## Production environment
- HyperFrames CLI: not found on PATH (`hyperframes --version` -> command not found); `npx --no-install hyperframes` fails (exit 1). Not installed. HyperFrames skills: yes (listed in the skill list).
- ffmpeg: yes (`/opt/homebrew/bin/ffmpeg`); ffprobe: yes (`/opt/homebrew/bin/ffprobe`). Versions not printed (command output empty).
- Node: v26.7.0; npx 11.19.0.
- Website for capture: https://whispaste.de (not opened; access not checked).

## Open questions for the interview
1. Which goal first: reach (new viewers), brand recall, or downloads/conversion? (Default in the skill: reach first.)
2. Which audience: writers/knowledge workers, developers, or people with RSI/typing fatigue?
3. Which single message, and which platform does the video lead with (macOS, Windows, Linux)?
4. What does "teilen" mean for this video: a clip people send to friends, a post for developers, a short for the store? Is there a tracked share mechanism?
5. Is a video length and format target set (e.g. 9:16 vertical, 1:1, 16:9; 15 s, 30 s)?
6. Budget: any paid voice-over or AI generation approved? (Default: none.)
7. Language: German, English, or both?
8. Is the desktop screen recording of the real app allowed (not captured yet), or only code-drawn mockups?
