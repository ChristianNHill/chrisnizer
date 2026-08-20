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

# Pseudo-cleft abstraction: "X is what should Y" / "the shape is what holds".
# A vague noun stands in for the real subject instead of naming it. Require a
# modal/auxiliary after "what" so this doesn't fire on reported-speech uses
# like "that's what tool descriptions say" or "states what it can access",
# which are plain relative clauses, not a cleft standing in for a subject.
_PSEUDO_CLEFT = re.compile(
    r"\b(?:is|was|are|were)\s+what\s+(?:should|must|has to|have to|need(?:s)?(?:\s+to)?|ought(?:\s+to)?|"
    r"can|could|will|would|holds?|matters?|works?|counts?)\b",
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

PLURAL_FIRST_PERSON = ["we", "our", "ours", "us", "we're", "we've", "we'd", "ourselves"]

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

        if _EMOJI.search(raw):
            findings.append(Finding(i, "emoji", raw.strip()[:80],
                "no decorative emoji in prose"))

        if not academic:
            for hit in _word_hits(m, PLURAL_FIRST_PERSON):
                findings.append(Finding(i, "plural_first_person",
                    f"'{hit}' in: {raw.strip()[:80]}",
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

    def flush_run() -> None:
        if len(run) >= STACCATO_RUN:
            findings.append(Finding(run[0][0], "staccato",
                " / ".join(s[:30] for _, s in run),
                f"{len(run)} short, similarly-shaped sentences in a row; "
                "merge two or vary the shape"))
        run.clear()

    for mtch in re.finditer(r"[^.!?]*[.!?]", full, re.DOTALL):
        s = mtch.group().strip()
        if not s:
            continue
        line = line_of(mtch.start())

        words = s.split()
        opener = _opener(s)
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
        if opener not in _IMPERATIVES and (
            re.search(_passive_by, s, re.I) or re.search(_passive_verbal, s, re.I)
        ):
            findings.append(Finding(line, "passive_voice", s[:90],
                "prefer active voice (name the actor)"))

    flush_run()

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
