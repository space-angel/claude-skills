---
name: writer-checker-loop
description: "틀리면 안 되는 문서(이력서, 포트폴리오 카피, 자기소개서, 지원서 문항, 기고문)를 작성 에이전트 하나와 읽기 전용 검사 에이전트 여럿의 루프로 만든다. 단계마다 사람이 게이트에서 판정한다. \"이력서 루프 돌려줘\", \"포폴 초안 검사 루프\", \"자소서 사실 검증하면서 써줘\", \"작성자-검사자 루프\", \"에이전트끼리 검사시켜줘\", \"숫자 틀리면 안 되는 문서야\" 같은 요청에 쓴다. English triggers: writer-checker loop, multi-agent drafting, fact-check my resume/portfolio/cover letter, draft with reviewer agents, generator-evaluator loop. 원천 자료 → 사실 카드 → 초안 → 사실 검사 ∥ 규칙 검사 → 사람 게이트 → 수정을 반복한다. 검사자에게는 쓰기 도구가 없고, 작성자는 원천이 아니라 카드만 본다."
---

# Writer–checker loop

One writer agent drafts. Several read-only checker agents report. A human decides at every gate. The loop exists because a model that writes and then checks its own work is mostly confirming itself.

Use it for documents where a wrong number or an overclaim costs more than the extra rounds: resumes, portfolio pages, cover letters, application answers, published articles. For a one-paragraph email, skip it.

## Principles — each one is enforced by structure, not by asking nicely

| Principle | How the loop enforces it |
|---|---|
| Generator and evaluator must differ | Writer runs on `opus`, checkers on `sonnet`. Different model, different context, no shared memory of "why I wrote it that way". |
| Checkers report; they do not fix | Checker agents get **no `Write`/`Edit` tools**. They cannot fix, so they don't. Their only output is the final message. |
| Constraints at the input beat checks at the output | The writer **never sees raw sources**. It sees only cards — atomic facts with source pointers — produced by the miner. If it isn't on a card, it doesn't exist. (The writer still has `Read`, so this holds only if the orchestrator never puts a `sources/` path in its prompt.) |
| One axis per checker | Fact-checking (is it true and traceable?) and rule-checking (does it follow the house rules?) are **separate agents**. Mixing them lets one kind of finding crowd out the other. |
| "Pass" is not a report | Every checker reports a **full cross-check with counts**: `claims checked 14 · traced 14 · violations 0`. A bare "looks good" is treated as a failed run and re-run. |
| Humans judge "enough"; nobody judges "true" | Whether the draft is persuasive enough is the human's call each round. Whether a number is sourced is not negotiable (see Termination). |

## The agents

Templates live in `agents/`. They are ordinary Claude Code subagent files.

| Agent | Model | Tools | Reads | Produces |
|---|---|---|---|---|
| `wcl-miner` | sonnet | Read, Grep, Glob, Write | one source folder/file set | one card file in `_cards/` |
| `wcl-brief-analyst` *(optional)* | sonnet | Read, Write | the target brief (job post, CFP, editor brief, rubric) | `_cards/BRIEF_<id>.md` — atomic requirements |
| `wcl-matcher` *(optional)* | opus | Read, Glob, Write | all cards + all briefs | `_cards/_MATCH.md` — requirement × fact map, gaps, message candidates |
| `wcl-writer` | **opus** | Read, Write | cards + `_MATCH.md` + `rules.md` (+ violation list in revise mode) | `drafts/<unit>.md` |
| `wcl-fact-checker` | **sonnet** | Read, Grep, Glob | draft + cards | violation table, **message only** |
| `wcl-rule-checker` | **sonnet** | Read, Grep | draft + `rules.md` + gate ① message | full checklist verdict, **message only** |
| `wcl-reader-sim` | opus | **Read only** | finished drafts + one brief + gate ① message per unit | skim verdict + weakest slot, **advisory** |

Use the optional pair when the document answers a specific target (a job post, a call for proposals). Skip them for an untargeted article; then gate ① picks the message directly from the cards.

**Not agents:** choosing the message, choosing what to foreground, tone, accepting a draft. Those are judgments, and they stay with the human.

## Install

Agent files must sit where Claude Code loads subagents.

```bash
# project-scoped (recommended: the loop lives with the document)
mkdir -p .claude/agents
cp ~/.claude/skills/writer-checker-loop/agents/*.md .claude/agents/

# or user-scoped
cp ~/.claude/skills/writer-checker-loop/agents/*.md ~/.claude/agents/
```

Subagents load at session start. After copying, start a new session (or run `/agents` to confirm they're listed). The `wcl-` prefix avoids collisions with agents the user already has.

Subagents cannot spawn subagents. **The main session is the orchestrator** — it is the one running this skill.

## Workspace layout

Pick one working folder per document and tell every agent its paths. The templates take paths from the caller; none are hard-coded.

```
<work>/
  sources/        raw material — read by the miner only
  rules.md        house rules + numbered checklist (the rule-checker's only standard)
  _cards/         machine layer: cards, briefs, _MATCH.md. Never hand-edit; re-run the miner
  drafts/         one file per unit (one page, one answer, one section)
  rounds.md       round log: each round's counts (fact/rule/MISSING/non-waivable), what it fixed, what is still open.
                  Checkers only message, so this file is where the next report's "prev N" comes from
```

If `rules.md` does not exist, draft one with the user before the first round. Minimum content: the writer's absolute rules (see `agents/wcl-writer.md`), banned phrasings, the structure template, and a **numbered checklist** — the rule-checker judges every numbered item.

## Card format

A card is the only thing the writer may cite. One card per source unit (project, role, study).

```markdown
# Card — <name>
> **Card ID:** C1 · **Mined from:** <paths> · **Mined:** YYYY-MM-DD

## Facts
| # | Claim | Number | Base (denominator) | Evidence type | Source (file-level) |
|---|---|---|---|---|---|
| F1 | Checkout drop-off fell after redesign | 12% | 3 of 25 testers | measured | sources/test-log.md |

## Artifacts
| # | What | Form | Source |

## Quotable lines — verbatim
| # | Sentence | Source |

## Time / scope limits
Only what the source states. Otherwise "none stated".

## Not in source — could not fill
```

Rules the miner keeps: no base → write `none` (never estimate one). Evidence type is one of `measured` / `content-analysis` / `interview` / `self-assessed` / `fact` / `self-reported`. `self-reported` (the author's own unrecorded account) is never upgraded to another type. Every fact row has a file-level source or it is deleted.

## The loop

```
FAN-OUT (once)
  miner × N sources ─┐
  brief-analyst × M ─┴─→ matcher ─→ _MATCH.md
                                       │
                               ◆ GATE ① human
                                       │
PRODUCTION (one unit at a time, to completion)
  for unit in units:
      writer ─→ draft
      ┌─────────── round ───────────┐
      │ fact-checker ∥ rule-checker │   (launch both in one message)
      │        → merged report      │
      │        ◆ GATE ② human       │
      │ writer (revise mode) ───────┘
  ※ finish the first unit fully before starting the second:
    template defects surface once, not N times.

JUDGMENT (after all units)
  reader-sim × M briefs
        ◆ GATE ③ human → re-enter production for the weakest units only
```

Run independent agents in parallel: all miners in one message, both checkers in one message.

## Gates — what to show the human

No numeric pass threshold. Instead the human gets the same material in the same shape every time.

| Gate | When | Show | Human decides |
|---|---|---|---|
| ① | after matcher (or after mining) | requirement map, **gaps**, message candidates per unit | **one message per unit**; what the document should prove |
| ② | every round | merged round report (below) | continue / stop / change direction |
| ③ | after reader-sim | verdicts, rejection reasons, weakest slot | which units re-enter |

### Gate ② checklist — the round report

Assemble this from both checkers' messages. Do not paraphrase their quoted sentences.

```
Unit <name> · Round N

Fact violations   N  (prev N → ±N)    claims checked N · traced N
Rule violations   N  (prev N → ±N)    checklist items judged N of N
MISSING slots     N

🔴 Repeat violations — survived 2+ rounds
| Sentence | Type | Rounds |

New violations
| Sentence | Type | Checker |

Resolved since last round

Non-waivable still open: N   ← must be 0 to stop
```

Before showing it, verify:
- [ ] Both checkers reported counts. A checker that only said "pass" is re-run.
- [ ] Rule-checker judged **every** numbered checklist item (`judged N of N`). Missing items = re-run.
- [ ] Repeat violations are at the top.
- [ ] The non-waivable count is computed, not estimated.

**Repeat violations go first** because a finding that survives two rewrites is not a wording problem. Either the fact isn't on any card (go mine, or drop the claim) or the slot asks for something the material can't supply (change the template). Rewriting a third time won't fix it — escalate.

## Termination

A run ends only when **both** hold:

1. **Non-waivable violations = 0.** These are fact-checker types `V-UNSOURCED`, `V-NO-BASE`, `V-MISMATCH`, `V-DERIVED`, `V-SCOPE`, `V-OVERCLAIM`. At gate ② the human cannot choose "ship it anyway" while any are open. Truth is not up for a vote.
2. **The human says stop.** Everything else — rule-checker findings, `V-TYPE-MIX`, `V-ESTIMATE` judgment calls, tone, length, persuasiveness — is the human's discretion.

Other exits:
- **Escalate, don't loop:** a violation that survives 2 rounds goes back to the human as a material or template problem (see above), not to the writer for a third try.
- **Honest gap:** the writer may replace an unfillable claim with `⚠️ MISSING — <what's missing>`. That is not a violation. The human decides whether to find the material or cut the slot.
- **Reader-sim never terminates the loop.** Its verdict is advice for gate ③.

When the run ends: strip `[C1-F3]`-style card citations from the final copy, log the last round in `rounds.md`, and tell the user the final counts (claims traced, rules judged, rounds run).

## Persuasion is selection, not invention

The writer optimizes each unit for **one message**, and the reader-sim judges whether that message lands in a **5-second skim** — headings and bold text only, the way a screener actually reads. Choosing which true facts to foreground, and keeping weak results out of headlines, is legitimate editing. Inventing, inflating, or computing new numbers is not; the fact-checker blocks that regardless of how well it reads.

## Other shapes of the same loop

The structure — extractor → single writer → read-only checkers with counts → human gate — fits more than prose:
- **Job applications:** research the company → review fit → benchmark against other candidates → optimize the answer → evaluate as the screener.
- **Pipeline evals:** the pipeline is the writer; checkers score outputs against cards of ground truth; the human decides whether a regression is acceptable.

Swap the agents' inputs; keep the four constraints: separate models, no write tools for checkers, cards-only input for the writer, counts instead of "pass".
