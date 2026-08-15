import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from chrisnizer_lint import lint, apply_mechanical  # noqa: E402


def cats(text, **kw):
    return {f.category for f in lint(text, **kw)}


def test_em_dash_flagged():
    assert "em_dash" in cats("The plan, announced today — was blocked.")


def test_filler_and_boosterism():
    c = cats("This is genuinely a groundbreaking, seamless tool.")
    assert "filler" in c and "boosterism" in c


def test_plural_first_person_flagged_and_academic_exempt():
    assert "plural_first_person" in cats("We built our system.")
    assert "plural_first_person" not in cats("We built our system.", academic=True)


def test_negative_parallelism():
    assert "negative_parallelism" in cats("It is not just fast but reliable.")


def test_passive_voice():
    assert "passive_voice" in cats("The results are shown to the user.")


def test_long_sentence():
    long = "I met with the team last week to learn about the board and " \
           "discuss running some demos and a possible collaboration and the " \
           "budget and the timeline and the next steps and who owns what part."
    assert "long_sentence" in cats(long)


def test_title_case_heading_and_label_bullet():
    c = cats("## Key Features And Benefits\n\n- **Speed:** it is fast.\n")
    assert "title_case_heading" in c and "label_bullet" in c


def test_mechanical_fix_normalises_quotes():
    fixed, n = apply_mechanical("He said “hi” and left…")
    assert '"hi"' in fixed and "..." in fixed and n >= 1


def test_code_and_urls_ignored():
    # "we" inside code and a URL must not be flagged
    assert "plural_first_person" not in cats("`we = 1` and https://we.example.com/our")


def test_humanizer_patterns():
    c = cats("Great question! Let's dive in. I hope this helps, let me know if you want.")
    assert {"sycophancy", "signposting", "collaborative_artifact"} <= c


def test_authority_and_cutoff():
    assert "authority_trope" in cats("At the end of the day, what really matters is speed.")
    assert "cutoff_disclaimer" in cats("As of my last update, the data was limited.")


def test_emoji_flagged_but_math_is_not():
    assert "emoji" in cats("Ship it 🚀 today.")
    assert "emoji" not in cats("The part is 20 mm x 30 mm at 45° within ±0.2 mm.")


def test_clean_text_passes():
    clean = "I am writing to ask for an hour with the board this week. " \
            "I want to run two demos on it. Would Thursday work?"
    assert lint(clean) == []
