# chrisnizer

If you want to sound more human, or really, more like me, this skill does that. It
is a writing linter tuned to my own voice, packaged as a Claude Code skill. It finds
where a draft drifts into AI-writing tells or away from my house rules, and fixes the
mechanical parts, so a draft comes back sounding like me instead of like a model.

It does not rewrite on its own. The linter flags; I (or an agent running the skill)
apply the judgment calls in voice. The rules live in [`VOICE.md`](VOICE.md), built
from three sources: samples of my own solo writing, the AI-writing tells a humanizer
catches, and the register of my research papers.

## What it catches

Auto-fixed with `--fix`: curly quotes, stray Unicode, doubled spaces, trailing
whitespace.

Flagged for me to apply in voice: em dashes, filler and boosterism, hedging,
negative parallelism ("not just X but Y"), passive voice, sentences that run past
one idea, first person plural in solo writing, labelled bullet fragments where a
paragraph belongs, and Title Case headings.

It also carries the general AI-writing tells, added where they do not overlap the
personal rules: signposting ("let's dive in"), sycophancy ("great question"),
chatbot artifacts ("I hope this helps"), conversational openers, authority tropes
("at its core"), knowledge-cutoff disclaimers, and decorative emoji. These come
from the "Signs of AI writing" taxonomy that the humanizer skill is based on.

## Use it

As a Claude Code skill, invoke `/chrisnizer` on a draft. Or run the linter directly:

```sh
python3 scripts/chrisnizer_lint.py draft.md          # report
python3 scripts/chrisnizer_lint.py --fix draft.md    # apply mechanical fixes
python3 scripts/chrisnizer_lint.py --academic draft.md   # allow we/our for papers
cat draft.md | python3 scripts/chrisnizer_lint.py -  # from stdin
```

Stdlib only, no install, no API keys. It skips code blocks, inline code, and URLs.

## Install as a skill

```sh
ln -sfn "$(pwd)" ~/.claude/skills/chrisnizer
```

## Tune it

The word lists are at the top of `scripts/chrisnizer_lint.py` and the judgment rules
are in `VOICE.md`. Both are meant to be edited as I notice more of my own habits. A
longer unedited writing sample would sharpen the rhythm and sentence-length rules;
when I have one it goes in `samples/`.

## Tests

```sh
pytest tests/
```
