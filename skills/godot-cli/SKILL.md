---
name: godot-cli
description: Drive the Godot Engine editor/binary from the command line — headless export, asset import, running a GDScript task, syntax checks, GUT tests, CI pipelines. Use for 'Godot exportieren', 'Godot headless', 'Godot-Projekt bauen', 'Godot CLI'.
---

# Godot Command Line

Godot ships as one binary that doubles as editor, runtime, and build tool — no separate CLI to install. Everything below targets Godot 4.x; run `godot --version` first to confirm the exact build, since flags do drift between minor versions.

## Finding the binary

- Linux/Windows, or macOS via Homebrew/Scoop: `godot` is on `PATH`.
- macOS `.app` bundle without Homebrew: `cd` to the folder holding `Godot.app`, then run `Godot.app/Contents/MacOS/Godot` (the bundle is a folder, not an executable file — you can't invoke it by path from elsewhere).
- Unknown/misspelled flags are **silently ignored — no error, no warning**. A typo'd flag looks like a clean run. Never trust "no error" alone; check actual output/exit code.

## Project path

Run from inside the project directory, or pass `--path <dir>` (must contain `project.godot`). From a subdirectory, `--upwards` walks up to find it automatically.

## Headless mode

`--headless` (`= --display-driver headless --audio-driver Dummy`) is the default for any agent/CI invocation — import, export, scripting, and testing all work without a GPU or display. Only drop it when you need to actually see the running scene.

## Core workflows

**Import assets (once, before first export)** — a project with no `.godot` cache can freeze on export otherwise:
```
godot --headless --path <project> --import
```
(`--import` implies `--editor --quit`.) `--export-debug`/`--export-pack`/`--export-patch` run this implicitly; **`--export-release` does not** — run the import pass yourself first.

**Export a build:**
```
godot --headless --path <project> --export-release "<preset-name>" <output-path>
```
- `<preset-name>` must exactly match a preset in `export_presets.cfg` (quote it if it has spaces).
- `<output-path>`, if relative, resolves against the **project directory**, not your shell's CWD.
- Export templates for that platform must be installed. Swap `--export-release` for `--export-debug` (implies import) or `--export-pack <preset> file.pck` for a pack-only build.

**Run a one-off GDScript task** (batch conversion, custom import/export tooling) — script must extend `SceneTree` or `MainLoop`:
```
godot --headless -s script.gd
```
Path is resolved as `res://script.gd` relative to the project; use an absolute filesystem path to run a script outside the project.

**Syntax-check a script without running it:**
```
godot --headless --check-only -s script.gd
```

**Run GUT unit tests** (if the project vendors the GUT addon at `addons/gut`) — this is the real test runner for a project, not the engine's own `--test`:
```
godot --headless -s res://addons/gut/gut_cmdln.gd -gexit
```
Scope with `-gdir=res://test/unit`, `-gprefix=`, `-gsuffix=`, or point at `res://.gutconfig.json`. Exit code 0 = all tests passed, 1 = a failure (pending tests don't flip it). `--test` is a different thing entirely — it runs Godot's internal C++ engine test suite and only exists on a binary compiled with `tests=yes`; it is never the right tool for testing a game project.

**Run/smoke-test a scene:**
```
godot --path <project> scene.tscn --quit-after 60
```
Add `-d` for the stdout debugger on a crash; drop `--headless` only if visual confirmation is needed.

## Other gotchas

- `--write-movie <file>` forces `--fixed-fps` — expected when recording, surprising otherwise.
- `-q`/`--quiet` silences normal stdout but errors still print — prefer it over `> /dev/null` when a failure still needs to be visible.
- `--path`, `-s`/`--script`, `--main-pack` need an "extended" build (editor, or export templates compiled with `disable_path_overrides=false`) — irrelevant when calling the editor binary itself, but relevant if scripting an already-exported release build.

## Full flag reference

Anything beyond the above — display/window flags, debug/profiling flags, the doctool/API-dump family, 3-to-4 conversion — is in [REFERENCE.md](REFERENCE.md), or just run `godot --help`.
