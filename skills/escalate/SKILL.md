---
name: escalate
description: Escalate the task to a stronger subagent (opus/fable) via the Agent tool when its stakes or difficulty exceed Sonnet's default: UI work, a stuck bug, hard reasoning, security-sensitive changes. Say 'escalate this' / 'eskaliere das'.
---

# Escalate

Route the task to whichever model tier its difficulty or stakes actually need, and hand it off through the Agent tool — instead of grinding on it at the current tier hoping quality will catch up.

## Step 1: Pin down the task

If the skill was invoked with an argument, that argument is the task. Otherwise it's the task on the table right now — the request the user just made, or the step currently being worked on. State it back in one sentence before continuing; if it doesn't compress to one sentence, split it into the parts that do and route each separately in Step 2.

## Step 2: Match it against the escalation table

| Signal | Target | Why |
|---|---|---|
| Any UI, component, layout, animation, or motion work — including a "trivial" addition to an existing component (new row interaction, swipe action, badge) | `fable` | mandatory design escalation |
| Architecture or roadmap/ticket synthesis (not a `/code-review` or security audit — those skills already self-escalate to opus and own their own routing) | `opus` | mandatory planning/review escalation |
| Hard algorithmic or multi-step logical reasoning where a wrong step compounds silently | `opus` | correctness depends on reasoning depth Sonnet doesn't reliably reach |
| A bug or diagnosis that has already resisted one or more straightforward Sonnet attempts | `opus` | a stuck problem needs a different reasoning path, not another pass at the same one |
| High-stakes, hard-to-reverse correctness (data migrations, auth/security-sensitive code, financial or legal-adjacent logic) | `opus` | the cost of a wrong answer outweighs Sonnet's speed |
| Everything else — routine implementation, backend/business logic, tests, config, mechanical edits | *(none)* | Sonnet is the mandated default; escalating it is waste |

If two rows match at once (e.g. a settings screen that's also architecturally gnarly), split the task and dispatch each part to its own row's tier rather than forcing one subagent to cover both.

## Step 3: No match → say so and stop

If the task lands only in the last row, escalation would burn tokens for no quality gain. State in one line that this stays on Sonnet, then continue working normally — don't invoke Agent.

## Step 4: Dispatch

Call `Agent` with `model` set explicitly to the matched tier (`opus` or `fable` — never a full model ID). Default to the subagent doing the work itself, not just advising — that's how the design and planning escalation rules already operate. Write the prompt as a self-contained brief: the goal, the relevant file paths and context, and what's already been ruled out — the subagent has not seen this conversation. Never write "based on the above, do X"; that pushes synthesis already done here onto a subagent that can't see it. Never set `isolation: "worktree"`. If the task calls for a recommendation to act on rather than a finished change, say so explicitly in the brief and ask for a report instead.

## Step 5: Relay

Read back what the subagent actually changed or found before reporting it — its summary describes intent, not necessarily the result. Tell the user which tier handled the task, why, and what changed; the escalation should be visible, not silent.
