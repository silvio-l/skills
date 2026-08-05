# Post-production: polish and export

The raw take from any branch is a flat, full-frame, real-time recording. Free tooling gets most of the way to a Screen-Studio-style polished look, but the automatic-zoom step is GUI-only, not CLI-scriptable — say so plainly rather than pretending it's a one-liner.

## Auto-zoom / cursor-highlight polish (GUI step)

- [OpenScreen](https://github.com/siddharthvaddem/openscreen) — free, open-source (MIT), Swift, macOS/Windows/Linux; auto-zoom, real cursor tracking and click effects, AI-assisted editing via MCP. Closest free equivalent to Screen Studio.
- DaVinci Resolve (free tier) — for hand-keyframed pan/zoom, callouts, music timing, and device-frame compositing when a shot needs more control than auto-zoom gives.

If the deliverable doesn't need that look (e.g. a plain feature-walkthrough GIF), skip this step and go straight to export.

## Scriptable fallback: ffmpeg

A fixed push-in on an existing video (not a still image) needs `d=1` — apply the zoom expression per source frame rather than holding it for a fixed frame count — and an explicit `fps` matching the source, or the output stutters:

```bash
ffmpeg -i raw.mov -vf "scale=3840:-2,zoompan=z='min(zoom+0.0008,1.3)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':fps=30:s=1920x1080" -c:v libx264 -crf 18 zoomed.mp4
```

Scaling up before `zoompan` (here to 3840 wide) gives the filter headroom to zoom into without visible upscaling artifacts.

Crop/scale to the target aspect ratio, and composite a device bezel PNG if the deliverable is an App Store preview:

```bash
ffmpeg -i raw.mov -i bezel.png -filter_complex "[0:v]scale=1170:2532[app];[1:v][app]overlay=45:60" -c:v libx264 -crf 18 framed.mp4
```

## Export: MP4

```bash
ffmpeg -i polished.mov -vf "scale=1920:-2" -c:v libx264 -crf 18 -pix_fmt yuv420p demo.mp4
```

## Web delivery: `<video>`, not GIF, for anything substantial

A GIF re-encodes every frame as a palette image with essentially no inter-frame compression; a silent, autoplaying `<video>` of the same clip is typically several times smaller at equal or better quality. Reserve GIF/WebP for a platform that specifically requires a static-image-style embed (chat previews, some CMS fields) — everywhere else, ship video:

```html
<video autoplay muted loop playsinline poster="demo-poster.jpg" preload="none"></video>
```

- `muted` + `playsinline` are required for autoplay to actually run on mobile Safari/Chrome.
- Ship WebM (VP9) as the primary source with MP4 (H.264) as the fallback — WebM usually runs 30–50% smaller at the same visual quality.
- `preload="none"` plus lazy-mounting the element (only once it's near the viewport) keeps an off-screen clip from costing bandwidth nobody asked for.
- Strip the audio track entirely (`-an`) — a silent autoplaying clip needs no audio stream.
- Respect `prefers-reduced-motion`: swap in the poster frame, or a much slower non-autoplaying cut, for users who've asked for less motion.
- The clip is never the only carrier of what it shows: the benefit it demonstrates needs to exist as real, visible page text near the embed too, for anyone who never sees it play. This isn't opt-in the way burned-in captions are — it's a standing requirement, independent of whether the video itself carries any text.

```bash
ffmpeg -i polished.mov -an -c:v libvpx-vp9 -b:v 0 -crf 32 -pix_fmt yuv420p demo.webm
ffmpeg -i polished.mov -an -vf "scale=1920:-2" -c:v libx264 -crf 18 -pix_fmt yuv420p demo.mp4
```

Burned-in on-screen text — captions, callouts, an animated headline inside the frame — is a separate, opt-in decision from the clip itself; per `SKILL.md` step 4, add it only if actually requested, and default to a clean, text-free clip otherwise. That's independent of the page-text requirement above: a silent clip with zero burned-in text still needs its benefit stated in real text nearby.

## Export: GIF

Keep clips under ~10s, 15–20 fps, width 480–720px — beyond that, GIF file size balloons for no perceptible quality gain. Two good paths:

```bash
# ffmpeg two-pass palette (fine-grained control, smaller files)
ffmpeg -i demo.mp4 -vf "fps=18,scale=640:-1:flags=lanczos,palettegen" palette.png
ffmpeg -i demo.mp4 -i palette.png -filter_complex "fps=18,scale=640:-1:flags=lanczos[x];[x][1:v]paletteuse" out.gif
gifsicle -O3 out.gif -o out.gif   # further-optimize, in place

# gifski (best color quality; it doesn't read mp4 directly, so pipe raw frames in via ffmpeg)
ffmpeg -i demo.mp4 -vf "fps=18,scale=640:-1:flags=lanczos" -f yuv4mpegpipe - | gifski -o out.gif --fps 18 -
```

## Export: animated WebP

Prefer this over GIF for a website/store listing where the platform accepts it — typically 4–6x smaller at equal or better quality:

```bash
ffmpeg -i demo.mp4 -vcodec libwebp -filter:v fps=20 -loop 0 -q:v 60 -preset default -an out.webp
```

## Export: App Store / Play Store preview video

Apple's App Preview spec (verify current numbers in App Store Connect before a real submission — these drift):

- Resolution: 886×1920 or 1920×886 for current iPhones; 1200×1600 or 1600×1200 for 13"/11" iPad.
- H.264 High Profile, level ≤ 4.0, constant 30 fps, `yuv420p`, `.mp4` with the faststart flag; ProRes 422 HQ `.mov` also accepted.
- Duration 15–30s; file size under 500 MB (aim under 100 MB for a faster upload).

```bash
ffmpeg -i polished.mov -vf "scale=886:1920" -r 30 -c:v libx264 -profile:v high -level 4.0 \
  -pix_fmt yuv420p -movflags +faststart -an appstore-preview.mp4
```

Play Store listing video specs (length, aspect ratio) change on a similar cadence — check the current Play Console help before finalizing rather than trusting a remembered number.

## Verify (step 4's completion criterion)

Don't trust a zero exit code alone — confirm the file actually opens at the target spec:

```bash
ffprobe -v error -show_entries stream=width,height,codec_name -show_entries format=duration out.mp4
gifsicle --info out.gif   # frame count, dimensions, size
```
