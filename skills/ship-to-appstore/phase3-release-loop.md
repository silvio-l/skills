# Phase 3 — Guided Release Loop

> **Stub — implemented in slice 04.**

This phase is the interactive, step-by-step guided release loop — grill-me style
for release steps. It combines the Phase 0 situation report, Phase 1 freshness
research, and Phase 2 ASC status into a prioritized release checklist, then walks
the user through each step with a feedback loop:

1. Present the next release step with a clear explanation.
2. Wait for the user's response: "done", "stuck here", "skip", or a question.
3. On "done": mark the step complete, present the next one.
4. On "stuck here": dig into the specific blocker, provide targeted guidance.
5. On a question: answer it inline, then return to the current step.
6. Never advance past a blocker without the user's explicit sign-off.

Planned release checklist (order may vary based on ASC state):
- Version bump (marketing version + build number)
- Certificate and provisioning profile validity
- flutter build ipa (Archive build)
- Upload to ASC (via Xcode Organizer or altool/notarytool)
- TestFlight internal testing
- App metadata completeness (screenshots, description, keywords, support URL)
- Privacy nutrition labels
- Age rating questionnaire
- Export Compliance / encryption declaration
- Submit for Review
- Phased Release configuration

Slice 04 will implement this phase in full.
