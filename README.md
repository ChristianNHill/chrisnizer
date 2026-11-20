# chrisnizer

If you want to sound more human, or really, more like me, this skill does that. It
is a writing linter tuned to my own voice, packaged as a Claude Code skill. It finds
where a draft drifts into AI-writing tells or away from my house rules, then fixes
the mechanical parts. A draft comes back sounding like me instead of like a model.

The skill does not rewrite on its own. The linter flags; I (or an agent running the skill)
apply the judgment calls in voice. The linter is also the last step, not the first.
`SKILL.md` starts from the reader: name who reads the draft, cut what they don't
need, rewrite, lint, then give the result to a new reader who has seen none of the
earlier work. A clean lint report doesn't mean the draft is done. The rules live in [`VOICE.md`](VOICE.md), built
from three sources: samples of my own solo writing, the AI-writing tells a humanizer
catches, and the register of my research papers.

## What it catches

Auto-fixed with `--fix`: curly quotes, stray Unicode, doubled spaces, trailing
whitespace.

Flagged for me to apply in voice: em dashes, filler and boosterism, hedging,
negative parallelism ("not just X but Y"), passive voice, sentences that run past
one idea, runs of three or more short sentences in the same shape, first person
plural in solo writing, labelled bullet fragments where a paragraph belongs,
Title Case headings, and stilted literary turns ("and so does a tap on it", "off
means off"). With `--ui`, for READMEs and on-screen text, it also flags clipped
sentences with no articles or pronouns, and lists that mix nouns and adjectives.

It also flags four things across a whole document. They are the same first four
words opening five or more sentences, a document that talks about its own earlier
versions, a paragraph that opens on a pronoun, and an asterisk with no note in its
section. With
`--terms FILE` it flags other names for a thing that has one name.

It also checks each sentence for a lead-in and a hedged figure. The first check
flags a lead-in such as "The following table lists the jobs", which names the
container and not the content. The second flags a hedged planning figure such as
"about 3 to 5 weeks" when the sentence doesn't say where the figure comes from.

`--facts OLD NEW` compares two versions and lists every number, id, link, anchor
and code name that a rewrite lost or added. `--drift OLD NEW` shows whether the
rewrite moved the prose the way model rewrites move it: longer words, small words
cut, contractions written out, more commas, and sentences closer to one length.

Words that models overuse but that are also ordinary English ("pivotal",
"showcase", "dependable") are weak findings. The linter reports them only when two
or more land in one paragraph, and `--all` shows every one.

It skips text in double quotes, so a doc can quote a tell as an example.
`EXAMPLES.md` has real before-and-after rewrites.

It also carries the general AI-writing tells, added where they do not overlap the
personal rules: signposting ("let's dive in"), sycophancy ("great question"),
chatbot artifacts ("I hope this helps"), conversational openers, authority tropes
("at its core"), knowledge-cutoff disclaimers, and decorative emoji. These come
from the "Signs of AI writing" taxonomy that the humanizer skill is based on.

Three things stay out of the linter because no regex decides them, so `SKILL.md`
asks the reader to check them by hand: a strong claim the piece asserts but never
justifies, two clauses in different paragraphs echoing the same shape, and a
sentence that passes every rule but still reads as private shorthand to a newcomer.

## Use it

As a Claude Code skill, invoke `/chrisnizer` on a draft. Or run the linter directly:

```sh
python3 scripts/chrisnizer_lint.py draft.md          # report
python3 scripts/chrisnizer_lint.py --fix draft.md    # apply mechanical fixes
python3 scripts/chrisnizer_lint.py --academic draft.md   # allow we/our for papers
python3 scripts/chrisnizer_lint.py --ui README.md    # also flag clipped text
python3 scripts/chrisnizer_lint.py --neutral doc.md   # team doc: no I/my/we/our
python3 scripts/chrisnizer_lint.py --terms terms.txt doc.md   # one name for one thing
python3 scripts/chrisnizer_lint.py --facts old.md new.md      # what a rewrite lost
python3 scripts/chrisnizer_lint.py --drift old.md new.md      # how a rewrite moved the style
cat draft.md | python3 scripts/chrisnizer_lint.py -  # from stdin
```

Stdlib only, no install, no API keys. It skips code blocks, inline code, and URLs.

## Install as a skill

```sh
ln -sfn "$(pwd)" ~/.claude/skills/chrisnizer
```

## Large documents

`STYLE-BRIEF.md` is a template for a one-page brief that every editor and reviewer
of a long document gets: the readers, the hard rules, the decisions already made,
the one name for each thing, and before-and-after pairs from the document itself.
`SKILL.md` has the rest of the method for large documents.

## Tune it

The word lists are at the top of `scripts/chrisnizer_lint.py` and the judgment rules
are in `VOICE.md`. Both are meant to be edited as I notice more of my own habits.
The words a model overuses change with each model release, so each word list
carries the date it was last checked. Re-check a list against current text before
adding to it. A
longer unedited writing sample would sharpen the rhythm and sentence-length rules;
when I have one it goes in `samples/`.

## Tests

```sh
pytest tests/
```
