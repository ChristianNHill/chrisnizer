---
name: chrisnizer
description: >
  If you want to sound more human, or really, more like Chris Hill, this skill
  does that. It flags AI-writing tells and drift from his house rules (no em
  dashes, no boosterism, active voice, first person singular or neutral voice for
  team docs, named sets instead of vague counts, one idea per sentence, lede first),
  auto-fixes the mechanical ones, and
  rewrites the judgment calls in his voice. It starts from who reads the draft and
  ends with a new-reader check, with the linter as the cleanup pass between. Use when asked to chrisnize, de-slop,
  humanize, or fix the tone of a draft, or on /chrisnizer.
---

# chrisnizer

If you want to sound more human, or really, more like me, this skill does that.
It is a voice profile, a reading method and a deterministic linter. The linter
finds where a draft drifts from the house rules in `VOICE.md`. You apply the fixes
in voice.

Read `VOICE.md` first. It is the profile you are editing toward.

The linter is the cleanup pass at the end. A draft that passes it can still fail
its reader. One document passed every rule and then drew 368 review findings, for
undefined terms, numbers with no source and paragraphs that contradicted each
other. Start from the reader and finish with a reader. A clean lint report doesn't
mean the draft is done.

## Workflow

1. **Name the reader.** Write down who reads the draft, what they do with it, and
   what they need from each section. A proposal writer who will reuse the numbers
   needs something different from an engineer who will build from the ids.
2. **Propose cuts before rewording.** For each section and paragraph, ask whether
   that reader needs it. Merge a paragraph that repeats another, as long as every
   fact survives. A cut that removes a fact is the owner's call. In your own
   draft, you are the owner. In someone else's, list the cut with a one-line
   reason and carry on with the content kept (see "Wording changes and content
   changes"). Rewording a paragraph that should go is wasted work.
3. **Rewrite for the reader**, in Chris's voice: lede first, flowing paragraphs,
   one idea per sentence, active, plain, no dashes. `EXAMPLES.md` has real
   before-and-after pairs to calibrate against.
4. **Run the linter** (`--academic` for a paper, `--ui` for a README or on-screen
   text, `--neutral` when a team or a stakeholder reads it). Run the report, run
   `--fix` for the mechanical findings, then apply the flagged items by judgment.
   The mode flag goes on every lint run, with or without `--fix`. `--facts` and
   `--drift` take no mode. Linting the original before step 3 is a good way to see
   what the rewrite has to fix. If a fix makes a
   sentence longer or stranger, keep the original (see "When a rule makes the
   sentence worse").
5. **Check the facts survived.** Run `--facts OLD NEW` on the version from before
   the rewrite and the new one. Every lost number, id, link and code name must be
   a cut the owner approved. Put back anything else. Then run `--drift OLD NEW`.
   It shows whether the rewrite moved the prose the way model rewrites move it:
   longer words, small words cut, contractions written out, more commas, and
   sentences closer to one length. Look at each flagged measure and undo the
   drift where the original read better.
6. **Pass a new reader.** The draft is done when a reader who has seen none of the
   earlier work reads it once without stopping. With agents available, start a
   fresh one that gets only the text and a line on who the reader is. Ask it to
   list each sentence it had to reread and each term it couldn't define. Fix
   those sentences, then run the linter and `--facts` again. For a document
   someone will act on, also run the reader question test (see "The reader
   question test"). Repeat the new-reader check after every batch of edits. Stop
   when a reader reports nothing, or when the last batch changed only the
   sentences the reader named. Without agents, do the stranger test yourself.
7. Report what changed in a short summary, not a wall of diffs. Include what was
   cut, anything the linter still flags that was left on purpose, and the
   questions only the owner can answer.

### The reader question test

The new-reader check finds sentences that are hard to read. The question test
finds facts that are missing or wrong, which a clear sentence can hide.

1. Write 5 to 10 questions the named reader will ask of the document, such as
   "What does it cost?", "What is decided?" and "What do I do next?".
2. Give a fresh agent only the document and the questions. Ask it to answer each
   from the document alone, and to say "the document doesn't say" when it doesn't.
3. Compare the answers with what you know to be true. A wrong answer marks a
   sentence that misleads. "The document doesn't say" marks a gap, and so do two
   different answers to one question.

Ask the agent what the document says. Don't ask it to rate the writing, because
a rating gives you nothing to fix.

### Wording changes and content changes

A wording change keeps every claim, and you make it without asking. Reordering
text is a wording change. A content change adds, removes or alters a claim, and it
is the owner's call. These are content changes, even where a rule in this file
says to make them:

- cutting a sentence or paragraph that holds a fact
- removing a document's account of its earlier versions (self_history)
- replacing a number that has no backing with "not identified yet"
- rewriting a stated decision as open, or an open one as decided
- adding a footnote note whose meaning you'd have to guess, or dropping its marker

In your own draft you are the owner, so make them. In someone else's document,
propose each one with a one-line reason. If the owner can't answer now, deliver
the reworded text with the content kept, and list the proposals and questions in
the summary. Don't hold the whole edit for an answer.

## Run the linter

The script is stdlib-only Python, no install. `scripts/` is in this skill's
folder, and `DRAFT.md` stands for the path to the draft.

```sh
python3 scripts/chrisnizer_lint.py DRAFT.md          # report
python3 scripts/chrisnizer_lint.py --json DRAFT.md   # findings as JSON
python3 scripts/chrisnizer_lint.py --fix DRAFT.md    # apply mechanical fixes in place
python3 scripts/chrisnizer_lint.py --academic DRAFT.md   # allow we/our for papers
python3 scripts/chrisnizer_lint.py --ui README.md    # also flag clipped text
python3 scripts/chrisnizer_lint.py --neutral DOC.md  # team or stakeholder doc: no I/my/we/our
python3 scripts/chrisnizer_lint.py --terms TERMS.txt DOC.md  # flag other names for one thing
python3 scripts/chrisnizer_lint.py --facts OLD.md NEW.md     # what a rewrite lost or added
python3 scripts/chrisnizer_lint.py --drift OLD.md NEW.md     # how a rewrite moved the style
python3 scripts/chrisnizer_lint.py --all DRAFT.md            # also show lone weak findings
```

`--terms` takes a file with one line per thing: the name to use, a colon, then the
other names to flag, such as `workflow: task, job`. It flags each other name with
its lines. Some hits are a different meaning of the word, so read each one.

`--facts` compares two versions and lists every number, id, link, anchor and code
name whose count went down or up. Anything lost is either a deliberate cut or a
mistake, so account for each one. It counts digits only, so it doesn't see a
number written as a word ("three").

`--drift` compares the prose of two versions on seven measures: letters per word,
word variety, the share of small function words, contractions, commas per
sentence, dashes, and the spread of sentence lengths. It marks a measure that
moved by 10% or more in the direction model rewrites move it. A mark is a prompt
to look, because a real improvement can also move a measure. Skip it for a draft
under 300 words, where one sentence can move a measure by 10%.

Some findings are weak: one alone says little. The linter reports a weak finding
only when its paragraph holds two or more, and `--all` shows every one.

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
Chris's voice. This list is a reference: read the entries for the categories the
linter reported, and skip the others.

- **em dash / en dash**: house style. Never leave one. Replace it with a comma, a
  period, a colon or parentheses, or restructure the sentence. Vary the
  replacement: a comma in every spot becomes its own habit.
- **filler, ai_vocab, boosterism, hedge**: cut the word or say it plainly. Do not
  swap one inflated word for another. Never use "silently" or "quietly", not even
  in technical prose where they look descriptive. Say what happened, so "it fails
  silently" becomes "it fails with no notification" or "it dies with no
  notification". Filler means intensifiers and padding, never function words:
  do not cut "that", "the" or "a" to shorten a sentence. "The walking policy
  that ships upstream" is right, and "the walking policy upstream ships" is not.
- **negative_parallelism** ("not just X but Y"): rewrite as one plain clause.
  It also flags four newer contrast frames, listed here.
  A plain "rather than" comparison is fine.
  - "rather than simply"
  - "is more than a tool, it"
  - "is not simply"
  - "This doesn't mean X. It means Y."
- **stock_frame**: a frame that announces a point without making it.
  Say what matters and why, or what happens next.
  If the sentence only restates the paragraph, cut it. If the frame carries a
  claim, keep the claim in plain words: when "looking ahead" means the thing is
  planned and not built, write "planned". The frames are:
  - "this matters", "why the queue size matters", "matters most"
  - "looking ahead", "what comes next", "adds another layer"
  - "Bottom line:" and "In short,"
- **weak_vocab** (weak): words models overuse that are also ordinary English,
  such as "pivotal", "showcase", "intricate", "dependable" and "meaningful". Two
  or more in one paragraph read as model text. Use the plain word for each.
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
  "X, Y and Z" list is fine. If you don't have the items or the number, ask the
  author. Never make one up to clear the finding.
- **positional**: "above the person", "upstream", "later stages", "the table
  below", "the next slide". The reader has to guess the place. Name the section,
  figure, step or people: "views above the person" becomes "views for teams and
  managers", and "later stages hide it" becomes "the task roll-up hides it". If
  you can't tell which place or people the text means, ask the author.
- **first_person** (`--neutral` only): "I" or "my" in a team doc. Name the doc, the
  team or the thing instead: "I estimate" becomes "the estimate is". The same goes
  for a plural: "We decided to ship in May" becomes "The decision is to ship in
  May". Don't name a decider the text doesn't name.
- **dramatic_closer**: a punchy summary built on "nobody" ("Upkeep and hosting are
  the costs nobody has measured"). It reads as AI copy and is often not literally
  true. Check the claim, then say what is and isn't known: "Hosting and the test
  accounts aren't priced yet." If you can't check it, keep the claim and drop the
  "nobody": "the cause hasn't been measured".
- **fragment**: a prose sentence with no subject and verb, such as one that opens
  on a participle ("Labeled 2 of 3 users.") or ends on one ("Counsel review needed
  before relying on it."). Write a full sentence: "Legal counsel hasn't reviewed
  it, so it can't be relied on yet."
- **long_paragraph**: over 120 words or 6 sentences. If it walks through parallel
  items (options with their costs and downsides, dependencies, findings), turn it
  into a table or a list with a one-sentence lead. Keep it as a paragraph only
  when it is one line of reasoning.
- **repeated_opener**: the same first four words open five or more sentences
  ("The following table lists ..."). The frame reads as a template. Vary each lead
  by what its rows or its paragraph hold, such as "Each row is one option:" on one
  table and "For each step, the table gives ..." on another. Don't reuse one
  replacement everywhere, or it becomes the next template. If the repeated
  sentence is the same explanation in many sections, keep one full copy and point
  to it by name.
- **empty_lead**: a lead-in that names the container and not the content ("The following table lists the jobs."). One use is enough to flag. Say what a row or an item is: "Each row is one job, with its owner:". Vary the replacement by what each table holds, or "Each row is" becomes the next template. Keep the original when it already says what a row is and the rewrite reads worse.
- **hedged_number**: a hedge on a planning figure ("about 3 to 5 weeks", "roughly twenty people", "around $40") in a sentence that doesn't say where the figure comes from. The check covers a hedged range in any unit, and a single hedged figure in days or longer, people or money. Find the source first. If the figure was measured or counted, say so. If it has a method but no measurement, call it an estimate and name the method. If it has no source, it falls under "A number with no backing doesn't go in", and the owner decides. Two cheap ways to clear the finding make the text worse, and neither is a fix. Deleting "about" makes an unbacked figure look firm. Adding "estimated" with no source turns the check off and tells the reader nothing. The words "measured", "counted", "estimate", "calculated", "according to" and "based on" turn the check off, so leave the finding when the sentence before it gives the source.
- **self_history**: the document talks about its own past, such as
  "Earlier versions of this page gave ..." or "this report now uses ...".
  The reader wants what is true now. Cut it, and keep the history in a changelog
  or decision log. The old figure is a fact, so in someone else's document the
  cut is a proposal.
- **distant_pronoun**: a paragraph opens on "It is", "This means" or "They are".
  The noun is in another paragraph. Name the thing. Apply the same test inside a
  paragraph when the noun is more than a clause away.
- **orphan_asterisk**: a figure carries an asterisk and its section has no note
  line that explains it. Add the note where the figure is quoted, and have the
  note name only the figures in its own section. If you don't know what the
  asterisk means, ask the owner and leave it.
- **term_drift** (`--terms` only): another name for a thing that has one name.
  Change it, unless the word means something else in that sentence.
- **telegraphic** (`--ui` only): a sentence with no article, possessive or
  pronoun ("Closing window ends garden"). Put the small words back.
- **mixed_list** (`--ui` only): a list that mixes nouns and adjectives ("hunger,
  thirst, sleep, tired, bored"). Make every item the same kind of word ("hungry,
  thirsty, sleepy, tired, bored").

## When a rule makes the sentence worse

The rules are a means. Each one can produce its own fault, so check the sentence
after a fix and keep the original when the fix reads worse:

- Cutting filler strips function words ("that", "the"), and the sentence turns
  into shorthand.
- Forcing active voice bends a sentence whose actor doesn't matter.
- Splitting every long sentence produces a run of short ones in the same shape,
  which the staccato rule then flags. Merge two with "because", "so" or "but".
- Swapping a flagged word for a longer phrase keeps a weak sentence. When "several"
  or "above" is flagged, try restructuring or cutting the sentence first.
- A rule applied the same way everywhere becomes a template. "Put a sentence before
  every table" produced dozens of identical table openers.

Leave a finding unfixed when the fix is worse, and say so in the summary.

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
- **One word, one meaning.** If the same word names two things, such as "jobs"
  for both queue entries and kinds of job, give one of them another name. If you
  can't tell which meaning a use has, ask the owner.
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
- **Define a term in each section readers can land on.** A page with tabs, slides
  or deep links has no "first use". Give a term its few-word definition the first
  time it appears in each section: "the ranker, the model call that orders the
  search results".
- **Say what a coined name or a code reference is.** A check named in quotes, a
  commit hash or a branch name means nothing alone. Write "the current `main` code
  (`a1b2c3d`, 4 March)", and say what a named check checks.
- **A number with no backing doesn't go in.** A rough range gets copied into a
  proposal as if it were measured. A figure has backing when the text or its
  sources say where it comes from: a measurement, a test or a stated method. A
  figure with a method but no measurement is an estimate, and it stays, called an
  estimate each time. A figure with no source at all becomes "not identified
  yet". The owner decides which kind a figure is, so in someone else's document
  ask before replacing it. Calling a figure an estimate is a wording change only
  when the text already hedges it with "about" or "roughly".
- **An open decision stays open.** Don't write the leading candidate as the
  decision. Write "not decided yet", or "exploring" with the option named. Take
  the text at its word: if it says a thing is decided, keep it decided, and ask
  the owner if the rest of the document suggests otherwise.
- **When a number changes, find its neighbours.** Search for every place that
  states the figure, adds it into a total, or implies it. A paragraph that says a
  feature has no measured cost contradicts the table that now gives one.
- **Put the reason after the rule.** State what happens, then why. A sentence that
  opens on "because" makes the reader hold the reason before they know the rule.
- **Write a formula as steps.** Give each formula in words in its own bullet, then
  say which inputs are known and which aren't. A paragraph that chains two
  multiplications gets reread.
- **Keep one unit for one quantity.** If cost is per call, don't switch to per day
  or per person part-way through.
- **Label for the reader's question.** A column or status name answers what the
  reader wants to know, such as whether a fix exists, and doesn't describe the
  mechanics behind it. Check each label with the owner, because the label frames
  the finding.
- **In a table cell with several results, give each its own sentence** and start
  it with its source: "Test set: ...", "Live run: ...".

## Large documents

For a document too long to hold in one pass, or one that more than one person or
agent edits:

- **Write a style brief first.** `STYLE-BRIEF.md` is a template. The brief names
  the readers, the hard rules, the decisions the owner already made, the one name
  for each thing, and before-and-after pairs taken from the document itself. Every
  editor and reviewer gets the same brief.
- **Save the version from before the edits,** so `--facts` has something to compare.
- **Rename first, reword second.** Apply document-wide renames before sentence
  edits. Edits written against the old names fail to match once the names change.
- **Edit by list.** Each edit is an old text and a new text, where the old text
  occurs exactly once, with a one-line reason. Apply the list with a count check,
  so an edit that matches nothing or matches twice is reported and not guessed.
- **Split writer, new reader and reviewer.** The writer proposes edits. A new
  reader with no context reports what it had to reread. A reviewer checks facts
  against the sources. The writer's own check doesn't replace the other two.
- **Look for contradictions as a separate pass.** After the edits, read only for
  two places that disagree, or a paragraph that implies something a table denies.

## Rule

Rewording never changes a claim. Preserve every fact, number, name and link in
the text that stays. When a flagged word is load-bearing (a real 90-degree angle,
a quoted term), leave it and say why.

A cut is a separate act from a rewording. In someone else's document, propose
each cut that removes a fact and apply it only when the owner agrees. List every
cut in the summary.
