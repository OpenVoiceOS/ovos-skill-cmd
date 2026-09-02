"""Golden-utterance end-to-end coverage for ovos-skill-cmd (en-US).

The golden corpus (``golden_utterances.jsonl``) is a vendored slice of the
shared ovoscope golden-utterance dataset (skill_id
"ovos-skill-cmd.openvoiceos"), supplemented with rows derived from this
skill's own ``RunScriptCommandIntent.intent``/``skill.json`` templates: the
master corpus carries only one bare stub row ("run command") for this
skill, which cannot route on its own because ``RunScriptCommandIntent`` is
trained from ``RunScriptCommandIntent.intent`` and needs the ``{script}``
slot filled by a dynamically-registered Padatious entity (see
``initialize()`` in ``ovos_skill_cmd/__init__.py``). That stub is kept here
with ``needs_manual: true`` (flagged, not deleted) as a finding for the
master corpus: it needs an alias suffix (e.g. "run command backup") to be a
valid routable row.

A settings file seeding two aliases ("backup", "weather") is written under a
private XDG config root before the MiniCroft loads the skill, matching
``test_intents_en_us.py``'s existing mechanism.

Run:
    uv run pytest test/end2end/ -v
"""
import json
import os
import tempfile
from pathlib import Path

import pytest

SKILL_ID = "ovos-skill-cmd.openvoiceos"
LANG = "en-US"
ALIASES = {"backup": "echo backup", "weather": "echo weather"}


def _seed_settings() -> None:
    root = tempfile.mkdtemp(prefix="ovos-skill-cmd-golden-")
    os.environ["XDG_CONFIG_HOME"] = os.path.join(root, "config")
    settings_dir = os.path.join(root, "config", "mycroft", "skills", SKILL_ID)
    os.makedirs(settings_dir, exist_ok=True)
    with open(os.path.join(settings_dir, "settings.json"), "w") as handle:
        json.dump({"alias": ALIASES, "__mycroft_skill_firstrun": False}, handle)


_seed_settings()

from ovos_bus_client.message import Message  # noqa: E402
from ovos_bus_client.session import Session  # noqa: E402
from ovoscope import PADACIOSO_PIPELINE, CaptureSession, get_minicroft  # noqa: E402

GOLDEN_PATH = Path(__file__).parent / "golden_utterances.jsonl"

# Confusables lifted from other skills' domains, picked for lexical overlap
# with "run"/"execute"/"launch"/"command"/"script".
NEGATIVE_UTTERANCES = [
    ("what's the weather", "ovos-skill-weather.openvoiceos"),
    ("play some music", "ovos-skill-music.openvoiceos"),
    ("launch a timer for 5 minutes", "ovos-skill-alerts.openvoiceos"),
    ("run the news for me", "ovos-skill-news.openvoiceos"),
    ("execute a wolfram alpha search", "ovos-skill-wolfie.openvoiceos"),
    ("tell me a joke", "skill-icanhazdadjokes.openvoiceos"),
    ("search the web for cats", "ovos-skill-ddg.openvoiceos"),
]


_NEEDS_MANUAL_REASONS = {
    "run command": (
        "bare master-corpus stub with no script alias suffix -- "
        "RunScriptCommandIntent is trained from RunScriptCommandIntent.intent "
        "and needs the {script} slot filled by a dynamically-registered "
        "Padatious entity (see initialize() in "
        "ovos_skill_cmd/__init__.py), so this utterance alone can never "
        "route. Kept as a flagged row (not deleted) for master-corpus "
        "absorption: needs an alias suffix, e.g. 'run command backup'."
    ),
    "please run command backup for me": (
        "RunScriptCommandIntent.intent is a fixed Padatious template with no "
        "filler-word tolerance; the prior Adapt keyword match ('Run' + "
        "'Script' present anywhere in the utterance) routed this regardless "
        "of the surrounding 'please ... for me', which the .intent template "
        "does not model. Kept as a flagged row (not deleted) for "
        "master-corpus absorption."
    ),
    "can you execute script weather now": (
        "RunScriptCommandIntent.intent is a fixed Padatious template with no "
        "filler-word tolerance; the prior Adapt keyword match ('Run' + "
        "'Script' present anywhere in the utterance) routed this regardless "
        "of the surrounding 'can you ... now', which the .intent template "
        "does not model. Kept as a flagged row (not deleted) for "
        "master-corpus absorption."
    ),
}


def _load_golden_rows():
    rows = []
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _as_param(row):
    if row.get("needs_manual"):
        reason = _NEEDS_MANUAL_REASONS.get(row["utterance"])
        assert reason, f"missing _NEEDS_MANUAL_REASONS entry for {row['utterance']!r}"
        return pytest.param(row, id=row["utterance"], marks=pytest.mark.xfail(strict=True, reason=reason))
    return pytest.param(row, id=row["utterance"])


GOLDEN_ROWS = [_as_param(r) for r in _load_golden_rows()]


@pytest.fixture(scope="module")
def minicroft():
    mc = get_minicroft([SKILL_ID])
    yield mc
    mc.stop()


def _capture(mc, text, session_id):
    session = Session(session_id)
    session.lang = LANG
    session.pipeline = PADACIOSO_PIPELINE
    utterance = Message(
        "recognizer_loop:utterance",
        {"utterances": [text], "lang": LANG},
        {"session": session.serialize(), "source": "A", "destination": "B"},
    )
    capture = CaptureSession(mc)
    capture.capture(utterance, timeout=30)
    return capture.finish()


@pytest.mark.timeout(60)
@pytest.mark.parametrize("row", GOLDEN_ROWS, ids=lambda r: r["utterance"])
def test_golden_utterance(minicroft, row):
    # NOTE: on this ovos-core/ovos-bus-client version, the Padatious pipeline
    # emits the matched intent directly as msg_type
    # "<skill_id>:<IntentName>" (observed via capture below) rather than a
    # generic "ovos.intent.matched" wrapper carrying data.intent_name -- the
    # latter is not present in this message stream. Assert against the
    # observed msg_type, matching the pattern already used by
    # ovos-skill-volume/ovos-skill-weather's golden suites.
    expected_intent = f"{SKILL_ID}:{row['intent_label']}"
    messages = _capture(minicroft, row["utterance"], f"golden-{row['utterance']}")
    types = [m.msg_type for m in messages]
    assert expected_intent in types, (
        f"{row['utterance']!r}: expected {expected_intent!r} in message types, got {types!r}"
    )


@pytest.mark.timeout(60)
@pytest.mark.parametrize("negative", NEGATIVE_UTTERANCES, ids=lambda n: n[0])
def test_negative_confusable_not_claimed(minicroft, negative):
    # NOTE: this repo's ovos-core/ovos-bus-client version never emits a
    # generic "ovos.intent.matched" wrapper message (see the identical note
    # on test_golden_utterance above) -- filtering on that msg_type here
    # made this assertion vacuously true (`assert not []` always passes)
    # regardless of what the skill actually claimed. Confirmed by mutation:
    # feeding this check one of this suite's own golden rows as a
    # "negative" still passed. Fixed to key on the observed
    # "<skill_id>:<IntentName>" msg_type shape directly, matching the
    # positive assertion above (and ddg/personal's negative checks).
    text, source_skill = negative
    messages = _capture(minicroft, text, f"negative-{text}")
    types = [m.msg_type for m in messages]
    claimed = any(t.startswith(f"{SKILL_ID}:") for t in types)
    assert not claimed, f"{text!r} (from {source_skill}) was incorrectly claimed by {SKILL_ID}: {types!r}"
