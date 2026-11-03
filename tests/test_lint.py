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


def test_staccato_run_flagged():
    assert "staccato" in cats("It defers the cost. It exposes neither key. It reports what moved.")
    # two in a row is punch, not a pattern
    assert "staccato" not in cats("It defers the cost. It exposes neither key.")
    # short sentences with varied openings are fine
    assert "staccato" not in cats("It defers the cost. Nothing leaks. I report the delta.")


def test_staccato_matches_shape_not_just_word():
    # different pronoun subjects, same shape
    assert "staccato" in cats("It defers the cost. This exposes no key. That reports the delta.")


def test_fragment_colon_skips_real_sentence_with_pronoun_subject():
    text = "Two things you check by reading, because no regex catches them:\n\n- one\n- two\n"
    assert "fragment_colon" not in cats(text)
    frag = "Three fingerprints, all built from signatures:\n\n- one\n- two\n"
    assert "fragment_colon" in cats(frag)


def test_stilted_turns_flagged():
    for line in ("F shakes the tree, and so does a tap on it.",
                 "Click to step it, and off means off for the ducks.",
                 "What they hear is the garden's business.",
                 "A duck sits or stands about until boredom sets it wandering.",
                 "It shows its mood, as a Chao does.",
                 "A hand appears in place of the cursor."):
        assert "stilted" in cats(line), line


def test_stilted_leaves_plain_prose_alone():
    for line in ("Add --blind to hide who is who until you quit.",
                 "Clicking the tree also shakes fruit down.",
                 "It sits or stands around until it gets bored.",
                 "It shows its mood the way a Chao does."):
        assert "stilted" not in cats(line), line


def test_quoted_examples_not_flagged():
    assert cats('Rewrite "not just X but Y" as one plain clause.') == set()
    assert "negative_parallelism" in cats("It is not just fast but reliable.")


def test_ui_flags_telegraphese_and_mixed_lists():
    assert "telegraphic" in cats("Closing window ends garden and saves state.", ui=True)
    assert "mixed_list" in cats("Its needs are hunger, thirst, sleep, tired and bored.", ui=True)
    assert not {"telegraphic", "mixed_list"} & cats(
        "Closing the window saves the garden. Its needs are hungry, thirsty, sleepy, tired and bored.", ui=True)
    assert "telegraphic" not in cats("Closing window ends garden and saves state.")


def test_decimals_and_et_al_do_not_split_sentences():
    long = ("The brain is the connectome of 2.7 million connections from Dorkenwald et al. "
            "(2024), which I run as spiking neurons on five ducks in a garden, each with its own copy.")
    assert "long_sentence" in cats(long)


# --- checks added 2026-11-03 from edits to a team document -----------------

def test_vague_set_flags_unnamed_sets():
    assert "vague_set" in cats("Two scores have no cohort series.")
    assert "vague_set" in cats("The missing ones include the three that a pilot needs most.")
    assert "vague_set" in cats("The labeler rarely names a habit from what it's given.")
    assert "vague_set" in cats("The rest wait for later.")


def test_vague_set_allows_named_sets_and_counts():
    assert "vague_set" not in cats("Prompt quality and delegation depth have no cohort series.")
    assert "vague_set" not in cats("The three parts (capture, support, dashboard) run on one server.")
    assert "vague_set" not in cats("The four questions are these: tips, check-ins and the dashboard.")
    assert "vague_set" not in cats("3 of 7 tool tips describe other products.")


def test_positional_terms():
    assert "positional" in cats("Views above the person are planned as aggregates.")
    assert "positional" in cats("The labeler can abstain, but later stages hide it.")
    assert "positional" in cats("The table below lists each step.")


def test_positional_allows_amounts():
    assert "positional" not in cats("Scores above 30% pass the check.")
    assert "positional" not in cats("Anything below $5 a month is fine.")


def test_neutral_flags_singular_first_person_only_in_neutral_mode():
    assert "first_person" in cats("I estimate the work at 26 weeks.", neutral=True)
    assert "plural_first_person" in cats("Our estimate is 26 weeks.", neutral=True)
    assert "plural_first_person" in cats("Our estimate is 26 weeks.", neutral=True, academic=True)
    assert "first_person" not in cats("I estimate the work at 26 weeks.")


def test_dramatic_closer():
    assert "dramatic_closer" in cats("Upkeep and hosting are the costs nobody has measured.")
    assert "dramatic_closer" not in cats("Hosting and the test accounts aren't priced yet.")


def test_fragment_shapes():
    assert "fragment" in cats("Labeled 2 of 3 scripted users before the run stopped.")
    assert "fragment" in cats("Counsel review needed before relying on it.")


def test_fragment_allows_full_sentences_and_intro_phrases():
    assert "fragment" not in cats("Labeled data is stored in the turns table.")
    assert "fragment" not in cats("Based on the gold set, the model named 48% of patterns.")
    assert "fragment" not in cats("Built-in checks run every day.")
    assert "fragment" not in cats("Legal counsel hasn't reviewed it, so it can't be relied on yet.")


def test_long_paragraph():
    para = " ".join(["The option sends prompts with names removed and needs a review."] * 12)
    assert "long_paragraph" in cats(para)
    assert "long_paragraph" not in cats("A short paragraph. It has two sentences.")
