# Report Template

The report has these sections, in this order, for every run. Each says what to **find** in the transcripts, what to **show**, and what to **write**. Replace every `<…>` with what this run shows. Name things by what they are in this run: a unit may be a layer, a task, a PR. A section the run has no data for stays, with one line saying so.

Sections 10 and 11 are written fresh for each run. Every other section is fixed in what it must answer.

## Conventions

- **Times** are local, with the zone named once in the header. Durations are in minutes, and in hours and minutes above 90.
- **Every figure** is as of the snapshot. Every projection is labelled an estimate and states its basis.
- **Prose** is one or two short paragraphs per section: the finding first, numbers from the measurements, quotes from transcripts and definitions.
- **Charts** each carry a title, one line on how to read them, a legend, a value on hover or focus, and a table view of the same data.
- **Colour** means the same thing in every chart: one colour per actor, grey for waiting, hatching for a resumed run. Activities use a second palette: one colour for model inference, one per named activity, grey for the rest.

## 1. Header

- **Eyebrow:** `<session name> · opened <date, time> · <run command> since <time> · snapshot <date, time, zone>, <in progress | finished>`
- **Title:** `<the question the page answers, as the user would ask it>`
- **Lede**, three to five sentences: `<is anything stuck>` · `<session wall clock>` · `<what the time before the run went to>` · `<run wall clock and progress: units done of total>` · `<what one unit costs, and whether units run in sequence>` · `<estimate of what remains, with its basis>`
- **Second paragraph:** `<the two or three things that carry the time inside the run, each with its share>` · `<the single most expensive event>`
- **Stat row**, five figures with a one-line label each: `<session wall clock>` · `<run wall clock>` · `<units done of total>` · `<inference share of agent work, with the API call count>` · `<top activity besides inference: runs and minutes>`

## 2. Wall Clock Since the Session Opened

- **Find:** when the process started and with which command; every phase from then to the snapshot, including earlier transcripts of the same process; for each phase, how much was agents working and how much was waiting on the human; each question that sat open and for how long.
- **Show:** a horizontal bar per phase, in the order they happened, in minutes of wall clock. Two colours: agents working, waiting for the human. The value at the end of each bar.
- **Write:** `<when the session opened and with what>` · `<what each phase before the run was>` · `<total waiting on the human and total agents working>`

## 3. The Run So Far

- **Find:** every agent run with its start and end, its role, and whether it is a first or a resumed run; the coordinator's own turns; the moments the run waited on the human.
- **Show:** a run strip. Clock time on the horizontal axis with hourly ticks; one row per actor (the human, the coordinator, each agent role); one block per run from start to end, hatched when resumed; a band above the rows naming the phase or unit under way.
- **Show:** a table, one row per phase: `Phase | Clock | Minutes | What happened`.
- **Write:** `<how to read the strip>` · `<whether agents run one at a time or overlap>` · `<whether any idle time hides between blocks>`

## 4. Where Each Unit's Time Went

- **Find:** for each unit, its window and the minutes of each kind of run inside it: first pass per role, resumed rounds per role, and the remainder (handoffs, waits, checks). The cheapest unit and what it changed. Which units went back for another round, why, and what the round cost.
- **Show:** a horizontal stacked bar per unit, in the order they were built, in minutes. One segment per kind of run, resumed rounds hatched, the remainder in grey. The total at the end of each bar.
- **Show:** a table view: `Unit | Total | <minutes per kind of run> | <runs of the top activity, by role> | <minutes of it>`, with a sum row over the settled units.
- **Write:** `<the cheapest unit, what it changed, and so the fixed cost of one pass through the loop>` · `<what that fixed cost is made of>` · `<the units that needed another round, why, and the cost>` · `<the outliers>`

## 5. What the Agents Were Doing

- **Find:** total minutes of agent work, split into model inference and tool time by activity; the same split per role.
- **Show:** one full-width stacked bar of shares for all agents together, then one stacked bar per role in minutes. Segments: model inference, the top activity, the rest of its family, other tools. The legend carries minutes and share.
- **Write:** `<total work, and how much of it is inference, the top activity, the rest>` · `<the roles whose split stands out>`

## 6. Model Time

- **Find:** the number of API calls; how long a typical call takes; the share of calls over 30 seconds and their share of model time; the longest calls with their thinking time and what they produced; the model and effort each agent ran at, and whether its definition sets them or they are inherited from the session; context size against call duration.
- **Show:** paired bars per duration band (0 to 5 s, 5 to 15, 15 to 30, 30 to 60, 60 to 120, over 120): share of calls next to share of model time.
- **Show:** a table of the longest single calls: `Duration | Agent | Thinking | What it produced`.
- **Write:** `<call count and typical duration>` · `<how few calls hold how much of the time, and what those calls are>` · `<model and effort per role, and where they are set>` · `<how context size moves latency>`

## 7. Most Relevant Activity: `<its name>`

The activity besides inference that this run's tool time ranks first. Repeat the section for a second activity when it also carries real time.

- **Find:** what the activity is and where the project configures it; how long one run of it takes; its runs, median, and total; who ran it and how often per unit; how many runs repeated it on unchanged code; the line in a skill, an agent definition, or a brief that prescribes it; what in the project makes it slow; anything in the run that already changes it.
- **Show:** a list of facts, each a bold claim with its figures. A table of the costliest commands when more than one matters: `Command | Activity | Runs | Median | Total | Who`.
- **Write:** `<what it is and what one run costs>` · `<who is told to run it, quoting the line>` · `<who repeats it, and on what>` · `<why it is slow>`

## 8. What Is Not the Problem

- **Find:** a figure for each usual suspect: permission prompts (how long file edits take), stuck or looping agents (retries, handoff time), version-control and code-host tooling, lint, CI (whether anything was pushed, and how long recent runs take), machine contention (the same command's duration across the run).
- **Show:** a list, one line per suspect the data clears: the suspect in bold, then the figure that clears it.

## 9. Is the Loop Right?

- **Find:** the skill and agent definitions that drove the run; where the run followed them; each place it did not, with the time and the quoted row; which of the run's costs the definitions prescribe; the single most expensive event and what it was made of.
- **Write:** `<the verdict in one sentence>` · `<each deviation: what the definition says, what the run did, what it cost>` · `<the costs that are design, not error>` · `<the most expensive event>`

## 10. Proposals

Written for this run. Open with one paragraph saying how the groups are ranked.

Two groups, always these: **Improve the agentic loop** and **Improve the software bottleneck**. Each opens with its green-field design and is ranked by outcome quality. Each proposal is a card:

- **Id and title:** `<A1, A2 … | B1, B2 …>` `<the change, as an instruction>`
- **Tag:** `<Green-field | No quality trade-off | Relaxes an invariant | Quality risk | Unmeasured | Already built>`
- **Change** (or **Design**, for the green-field card): `<what to change, concretely enough to act on>`
- **Evidence:** `<the figures from this run that motivate it>`
- **Effect:** `<what it would save or improve, with the basis>`
- **Caveat:** `<what it costs, risks, or leaves unmeasured>`

## 11. What the Changes Would Save

- **Find:** for each proposal with a measurable basis, the saving on a stretch of the run that is already complete.
- **Show:** a table: `Change | Basis in this run | Saving`.
- **Write:** `<the stretch the savings were measured on>` · `<that the rows overlap and do not add up>` · `<the combined projection, labelled as one>`

## 12. Method and Limits

- **How this was measured:** `<where the data came from>` · `<that nothing was sent to the analyzed session>` · `<how gaps were attributed>` · `<what each projection assumes>`
- **Snapshots:** `<which figures are as of which time>`
- **Corrections:** `<what an earlier version of this page got wrong>`, when the page was republished.
- **Limits:** `<what the transcripts could not show, and what was not analyzed>`
