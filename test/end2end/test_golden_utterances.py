"""Golden rows in every locale route to their intent on the m2v pipeline.

For each ``golden_utterances_<lang>.jsonl`` in this directory, one MiniCroft
loads the real skill in that language on the m2v prototype pipeline, the
model2vec engine built at boot from the skill's own ``.intent`` files. Each
row's utterance goes through that pipeline's high, medium and low tiers in
order, and the row passes when the first tier to match names its
``intent_label``. The engine embeds the utterance, so a row that no template
spells out word for word still matches when it means the same thing.

The ``{script}`` slot is filled at boot from each locale's ``script.entity``
file. The aliases a user configures register later, in ``initialize()``, and
the m2v prototypes do not see them.

Each locale must pass at least ``MIN_MATCH_RATE`` of its rows. All rows run,
including rows marked ``needs_manual`` or ``machine_generated``, and the test
prints every row that misses with the intent that matched instead.

Each intent with rows in a locale must also match at least
``MIN_MATCHED_ROWS_PER_INTENT`` of them. A locale in ``GOLDEN_LOCALE_GAPS``
runs its rate check as a non-strict xfail, but still fails on the per-intent
floor and on a rate far below the one measured for it.

For every locale but en-US, the rows in the form dev wrote them also run on
padacioso, as a stand-in for padatious in a default install.

A locale with a ``negative_utterances_<lang>.jsonl`` file also runs those
requests for other skills (weather, timers, music) on an m2v MiniCroft. No
negative row may match an intent of this skill, except a claim listed in
``NEGATIVE_KNOWN_CLAIMS``. A locale in ``NEGATIVE_ENGINE_GAPS`` runs as a
non-strict xfail, because the published model cannot separate those requests
from this skill.
"""
import json
from pathlib import Path

import pytest
from ovos_bus_client.message import Message
from ovoscope import M2V_PUBLISHED_MODEL, get_m2v_minicroft, get_minicroft
from ovoscope.golden_minicroft import warm_m2v_models

SKILL_ID = "ovos-skill-cmd.openvoiceos"
M2V_PROTOTYPE = "ovos-m2v-prototype-pipeline"
PADACIOSO = "ovos-padacioso-pipeline-plugin"
TIERS = ("high", "medium", "low")
# m2v gives some rows a different answer on each boot, so the test gates on
# the share of rows that match per locale, not on each row.
MIN_MATCH_RATE = 0.8
# Padacioso matches template lines, not meaning, so it runs the rows in the
# form dev wrote them (rewritten_from), as a stand-in for padatious in a
# default install. en-US has its own padacioso effect tests.
# Dev rows written in a form that a corrected template line no longer makes,
# because the form was wrong. These must not route on padacioso.
PADACIOSO_WRONG_FORMS = {
    "ca-ES": {"quins ordres pots executar"},
    "de-DE": {"führe befehl weather"},
    "fa-IR": {"لیست نوشته های من", "دستورالعمل های من را بنویسید", "رانندگی فرماندهی backup",
              "اجرای فرماندهی weather"},
    "fr-FR": {"quels commandes sont configurés", "exécute la script weather"},
    "it-IT": {"avvia un script weather"},
    "nl-NL": {"voer uit commando backup", "voer uit script weather"},
    "oc-FR": {"quins comandas son configurats"},
    "pl-PL": {"wyliść moje aliasy", "Polecenie uruchomienia weather"},
}
# A locale also fails when any of its intents has fewer matched rows than this.
MIN_MATCHED_ROWS_PER_INTENT = 1
END2END_DIR = Path(__file__).parent
LOCALE_ROOT = END2END_DIR.parents[1] / "ovos_skill_cmd" / "locale"
NEGATIVE_ENGINE_GAPS = {}
# Negative rows that m2v claimed for this skill in at least one measured run.
# The set holds the intents a row may go to. A listed claim is allowed, not
# required, so a row that flips between boots does not fail the test. Any other
# claim fails the locale. The alarm and reminder rows go to list_scripts on the
# old files and on this head; the fa-IR and pl-PL music rows go to list_scripts
# on the old files and to run_script_command on this head, so both intents are
# allowed.
# The en-US news row goes to run_script_command only at the 0.56 low tier.
# The real fix for the split between list_scripts and run_script_command is a
# `.required` word list.
LIST, RUN = "list_scripts", "run_script_command"
NEGATIVE_KNOWN_CLAIMS = {
    "ca-ES": {"llista les meves alarmes": {LIST}},
    "da-DK": {"vis mine alarmer": {LIST}},
    "de-DE": {"zeig mir meine wecker": {LIST}},
    "en-US": {
        "list my reminders": {LIST},
        "launch backup camera": {RUN},
        "run the news for me": {RUN},
    },
    "fa-IR": {
        "یک تایمر ده دقیقه\u200cای بگذار": {LIST},
        "کمی موسیقی پخش کن": {LIST, RUN},
        "هشدارهای من را نشان بده": {RUN},
    },
    "fr-FR": {"liste mes alarmes": {LIST}},
    "gl-ES": {"lista as miñas alarmas": {LIST}},
    "it-IT": {"elenca le mie sveglie": {LIST}},
    "nl-NL": {"toon mijn alarmen": {LIST}},
    "pl-PL": {"włącz jakąś muzykę": {LIST, RUN}},
    "pt-BR": {"liste meus alarmes": {LIST}},
    "pt-PT": {"lista os meus alarmes": {LIST}},
    "ru-RU": {
        "какая завтра будет погода": {LIST},
        "покажи мои будильники": {LIST},
    },
    "sv-SE": {"lista mina larm": {LIST}},
}
# Locales below MIN_MATCH_RATE after natural template lines, with the lowest
# rate measured in three runs. The rate check runs as a non-strict xfail. The
# per-intent floor still fails hard, and so does a rate more than
# GAP_TOLERANCE below the measured rate.
GOLDEN_LOCALE_GAPS = {
    "kab": {"rate": 4 / 6, "reason": "linguonnx has no en->kab route under a commercial licence"},
    "pl-PL": {"rate": 7 / 9, "reason": "7 of 9 rows match in the weakest of three runs with the shipped lines only"},
    "ru-RU": {"rate": 6 / 9, "reason": "6 of 9 rows match in the weakest of three runs with the shipped lines only"},
}
GAP_TOLERANCE = 0.10


def _rows_by_lang(prefix):
    rows = {}
    for path in sorted(END2END_DIR.glob(f"{prefix}*.jsonl")):
        lang = path.stem.removeprefix(prefix)
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                row = json.loads(line)
                assert row["lang"] == lang, f"{path.name}:{number} has lang {row['lang']!r}"
                rows.setdefault(lang, []).append(row)
    return rows


ROWS = _rows_by_lang("golden_utterances_")
NEGATIVES = _rows_by_lang("negative_utterances_")


def _matched_intent(engine, utterance, lang):
    message = Message("recognizer_loop:utterance",
                      {"utterances": [utterance], "lang": lang}, {"lang": lang})
    match = next(filter(None, (getattr(engine, f"match_{tier}")([utterance], lang, message)
                               for tier in TIERS)), None)
    return match.match_type if match else None


def _match_all(lang, rows):
    minicroft = get_m2v_minicroft([SKILL_ID], model=M2V_PUBLISHED_MODEL,
                                  lang=lang, classifier=False)
    try:
        warm_m2v_models(minicroft)
        engine = minicroft.intents.pipeline_plugins[M2V_PROTOTYPE]
        return [_matched_intent(engine, row["utterance"], lang) for row in rows]
    finally:
        minicroft.stop()


@pytest.mark.timeout(900)
@pytest.mark.parametrize("lang", sorted(ROWS))
def test_golden_rows_match_their_intent(lang):
    rows = ROWS[lang]
    misses = []
    hits = {row["intent_label"]: 0 for row in rows}
    for row, got in zip(rows, _match_all(lang, rows)):
        if got == f"{SKILL_ID}:{row['intent_label']}":
            hits[row["intent_label"]] += 1
        else:
            misses.append(f"{row['utterance']!r}: expected {row['intent_label']}, got {got}")
    starved = sorted(label for label, count in hits.items()
                     if count < MIN_MATCHED_ROWS_PER_INTENT)
    rate = 1 - len(misses) / len(rows)
    print(f"[{lang}] {rate:.1%} of {len(rows)} rows match", *misses, sep="\n  ")
    if starved:
        print(f"[{lang}] intents below {MIN_MATCHED_ROWS_PER_INTENT} matched rows: {starved}")
    assert not starved, f"[{lang}] intents below {MIN_MATCHED_ROWS_PER_INTENT} matched rows: {starved}"
    gap = GOLDEN_LOCALE_GAPS.get(lang)
    if gap:
        assert rate >= gap["rate"] - GAP_TOLERANCE, (
            f"[{lang}] {rate:.1%} of rows match, more than {GAP_TOLERANCE:.0%} below the "
            f"measured {gap['rate']:.1%}:\n  " + "\n  ".join(misses)
        )
        if rate < MIN_MATCH_RATE:
            pytest.xfail(f"[{lang}] {rate:.1%} of rows match: {gap['reason']}")
    assert rate >= MIN_MATCH_RATE, (
        f"[{lang}] {rate:.1%} of rows match, below {MIN_MATCH_RATE:.0%}:\n  " + "\n  ".join(misses)
    )


@pytest.mark.timeout(900)
@pytest.mark.parametrize("lang", [
    pytest.param(lang, marks=pytest.mark.xfail(reason=NEGATIVE_ENGINE_GAPS[lang], strict=False))
    if lang in NEGATIVE_ENGINE_GAPS else lang
    for lang in sorted(NEGATIVES)
])
def test_negative_rows_match_no_cmd_intent(lang):
    rows = NEGATIVES[lang]
    known = NEGATIVE_KNOWN_CLAIMS.get(lang, {})
    claims = [(row["utterance"], got.removeprefix(f"{SKILL_ID}:"))
              for row, got in zip(rows, _match_all(lang, rows))
              if got and got.startswith(f"{SKILL_ID}:")]
    unknown = [f"{utterance!r}: matched {intent}" for utterance, intent in claims
               if intent not in known.get(utterance, ())]
    print(f"[{lang}] {len(claims)} of {len(rows)} negative rows claimed, "
          f"{len(unknown)} not in NEGATIVE_KNOWN_CLAIMS", *unknown, sep="\n  ")
    assert not unknown, f"[{lang}] negative rows claimed by this skill:\n  " + "\n  ".join(unknown)


@pytest.mark.timeout(900)
@pytest.mark.parametrize("lang", sorted(set(ROWS) - {"en-US"}))
def test_rows_on_padacioso(lang):
    """Every row runs on padacioso, the stand-in for padatious in a default install.

    A row written as a dev template expansion (the dev text, or ``rewritten_from``
    of a rewritten row) must route to its intent, except the dev forms in
    PADACIOSO_WRONG_FORMS, which a corrected line no longer makes and which must
    not route. A natural row, which padacioso cannot match without a template
    line, may match nothing but must not route to the other intent.
    """
    rows = ROWS[lang]
    wrong = PADACIOSO_WRONG_FORMS.get(lang, set())
    dev_forms = [(row.get("rewritten_from", row["utterance"]), row["intent_label"]) for row in rows
                 if "rewritten_from" in row or not row.get("machine_generated")]
    minicroft = get_minicroft([SKILL_ID], lang=lang, max_wait=150)
    try:
        engine = minicroft.intents.pipeline_plugins[PADACIOSO]
        dev_got = [_matched_intent(engine, utterance, lang) for utterance, _ in dev_forms]
        row_got = [_matched_intent(engine, row["utterance"], lang) for row in rows]
    finally:
        minicroft.stop()
    checked = [(u, label, got) for (u, label), got in zip(dev_forms, dev_got) if u not in wrong]
    misses = [f"{u!r}: expected {label}, got {got}" for u, label, got in checked if got != f"{SKILL_ID}:{label}"]
    still_routed = [u for (u, _), got in zip(dev_forms, dev_got) if u in wrong and got]
    crossed = [f"{row['utterance']!r}: expected {row['intent_label']}, got {got}"
               for row, got in zip(rows, row_got) if got and got != f"{SKILL_ID}:{row['intent_label']}"]
    print(f"[{lang}] padacioso: {len(rows)} rows run, {len(checked)} dev forms must route, "
          f"{len(misses)} do not, {len(crossed)} rows cross to the other intent", *misses, *crossed, sep="\n  ")
    assert not misses, f"[{lang}] dev forms that no longer route on padacioso:\n  " + "\n  ".join(misses)
    assert not still_routed, f"[{lang}] wrong forms still route on padacioso: {still_routed}"
    assert not crossed, f"[{lang}] rows that route to the other intent on padacioso:\n  " + "\n  ".join(crossed)


def _shipping_locales():
    return {d.name for d in LOCALE_ROOT.iterdir() if d.is_dir() and any(d.glob("*.intent"))}


def test_every_shipping_locale_has_a_golden_file():
    golden = {p.stem.removeprefix("golden_utterances_")
              for p in END2END_DIR.glob("golden_utterances_*.jsonl")}
    shipping = _shipping_locales()
    assert golden == shipping, f"golden files {sorted(golden ^ shipping)} differ from shipping locales"


def test_every_locale_ships_every_en_us_intent():
    reference = {p.name for p in (LOCALE_ROOT / "en-US").glob("*.intent")}
    missing = {lang: sorted(reference - {p.name for p in (LOCALE_ROOT / lang).glob("*.intent")})
               for lang in sorted(_shipping_locales())}
    missing = {lang: files for lang, files in missing.items() if files}
    assert not missing, f"locales missing en-US intent files: {missing}"


def test_negative_files_cover_en_us_and_shipping_locales_only():
    assert "en-US" in NEGATIVES
    assert set(NEGATIVES) <= set(ROWS), f"negative files without golden rows: {sorted(set(NEGATIVES) - set(ROWS))}"
