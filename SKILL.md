---
name: chrisnizer
description: >
  If you want to sound more human, or really, more like Chris Hill, this skill
  does that. It flags AI-writing tells and drift from his house rules (no em
  dashes, no boosterism, active voice, first person singular or neutral voice for
  team docs, named sets instead of vague counts, one idea per sentence, lede first),
  auto-fixes the mechanical ones, and
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
python3 scripts/chrisnizer_lint.py --ui README.md    # also flag clipped text
python3 scripts/chrisnizer_lint.py --neutral DOC.md  # team or stakeholder doc: no I/my/we/our
```

Use `--neutral` for a document a team or a stakeholder reads, such as a system
breakdown, a plan or a briefing. It should read the same whoever wrote it, so it
flags "I" and "my" as well as "we" and "our".

Use `--ui` for text a newcomer reads once: a README, help text, labels, on-screen
messages. That text fails by being too clipped as often as by being padded.

For pasted text, write it to a temp file and lint that. The linter skips text in
double quotes, so a doc that quotes a tell as an example is not flagged for it.

## What the linter decides vs what you decide

The linter auto-fixes only the mechanical, unambiguous things under `--fix`:
curly quotes to straight, stray Unicode removed, doubled spaces collapsed,
trailing whitespace trimmed.

Everything else it flags with a suggestion, and you apply it using judgment, in
Chris's voice:

- **em dash / en dash**: replace with a comma, period, or colon. Never leave one.
- **filler, ai_vocab, boosterism, hedge**: cut the word or say it plainly. Do not
  swap one inflated word for another. Never use "silently" or "quietly", not even
  in technical prose where they look descriptive. Say what happened, so "it fails
  silently" becomes "it fails with no notification" or "it dies with no
  notification". Filler means intensifiers and padding, never function words:
  do not cut "that", "the" or "a" to shorten a sentence. "The walking policy
  that ships upstream" is right, and "the walking policy upstream ships" is not.
- **negative_parallelism** ("not just X but Y"): rewrite as one plain clause.
- **pseudo_cleft** ("the shape is what should hold"): name the real subject and
  verb directly ("the shape should hold" becomes "the idea is that").
- **fragment_colon** ("Three fingerprints, all built from signatures:", "The Batch
  API is real:"): give the clause before the colon a real verb ("Three methods
  built from signatures are:"), or drop a dramatic "is real" assertion and
  state the point plainly. The check only fires when a list follows the colon,
  so a colon leading into a code block or into explanatory prose is left alone.
- **passive_voice**: name the actor and make it active, when it reads better.
  Keep the passive when the actor does not matter or a forced active reads worse:
  "a thrown duck trusts you less" is fine, and "the tree's shaking by you" is not
  an improvement.
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
- **stilted**: a literary or old-fashioned turn ("and so does a tap on it", "off
  means off", "the garden's business", "stands about", "in place of"). Say it the
  plain modern way a newcomer reads once: "clicking the tree also works".
- **vague_set**: "the rest", "a few", "several", "most gaps", "rarely", or a set
  named only by its size ("the three", "two scores") with no list after it. Name
  the items or give the number: "Two scores have no cohort series" becomes
  "Prompt quality and delegation depth have no cohort series", and "rarely names
  a habit" becomes "named 0 of 41". A size followed by a colon, parentheses or an
  "X, Y and Z" list is fine.
- **positional**: "above the person", "upstream", "later stages", "the table
  below", "the next slide". The reader has to guess the place. Name the section,
  figure, step or people: "views above the person" becomes "views for teams and
  managers", and "later stages hide it" becomes "the task roll-up hides it".
- **first_person** (`--neutral` only): "I" or "my" in a team doc. Name the doc, the
  team or the thing instead: "I estimate" becomes "the estimate is".
- **dramatic_closer**: a punchy summary built on "nobody" ("Upkeep and hosting are
  the costs nobody has measured"). It reads as AI copy and is often not literally
  true. Check the claim, then say what is and isn't known: "Hosting and the test
  accounts aren't priced yet."
- **fragment**: a prose sentence with no subject and verb, such as one that opens
  on a participle ("Labeled 2 of 3 users.") or ends on one ("Counsel review needed
  before relying on it."). Write a full sentence: "Legal counsel hasn't reviewed
  it, so it can't be relied on yet."
- **long_paragraph**: over 120 words or 6 sentences. If it walks through parallel
  items (options with their costs and downsides, dependencies, findings), turn it
  into a table or a list with a one-sentence lead. Keep it as a paragraph only
  when it is one line of reasoning.
- **telegraphic** (`--ui` only): a sentence with no article, possessive or
  pronoun ("Closing window ends garden"). Put the small words back.
- **mixed_list** (`--ui` only): a list that mixes nouns and adjectives ("hunger,
  thirst, sleep, tired, bored"). Make every item the same kind of word ("hungry,
  thirsty, sleepy, tired, bored").

## What the linter cannot see

Three things you check by reading, because no regex catches them:

- **Claims written as cheques**: a strong short assertion ("the order matters")
  lands well but is only asserted. Check that the piece cashes it later, and if
  it does not, either justify it on the spot or cut it.
- **The stranger test**: read each sentence as someone new to the subject. A
  sentence can pass every rule and still be private shorthand: jargon never
  explained ("a body" for a simulation), a dropped "that" ("the policy upstream
  ships"), a poetic image ("a lawn sits in a bowl of rock"), or a rule stated
  as a riddle ("your shakes keep working up to twelve"). The rules can cause
  this: cutting filler strips words like "that", and forcing active voice bends
  sentences. Keep the function words and say it plainly.
- **Structural rhyme**: two clauses echoing the same shape in different
  paragraphs ("and what each fix is worth", "and report what it moved") read as
  a motif if deliberate and as repetition if not. Decide which it is, then keep
  it or break one of them.

## What readers of a team document catch

These came from a stakeholder doc that passed every rule above and was still sent
back. Check each one by reading:

- **One finding per sentence, and say when two have different sources.** A
  sentence that pairs how the system works today with a separate experiment's
  result reads as one claim. Split them and label each: "Today: ..." and
  "Separate test: ...".
- **Count in the reader's units.** Give the number the reader thinks in, not the
  implementation detail: "3 providers (ChatGPT, Claude, Copilot)", not "7 web
  addresses handled by three adapters".
- **Define a term at first use.** Spell out an abbreviation or coined term the
  first time it appears ("a work package (WP) is a named chunk of build work"),
  and don't use a coined verb ("size them") without saying what it means.
- **Don't invent groups, owners or statements.** Write only the teams, roles and
  decisions that exist. "The research team owns it" was wrong when everyone was
  one team. Quote a stakeholder's goal in their own words, and don't attribute a
  goal nobody stated.
- **Say what each number rests on, every time it appears.** Mark a figure from
  synthetic data, a test or real use where it is quoted, not once at the top. A
  footnote marker on each use works.
- **Short has to stay true.** A tightened sentence can drift from the facts. Check
  each punchy line against the table or source it summarises before keeping it.
- **Paragraph or table.** Use a paragraph for one line of reasoning. When items
  share the same attributes, such as options that each have a size and
  downsides, use a table.

## Workflow

1. Read `VOICE.md`.
2. Run `scripts/chrisnizer_lint.py` on the draft (`--academic` if it is a paper,
   `--ui` if it is a README or on-screen text, `--neutral` if a team or a
   stakeholder reads it).
3. Run `--fix` to clear the mechanical findings.
4. Apply the flagged judgment items by rewriting in Chris's voice: lede first,
   flowing paragraphs, one idea per sentence, active, plain, no dashes.
   `EXAMPLES.md` has real before-and-after pairs to calibrate against.
5. Re-run the linter and confirm it is clean or that anything left is deliberate.
   Clean is necessary, not sufficient: do the stranger test before calling it done.
6. Report what changed in a short summary, not a wall of diffs.

## Rule

Preserve every fact, number, name, and link. Change the wording, never the
claims. When a flagged word is load-bearing (a real 90-degree angle, a quoted
term), leave it and say why.
