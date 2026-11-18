# Editorial taste for blog posts, newsletters, announcements and explainers

## The job

Someone gives this text a few minutes of attention because they want to understand something: what changed, how a thing works, why it matters to them. Repay that. One clear thought per piece, explained with real things, by an author who is present and honest about what they know.

The principles below come from reading long-running, human-written blogs and essays from before generative text (sources and dates in the repo's origins doc, not shipped). The observations are paraphrased; the example sentences are written for this file.

## How this differs from landing-page copy

The `website-creator` taste is written for a visitor who is deciding (download, buy, sign up) and scans. This one is for a reader who has already decided to read.

| | Landing page | Blog / explainer / announcement |
|---|---|---|
| Reader's goal | decide quickly | understand, then maybe act |
| Length | 60–80 words per screen, paragraphs under ~70 words | as long as the thought needs; paragraphs up to ~120 words, varied |
| Voice | the brand | a person (or a small team) with a name, first person allowed |
| Headings | carry the whole page when skimmed | signposts; short pieces may have none |
| Evidence | a screenshot or demo per claim | the same, plus numbers with their conditions, links, admitted limits |
| Ending | a CTA that names the click | the last real point, a next step, or an open question |

Shared with it and still binding: concrete detail over benefit adjectives, one name for one thing, every claim checkable, no slogan pairs, no rhetorical-question chains, read it aloud.

## Principles

1. **Open with the thing, not the world.** Good openings start at the subject: a claim the piece will defend, the question a reader actually asked, an everyday situation that contains the problem, or a common misconception the piece will take apart. They never start with how fast the world changes or how important the topic is. Within two or three sentences the reader knows what this is about and why they might care.
2. **Say why you are writing.** "Several people asked me how X works" or "this release took four months, here is what changed" gives the reader a reason and sets the scale. One sentence is enough.
3. **Example before abstraction.** Show one concrete case (a real command and its output, a specific file, a familiar situation) and then name the general idea. A definition without an example is rarely understood; an example without the name is rarely remembered.
4. **One strong analogy, carried through.** A single well-chosen picture that the text keeps using does more than three decorative comparisons. If an analogy needs a paragraph of caveats, drop it.
5. **Translate numbers into scale.** Give the number with its unit and conditions, then one translation the reader can feel (per day, in seconds on a normal laptop, compared with something familiar). Say where it comes from.
6. **The author is present.** First person is fine and often better: what you tried, what surprised you, what you still do not know. Address the reader directly ("du", "you") when you give them something to do; describe in third person when you describe.
7. **State uncertainty once, plainly.** "Probably", "as far as I know", "this is simplified; the real mechanism has one more step" in the place it applies. Do not hedge every sentence, and do not sound certain where you are not. Name what the piece deliberately leaves out.
8. **Rhythm follows the thought.** Mostly medium sentences; a long one when a thought has parts that belong together; a short one after a build-up to land it. Variation is the result, never the goal. A paragraph of uniformly short punchy sentences reads as generated, so does one of uniformly long ones.
9. **Headings are signposts.** Use them when the piece has parts a reader might skip to; phrase them as the topic or the reader's question in plain words. Essays of a few screens can do without. Never "Einleitung", "Fazit", "Key takeaways".
10. **Asides go to the side.** Tangents, caveats and jokes that would break the line of thought go into parentheses, a footnote or a short separate paragraph, so the main line stays easy to follow.
11. **Humour comes from specifics.** Dry, self-directed, rare. A precise detail that is funny on its own beats any pun. No jokes in headings, no forced lightness in serious topics.
12. **End when you are done.** Return to the opening idea in a compressed or sharpened form, give the next concrete step, or leave the honest open question. No summary paragraph, no "the future is now".
13. **Prose over formatting.** Lists for real lists (steps, items to compare); prose for reasoning. No bold-label bullet stacks, no emoji bullets, no bold sprinkled over every second phrase.
14. **Same thing, same word.** Use the product's and the field's actual terms consistently; explain a technical term once when the reader needs it, then keep it.

## What generated text does (and these pieces did not)

Stock openers and closers; "not only X but also Y" and "it's not X, it's Y" frames over and over; staged reveals ("The result?"); three-item lists everywhere; superlative chains; vague benefit words in clusters; additive connectors starting consecutive sentences ("Darüber hinaus … Zudem …"); em dashes as all-purpose glue; a closing summary that repeats the headings; fake enthusiasm with exclamation marks. `scripts/prose_lint.py` flags these. Absence of these tells does not make a text good; the principles above do.

## Before and after (German)

The sentences in both tables are written for this file. Their numbers and product details are invented: they illustrate a decision, never a fact to reuse.

| Verwerfen | Bevorzugen | Grund |
|---|---|---|
| „In der heutigen digitalen Welt wird Datenschutz immer wichtiger.“ | „Wenn du eine Sprachnotiz diktierst, wohin geht dann eigentlich deine Stimme?“ | Steigt bei der Frage ein, die der Leser wirklich hat. |
| „Die neue Version ist nicht nur schneller, sondern auch zuverlässiger.“ | „Der Text erscheint jetzt, während du sprichst. Und wenn das WLAN wegbricht, geht nichts mehr verloren.“ | Zwei konkrete Veränderungen statt einer Kontrastformel. |
| „Das Ergebnis? Eine deutlich verbesserte Performance.“ | „Auf einem drei Jahre alten Laptop startet die App jetzt in zwei statt fünf Sekunden.“ | Zahl mit Bedingung statt inszenierter Pointe. |
| „Darüber hinaus wurde die Benutzeroberfläche optimiert.“ | „Die Einstellungen liegen jetzt auf einer Seite. Du musst nicht mehr suchen, wo die Sprache umgestellt wird.“ | Handlung und Folge statt Verwaltungsverb. |
| „Zusammenfassend lässt sich sagen, dass Version 2 ein Meilenstein ist.“ | „Das Update kommt in den nächsten Tagen automatisch. Wenn dir etwas fehlt, schreib uns.“ | Endet mit dem nächsten Schritt. |
| „Die Gezeiten entstehen, weil der Mond das Wasser anzieht.“ (falsch vereinfacht) | „Die naheliegende Erklärung ist, dass der Mond das Wasser zu sich zieht. Dann gäbe es aber nur einen Flutberg, nicht zwei.“ | Fehlvorstellung zuerst, dann der Widerspruch, der neugierig macht. |

## Before and after (English)

| Discard | Prefer | Why |
|---|---|---|
| "In today's fast-paced world, productivity is more important than ever." | "Last month three people asked me the same question: why does my laptop fan spin up when I'm only typing?" | Starts at a real question. |
| "This isn't just an update — it's a whole new experience." | "You can now edit the transcript before it's pasted. That was the most requested change in the feedback form." | Names the change and its source. |
| "Here's the thing: caching is crucial." | "The resolver usually already knows the answer, because someone asked a minute ago. That's the cache." | Example first, then the term. |
| "It's incredibly fast, massively improved and truly groundbreaking." | "Transcribing a ten-minute recording now takes about 40 seconds on an M2 MacBook Air, down from 90." | One measured claim instead of three adjectives. |
| "In conclusion, the future of note-taking is bright." | "I still don't know why the first run is slower on Linux. If you do, I'd like to hear it." | Ends on an honest open question. |

## Deutsch

- **Anrede** wie die Publikation. Ohne Vorgabe: Blog und Newsletter eines kleinen Teams duzen, Fachpublikum und Behördenkontext siezen. Innerhalb eines Textes nie wechseln.
- **Gedankenstrich** ist im Deutschen der Halbgeviertstrich mit Leerzeichen („ – “), sparsam. Der englische Geviertstrich ohne Leerzeichen („—“) wirkt im deutschen Text fremd. Lange, gut gebaute Sätze mit Nebensätzen sind im Deutschen normal und kein Fehler; die Grenze ist der Atem beim Vorlesen.
- **Verben statt Substantivketten.** „Wir haben die Synchronisierung beschleunigt“ statt „Es erfolgte eine Beschleunigung der Synchronisierung“. Genitivketten auflösen.
- **Lehnübersetzungen meiden**, die im Deutschen nach Werbetext klingen: nahtlos, ganzheitlich, Ökosystem, Landschaft (für Markt), Mehrwert schaffen, auf das nächste Level heben, eintauchen, Reise (für Prozess).
- **Anführungszeichen** „so“, Zahlen mit Punkt als Tausendertrenner und Komma als Dezimalzeichen (3.000 Nutzer, 2,5 Sekunden), Datumsangaben ausgeschrieben oder „16. November 2026“.
- **Gendern** wie die Publikation (Doppelpunkt, Paarform oder neutrale Form); ohne Vorgabe neutrale Formulierungen bevorzugen („wer diktiert“ statt „Nutzer“).
- **Floskeln**, die nichts tragen: „Es bleibt spannend“, „Man darf gespannt sein“, „Last but not least“, „In diesem Sinne“, „Am Ende des Tages“. Streichen; meist steht davor schon der richtige Schlusssatz.
- **Überschriften** im Satzstil und ohne Ausrufezeichen: „Was sich beim Diktieren ändert“ statt „Diktieren neu gedacht!“.

## English

- **Plain, spoken English.** Contractions are fine. Prefer the short Germanic word when it is as precise ("use", "help", "start", "show").
- **Avoid the generated vocabulary** even when each word is harmless alone: delve, tapestry, testament, landscape, realm, robust, seamless, crucial, pivotal, elevate, unlock, journey, game-changer.
- **Dashes:** an em dash now and then is normal English; several per paragraph is a tell. Commas, parentheses or a new sentence usually work better.
- **Headings:** sentence case unless the venue uses title case; no colons-with-subtitle on every heading.
- **One spelling convention** (US or UK) per text, following the venue.

## Genres in one line each

- **Blog post / essay:** one claim or question, defended or answered with examples; the author's view is welcome and marked as such.
- **Explainer:** start from the reader's question or misconception, build from a concrete case, introduce terms only when needed, say what is simplified.
- **Newsletter:** a short personal note on what happened and why it matters to the reader, then the items; each item gets one concrete sentence, not a teaser.
- **Release announcement / milestone:** see `references/announcements.md`.

## Grow this file with real decisions

When the maintainer edits a text produced with this skill, keep only edits that reveal taste: original, approved version, reason, scope. A local decision becomes a rule here only when it holds for other texts too.
