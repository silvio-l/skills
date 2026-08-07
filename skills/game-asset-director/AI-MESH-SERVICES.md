# AI Mesh Services (fal.ai)

Every image-to-3D and text-to-3D endpoint this skill uses, reachable through **one already-configured
fal.ai account**. Meshy, Tripo, and Rodin are separate companies with proprietary models, but all
three are hosted on fal — there is no separate signup, no second credential file, no per-vendor SDK.

## Credentials

`FAL_KEY` lives in `~/.config/fal/.env` as `FAL_KEY=<id:secret>` (chmod 600, outside any repo, and it
survives a `skills update`). Setup, billing, and the account's cost-discipline rules are documented in
`~/.claude/infrastructure/fal-ai.md` — read that file rather than duplicating it here.

Scripts read the key via `os.environ` after parsing that `.env` with the stdlib. Never hardcode a key,
never echo one into a Markdown file, never pass one as a literal CLI argument.

If `FAL_KEY` is absent, **stop and report it**. Do not substitute a procedural placeholder.

## Calling pattern

Two transports, same auth:

```bash
# synchronous — fine for fast endpoints (Trellis, Hunyuan3D turbo)
curl -X POST https://fal.run/fal-ai/trellis \
  -H "Authorization: Key $FAL_KEY" \
  -H "Content-Type: application/json" \
  -d '{"image_url": "data:image/png;base64,..."}'

# queued + webhook — use for longer jobs (Rodin HighPack, Tripo HD, Meshy v6)
curl -X POST "https://queue.fal.run/fal-ai/hyper3d/rodin?fal_webhook=https://..." \
  -H "Authorization: Key $FAL_KEY" -H "Content-Type: application/json" -d '{...}'
```

The fal.ai Python SDK (`fal_client`) is **not assumed installed** — `pip3 install fal-client` fails on
a stock Homebrew Python with PEP 668's "externally-managed-environment" error, and this skill does not
force it with `--break-system-packages`. Call the plain REST API with `requests` (stdlib-adjacent,
already available) instead of adding that dependency:

```python
import requests

HEADERS = {"Authorization": "Key %s" % FAL_KEY, "Content-Type": "application/json"}

# synchronous endpoint
resp = requests.post("https://fal.run/fal-ai/trellis", headers=HEADERS,
                      json={"image_url": "data:image/png;base64,..."})
result = resp.json()

# queued endpoint (Rodin HighPack, Tripo HD, Meshy v6): submit, then poll status_url
resp = requests.post("https://queue.fal.run/fal-ai/hyper3d/rodin", headers=HEADERS, json={
    "input_image_urls": [data_uri], "tier": "Regular", "addons": "HighPack",
})
job = resp.json()
# poll job["status_url"] until status == "COMPLETED", then GET job["response_url"]
glb_url = requests.get(job["response_url"], headers=HEADERS).json()["model_mesh"]["url"]
```

Queue jobs that outlive the agent turn should use a webhook or a stored request id; do not busy-poll
a paid endpoint in a tight loop — and never `sleep`-loop the poll inside a single tool call either,
use the harness's background-execution/notification mechanism instead of a blocking wait.

## Endpoint catalog

| Endpoint | Vendor / lineage | Price | Output | Use for |
|---|---|---|---|---|
| `fal-ai/hyper3d/rodin` | Hyper3D / Deemos, proprietary latent-diffusion transformer, 4B+ params | **$0.40**/gen; **HighPack add-on = 3× (~$1.20)** for 4K textures + high-poly | GLB / USDZ / FBX / OBJ / STL, **quad topology + PBR** | **Category B default.** Quality tiers `high`/`medium`/`low`/`extra-low`; marketed as production-ready for Unity/Unreal/Maya. |
| `tripo3d/tripo/v2.5/image-to-3d` | Tripo (VAST); TripoSR foundation was open-sourced with Stability AI, 2.5/3.0 are proprietary | $0.20 no texture / **$0.30 standard** / $0.40 HD textures; +$0.05 each for style or quad options | GLB | **Category C default** (HD textures). Cleanest topology per research; auto-size to real-world units available. `.../multiview-to-3d` takes multiple reference angles — but read "Known limitation" below before treating that as a fix for reconstruction defects. |
| `fal-ai/meshy/v6-preview/image-to-3d` | Meshy, fully proprietary (Meshy-6, GA Jan 2026) | Not published in fal's announcement blog — **read the live model page before spending** | GLB | Category B alternate where Meshy's style suits the art direction better. |
| `fal-ai/meshy/v6-preview/text-to-3d` | Meshy | as above | GLB | Text-only prompt with no reference image. Prefer image-to-3D — a controlled reference gives a controlled mesh. |
| `fal-ai/meshy/v5/multi-image-to-3d` | Meshy | as above | GLB | Several reference angles of the same subject. Only worth paying for when the angles are **genuinely independent viewpoints** — see "Known limitation" below. |
| `fal-ai/hunyuan3d/v2/turbo` | Tencent Hunyuan3D, open weights | **$0.14**/gen | GLB | Volume background filler when the user signals cost/volume over per-asset fidelity. |
| `fal-ai/trellis` | Microsoft TRELLIS, open weights | **~$0.02**/gen — cheapest | GLB | Cheapest baseline; far-background filler, throwaway blockouts, sanity-checking a reference image before paying for a flagship pass. |

Original open TripoSR is also on fal as `fal-ai/triposr` — research baseline only, not a production
route for this skill.

### Generating a reference image with no existing photo to start from

Category B/D routing assumes a reference image already exists to feed the image-to-3D endpoints
above. When there is none — a from-scratch hero asset, no source photo, no earlier pack image to
condition on — **`fal-ai/nano-banana/edit` and `fal-ai/flux-pro/kontext` cannot start the chain**: both
are edit/conditioning endpoints that require an existing `image_url`/`image_urls` input, not pure
text-to-image generators. Following this file's routing table literally in that situation blocks with
no next step.

Use **`fal-ai/flux-pro/v1.1-ultra`** instead (verified live on its fal.ai model page): $0.06/image,
prompt-only input, `aspect_ratio` parameter, no conditioning image required. Generate the from-scratch
reference with it, then hand that image to the normal Category B/C/D image-to-3D routing above.

## Choosing a tier

- **Hard-surface, procedural, or repeatable** — do not use any of these. `blender-scripting` produces
  cleaner topology and costs nothing (routing category A).
- **Organic, character, hero, unique silhouette** — Rodin + HighPack. Quad output and native PBR mean
  less retopo work downstream, which is where the real time cost sits, not the $1.20.
- **Visible but not hero** — Tripo 2.5 HD.
- **Far background, high count** — Hunyuan3D turbo or Trellis.

Raw AI mesh output is **never** shippable as-is: expect dense triangulated geometry, arbitrary UV
layout, and baked-in lighting. Everything that arrives from these endpoints goes through
[FINISHING-PIPELINE.md](FINISHING-PIPELINE.md) before it counts as an asset. *Simple* static
hard-surface subjects survive the raw output better than organic/character ones — which is exactly
backwards from where you want the quality, hence the retopo/bake step being mandatory rather than
optional. Do not extend that to ornate architecture: a hero building is static hard-surface and still
reconstructs badly, for a different reason (occlusion, not topology) — see the next section.

### Known limitation: image-to-3D cannot reconstruct geometry it never saw

This is a **structural limit of current (2026) image-to-3D technology** — not a tuning problem, not a
Blender-pipeline bug, and not a vendor worth switching away from. It is load-bearing for every AI-mesh
route in categories B and C. State it to the user up front; do not let them find it in a render.

**Evidence.** One ornate hero building (Anno-1800-style town hall: dormers, wrought-iron balconies,
clock tower, corner turret), three generations, two vendors, one defect class:

| Run | Endpoint | Result |
|---|---|---|
| 1 | `fal-ai/hyper3d/rodin`, single image, HighPack | open/hollow cavity where the dormer/roof-interior geometry belongs; warped, blob-like balconies |
| 2 | `fal-ai/hyper3d/rodin`, multi-image | same defect class |
| 3 | `fal-ai/meshy/v5/multi-image-to-3d`, native quad remesh, **zero Blender involvement** | same defect class |

Run 3 is the decisive one: a different vendor, its own quad remesher, and not a single line of this
skill's Blender code in the path — same defects. All three were confirmed by rendering the
**completely untouched raw AI mesh** before any Blender processing ran, so the defects are in the
vendors' output, not introduced downstream.

**Cause.** A reference image only constrains the surfaces it actually shows. Roof undersides, dormer
interiors, the far side of a balcony — the model invents them, and on one-off ornate architecture the
invention is visibly wrong. No quality tier, vendor, or Blender script recovers information that was
never in the input.

Two defect classes follow, with different prospects:

- **Thin, lattice-like detail reads as flat, warped blobs.** Wrought-iron balconies and railings came
  back unrecognizable even on facades directly visible in the reference. Genuinely independent extra
  viewpoints might plausibly help here — untested, see below.
- **Sealed interior volume comes back as an open cavity.** The roof interior behind the dormers, with
  torn mesh fragments and raw non-manifold edges (see FINISHING-PIPELINE.md's cleanup-pass rationale).
  **No multi-view route can fix this at any tier or price**: no external orbit camera gets inside a
  sealed roof cavity, so no set of orbit images carries the missing information. Cap it in Blender
  (SKILL.md, "Validation is necessary, not sufficient") or keep the asset out of category B entirely
  (SKILL.md's fixed-camera rule).

#### Multi-view input: what is settled, what is not

Three claims, deliberately kept apart — collapsing them either writes off multi-view or oversells it:

1. **Near-duplicate multi-image input is tested and does not fix it.** Runs 2 and 3 above. Handing a
   mesh service several images that are all close variants of one viewpoint buys nothing; the missing
   information is still missing.
2. **Genuinely independent multi-view input is untested, and plausible for the thin-lattice defect
   only.** `fal-ai/era3d` — confirmed live via
   `https://fal.ai/api/openapi/queue/openapi.json?endpoint_id=fal-ai/era3d` (HTTP 200, full schema) —
   takes a single `image_url` and returns `images[]` **and** `normal_images[]`. It is real multiview
   diffusion (arXiv 2405.11616: row-wise attention, canonical camera space), not a repaint. Its output
   feeds the consumers that actually want distinct viewpoints: `fal-ai/hunyuan3d/v2/multi-view`
   (explicit `front_image_url` / `back_image_url` / `left_image_url`),
   `tripo3d/tripo/v2.5/multiview-to-3d`, `fal-ai/meshy/v5/multi-image-to-3d`. **Nothing has been spent
   on era3d yet.** It is the concrete next experiment for closing the balcony/thin-lattice defect — not
   a documented fix — and it cannot help the sealed-cavity defect.
3. **Image-editing "rotation" is a proven dead end for producing reference views.**
   `fal-ai/nano-banana/edit` was tested for exactly that (asking an edit model to show the subject from
   another angle) and does not synthesize a genuinely new viewpoint; it repaints the view it was given,
   and the resulting
   "multi-view" set is just case 1 again. Do not use edit/conditioning endpoints to manufacture
   reference angles. They stay correct for pack consistency — see the Meshy caveat below.

### Considered and rejected: moving hero buildings to procedural generation

Tested this session so nobody re-runs it. Given the limitation above, the obvious pivot is to drop
category B for hero buildings and let category A (`blender-scripting`, procedural `bpy`) build them
instead. A crude parametric blockout of the same reference building was written and rendered from the
same camera angle as the AI-mesh renders, to test exactly that. **Verdict: no routing-table change.
Category A stays what the table says it is — procedural hard-surface: rocks, terrain, modular kits,
generic props.**

What the blockout got right is real and worth recording: massing and composition (hip roof, dormer
rhythm along the ridge, central clock tower with bell stage, corner turret, balcony rows), and it is
manifold-clean and fully rotatable **by construction** — every face is authored, nothing is
reconstructed from a photo, so the unseen-side problem does not exist at all. What it lacks is the
ornamental detail density that makes the reference AAA-grade: scrolled/stepped gable pediments,
wrought-iron lattice railings, window framing and mullions, cornice moldings, arched openings with
keystones, roof-tile texture. It reads as a generic parametric building.

The gap is not a dead end, it is an unbuilt asset. Genuine AAA ornamental detail out of procedural
rules is proven production practice — CityEngine/CGA shape grammars, used on Blade Runner 2049 and
Zootopia; Blender-native equivalents are Buildify, `building_tools`, and `bcga`/`prokitektura-blender`.
Getting there means authoring a real trim/ornament kit with parametrized gable, railing, and window
generators. That is a legitimate, scoped engineering project — **not** something a quick script
achieves, and not to be reported as done or as a cheap pivot. Until that kit exists, hero buildings
route per SKILL.md: category H when a fixed/stepped camera suffices, category B when free rotation is
genuinely required.

## Caveat: Meshy's "3D agent" is not an API feature

Meshy's conversational "3D agent", which batch-generates a visually consistent asset pack in one
session, is a **web-UI product surface**. It is *not* confirmed present in the `fal-ai/meshy/*` API
surface. Do not build automation that assumes it exists, and do not promise a user pack consistency on
that basis.

Pack consistency in this skill is achieved the scriptable way instead: generate a consistent set of
**reference images** first (`fal-ai/nano-banana/edit` or `fal-ai/flux-pro/kontext`, both already in
active use per `~/.claude/infrastructure/fal-ai.md`), then convert each image to 3D individually.
Consistency comes from the shared conditioning image, not from the mesh service. See
[SPRITE-PIPELINE.md](SPRITE-PIPELINE.md) for how the reference set is produced.

## Out of scope

- **Kaedim** — no reliable self-serve REST API, not on fal. Excluded.
- **Substance 3D Sampler, Materialize, ArmorPaint, Material Maker** — GUI-only, not headless-scriptable.
  Procedural `bpy` materials cover the no-reference-photo case (routing category E).
- **Meshy rigging/animation** — needs manual joint placement; downstream of asset generation.
- **Texture compression (ASTC/ETC2)** — an engine-side import setting, `godot-cli` territory.
