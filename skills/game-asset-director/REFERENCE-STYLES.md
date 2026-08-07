# Reference Style Profiles

Named, reusable descriptions of a concrete art direction, written so they can be **folded into a
generation prompt verbatim**. This file holds examples, not defaults. This skill is style-agnostic:
nothing here is applied unless the request actually asks for it.

**Profiles currently written up:** 19th-century European industrial and trading-town architecture.
That is one entry in an open set, not the range of styles this skill supports — cel-shaded fantasy,
clean-flat mobile casual, gritty sci-fi, whatever the next project needs, all belong here as sibling
`## Profile:` sections written to the same recipe. The mechanism is the point; the profile below is an example of it.

## What a profile is for

Every 3D route in this skill starts from a reference image, and category D starts from a whole
reference-image *set* (see [AI-MESH-SERVICES.md](AI-MESH-SERVICES.md), "Generating a reference image with
no existing photo to start from", and [SPRITE-PIPELINE.md](SPRITE-PIPELINE.md)). The quality ceiling of
everything downstream is set there — a vague reference produces a vague mesh, and no retopo, bake, or
validator pass recovers art direction that was never in the image.

An adjective is not art direction. "Historic", "old-timey", "European", "charming" give an image model
nothing to hold onto and produce generic output. A profile replaces the adjective with the specific,
checkable visual facts a prompt can carry: materials, roof shapes, ornament placement, palette, weather
state, light.

**How to apply one:**

1. Read the request for a **named or clearly implied style** ("in the style of *X*", a named period or
   look, a genre the user has established for this project).
2. If a matching profile exists here, pull **four to eight concrete cues** from it into the
   reference-image prompt — materials, roofline, ornament, palette, and lighting are usually the load
   bearing five. Copy the specifics, not the section headings.
3. If the user supplied their **own** reference images, those win. A profile is what fills the gap when
   there is a style name and no image, not a thing to layer on top of an image the user chose.
4. If nothing here matches, say so and ask for a reference image rather than inventing a profile on the
   spot from an adjective.

A profile never changes **which category a request routes to** — routing is decided by asset class and
camera behaviour in [SKILL.md](SKILL.md). It changes only what the reference image looks like, which is
why the same profile serves a 3D hero building (category B), a background prop (C), a matching pack (D),
and a 2D sprite of the same subject (H) equally well.

## Adding a profile

Derive it from reference images you have **actually looked at**, and write down only what is visible in
them. Training-data recall about "the *X* look" is exactly the failure this file exists to prevent.
Then write the result as self-contained prose: a profile must stand on its own here, with no dependence
on where the source images lived or what they were called — those move, get renamed, and get deleted.
Name the profile with the words a user would actually say when asking for it.

---

## Profile: 19th-century European industrial and trading-town architecture

The look of a late-industrial-revolution European port and factory town as rendered by a modern
city-builder: warm brick and plaster, steep slate roofs, dense but *placed* stone ornament, everything
visibly in use. Applies to houses, civic buildings, warehouses, factories, mills, and quay structures.

**Triggers:** "19th century", "industrial revolution", "Victorian industrial", "steam-era port town",
"Gilded-Age brick and ornament", trading-post or *Kontor* architecture, or a request that names a
historical city-builder look in this period. German phrasings the user actually types:
`'19. Jahrhundert'`, `'Gründerzeit'`, `'Industriezeitalter'`, `'Hafenstadt'`,
`'Dorfzentrum/Kontor/Rathaus im Stil des 19. Jahrhunderts'`.

### Massing and silhouette

Compact rectangular footprints, one to three storeys. The silhouette is carried by the **roof**, not by
a complicated floor plan: steep pitches throughout — plain gables on small houses, hipped and mansard
roofs on civic and hero buildings, with the largest ones flattening to a narrow deck at the ridge. One
strong vertical accent per hero building: a clock or bell tower, or a slim ridge turret with a bulbous
onion or steep pyramidal cap. Industrial districts add their own verticals — tall slim brick chimney
stacks, conical bottle kilns, windmill towers with wooden sail crosses and a timber gallery.

Roof furniture is a large part of the read and must be modelled, not painted: dormers in an even rhythm
along the slope, chimneys, ridge finials, small flagpoles with pennants, roof lanterns and vents.

### Roofs

Blue-grey slate and standing-seam metal on civic and industrial buildings; warm terracotta and orange
clay tile or wood shingle on housing and lower tiers; thatch on rural and farm buildings; ribbed
corrugated sheet on sheds, lean-tos and dock canopies. Oxidised copper green is reserved for the most
prestigious civic roofs and tower caps. Eaves overhang with a visible fascia or cornice band; rustic
buildings show exposed rafter ends. Tile courses and seam lines stay legible as texture at gameplay
distance.

### Walls and materials

- **Red-brown fired brick** with visible coursing — warehouses, factories, trading posts — usually paired
  with **pale limestone dressing**: corner quoins, string courses, window surrounds, portal frames.
- **Plaster and stucco** in cream, off-white, muted ochre and pale sage for civic and better residential
  buildings.
- **Half-timbering** on rustic and early-tier buildings: dark exposed frame over light infill panels,
  standing on a rubble-stone or fieldstone base course.
- **Bare timber** board-and-plank walls on mills, sheds and jetties; jetties on driven timber piles.
- **Rubble stone and cut-stone quay walls** with dressed coping; cobbled or gravel ground.

### Ornament

Dense but **placed at edges and openings**, never spread evenly over a surface — that contrast between
worked edges and plain wall is what makes it read as expensive rather than busy. The vocabulary:

- arched openings with keystones; a large arched portal with fanlight or multi-pane glazing bars on the
  main public entrance,
- stepped, scrolled or pedimented gables topped with small stone finials or obelisks,
- a carved date cartouche or a relief panel over the main door,
- pilasters or lesenes dividing a long facade into bays; cornice and string-course bands separating
  storeys,
- thin dark **wrought iron**, always in silhouette: railings, lamp brackets, hoist arms, canopy frames,
- painted hanging shop signs, striped awnings, banners on poles at civic buildings.

Budget roughly three to five distinct motifs per facade with plain wall between them. Uniformly
encrusted facades are off-style.

### Windows and doors

A regular grid rhythm of small to medium rectangular windows with pale stone lintels and sills and dark
multi-pane sashes. Tall or arched openings are reserved for the ground floor and the main entrance.
Dormers repeat the same window motif at reduced scale. Working buildings get large double-leaf timber
cargo doors and loading bays with pulley hoists; civic buildings get a framed stone portal reached by
steps.

### Palette

A warm earthy base — brick red-brown, terracotta, ochre, cream, weathered timber — against cool accents:
slate blue-grey roofs, verdigris green, dark iron. Vegetation saturated green, water teal shading to
deep blue. Saturation is moderate-to-high but grounded; no neon, no pastel wash.

### Surface state

Everything reads used. Soot streaks below chimneys, dirt wash rising up the base of walls, plaster
chipped away to show brick beneath, moss and algae at the waterline, rust on metal fittings, faded and
peeling paint. The detail level targets legibility at the game camera — visible brick coursing, tile
rows and plank lines — not photoreal micro-surface.

### Lighting mood

Bright, warm, mid-to-low sun with long soft shadows and strong shadow contrast; golden warmth on the
lit facades, cool bounce in shadow. High-key daylight, not moody or overcast.

### Context

These buildings are never presented isolated. They sit among working clutter: cobbled roads, fences,
crates, barrels and timber stacks, carts, cranes, jetties, small figures for scale. When judging an
asset in this style, build that context into the scene-context render — it is the same test SKILL.md's
"Render at the distance and lighting the asset actually ships at" requires.

### Camera implication

The style is presented from a **high, stepped isometric camera at moderate elevation**, showing the roof
and two facades at once. Two consequences for asset work in this style: the roof is a **first-class
visible surface**, so roof defects are never "hidden geometry" here; and the two facades facing the
camera carry the whole ornament budget, while the far sides can be simplified.
