---
name: inference-tracing
description: Traces where another Claude Code session's wall clock went — model inference, tools, waiting on the human — from its transcripts on disk, and publishes the findings as a timing report that ends in proposals to shorten the run. Use when the user asks why a session or an agentic run is taking so long, or wants that report refreshed while the run continues. Takes a session name, a session id, or a transcript path. Not for the session it is invoked in, not for token or cost accounting, and never a way to steer the analyzed session.
argument-hint: "[session-name | session-id | transcript-path]"
disable-model-invocation: true
---

# Inference Tracing

## Overview

A session that takes hours leaves its whole timeline on disk: every model response, tool call, and incoming message is a timestamped transcript row. This skill reads those rows, attributes every gap to what the session was waiting on, and reports it as one page. The sections of that page are the same for every run — `report-template.md` says what each must answer — and the proposals at its end are written for this run. The analyzed session is never touched: the report is made from files, not from questions.

## When to Use

- The user invokes it with a target: `$ARGUMENTS` is a session name, a session id, or a transcript path.
- Invoked again on the same target: refresh — see Refreshing.
- No argument: list the live sessions (step 1) and ask which one; never guess.
- Not for the session this skill runs in, and not for a question the user wants put to the other session — that is a message, and this skill sends none.

## The Trace

```text
target → clocks → measure → most relevant activities → loop check → not the problem → proposals → page → publish
```

**Read-only, throughout.** Never message, interrupt, or write to the analyzed session, its worktree, or its transcripts. Plan facts — how many units of work, what each one is — come from the transcripts, never from another session's `.claude/specs/<slug>/`. Reading the project's tracked files and the skill and agent definitions that drove the run is part of the work.

1. **Target.** Resolve `$ARGUMENTS` to the main transcript, the one the run under analysis is in.
   - A live session by name: `jq -r '[.name, .sessionId, .pid, .cwd, .startedAt] | @tsv' ~/.claude/sessions/*.json`.
   - A session id: `ls ~/.claude/projects/*/<id>.jsonl`. The project directory is the session's working directory with every `/` and `.` written as `-`.
   - Its subagents sit beside it in `<id>/subagents/`: `agent-<x>.jsonl` is the transcript, `agent-<x>.meta.json` holds its `agentType` and `description`.
   - Earlier transcripts of the same process: `/clear` starts a new transcript, and a session that entered a worktree continues under the worktree's project directory. List both project directories by modification time; an earlier transcript ends seconds before the next one begins. They are part of the session's wall clock.
2. **Clocks.** Before any other number, establish three and report all of them:
   - when the session opened: `ps -o lstart= -p <pid>`, next to the first row of the earliest transcript;
   - when the run under analysis started: the prompt or command that began it;
   - the snapshot: the last row read.

   Transcript timestamps are UTC; every time in the report is local, with the zone named.
3. **Measure.** Apply the rules in Reading the Transcripts to the main transcript and every subagent transcript, and compute what `${CLAUDE_SKILL_DIR}/report-template.md` asks for, section by section. Read that file now: it is the list of what to find. Whatever queries or scratch code this takes are working material in this session's scratchpad, never a deliverable.
4. **Most relevant activities.** Find what dominates the wall clock besides inference. It differs per run: a test suite, a build, a dependency install, CI polling, a wait loop, web fetches, scripts the agents wrote, or waiting on the human. Rank tool time by what the command does, then for the top one or two:
   - quantify: runs, median duration, total, who ran them, how often per unit of work, and how many repeated the same command on unchanged code;
   - explain: read the skill and agent definitions that drove the run, the brief each agent received (the first row of its transcript), and the project's own configuration, and quote the line that prescribes the behaviour.
5. **Loop check.** Compare what the run did with the definitions that drove it: the order of steps, who does what, when a unit settles. List each deviation with its transcript evidence — the time and the quoted row — and what it cost. A cost the definitions prescribe is design, and is said to be.
6. **Not the problem.** Check the usual suspects against the numbers and keep only what the data supports: permission prompts, stuck or looping agents, handoffs, version-control and code-host tooling, lint, CI, machine contention.
7. **Proposals.** Two fixed groups: **Improve the agentic loop** and **Improve the software bottleneck**. Each opens with the green-field design — what this would look like built from scratch today — and is ranked by outcome quality: correctness, security, maintainability, performance, operability. Effort and rollout cost are caveats, never ranking inputs. Every proposal carries its change, its evidence from this run, its expected effect, and its caveat.
8. **Page.** Write the report as an Artifact page that follows `report-template.md` section by section, in its order. The Artifact tool's page guidance governs the page and the `dataviz` skill governs every chart; the template says what each chart must show, not how it is styled. Look at the rendered page once before anyone else does.
9. **Publish.** Publish the page with the Artifact tool and report the link with the three clocks and the snapshot time.

### Refreshing

A live run moves on. Measure again, update every figure that moved and every sentence that no longer holds, and publish the same file path again: it redeploys to the same link. Record what the earlier version got wrong under the report's limits. Never refresh the charts under prose written for the previous snapshot.

## Reading the Transcripts

A transcript is one JSON object per line. Only `user` and `assistant` rows carry the timeline.

| Row | What it is | Fields that matter |
|---|---|---|
| `assistant` | One content block of a model response. Rows sharing `message.id` are one API call. | `timestamp`; `message.content[]` blocks of type `thinking`, `text`, or `tool_use` (`id`, `name`, `input`); `message.model`; `effort`; `thinkingDurationMs`; `message.usage` |
| `user` with `tool_result` blocks | The answer to the `tool_use` with the same `tool_use_id`. | `timestamp` |
| `user` with text | An incoming message: a prompt the human typed (`origin.kind == "human"`), or a hand-back, a coordinator's message, a notification (often `isMeta`). | `timestamp`, `origin`, the text |
| `system`, `subtype: "turn_duration"` | The end of a turn. | `durationMs` |

Attribute every gap between two consecutive rows of one transcript by the row that ends it:

| The gap ends in | It counts as |
|---|---|
| A model block | Model time. An API call lasts from the row before its first block to its last block. |
| A tool result | Tool time for the call it answers. With several calls pending, the gap belongs to the one that ran longest. |
| An incoming message, more than about five seconds later | Waiting. It ends the agent's current run; the next row starts a new run. |

- **Runs.** An agent's first run is its first pass; every later run is a resumed one. Read the message that resumed it before calling it rework: it may be a fix round, or a continuation after a block.
- **Units.** A unit groups the agents working on one piece of work — a layer, a task, a PR — as their descriptions name it. Its window runs from the moment it opened to the moment its last agent stopped.
- **Waiting on the human.** A question tool waiting for its answer, plus the session idle until a human prompt while no agent was running.
- **Activities.** Classify each shell command by what it does (tests, build, lint, install, version control, code host, containers and databases, network, wait loop, script) and each other tool by its name. Give a command a signature that ignores flags and redirections, so repeats of it can be counted.
- **Context.** A call's context size is its input tokens plus cache-read plus cache-creation tokens.

## Pitfalls

Each of these has already produced a wrong report once.

- **Session start is not run start.** Counting from the run's first prompt hides the hours the session was already open. Three clocks, always.
- **`isMeta` rows are waits too.** Hand-backs and notifications arrive as meta `user` rows; skipping them turns an agent's idle time into model time.
- **Parallel tool calls.** A quick command issued next to a slow one returns when the slow one does. The gap belongs to the slow one.
- **Background commands are invisible.** They return at once, so their duration is in no tool figure. Count them and say so.
- **A question to the human looks like a tool call.** It is waiting, and belongs to nobody's work.
- **A wrapper script hides what it runs.** `bash check.sh` may be the whole test suite: read the scripts behind the costliest commands.
- **Output-token counts are unreliable.** The transcripts under-report them; never publish one.
- **Totals move while the run is live.** Every figure carries its snapshot time.
- **A mid-run projection was off by two hours.** A projection is an estimate with a stated basis, never a headline figure.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "I'll ask the session what it is doing; it is quicker than reading its transcripts." | A message changes the run being measured and spends its context. The transcripts already hold the answer. |
| "The run started at this prompt; that is the clock that matters." | The user has been waiting since the session opened. The first report made this cut and had to be corrected. |
| "The test suite was the bottleneck last time; I'll look for it." | Each run has its own. Rank this run's tool time first, and name what its numbers name. |
| "The plan file says how many units there are." | Another session's `.claude/specs/` is its work in flight. Unit counts come from the transcripts. |
| "This run has no layers, so that section does not apply." | Every section stays. Name the unit this run has, or say in one line that it has none. |
| "This proposal is the cheapest to build, so it goes first." | Groups are ranked by outcome quality. Cost is a caveat. |
| "The agent was resumed, so that is a fix round." | A resumed agent may be continuing after a block. Read the message that resumed it. |
| "About four more hours." | Without a basis it is a guess presented as a measurement. State what it assumes. |
| "The numbers moved a little; I'll republish with the old text." | The text quotes the numbers. Re-read every sentence against the new figures. |

## Red Flags

- A message to the analyzed session, or any write under its worktree or under `~/.claude/projects/`.
- A file read under another session's `.claude/specs/`.
- A report that shows one clock, or a figure without a snapshot time.
- A section of the template missing, reordered, or renamed into something else.
- A number in the prose that no measurement or quoted row backs.
- A most-relevant-activity section chosen before the tool time was ranked.
- A proposal group that does not open with its green-field design, or a proposal without evidence from this run.
- A "not the problem" item with no figure next to it.
- A second Artifact for a refresh of the same run.

## Verification

Before reporting the link:

- [ ] The report shows when the session opened, when the run started, and the snapshot, in local time with the zone named.
- [ ] Earlier transcripts of the same process were looked for, and each one found is in the session's wall clock.
- [ ] Every section of `report-template.md` is present, in order, with the chart and the table it asks for.
- [ ] The most-relevant-activity section names what this run's tool time ranks first, with runs, median, total, who ran it, and the quoted line that prescribes it.
- [ ] Every deviation in the loop section cites a time and a transcript row; every "not the problem" item cites a figure.
- [ ] Each proposal group opens with its green-field design and is ranked by outcome quality; every saving states its basis; every projection is labelled an estimate.
- [ ] The page was looked at once, rendered, before publishing.
- [ ] Nothing was sent to the analyzed session and nothing was written outside this session's own directory.
- [ ] A refresh went to the same file path and the same link.
