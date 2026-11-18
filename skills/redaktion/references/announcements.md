# Release announcements, newsletters and milestones

An announcement is still an explainer: the reader wants to know what is different for them, whether to update, and what to watch out for. Pride is welcome. It convinces when it is carried by facts the reader can check, and it stops convincing at the second superlative.

## Structure that works

1. **The news in the first two sentences.** What was released, for whom, and the one change most readers will notice. "Version 1.5 is out" plus the change, not a run-up.
2. **Why it took what it took.** One short paragraph of backstory when it helps the reader understand the scale or a decision (time spent, what was rebuilt, what was learned). Skip it for routine releases.
3. **What changes for the reader,** ordered by how many people notice it, each as a situation: before / now. Group many small items into one sentence or link the changelog; do not list 30 bullets in the post.
4. **What does not work yet / what changed in a way people may not like.** Known issues, removed features, new requirements (OS versions, prices). Plainly and early enough to be read.
5. **How to get it** (automatic update, download link, store), and where to send feedback.
6. **Thanks**, specific: who reported what, who tested, how many people contributed. A named, concrete thank-you reads as human; "thanks to our amazing community" does not.

A newsletter follows the same order in miniature: one personal paragraph on what happened and why it matters, then the items.

## Sounding proud without hype

- **Let one fact carry the pride.** Pick the single most telling measure of size or effort and state it with its basis: number of changes merged, months of work, platforms now supported, the first time something was possible. "The largest update so far" is fine once, if that number backs it.
- **One superlative per text, at most,** and only when it is measurably true. Never stack them ("biggest, fastest, most powerful"). Never "revolutionary", "game-changer", "next level".
- **Name the milestone as a step, not a summit.** "The next big step" plus what it makes possible next is confident; "a new era" is not checkable.
- **Show effort with specifics, not adjectives.** "We rewrote the audio pipeline, which is why this took four months" beats "countless hours of hard work".
- **Own the excitement in first person,** once and briefly: "We are really happy with how this turned out" or "Wir sind ziemlich stolz auf diese Version" is honest; exclamation marks and capitalised words are not needed for it.
- **Be honest about the cost.** A milestone release that also raises system requirements or drops a feature says so in the same calm tone. Pride that hides the downside reads as marketing.
- **Do not compare with competitors** unless the comparison is measured, sourced and fair.

## Before and after

The sentences are written for this file; the product details are invented.

| Discard | Prefer |
|---|---|
| „Heute ist ein historischer Tag: Mit Version 2.0 erscheint unser größtes, schnellstes und bestes Update aller Zeiten!“ | „Version 2.0 ist da. Es ist das größte Update bisher: 180 Änderungen aus vier Monaten, und die wichtigste merkst du beim ersten Diktat.“ |
| „Wir sind unglaublich stolz und können es kaum erwarten, dass ihr es ausprobiert!!“ | „Wir sind ziemlich stolz auf diese Version. Am meisten auf eine Kleinigkeit: …“ |
| „Ein Meilenstein, der alles verändert.“ | „Für uns ist das der nächste große Schritt: Zum ersten Mal läuft die App auf allen drei Systemen mit demselben Funktionsumfang.“ |
| "This release takes everything to the next level." | "This is the biggest release so far: 180 changes over four months. Here is what you will notice first." |
| "A huge thank you to our amazing community!" | "Thanks to everyone who sent crash reports from Linux in October; most fixes in this release started there." |

## Checklist before publishing

- Version number, date, platforms, requirements and prices match the release notes and the store or download page.
- Every claimed feature is in the shipped build (not only merged to a branch, not only planned).
- The known-issues paragraph exists if there are known issues.
- Exactly zero or one superlative, and it is backed by a stated number.
- The link to download or update works.
