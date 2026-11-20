#!/usr/bin/env python3
"""chrisnizer: a deterministic writing linter tuned to Chris Hill's voice.

It does not rewrite. It flags where a draft drifts from the house rules in
VOICE.md and auto-fixes only the mechanical, unambiguous things (curly quotes,
stray Unicode, doubled spaces). Judgment calls (em dashes, filler, passive
voice, dense sentences) are flagged with a suggestion for a human or an agent
to apply in voice.

Usage:
    chrisnizer_lint.py FILE [FILE ...]        # check, human-readable report
    chrisnizer_lint.py --json FILE            # findings as JSON
    chrisnizer_lint.py --fix FILE             # apply mechanical fixes in place
    chrisnizer_lint.py --academic FILE        # allow "we"/"our" (paper mode)
    chrisnizer_lint.py --ui FILE              # also flag clipped text (READMEs, help, UI)
    chrisnizer_lint.py --neutral FILE         # team or stakeholder doc: no I/my/we/our
    chrisnizer_lint.py --terms TERMS FILE     # flag other names for a thing that has one name
    chrisnizer_lint.py --facts OLD NEW        # list numbers, ids, links and code lost in a rewrite
    chrisnizer_lint.py --drift OLD NEW        # show how a rewrite moved the style of the prose
    chrisnizer_lint.py --all FILE             # also report weak findings that stand alone
    cat draft.md | chrisnizer_lint.py -       # read stdin

Stdlib only. Skips fenced code blocks, inline code, URLs, and text in double
quotes, so a doc that quotes a tell as an example is not flagged for it.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict

# --- the ruleset (edit these to tune your own voice) -----------------------

# Filler and intensifiers you cut from AI drafts, so you avoid them in your own.
FILLER = [
    "genuinely", "actually", "really", "simply", "very", "quite", "truly",
    "notably", "importantly", "essentially", "fundamentally", "remarkably",
    "significantly", "arguably", "effectively", "wildly", "silently", "cleanly",
    "quietly", "honestly", "seamlessly", "basically", "literally", "just",
]

# Boosterism and inflated phrasing: state effort and value flatly, do not inflate.
BOOSTERISM = [
    "big lift", "game-?changer", "game changing", "best-in-class", "cutting-edge",
    "state-of-the-art", "world-class", "seamless", "robust", "powerful",
    "delighted to", "thrilled to", "excited to announce", "leverage", "unlock",
    "supercharge", "elevate", "vibrant", "revolutioniz", "groundbreaking",
    "must-have", "next-level", "turbocharge",
]

# The word lists date quickly: which words a model overuses changes with each
# model release. Each list says where it came from and when it was last checked,
# so a stale one can be re-checked against current text instead of grown.

# Generic AI-tell vocabulary (from the humanizer / Wikipedia AI-writing signs).
# Checked 2026-11 against Wikipedia's "Signs of AI writing" and OpenAI's GPT-6
# prompting guide. "crucial", "vital", "underscore" and "boasts" are dated as
# tells but stay here as house style: they inflate.
AI_VOCAB = [
    "delve", "foster", "surfaces", "multifaceted", "nuanced",
    "underscore", "crucial", "vital", "boasts",
    "it is worth noting", "it's worth noting", "that being said",
]

# Weak tier: one of these alone says little, so the linter reports them only when
# two or more land in one paragraph (or with --all).
# 2023 to 2025 model vocabulary, demoted 2026-11. Sources: Wikipedia's "Signs of
# AI writing" lists these under earlier model eras, and Graphite's "AI Tells"
# reports (Sept and Oct 2026) measured the well-known tells falling.
DATED_VOCAB = [
    "testament", "tapestry", "showcase", "garner", "intricate",
    "realm", "interplay", "pivotal", "nestled",
]
# Evaluative adjectives reported for models released in 2026, added 2026-11.
# Source: Graphite's Oct 2026 update (Claude Opus 5.5).
EVALUATIVE = ["dependable", "steady", "thoughtful", "meaningful"]

# stock_frame: sentence frames reported for models released in 2026, added
# 2026-11. Each one announces importance or what comes next without saying it.
# Sources: Graphite's "AI Tells" reports (Sept and Oct 2026) and OpenAI's GPT-6
# prompting guide. The reports were read in summary, so re-check before tuning.
_STOCK_FRAMES = [
    re.compile(r"\bthis matters\b", re.I),
    re.compile(r"\bwhy (?:[\w'-]+ ){1,3}matters\b", re.I),
    re.compile(r"\bmatters (?:most|because|enormously)\b", re.I),
    re.compile(r"\bjust as important\b", re.I),
    re.compile(r"\blooking ahead\b", re.I),
    re.compile(r"\bwhat comes next\b", re.I),
    re.compile(r"\badds? another (?:layer|dimension)\b", re.I),
    re.compile(r"(?:^|[.!?]\s+)together,? these\b", re.I),
    re.compile(r"\bbottom line:", re.I),
    re.compile(r"(?:^|[.!?]\s+)in short[:,]", re.I),
    re.compile(r"\bthe simplest mental model\b", re.I),
]

# Contrast frames reported for models released in 2026, added 2026-11. A plain
# "rather than" comparison is ordinary English and is not flagged. Sources: the
# same Graphite reports and Wikipedia's mid-2026 section.
_CONTRAST_FRAMES = [
    re.compile(r"\brather than (?:simply|merely|just|relying)\b", re.I),
    re.compile(r"\b(?:is|are|was|were) more than (?:a|an|just)\b[^.]{0,50}, (?:it|they)\b", re.I),
    re.compile(r"\b(?:is|are|was|were) not (?:simply|merely)\b", re.I),
    re.compile(r"\bnot only about\b", re.I),
    re.compile(r"\b(?:doesn't|does not) mean\b[^.]{1,80}\.\s+It means\b", re.I),
    re.compile(r"\b(?:isn't|is not) about\b[^.]{1,80}\.\s+It(?:'s| is) about\b", re.I),
]

HEDGES = [
    "could potentially", "might possibly", "it could be argued",
    "it is important to note", "in order to", "somewhat",
    "a bit of a", "sort of", "kind of a",
]
# "rather" is a hedge only on its own ("rather good"), not in "rather than".
_HEDGE_RATHER = re.compile(r"\brather\b(?!\s+than\b)", re.IGNORECASE)

# Pseudo-cleft abstraction: "X is what should Y" / "the shape is what holds".
# A vague noun stands in for the real subject instead of naming it. Require a
# modal/auxiliary after "what" so this doesn't fire on reported-speech uses
# like "that's what tool descriptions say" or "states what it can access",
# which are plain relative clauses, not a cleft standing in for a subject.
_PSEUDO_CLEFT = re.compile(
    r"\b(?:is|was|are|were)\s+what\s+(?:should|must|has to|have to|need(?:s)?(?:\s+to)?|ought(?:\s+to)?|"
    r"can|could|will|would|holds?|matters?|works?|counts?|keeps?|makes?|drives?|lets?|"
    r"decides?|sets?)\b",
    re.IGNORECASE,
)

# Rough finite-verb detector for the fragment_colon check: common copulas,
# auxiliaries, and modals. Deliberately does not pattern-match word endings
# (a plural noun like "signatures" ends in -s but is not a verb).
_HAS_VERB = re.compile(
    r"\b(?:is|are|was|were|be|been|being|am|has|have|had|do|does|did|"
    r"can|could|will|would|shall|should|may|might|must)\b",
    re.IGNORECASE,
)

# A pronoun subject followed by another word is a clause with a subject doing
# something, so the colon line is a sentence, not a verbless headline. Cheaper
# and less brittle than growing _HAS_VERB into a dictionary of every verb.
_PRONOUN_SUBJECT = re.compile(r"\b(?:I|you|we|they|it|he|she|this|that|these|those)\s+\w", re.IGNORECASE)

NEGATIVE_PARALLELISM = [
    "not only", "not just", "isn't just", "it's not just", "not merely",
    "it's not about", "it is not just",
]

# General AI-writing tells from the "Signs of AI writing" taxonomy, added only
# where they do not overlap with the categories above.
SIGNPOSTING = [
    "let's dive in", "lets dive in", "let's explore", "let's break this down",
    "here's what you need to know", "without further ado", "now let's look at",
    "in this article", "dive into", "let's take a look",
]
SYCOPHANCY = [
    "great question", "you're absolutely right", "you are absolutely right",
    "excellent point", "great choice", "i'd be happy to", "happy to help",
]
COLLABORATIVE = [
    "i hope this helps", "let me know if", "would you like me to", "want me to",
    "feel free to", "of course!", "certainly!", "here's a quick",
]
OPENERS = ["here's the thing", "the thing is", "let's be honest", "real talk"]
AUTHORITY_TROPE = [
    "the real question is", "at its core", "what really matters",
    "the deeper issue", "the heart of the matter", "at the end of the day",
    "make no mistake", "in reality,",
]
CUTOFF_DISCLAIMER = [
    "as of my last", "as of my knowledge", "as of my training",
    "while specific details", "based on available information",
    "up to my last update",
]
# Pictographs, flags, and dingbats only. Deliberately excludes math symbols
# (x, degree, approx) so technical prose is not flagged.
_EMOJI = re.compile("[\U0001F300-\U0001FAFF\U0001F1E6-\U0001F1FF\U00002700-\U000027BF\U00002B00-\U00002BFF]")

# stilted: literary or old-fashioned turns that pass every rule above and still read
# oddly to a newcomer ("and so does a tap on it", "off means off", "the garden's
# business", "sits or stands about"). Plain modern English says the same thing flatly.
STILTED = [
    "upon", "amid", "amidst", "whilst", "thereof", "wherein", "whereby", "lest",
    "thus", "hence", "henceforth", "in place of", "in the style of", "a wash of",
]
_STILTED_SHAPES = [
    (re.compile(r"\b(?:and|as) so (?:does|do|did|is|are|was|were)\b", re.I),
     "inverted 'and so does X': say 'X also works'"),
    (re.compile(r"\bas (?:a|an|the) [\w' ]{1,30}? (?:does|do|did)\b", re.I),
     "'as a X does': say 'the way a X does', or 'like a X'"),
    (re.compile(r"\b(\w+) means \1\b", re.I),
     "tautology ('off means off'): say what actually happens"),
    (re.compile(r"\b(?:is|are|was|were) (?:the |its |their )?\w+'s (?:business|affair|concern|lookout)\b", re.I),
     "'is the X's business': say who does it"),
    (re.compile(r"\b(?:stands?|sits?|lies?|push(?:es|ed)?|mills?|lounges?|potters?) about\b", re.I),
     "'about' for 'around': say 'around', or name what happens"),
    (re.compile(r"\bsets? (?:it|them|him|her|you) \w+ing\b", re.I),
     "'sets it wandering': say 'it starts to wander'"),
]

# --ui: text a newcomer reads once (a README, help text, labels) fails by being
# too clipped as often as by being padded. A sentence with no article, possessive
# or pronoun reads as telegraphese ("Closing window ends garden"), and a list
# that mixes nouns with adjectives ("hunger, sleep, tired") reads as unfinished.
TELEGRAPHIC_WORDS = 5
_DETERMINERS = {
    "a", "an", "the", "its", "their", "this", "that", "these", "those", "your",
    "my", "his", "her", "our", "each", "every", "some", "any", "no", "all",
    "it", "they", "you", "i", "we", "he", "she", "them", "me", "us", "one",
}
_ADJ_END = re.compile(r"\w{2,}(?:y|ed|ful|ous|ish|less|ive|able)$")
_NOUN_END = re.compile(r"\w{2,}(?:ion|ness|ment|ity|er|th|ure|dom|ship|ance|ence|st)$")

PLURAL_FIRST_PERSON = ["we", "our", "ours", "us", "we're", "we've", "we'd", "ourselves"]
SINGULAR_FIRST_PERSON = ["I", "me", "my", "mine", "myself", "I'm", "I've", "I'd", "I'll"]

# vague_set: a count or quantity the reader can't check. "The rest", "a few" and
# "two scores" leave the reader asking which ones; name them or give the number.
VAGUE_QUANTITY = [
    "the rest", "the others", "the remaining", "a few", "several", "a handful",
    "a number of", "various", "rarely", "often", "many", "most",
]
# Uses of those words that aren't a vague set: "the rest of this page", "how often",
# "at most", "narrow it most".
_VAGUE_OK = re.compile(r"\bthe rest of\b|\bhow (?:often|many)\b|\bat most\b|\b(?:it|them|this|that) most\b", re.I)
# "most" is only a vague set as a determiner: "most gaps", "most of the rows".
_MOST_DET = re.compile(r"\bmost\s+(?:of\b|[a-z]+s\b)", re.I)
_NUMBER_WORD = r"(?:two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
# "the three", "these two", "both" ... a set referred to by its size alone.
_COUNT_REF = re.compile(rf"\b(?:the|these|those|its|their)\s+{_NUMBER_WORD}\b(?!\s+of\b)", re.I)
# "Two scores have ..." at the start of a sentence: a set named by its size alone.
_COUNT_OPEN = re.compile(rf"^{_NUMBER_WORD}\s+[a-z]+s\b(?!\s+of\b)", re.I)
# A list follows when the sentence has a colon or parenthesis after the count, or
# an "X, Y and Z" run anywhere in it.
_HAS_LIST = re.compile(r"[:(]|\w+, [\w' -]+,? (?:and|or) \w+")

# positional: "above", "upstream", "later stages" point at a place the reader has
# to guess. Name the section, figure, step or people instead.
POSITIONAL = [
    "upstream", "downstream", "aforementioned", "as mentioned", "as noted",
    "earlier stages", "later stages", "the next slide", "the previous slide",
    "the former", "the latter", "see above", "see below",
]
# "above" and "below" are positional unless a number or amount follows ("above 30%").
_ABOVE_BELOW = re.compile(r"\b(?:above|below)\b(?!\s+(?:\$|\d|a |an |the (?:bar|threshold|limit|minimum|maximum)))", re.I)

# dramatic_closer: a punchy summary line built on "nobody" reads as AI copy, and it
# is often not literally true. Say what is and isn't known.
_DRAMATIC_CLOSER = [
    re.compile(r"\b(?:nobody|no one|no-one)\s+(?:has|have|had|knows|knew|measured|tested|checked|noticed|asked|bothered)\b", re.I),
    re.compile(r"\bare the \w+(?: \w+)? (?:that )?(?:nobody|no one)\b", re.I),
    re.compile(r"\bthe (?:one|only) thing (?:that )?(?:matters|counts|nobody)\b", re.I),
]

# fragment: a prose sentence with no subject and verb. Two shapes are reliable:
# one that opens on a past participle ("Labeled 2 of 3 users."), and a noun phrase
# ending in a bare participle ("Counsel review needed before relying on it.").
_PARTICIPLE_OPEN = re.compile(
    r"^(?!Based\b|Compared\b|Combined\b|Assumed\b)(?:[A-Z]\w*ed|Built|Done|Found|Kept|Made|Seen|Sent|Shown|Written|Held|Run)\b(?![-\w])(?!\s+(?:by|to)\b)(?![^,]*,)")
_BARE_PARTICIPLE = re.compile(
    r"^[A-Z][\w' -]{2,40}?\s+(?:needed|required|planned|pending|untested|unmeasured|missing|done|underway)\b", re.I)

# long_paragraph: a paragraph this long usually walks through parallel items
# (options, dependencies, findings) that read better as a table or a list.
LONG_PARAGRAPH_WORDS = 120
LONG_PARAGRAPH_SENTENCES = 6

# repeated_opener: the same first words on many sentences is a template.
REPEATED_OPENER_WORDS = 4
REPEATED_OPENER_MIN = 5

# empty_lead: a lead-in that names the container ("The following table lists")
# before it says anything about the content. One is enough to flag: the reader
# learns more from what a row is. Added 2026-11 from a skill trial.
_EMPTY_LEAD = re.compile(
    r"(?:^|\n)[\s>]*(?:the following (?:table|list|figure|chart|diagram) "
    r"(?:lists|shows|summari[sz]es|presents|outlines|provides|details|displays|illustrates|"
    r"contains|gives)\b"
    r"|(?:below|here) (?:is|are) (?:a|an|the) (?:table|list|summary|overview|breakdown)\b)",
    re.I)

# hedged_number: a hedge on a planning figure with no source in the sentence,
# such as "about 3 to 5 weeks" or "roughly twenty people". It fires on a hedged
# range in any unit, and on a single hedged figure only when it counts time in
# days or longer, people, or money. "About 12 seconds" and "about 0.03 cents"
# are rounded facts far more often than guesses, so they pass. A basis word in
# the sentence also turns the check off. Added 2026-11 from a skill trial.
_NUM = r"[$€£]?\d[\d,.]*%?"
_NUM_WORD = (r"(?:two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|thirty|"
             r"forty|fifty|a hundred|a thousand|a dozen)")
_HEDGE_WORD = (r"(?:about|around|roughly|approximately|approx\.?|nearly|almost|an estimated|"
               r"in the region of|on the order of|somewhere between)")
_PLAN_UNIT = (r"(?:(?:working |business |calendar )?(?:days?|weeks?|months?|quarters?|years?|sprints?)"
              r"|person-\w+|people|engineers?|developers?|staff|FTEs?"
              r"|dollars|euros|pounds|thousand|million|billion|k\b)")
_HEDGED_NUMBER = re.compile(
    rf"\b{_HEDGE_WORD}\s+{_NUM}\s*(?:to|or|and|-)\s*{_NUM}"                  # a hedged range
    rf"|\b{_HEDGE_WORD}\s+(?:{_NUM}|{_NUM_WORD})(?:\s+to\s+{_NUM_WORD})?\s+{_PLAN_UNIT}\b"
    rf"|\b{_HEDGE_WORD}\s+[$€£]\d[\d,.]*"
    rf"|(?<![\w~])~\s?(?:[$€£]\d[\d,.]*|\d[\d,.]*\s+{_PLAN_UNIT}\b)"
    rf"|\b\d[\d,.]*\s+{_PLAN_UNIT}\s+or so\b",
    re.I)
_NUMBER_BASIS = re.compile(
    r"\b(?:measured|counted|estimate[ds]?|calculated|according to|based on)\b", re.I)

# self_history: a document that talks about its own earlier versions. The reader
# wants what is true now, and the change history belongs in a changelog.
_SELF_HISTORY = re.compile(
    r"\b(?:earlier|previous|prior|older) (?:versions?|drafts?) of this "
    r"(?:page|document|doc|report|deck|note|section|brief|plan)\b"
    r"|\bthis (?:page|document|doc|report|deck|note|section|brief|plan) "
    r"(?:now|no longer|previously|used to|formerly|originally)\b"
    r"|\bas (?:previously|originally) (?:stated|reported|written)\b", re.I)

# distant_pronoun: a paragraph that opens on "It is" or "This means". The noun
# the pronoun stands for is in another paragraph, so the reader has to look back.
_PRONOUN_OPEN = re.compile(
    r"^(?:It|This|That|They|These|Those)\s+(?:is|are|was|were|has|have|had|can|could|"
    r"will|would|should|may|might|must|does|do|did|means|meant|makes|made|gives|gave|"
    r"shows|showed|needs|needed|leaves|left|lets|keeps|kept|runs|ran|adds|added|"
    r"happens|happened|works|worked|matters|mattered)\b")

# orphan_asterisk: a footnote marker ("2.4 cents*") in a section with no note
# line that explains it. A section runs to the next heading of level 1 to 3.
_EMPHASIS = re.compile(r"\*\*[^*\n]+\*\*|(?<![\w*])\*[^*\s][^*\n]*?\*(?![\w*])")
_ASTERISK_MARK = re.compile(r"[\w)%\]]\\?\*(?=[\s.,;:|)]|$)")
# A note is a line that opens "Note: *", an escaped "\\* ", or "*: ". A plain
# "* text" line is a list bullet, and "**Bold**" is emphasis, so neither counts.
_ASTERISK_NOTE = re.compile(r"^[\s>]*(?:note:\s*\\?\*(?!\*)|\\\*\s|\*:\s)", re.I)

# --facts: what a rewrite must not lose.
_FACT_KINDS = [
    ("code", re.compile(r"`[^`\n]+`")),
    ("link", re.compile(r"\]\(([^)\s]+)\)|https?://[^\s)>\]]+")),
    ("anchor", re.compile(r"\{#[\w-]+\}")),
    ("id", re.compile(r"\b[A-Z][A-Za-z]*\d*-\d+\b|\b[A-Z]{2,}\d+\b")),
    ("number", re.compile(r"(?<![\w.-])[$€£]?\d+(?:,\d{3})*(?:\.\d+)?%?")),
]

# Mechanical, safe to auto-fix.
MECHANICAL = [
    ("‘", "'"), ("’", "'"), ("“", '"'), ("”", '"'),
    ("…", "..."), (" ", " "), ("​", ""), ("‌", ""),
    ("‍", ""), ("﻿", ""), ("–", " REVIEW_EN_DASH "),
]

LONG_SENTENCE_WORDS = 30

# staccato: a run of short, similarly-shaped sentences reads as a list dressed
# as prose ("It defers... It exposes neither..."). Two is punch, three is a
# pattern. Same shape means the same opening word, or two different pronoun
# subjects doing the same job ("It defers... This exposes...").
STACCATO_RUN = 3
STACCATO_WORDS = 12
STACCATO_PRONOUNS = {"it", "this", "that", "they", "these", "those", "he", "she", "i", "we", "you"}


@dataclass
class Finding:
    line: int
    category: str
    text: str
    suggestion: str
    strength: str = "rule"  # "weak": reported only in a cluster, or with --all


# --- masking: never lint inside code or URLs -------------------------------

_URL = re.compile(r"https?://\S+")
_INLINE_CODE = re.compile(r"`[^`]*`")
_QUOTED = re.compile(r'"[^"\n]*"|\u201c[^\u201d\n]*\u201d')


def _mask_line(line: str) -> str:
    line = _URL.sub(lambda m: " " * len(m.group()), line)
    line = _INLINE_CODE.sub(lambda m: " " * len(m.group()), line)
    line = _QUOTED.sub(lambda m: " " * len(m.group()), line)
    return line


def _word_hits(masked: str, words: list[str]) -> list[str]:
    hits = []
    for w in words:
        if re.search(rf"\b(?:{w})\b", masked, re.IGNORECASE):
            hits.append(w.replace("-?", "").replace("\\", ""))
    return hits


def _phrase_hits(masked: str, phrases: list[str]) -> list[str]:
    low = masked.lower()
    return [p for p in phrases if p.lower() in low]


def _mixed_list(sentence: str) -> bool:
    """A run of three or more one- or two-word list items where some end like
    adjectives and others like nouns."""
    parts = re.split(r",\s*|\s+(?:and|or)\s+", sentence.strip(" .!?"))
    best = run = []
    for part in parts:
        run = run + [part] if 0 < len(part.split()) <= 2 else []
        best = run if len(run) > len(best) else best
    if len(best) < 3:
        return False
    last = [p.split()[-1].lower() for p in best]
    nouns = {w for w in last if _NOUN_END.match(w)}
    return bool(nouns) and any(_ADJ_END.match(w) for w in last if w not in nouns)


def load_terms(path: str) -> dict[str, list[str]]:
    """Read a terms file: one 'canonical name: other name, other name' per line."""
    terms: dict[str, list[str]] = {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        name, others = line.split(":", 1)
        terms[name.strip()] = [o.strip() for o in others.split(",") if o.strip()]
    return terms


def _prose_lines(text: str) -> list[str]:
    """Every line, with fenced code blanked and inline code, URLs and quotes masked."""
    out, in_fence = [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append("")
            continue
        out.append("" if in_fence else _mask_line(line))
    return out


def _term_drift(lines: list[str], terms: dict[str, list[str]]) -> list[Finding]:
    found = []
    for name, others in terms.items():
        for other in others:
            pattern = re.compile(rf"(?<![\w-]){re.escape(other)}(?:e?s)?(?![\w-])", re.I)
            hits = [i for i, ln in enumerate(lines, 1)
                    if not ln.lstrip().startswith("#") and pattern.search(ln)]
            if hits:
                where = ", ".join(f"L{i}" for i in hits[:8]) + (" ..." if len(hits) > 8 else "")
                found.append(Finding(hits[0], "term_drift",
                    f"'{other}' on {len(hits)} lines: {where}",
                    f"the terms file names this '{name}'; use one name for one thing"))
    return found


def _orphan_asterisks(text: str) -> list[Finding]:
    found = []
    section: list[tuple[int, str]] = []

    def flush() -> None:
        marks = [(i, ln) for i, ln in section
                 if _ASTERISK_MARK.search(_EMPHASIS.sub(" ", _INLINE_CODE.sub(" ", ln)))
                 and not _ASTERISK_NOTE.match(ln)]
        if marks and not any(_ASTERISK_NOTE.match(ln) for _, ln in section):
            found.append(Finding(marks[0][0], "orphan_asterisk", marks[0][1].strip()[:80],
                f"{len(marks)} lines carry an asterisk and this section has no note that "
                "explains it; add the note or drop the marker"))
        section.clear()

    in_fence = False
    for i, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if re.match(r"#{1,3}\s", line):  # a sub-heading (####) stays in its section
            flush()
            continue
        section.append((i, line))
    flush()
    return found


def facts(text: str) -> dict[str, dict[str, int]]:
    """Count each number, id, link, anchor and code span in a document."""
    counts: dict[str, dict[str, int]] = {kind: {} for kind, _ in _FACT_KINDS}
    for kind, pattern in _FACT_KINDS:
        for m in pattern.finditer(text):
            value = m.group(1) if kind == "link" and m.group(1) else m.group()
            counts[kind][value] = counts[kind].get(value, 0) + 1
        # a later kind must not count text that an earlier kind already owns
        text = pattern.sub(" ", text)
    return counts


def compare_facts(old: str, new: str) -> tuple[list[str], list[str]]:
    """Return (lost, added) lines describing how the facts differ between two versions."""
    before, after = facts(old), facts(new)
    lost, added = [], []
    for kind, _ in _FACT_KINDS:
        for value in sorted(set(before[kind]) | set(after[kind])):
            b, a = before[kind].get(value, 0), after[kind].get(value, 0)
            if a < b:
                lost.append(f"{kind:<7} {value}  ({b} -> {a})")
            elif a > b:
                added.append(f"{kind:<7} {value}  ({b} -> {a})")
    return lost, added


def _drop_lone_weak(findings: list[Finding], text: str) -> list[Finding]:
    """Keep a weak finding only when its paragraph holds two or more of them."""
    para_of, para = {}, 0
    for i, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            para += 1
        para_of[i] = para
    counts: dict[int, int] = {}
    for f in findings:
        if f.strength == "weak":
            counts[para_of.get(f.line, -1)] = counts.get(para_of.get(f.line, -1), 0) + 1
    return [f for f in findings
            if f.strength != "weak" or counts[para_of.get(f.line, -1)] >= 2]


_FUNCTION_WORDS = set("""a an the this that these those and but or so if because as of to in on at
by for with from into about than then there here it its he she they them his her their we us
our you your i me my is are was were be been being am do does did has have had not no can
could will would shall should may might must which who whom whose what when where why how
also just only very more most some any each every all both either neither""".split())
_CONTRACTION = re.compile(
    r"\b(?:\w+n't|\w+'(?:re|ve|ll|d|m)|(?:it|that|there|what|here|let|he|she|who)'s)\b", re.I)

# Each metric: name, the direction a model rewrite moves it, and a note on what moved.
_DRIFT_METRICS = [
    ("letters per word", +1, "longer words"),
    ("word variety", +1, "fewer repeated words; check that one thing still has one name"),
    ("function words, share", -1, "small words cut (that, the, of)"),
    ("contractions per 1,000 words", -1, "contractions written out"),
    ("commas per sentence", +1, "more commas"),
    ("dashes per 1,000 words", +1, "more dashes"),
    ("sentence length spread", -1, "sentences closer to one length"),
]
DRIFT_THRESHOLD = 0.10  # a relative change this large, in the model direction, is flagged


def style(text: str) -> dict[str, float]:
    """Measure the prose of a document: words, small words, punctuation and rhythm."""
    lines = [ln for ln in _prose_lines(text)
             if ln.strip() and not ln.lstrip().startswith(("#", "|", ":::", "!["))
             and not re.fullmatch(r"\s*[-*_=]{3,}\s*", ln)]  # rules and frontmatter fences
    # drop list markers and block-quote marks, so a "- item" bullet is not a dash
    prose = " ".join(re.sub(r"^[\s>]*(?:[-*+]|\d+[.)])?\s+", "", ln) for ln in lines)
    words = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", prose)
    low = [w.lower() for w in words]
    n = max(len(words), 1)
    sentences = [x for x in re.split(r"(?<=[.!?])\s+", prose) if len(x.split()) >= 2]
    lengths = [len(x.split()) for x in sentences] or [0]
    mean = sum(lengths) / len(lengths)
    spread = ((sum((v - mean) ** 2 for v in lengths) / len(lengths)) ** 0.5 / mean) if mean else 0.0
    window = 50  # variety: share of distinct words, averaged over 50-word windows
    if len(low) >= window:
        steps = range(0, len(low) - window + 1, 10)
        variety = sum(len(set(low[k:k + window])) / window for k in steps) / len(steps)
    else:
        variety = len(set(low)) / n
    return {
        "letters per word": sum(len(w.replace("'", "")) for w in words) / n,
        "word variety": variety,
        "function words, share": sum(w in _FUNCTION_WORDS for w in low) / n,
        "contractions per 1,000 words": 1000 * len(_CONTRACTION.findall(prose)) / n,
        "commas per sentence": prose.count(",") / max(len(sentences), 1),
        "dashes per 1,000 words": 1000 * len(re.findall(r"—|–|\s-\s|--", prose)) / n,
        "sentence length spread": spread,
    }


def compare_style(old: str, new: str) -> list[tuple[str, float, float, str]]:
    """Return (metric, old value, new value, note) rows; the note is empty unless
    the rewrite moved the metric the way model rewrites move it."""
    before, after = style(old), style(new)
    rows = []
    for name, direction, note in _DRIFT_METRICS:
        b, a = before[name], after[name]
        change = (a - b) / b if b else (1.0 if a else 0.0)
        rows.append((name, b, a, note if change * direction >= DRIFT_THRESHOLD else ""))
    return rows


def lint(text: str, academic: bool = False, ui: bool = False, neutral: bool = False,
         terms: dict[str, list[str]] | None = None, all_weak: bool = False) -> list[Finding]:
    findings: list[Finding] = []
    in_fence = False
    all_lines = text.splitlines()
    for i, raw in enumerate(all_lines, 1):
        if raw.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _mask_line(raw)
        if m.lstrip().startswith("|"):
            continue  # markdown table row: data, not prose

        for ch, name in ((("—"), "em dash"), (("–"), "en dash")):
            if ch in m:
                findings.append(Finding(i, "em_dash",
                    f"{name} in: {raw.strip()[:80]}",
                    "house style: use a comma, period, colon or parentheses, or restructure; "
                    "vary the replacement"))

        for cat, words, sug in (
            ("filler", FILLER, "cut it or say it plainly"),
            ("ai_vocab", AI_VOCAB, "plain word instead"),
        ):
            for hit in _word_hits(m, words):
                findings.append(Finding(i, cat, f"'{hit}' in: {raw.strip()[:80]}", sug))

        for cat, phrases, sug in (
            ("boosterism", BOOSTERISM, "no inflated phrasing; state it flatly"),
            ("hedge", HEDGES, "say it directly; you write matter-of-fact"),
            ("negative_parallelism", NEGATIVE_PARALLELISM, "make it one plain clause"),
        ):
            for hit in _phrase_hits(m, phrases):
                findings.append(Finding(i, cat, f"'{hit}' in: {raw.strip()[:80]}", sug))

        for hit in _word_hits(m, DATED_VOCAB + EVALUATIVE):
            findings.append(Finding(i, "weak_vocab", f"'{hit}' in: {raw.strip()[:80]}",
                "two or more of these in one paragraph read as model text; use the plain word",
                strength="weak"))

        for pattern in _STOCK_FRAMES:
            if pattern.search(m):
                findings.append(Finding(i, "stock_frame",
                    f"'{pattern.search(m).group().strip(' .!?')}' in: {raw.strip()[:80]}",
                    "the frame announces a point without making it; say what matters and why, "
                    "or what happens next"))
        for pattern in _CONTRAST_FRAMES:
            if pattern.search(m):
                findings.append(Finding(i, "negative_parallelism",
                    f"'{pattern.search(m).group()[:40]}' in: {raw.strip()[:80]}",
                    "say what the thing is in one plain clause; drop the set-up it is contrasted with"))

        if _HEDGE_RATHER.search(m):
            findings.append(Finding(i, "hedge", f"'rather' in: {raw.strip()[:80]}",
                "say it directly; 'rather than' comparisons are fine"))

        if _PSEUDO_CLEFT.search(m):
            findings.append(Finding(i, "pseudo_cleft", raw.strip()[:80],
                "name the real subject and verb directly, drop the 'is what' hedge"))

        for cat, phrases, sug in (
            ("signposting", SIGNPOSTING, "do the thing instead of announcing it"),
            ("sycophancy", SYCOPHANCY, "drop the flattery; get to the content"),
            ("collaborative_artifact", COLLABORATIVE, "chatbot correspondence; cut it from the content"),
            ("conversational_opener", OPENERS, "just say the point"),
            ("authority_trope", AUTHORITY_TROPE, "state the claim plainly, no ceremony"),
            ("cutoff_disclaimer", CUTOFF_DISCLAIMER, "say what is or isn't known, or cut it"),
        ):
            for hit in _phrase_hits(m, phrases):
                findings.append(Finding(i, cat, f"'{hit}' in: {raw.strip()[:80]}", sug))

        for hit in _word_hits(m, STILTED):
            findings.append(Finding(i, "stilted", f"'{hit}' in: {raw.strip()[:80]}",
                "literary turn; say it the plain modern way"))
        for shape, sug in _STILTED_SHAPES:
            if shape.search(m):
                findings.append(Finding(i, "stilted", raw.strip()[:80], sug))

        if _EMOJI.search(raw):
            findings.append(Finding(i, "emoji", raw.strip()[:80],
                "no decorative emoji in prose"))

        if neutral and not m.lstrip().startswith("#"):
            for hit in [w for w in SINGULAR_FIRST_PERSON if re.search(rf"(?<!Appendix )(?<!Part )(?<!Section )(?<!Phase )(?<!Stage )(?<![\w']){re.escape(w)}(?![\w'])", m)]:
                findings.append(Finding(i, "first_person",
                    f"'{hit}' in: {raw.strip()[:80]}",
                    "neutral voice for team and stakeholder docs: name the doc, the team or the thing"))

        if not m.lstrip().startswith("#") and _SELF_HISTORY.search(m):
            findings.append(Finding(i, "self_history",
                f"'{_SELF_HISTORY.search(m).group()}' in: {raw.strip()[:80]}",
                "say what is true now; the document's own history belongs in a changelog"))

        if not m.lstrip().startswith("#"):
            for hit in _phrase_hits(m, POSITIONAL):
                findings.append(Finding(i, "positional", f"'{hit}' in: {raw.strip()[:80]}",
                    "say which section, figure, step or people you mean"))
            if _ABOVE_BELOW.search(m):
                findings.append(Finding(i, "positional", f"'{_ABOVE_BELOW.search(m).group()}' in: {raw.strip()[:80]}",
                    "say which section, figure, step or people you mean"))
            for pattern in _DRAMATIC_CLOSER:
                if pattern.search(m):
                    findings.append(Finding(i, "dramatic_closer", raw.strip()[:80],
                        "punchy 'nobody' line; check it is literally true and say what is known instead"))
                    break

        if not academic or neutral:
            for hit in _word_hits(m, PLURAL_FIRST_PERSON):
                findings.append(Finding(i, "plural_first_person",
                    f"'{hit}' in: {raw.strip()[:80]}",
                    "neutral voice for team docs" if neutral else
                    "first person singular (I/my) for solo writing; use --academic for papers"))

        # verbless fragment previewing a list: "Three fingerprints, all built
        # from signatures:" reads like dramatic copy, not a sentence.
        if raw.rstrip().endswith(":") and not raw.lstrip().startswith(("#", "-", "*", ">", "|")):
            clause = raw.rstrip()[:-1].strip()
            words = clause.split()
            # "," narrows this to the apposition/participle shape ("Three X,
            # all built from Y:") rather than any short verbless clause, since
            # an ordinary complete sentence can end in a colon before a list.
            # The tell is a verbless headline previewing a LIST, so require a list to
            # follow. A colon handing off to a code block or to explanatory prose is
            # structural, and flagging those removes punctuation the document needs.
            following = next((l for l in all_lines[i:] if l.strip()), "").lstrip()
            previews_a_list = bool(re.match(r"(?:[-*+]\s|\d+[.)]\s)", following))
            # Five words, not three: a short pointer ("Four questions, in order:") is
            # navigation, while the tell carries a modifier phrase ("Three fingerprints,
            # all built from signatures:").
            has_comma_fragment = (
                len(words) >= 5
                and "," in clause
                and previews_a_list
                and not _HAS_VERB.search(clause)
                and not _PRONOUN_SUBJECT.search(clause)
            )
            # "X is real:" has a copula but is the same dramatic-assertion
            # tell used to preview a list ("The Batch API is real:").
            is_real_assertion = re.search(r"\bis real$", clause, re.IGNORECASE)
            if has_comma_fragment or is_real_assertion:
                findings.append(Finding(i, "fragment_colon", raw.strip()[:80],
                    "drop the dramatic assertion; state the point plainly"))

        # label-style bullet where a flowing sentence would read better
        if re.match(r"\s*[-*]\s+\*\*[^*]+:\*\*", raw):
            findings.append(Finding(i, "label_bullet", raw.strip()[:80],
                "you prefer flowing paragraphs to labelled fragments for narrative"))

        # Title Case heading
        h = re.match(r"#{1,6}\s+(.+)", raw)
        if h:
            words = [w for w in h.group(1).split() if w[:1].isalpha()]
            capped = [w for w in words if w[:1].isupper()]
            if len(words) >= 3 and len(capped) >= len(words) - 1:
                findings.append(Finding(i, "title_case_heading", raw.strip()[:80],
                    "sentence case: capitalise the first word only"))

        # curly quotes / stray unicode present (mechanical)
        if any(ch in raw for ch, _ in MECHANICAL if ch not in ("–",)):
            findings.append(Finding(i, "mechanical", raw.strip()[:80],
                "run --fix to normalise quotes and stray characters"))

    # sentence-level: length and passive voice, with real line numbers.
    # Non-prose lines (code, headings, lists, tables) are blanked but kept, so
    # character offsets still map back to source line numbers.
    masked_lines: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            masked_lines.append(" " * len(line))
            continue
        if in_fence or not line.strip() or line.lstrip().startswith(("#", "-", "*", "|", ">")):
            masked_lines.append(" " * len(line))
        else:
            masked_lines.append(_mask_line(line))
    full = "\n".join(masked_lines)
    line_starts = [0]
    for ln in masked_lines:
        line_starts.append(line_starts[-1] + len(ln) + 1)

    def line_of(offset: int) -> int:
        import bisect
        return bisect.bisect_right(line_starts, offset)

    _aux = r"\b(?:is|are|was|were|be|been|being)\b\s+"
    _passive_by = _aux + r"\w+(?:ed|en)\b\s+by\b"
    _verbal = (
        r"(?:shown|made|done|given|taken|seen|built|sent|held|put|written|"
        r"drawn|known|found|kept|told|brought|bought|caught|sold|paid|read|"
        r"processed|generated|computed|scored|produced|blocked|recorded|"
        r"executed|repaired|filled|closed|stored|returned|applied)"
    )
    _passive_verbal = _aux + _verbal + r"\b"

    # Imperative sentences ("Run this to...", "Add a tool that...") are already
    # active by construction, there's no unnamed actor to name. Skip the
    # passive check when the sentence opens on a bare imperative verb.
    _IMPERATIVES = {
        "run", "add", "set", "change", "use", "try", "see", "open", "type",
        "pass", "check", "make", "give", "keep", "read", "write", "call",
        "build", "install", "enable", "configure", "verify", "confirm",
        "look", "turn", "start", "stop", "delete", "remove", "update", "edit",
        "create", "put", "move", "copy", "paste", "save", "load", "clear",
        "reset", "point", "compare", "measure", "record", "grep", "find",
    }

    def _opener(sentence: str) -> str:
        w = sentence.split()
        return w[0].lower().strip(",;:\"'()") if w else ""

    def _same_shape(a: str, b: str) -> bool:
        return a == b or (a in STACCATO_PRONOUNS and b in STACCATO_PRONOUNS)

    run: list[tuple[int, str]] = []  # (line, sentence) for the current staccato run
    openers: dict[str, list[int]] = {}  # first words of a sentence -> lines that use them

    def flush_run() -> None:
        if len(run) >= STACCATO_RUN:
            findings.append(Finding(run[0][0], "staccato",
                " / ".join(s[:30] for _, s in run),
                f"{len(run)} short, similarly-shaped sentences in a row; "
                "merge two or vary the shape"))
        run.clear()

    # A sentence ends at . ! or ? followed by space or the end, so "2.7 million"
    # and "et al. (2024)" do not split one sentence into fragments.
    for mtch in re.finditer(r".+?(?:(?<!\bal)(?<!\be\.g)(?<!\bi\.e)[.!?](?=\s|$)|$)", full, re.DOTALL):
        s = mtch.group().strip()
        if not s:
            continue
        line = line_of(mtch.start() + len(mtch.group()) - len(mtch.group().lstrip()))

        words = s.split()
        opener = _opener(s)
        if len(words) > REPEATED_OPENER_WORDS:
            key = " ".join(w.lower().strip(",;:\"'()") for w in words[:REPEATED_OPENER_WORDS])
            openers.setdefault(key, []).append(line)
        lead = _EMPTY_LEAD.search(s)
        if lead:
            findings.append(Finding(line, "empty_lead", f"'{lead.group().strip()}' in: {s[:80]}",
                "the lead names the container before the content; say what each row or item "
                "is, such as 'Each row is one option:'"))
        hedged = _HEDGED_NUMBER.search(s)
        if hedged and not _NUMBER_BASIS.search(s):
            findings.append(Finding(line, "hedged_number", f"'{hedged.group()}' in: {s[:80]}",
                "a hedged planning figure with no source in the sentence; say what it rests "
                "on. Deleting the hedge or adding 'estimated' with no source is not a fix"))
        if len(words) <= STACCATO_WORDS and (not run or _same_shape(_opener(run[-1][1]), opener)):
            run.append((line, s))
        else:
            flush_run()
            if len(words) <= STACCATO_WORDS:
                run.append((line, s))
        # count the clause before a colon: a "sentence: a, b, c" list is long
        # because of the list, not because it packs several ideas.
        head = s.split(":", 1)[0]
        n = len(head.split()) if ":" in s else len(s.split())
        if n > LONG_SENTENCE_WORDS:
            findings.append(Finding(line, "long_sentence", s[:90],
                f"{n} words; one idea per sentence, consider splitting"))
        if ui and n >= TELEGRAPHIC_WORDS and ":" not in s and opener not in _IMPERATIVES and not (
            {w.lower().strip(",;:\"'()") for w in words} & _DETERMINERS
        ):
            findings.append(Finding(line, "telegraphic", s[:90],
                "no article, possessive or pronoun; put back the small words a newcomer needs"))
        if ui and _mixed_list(s):
            findings.append(Finding(line, "mixed_list", s[:90],
                "the list mixes nouns and adjectives; make every item the same kind of word"))
        s_ok = _VAGUE_OK.sub(" ", s)
        vague = [w for w in VAGUE_QUANTITY if w != "most" and re.search(rf"\b{w}\b", s_ok, re.I)]
        if _MOST_DET.search(s_ok):
            vague.append("most")
        count = _COUNT_REF.search(s) or _COUNT_OPEN.search(s)
        if count and _HAS_LIST.search(s[count.start():]):
            count = None
        if vague or count:
            what = ", ".join(f"'{w}'" for w in vague) or f"'{count.group()}'"
            findings.append(Finding(line, "vague_set", f"{what} in: {s[:80]}",
                "name the items or give the count, so the reader can check it"))
        if 3 <= len(words) and not _HAS_VERB.search(s) and (
            _PARTICIPLE_OPEN.search(s) or (len(words) <= 10 and _BARE_PARTICIPLE.search(s))
        ):
            findings.append(Finding(line, "fragment", s[:90],
                "no subject and verb; write it as a full sentence"))
        if opener not in _IMPERATIVES and (
            re.search(_passive_by, s, re.I) or re.search(_passive_verbal, s, re.I)
        ):
            findings.append(Finding(line, "passive_voice", s[:90],
                "prefer active voice (name the actor), unless a forced active reads worse"))

    flush_run()

    for key, lines in openers.items():
        if len(lines) >= REPEATED_OPENER_MIN:
            where = ", ".join(f"L{n}" for n in lines[:8]) + (" ..." if len(lines) > 8 else "")
            findings.append(Finding(lines[0], "repeated_opener",
                f"'{key} ...' opens {len(lines)} sentences: {where}",
                "the same frame reads as a template; say what each one is about instead"))

    # paragraph-level: a long block of prose usually walks through parallel items.
    para: list[str] = []
    start = 0
    for idx, ln in enumerate(masked_lines + [""], 1):
        if ln.strip() and not ln.lstrip().startswith(("![", ":::")):
            if not para:
                start = idx
            para.append(ln)
            continue
        if para:
            body = " ".join(para)
            if _PRONOUN_OPEN.match(body.strip()):
                findings.append(Finding(start, "distant_pronoun", body.strip()[:80],
                    "the paragraph opens on a pronoun whose noun is in another paragraph; "
                    "name the thing"))
            n_words = len(body.split())
            n_sent = len(re.findall(r"[.!?](?=\s|$)", body))
            if n_words > LONG_PARAGRAPH_WORDS or n_sent > LONG_PARAGRAPH_SENTENCES:
                findings.append(Finding(start, "long_paragraph",
                    body.strip()[:80],
                    f"{n_words} words, {n_sent} sentences; if it walks through options or other "
                    "parallel items, use a table or a list"))
            para = []

    findings.extend(_orphan_asterisks(text))
    if terms:
        findings.extend(_term_drift(_prose_lines(text), terms))

    return findings if all_weak else _drop_lone_weak(findings, text)


def _strip_code(text: str) -> str:
    out, in_fence = [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append("")
            continue
        out.append("" if in_fence else _INLINE_CODE.sub(" ", line))
    return "\n".join(out)


def apply_mechanical(text: str) -> tuple[str, int]:
    n = 0
    for src, dst in MECHANICAL:
        if src == "–":  # en dash is a review flag, not an auto-fix
            continue
        c = text.count(src)
        if c:
            text = text.replace(src, dst)
            n += c
    fixed = re.sub(r"[ \t]+$", "", text, flags=re.M)      # trailing whitespace
    if fixed != text:
        n += 1
    text = fixed
    collapsed = re.sub(r"(\S)  +(\S)", r"\1 \2", text)     # doubled spaces mid-line
    if collapsed != text:
        n += 1
    return collapsed, n


def _report(path: str, findings: list[Finding]) -> None:
    if not findings:
        print(f"{path}: clean")
        return
    print(f"{path}: {len(findings)} findings")
    by_cat: dict[str, int] = {}
    for f in findings:
        by_cat[f.category] = by_cat.get(f.category, 0) + 1
    print("  " + "  ".join(f"{k}={v}" for k, v in sorted(by_cat.items(), key=lambda x: -x[1])))
    for f in findings:
        loc = f"L{f.line}" if f.line else "  "
        print(f"  {loc:<5} {f.category:<20} {f.text}")
        print(f"        -> {f.suggestion}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="chrisnizer")
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fix", action="store_true", help="apply mechanical fixes in place")
    ap.add_argument("--academic", action="store_true", help="allow we/our (paper mode)")
    ap.add_argument("--ui", action="store_true", help="also flag clipped text: READMEs, help, UI")
    ap.add_argument("--neutral", action="store_true",
                    help="team or stakeholder doc: flag I/my as well as we/our")
    ap.add_argument("--terms", metavar="TERMS",
                    help="terms file, 'canonical: other, other' per line; flag the other names")
    ap.add_argument("--facts", action="store_true",
                    help="take two paths, OLD and NEW, and list the numbers, ids, links, "
                         "anchors and code spans that the rewrite lost or added")
    ap.add_argument("--drift", action="store_true",
                    help="take two paths, OLD and NEW, and show how the rewrite moved word "
                         "length, small words, punctuation and sentence rhythm")
    ap.add_argument("--all", action="store_true",
                    help="also report weak findings that stand alone in their paragraph")
    args = ap.parse_args(argv)

    if args.drift:
        if len(args.paths) != 2:
            ap.error("--drift takes two paths: OLD NEW")
        old, new = (open(p, encoding="utf-8").read() for p in args.paths)
        rows = compare_style(old, new)
        if args.json:
            print(json.dumps([{"metric": m, "old": b, "new": a, "drift": note}
                              for m, b, a, note in rows], indent=2))
        else:
            flagged = sum(bool(note) for *_, note in rows)
            print(f"drift: {flagged} of {len(rows)} measures moved the way model rewrites move them")
            for m, b, a, note in rows:
                print(f"  {m:<30} {b:>7.2f} -> {a:>7.2f}  {('<- ' + note) if note else ''}")
        return 0

    if args.facts:
        if len(args.paths) != 2:
            ap.error("--facts takes two paths: OLD NEW")
        old, new = (open(p, encoding="utf-8").read() for p in args.paths)
        lost, added = compare_facts(old, new)
        if args.json:
            print(json.dumps({"lost": lost, "added": added}, indent=2))
        else:
            for title, rows in (("lost", lost), ("added", added)):
                print(f"{title}: {len(rows)}")
                for row in rows:
                    print(f"  {row}")
        return 1 if lost else 0

    terms = load_terms(args.terms) if args.terms else None

    all_json = {}
    total = 0
    for path in args.paths:
        text = sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read()
        if args.fix and path != "-":
            fixed, n = apply_mechanical(text)
            if n:
                open(path, "w", encoding="utf-8").write(fixed)
            text = fixed
        findings = lint(text, academic=args.academic, ui=args.ui, neutral=args.neutral,
                        terms=terms, all_weak=args.all)
        total += len(findings)
        if args.json:
            all_json[path] = [asdict(f) for f in findings]
        else:
            _report(path, findings)
            if args.fix:
                print(f"  (mechanical fixes applied)")

    if args.json:
        print(json.dumps(all_json, indent=2))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
