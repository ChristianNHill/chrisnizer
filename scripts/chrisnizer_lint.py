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
    cat draft.md | chrisnizer_lint.py -       # read stdin

Stdlib only. Skips fenced code blocks, inline code, and URLs.
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

# Generic AI-tell vocabulary (from the humanizer / Wikipedia AI-writing signs).
AI_VOCAB = [
    "delve", "underscore", "testament", "tapestry", "showcase", "foster",
    "garner", "intricate", "realm", "interplay", "multifaceted", "nuanced",
    "crucial", "vital", "pivotal", "boasts", "nestled", "in the realm of",
    "it is worth noting", "it's worth noting", "that being said",
]

HEDGES = [
    "could potentially", "might possibly", "it could be argued",
    "it is important to note", "in order to", "somewhat",
    "a bit of a", "sort of", "kind of a",
]
# "rather" is a hedge only on its own ("rather good"), not in "rather than".
_HEDGE_RATHER = re.compile(r"\brather\b(?!\s+than\b)", re.IGNORECASE)

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

PLURAL_FIRST_PERSON = ["we", "our", "ours", "us", "we're", "we've", "we'd", "ourselves"]

# Mechanical, safe to auto-fix.
MECHANICAL = [
    ("‘", "'"), ("’", "'"), ("“", '"'), ("”", '"'),
    ("…", "..."), (" ", " "), ("​", ""), ("‌", ""),
    ("‍", ""), ("﻿", ""), ("–", " REVIEW_EN_DASH "),
]

LONG_SENTENCE_WORDS = 30


@dataclass
class Finding:
    line: int
    category: str
    text: str
    suggestion: str


# --- masking: never lint inside code or URLs -------------------------------

_URL = re.compile(r"https?://\S+")
_INLINE_CODE = re.compile(r"`[^`]*`")


def _mask_line(line: str) -> str:
    line = _URL.sub(lambda m: " " * len(m.group()), line)
    line = _INLINE_CODE.sub(lambda m: " " * len(m.group()), line)
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


def lint(text: str, academic: bool = False) -> list[Finding]:
    findings: list[Finding] = []
    in_fence = False
    for i, raw in enumerate(text.splitlines(), 1):
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
                    "replace with a comma, period, or colon; you avoid dashes"))

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

        if _HEDGE_RATHER.search(m):
            findings.append(Finding(i, "hedge", f"'rather' in: {raw.strip()[:80]}",
                "say it directly; 'rather than' comparisons are fine"))

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

        if _EMOJI.search(raw):
            findings.append(Finding(i, "emoji", raw.strip()[:80],
                "no decorative emoji in prose"))

        if not academic:
            for hit in _word_hits(m, PLURAL_FIRST_PERSON):
                findings.append(Finding(i, "plural_first_person",
                    f"'{hit}' in: {raw.strip()[:80]}",
                    "first person singular (I/my) for solo writing; use --academic for papers"))

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

    # sentence-level: length and passive voice, across the whole prose
    prose = "\n".join(
        l for l in _strip_code(text).splitlines()
        if l.strip() and not l.lstrip().startswith(("#", "-", "*", "|", ">"))
    )
    for sent in re.split(r"(?<=[.!?])\s+", prose):
        s = _mask_line(sent).strip()
        if not s:
            continue
        n = len(s.split())
        if n > LONG_SENTENCE_WORDS:
            findings.append(Finding(0, "long_sentence", sent.strip()[:90],
                f"{n} words; one idea per sentence, consider splitting"))
        # High precision: a "by" agent, or a clearly verbal participle. This
        # skips predicate adjectives like "is unsupported" or "is watertight".
        _aux = r"\b(?:is|are|was|were|be|been|being)\b\s+"
        _passive_by = _aux + r"\w+(?:ed|en)\b\s+by\b"
        _verbal = (
            r"(?:shown|made|done|given|taken|seen|built|sent|held|put|written|"
            r"drawn|known|found|kept|told|brought|bought|caught|sold|paid|read|"
            r"processed|generated|computed|scored|produced|blocked|recorded|"
            r"executed|repaired|filled|closed|stored|returned|applied)"
        )
        _passive_verbal = _aux + _verbal + r"\b"
        if re.search(_passive_by, s, re.I) or re.search(_passive_verbal, s, re.I):
            findings.append(Finding(0, "passive_voice", sent.strip()[:90],
                "prefer active voice (name the actor)"))

    return findings


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
    args = ap.parse_args(argv)

    all_json = {}
    total = 0
    for path in args.paths:
        text = sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read()
        if args.fix and path != "-":
            fixed, n = apply_mechanical(text)
            if n:
                open(path, "w", encoding="utf-8").write(fixed)
            text = fixed
        findings = lint(text, academic=args.academic)
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
