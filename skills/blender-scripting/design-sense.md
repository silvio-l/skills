# Design Sense

Read this before generating new geometry whose *appearance* matters — a building, prop, tree, rock, or terrain. Skip it for export, inspection, or debugging tasks. Procedural doesn't mean random: every principle below has a concrete `bpy` consequence, not just an aesthetic preference.

**Silhouette first.** ~70% of a form's read comes from its outline, not surface detail — check the shape as a flat black shape before adding a single bevel. Consequence: block out primary volumes with primitives/booleans and evaluate the silhouette *before* touching modifiers, materials, or scatter.

**Shape language carries meaning.** Square/rectangular = stable, heavy, industrial. Triangular = dynamic, dangerous, sharp. Circular/organic = soft, harmless, natural. Consequence: pick the dominant primitive deliberately — a "menacing" tower needs triangular accents, not just height.

**Form hierarchy: primary → secondary → tertiary.** Big masses first (they carry the design and must work alone), then secondary breakup (windows, panel seams, branch splits), then tertiary detail last (bolts, bark texture, moss). Consequence: order your script the same way — block volumes, then Boolean/Array breakup, then noise/detail modifiers, never the reverse. Never add tertiary detail to fix a primary silhouette that doesn't read.

**Trees grow toward light, not randomly.** Real branching follows apical dominance (the growing tip suppresses nearby lateral buds; suppression weakens with distance) and phototropism (growth biases toward open space/light). Consequence: weight branch angle and count by a decreasing function of distance from the tip, and bias new growth direction away from existing branches — not `random.uniform()` on angle. The Space Colonization Algorithm (Runions, Lane, Prusinkiewicz 2007) models this properly via attractor points and kill/influence radii; see [techniques.md](techniques.md) for what's actually shipped as tested code here vs. described only.

**Rock and terrain shape follows geology, not noise alone.** Igneous rock (granite) fractures into sharp crystalline facets; sedimentary rock shows flat layering and cross-bedding with chipped edges; erosion adds smoothing and material loss as a *second* deliberate pass, not just baked into the first noise layer. Consequence: pick a noise/Voronoi combination and displacement strength that matches the named rock type, and consider a second lower-frequency pass to fake weathering — don't apply one generic Voronoi-noise displacement to every rock regardless of type.

**Sizes follow a power law, not a uniform distribution.** Nature has few large objects and many small ones (boulders, branches, leaves, debris) — never a flat `random.uniform(min, max)`. Consequence: sample scatter/instance sizes from a power-law or exponential-like distribution (e.g. `min_size / random.random()**exponent`, clamped), not linear uniform random.

**Self-similarity is real but bounded.** Natural fractality holds only over a finite scale range — a rock face has facets-on-facets for 2-3 octaves of detail, not infinitely. Consequence: cap recursive/fractal detail generation (branching depth, noise octaves) at a level tied to the object's actual on-screen scale; more octaves past that point is wasted computation, not more realism.

**Repetition is the real "uncanny valley" of procedural generation** — not randomness. Players/viewers notice sameness fast; the fix is purposeful variation at the points that get noticed (silhouette breaks, damage, color) plus tight upfront constraints, not maximizing randomness everywhere. Consequence: vary the parameters that are visually prominent (overall shape, major breakup) more than the ones that aren't (minor vertex jitter); constrain the random ranges tightly enough that every output still reads as "the same kind of thing."

**Architecture needs a proportion system before placement.** Golden ratio (1:1.618) for facade/window proportions, Le Corbusier's Modulor (proportions tied to human scale), or a modular grid (e.g. the Japanese ken, ≈1.82m) — pick one baseline *before* placing walls/windows/floors, and keep structural elements statically plausible (load-bearing mass thick and low, not cantilevered without visible support). Consequence: compute a proportion/grid constant first, then derive wall/window/floor positions from it parametrically, rather than placing elements at arbitrary literal coordinates.

**Detail should imply history, not decorate arbitrarily.** Wear marks, stains, patched repairs, and asymmetric clutter should suggest function and time passing — a door gets scuffed near the handle height, not randomly on its face. Consequence: place "storytelling" detail (dirt, damage, moss, patches) using positional logic tied to function (handle height, water runoff paths, foot traffic) rather than uniform random placement across the whole surface.

## Sources

- worldofleveldesign.com — Silhouette Design in Game Environments
- 80.lv — "Defining Environment Language for Video Games"
- rocketbrush.com / pixune.com — shape-language guides for character/environment design
- Blender Bros — "Hard Surface Visual Design Principles"
- Runions, Lane, Prusinkiewicz (2007), algorithmicbotany.org — "Modeling Trees with a Space Colonization Algorithm"
- tripo3d.ai — procedural rock modeling guide (geological vocabulary)
- Houdini community references — Voronoi F2-F1 noise for rock facets, multi-resolution displacement
- gamedeveloper.com — "Devs weigh in on best ways to use (but not abuse) procedural generation"; "The Uncanny Narrative Valley"
- Le Corbusier, *Le Modulor* (1948) — architectural proportion system
- Worch & Smith, GDC 2010 — "What Happened Here? Environmental Storytelling"; Bellard, GDC 2021 — "Environment Design as Visual Storytelling"
