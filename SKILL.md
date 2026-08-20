---
name: chrisnizer
description: >
  If you want to sound more human, or really, more like Chris Hill, this skill
  does that. It flags AI-writing tells and drift from his house rules (no em
  dashes, no boosterism, active voice, first person singular, flowing paragraphs,
  one idea per sentence, lede first), auto-fixes the mechanical ones, and
  rewrites the judgment calls in his voice. Use when asked to chrisnize, de-slop,
  humanize, or fix the tone of a draft, or on /chrisnizer.
---

# chrisnizer

If you want to sound more human, or really, more like me, this skill does that.
It is a deterministic linter plus a voice profile. The linter finds where a draft
drifts from the house rules in `VOICE.md`. You apply the fixes in voice.

Read `VOICE.md` first. It is the profile you are editing toward.

## Run the linter

The script is stdlib-only Python, no install. Base directory is this skill's
folder.

```sh
python3 scripts/chrisnizer_lint.py DRAFT.md          # report
python3 scripts/chrisnizer_lint.py --json DRAFT.md   # findings as JSON
python3 scripts/chrisnizer_lint.py --fix DRAFT.md    # apply mechanical fixes in place
python3 scripts/chrisnizer_lint.py --academic DRAFT.md   # allow we/our for papers
```

For pasted text, write it to a temp file and lint that.

## What the linter decides vs what you decide

The linter auto-fixes only the mechanical, unambiguous things under `--fix`:
curly quotes to straight, stray Unicode removed, doubled spaces collapsed,
trailing whitespace trimmed.

Everything else it flags with a suggestion, and you apply it using judgment, in
Chris's voice:

- **em dash / en dash**: replace with a comma, period, or colon. Never leave one.
- **filler, ai_vocab, boosterism, hedge**: cut the word or say it plainly. Do not
  swap one inflated word for another.
- **negative_parallelism** ("not just X but Y"): rewrite as one plain clause.
- **pseudo_cleft** ("the shape is what should hold"): name the real subject and
  verb directly ("the shape should hold" becomes "the idea is that").
- **fragment_colon** ("Three fingerprints, all built from signatures:", "The Batch
  API is real:"): give the clause before the colon a real verb ("Three methods
  built from signatures are:"), or drop a dramatic "is real" assertion and
  state the point plainly. The check only fires when a list follows the colon,
  so a colon leading into a code block or into explanatory prose is left alone.
- **passive_voice**: name the actor and make it active, when it reads better.
- **long_sentence**: split into one idea per sentence.
- **staccato**: three or more short sentences in a row with the same shape
  ("It defers... It exposes neither... It reports...") reads as a list dressed as
  prose. Same shape means the same opening word, or different pronoun subjects
  doing the same job. Merge two of them or vary one. Two in a row is punch, so
  leave it.
- **plural_first_person**: change we/our to I/my for solo writing. Leave it under
  `--academic`.
- **label_bullet**: fold labelled fragments into a flowing paragraph when the
  content is narrative.
- **title_case_heading**: sentence case, first word capitalised only.

## What the linter cannot see

Two things you check by reading, because no regex catches them:

- **Claims written as cheques**: a strong short assertion ("the order matters")
  lands well but is only asserted. Check that the piece cashes it later, and if
  it does not, either justify it on the spot or cut it.
- **Structural rhyme**: two clauses echoing the same shape in different
  paragraphs ("and what each fix is worth", "and report what it moved") read as
  a motif if deliberate and as repetition if not. Decide which it is, then keep
  it or break one of them.

## Workflow

1. Read `VOICE.md`.
2. Run `scripts/chrisnizer_lint.py` on the draft (`--academic` if it is a paper).
3. Run `--fix` to clear the mechanical findings.
4. Apply the flagged judgment items by rewriting in Chris's voice: lede first,
   flowing paragraphs, one idea per sentence, active, plain, no dashes.
5. Re-run the linter and confirm it is clean or that anything left is deliberate.
6. Report what changed in a short summary, not a wall of diffs.

## Rule

Preserve every fact, number, name, and link. Change the wording, never the
claims. When a flagged word is load-bearing (a real 90-degree angle, a quoted
term), leave it and say why.
