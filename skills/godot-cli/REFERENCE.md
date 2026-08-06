# Godot CLI — Extended Flag Reference

Covers flags beyond SKILL.md's core workflows. `godot --help` always has the authoritative, version-matched list — prefer it over this file when in doubt.

## General

- `-h`/`--help` — list all options. `--version` — print version string.
- `-v`/`--verbose`, `-q`/`--quiet` — more/less stdout (errors always print).
- `--no-header` — suppress the version/renderer banner on startup.

## Run options

- `-e`/`--editor` — open the editor instead of running the project.
- `-p`/`--project-manager` — force the Project Manager even if a project is auto-detected.
- `--main-pack <file.pck>` — load a specific pack instead of the project directory.
- `--scene <path-or-uid>` — start a specific scene.
- `--quit` / `--quit-after <n>` — quit after the first iteration / after N iterations (0 disables).
- `-l`/`--language <locale>` — force a locale.
- `--render-thread <unsafe|safe|separate>`, `--audio-driver`, `--display-driver`, `--rendering-method <forward_plus|mobile|gl_compatibility>`, `--rendering-driver`, `--gpu-index` — override rendering/audio backends; `--help` lists what's available on the current machine.
- `--remote-fs <host[:port]>` + `--remote-fs-password` — remote filesystem mode.
- `--log-file <path>` — redirect stdout/stderr log to a file.

## Display

- `-f`/`--fullscreen`, `-m`/`--maximized`, `-w`/`--windowed`, `-t`/`--always-on-top`.
- `--resolution <W>x<H>`, `--position <X>,<Y>`, `--screen <N>`, `--single-window`.
- `--xr-mode <default|off|on>`.

## Debug

- `-d`/`--debug` — local stdout debugger (works with a scene or a script).
- `-b`/`--breakpoints <file::line,...>` (URL-encode spaces as `%20`).
- `--debug-collisions`, `--debug-paths`, `--debug-navigation`, `--debug-avoidance` — visual debug overlays.
- `--debug-canvas-item-redraw` — flash a rect on every canvas-item redraw (low-processor-mode troubleshooting).
- `--profiling`, `--gpu-profile`, `--gpu-validation` — profiling/validation layers.
- `--max-fps <n>`, `--fixed-fps <n>`, `--time-scale <n>`, `--frame-delay <ms>`, `--disable-vsync`, `--print-fps` — timing controls; `--frame-delay` simulates CPU load, it is not an FPS limiter (use `--max-fps`).
- `--disable-render-loop`, `--single-threaded-scene`.
- `--remote-debug <protocol://host[:port]>`, `--dap-port <n>`, `--lsp-port <n>` — remote/IDE debugger and language-server ports.

## Standalone tools (editor build required)

- `--import` — import assets, then quit (implies `--editor --quit`).
- `--export-release <preset> <path>` / `--export-debug <preset> <path>` / `--export-pack <preset> <path>` / `--export-patch <preset> <path>` — see SKILL.md for the import-order gotcha.
- `--patches <paths>` — comma-separated patch list for `--export-patch`.
- `--install-android-build-template` — install the Android build template before an Android export.
- `--convert-3to4 [<max_kb>] [<max_line>]` / `--validate-conversion-3to4 [...]` — Godot 3→4 project migration/dry-run.
- `--doctool [<path>]` [`--no-docbase`] — dump the engine API reference as XML.
- `--gdextension-docs` / `--gdscript-docs <path>` — generate API docs from loaded GDExtensions / from a GDScript source tree (used with `--doctool`).
- `--dump-gdextension-interface[-json]`, `--dump-extension-api[-with-docs]`, `--validate-extension-api <path>` — GDExtension binding generation/compatibility checks.
- `--build-solutions` — build C# scripting solutions (implies `--editor`, needs a valid project).
- `--benchmark` / `--benchmark-file <path>` — print or save startup/run timing.
- `--test [--help]` — the engine's own internal C++ unit tests; only works on a binary built with `tests=yes`. Not for testing a game project — use GUT (see SKILL.md).

## Setting the project path

Any command above accepts either a leading `project.godot` path, `--path <dir>`, or (from a subdirectory) `--upwards` to search parent directories automatically.
