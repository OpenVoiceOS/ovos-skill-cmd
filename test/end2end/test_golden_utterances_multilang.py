"""Multilingual golden-utterance end-to-end coverage for ovos-skill-cmd.

test_golden_utterances.py only exercises en-US; every locale under
ovos_skill_cmd/locale/ ships list_scripts.intent, and every locale except
kab also ships run_script_command.intent (kab has list_scripts.intent and
the dialog files but no run_script_command.intent, so it is covered only
for list_scripts here -- a real coverage gap, not an oversight).

run_script_command needs the {script} slot filled by a
dynamically-registered Padatious entity built from settings.alias (see
initialize() in ovos_skill_cmd/__init__.py), so a settings file seeding two
aliases ("backup", "weather") is written under a private XDG config root
before each MiniCroft loads the skill, exactly as test_golden_utterances.py
already does for en-US.

One MiniCroft is booted PER LOCALE (module-scoped fixture, indirectly
parametrized by lang; pytest reuses one boot per distinct lang value
across every row of that lang and tears it down before moving on).

Row construction: each row is derived mechanically from that locale's own
.intent template lines (its own bracket-alternation choices), never a
translation of the English rows.
"""
import json
import os
import tempfile
from pathlib import Path
from typing import List

import pytest

SKILL_ID = "ovos-skill-cmd.openvoiceos"
ALIASES = {"backup": "echo backup", "weather": "echo weather"}


def _seed_settings() -> None:
    root = tempfile.mkdtemp(prefix="ovos-skill-cmd-golden-multilang-")
    os.environ["XDG_CONFIG_HOME"] = os.path.join(root, "config")
    settings_dir = os.path.join(root, "config", "mycroft", "skills", SKILL_ID)
    os.makedirs(settings_dir, exist_ok=True)
    with open(os.path.join(settings_dir, "settings.json"), "w") as handle:
        json.dump({"alias": ALIASES, "__mycroft_skill_firstrun": False}, handle)


_seed_settings()

from ovos_bus_client.message import Message  # noqa: E402
from ovos_bus_client.session import Session  # noqa: E402
from ovoscope import PADACIOSO_PIPELINE, CaptureSession, get_minicroft  # noqa: E402

END2END_DIR = Path(__file__).parent

LANGS = [
    "en-US", "ca-ES", "da-DK", "de-DE", "es-ES", "eu-ES", "fr-FR",
    "gl-ES", "it-IT", "kab", "nl-NL", "oc-FR", "pt-BR", "pt-PT", "sv-SE",
]


def _load_rows(lang):
    path = END2END_DIR / f"golden_utterances_{lang}.jsonl"
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("needs_manual"):
                continue
            rows.append(row)
    return rows


ALL_ROWS = []
for _lang in LANGS:
    for _row in _load_rows(_lang):
        ALL_ROWS.append(_row)


def _golden_id(row):
    return f"{row['lang']}-{row['intent_label']}-{row['utterance']}"


@pytest.fixture(scope="module")
def minicroft(request):
    lang = request.param
    mc = get_minicroft([SKILL_ID], max_wait=150, lang=lang)
    yield mc
    mc.stop()


def _capture(mc, text, lang, session_id) -> List[Message]:
    session = Session(session_id)
    session.lang = lang
    session.pipeline = PADACIOSO_PIPELINE
    utterance = Message(
        "recognizer_loop:utterance",
        {"utterances": [text], "lang": lang},
        {"session": session.serialize(), "source": "A", "destination": "B"},
    )
    capture = CaptureSession(mc)
    capture.capture(utterance, timeout=30)
    return capture.finish()


KNOWN_BUGS = {}

_PARAMS = [
    pytest.param(row["lang"], row, id=_golden_id(row))
    for row in ALL_ROWS
]


@pytest.mark.timeout(300)
@pytest.mark.parametrize("minicroft,row", _PARAMS, indirect=["minicroft"])
def test_golden_utterance_multilang(minicroft, row):
    expected_intent = f"{SKILL_ID}:{row['intent_label']}"
    messages = _capture(minicroft, row["utterance"], row["lang"], f"golden-{_golden_id(row)}")
    types = [m.msg_type for m in messages]
    matched = expected_intent in types
    bug_key = (row["lang"], row["utterance"])
    if bug_key in KNOWN_BUGS and not matched:
        pytest.xfail(reason=f"known-bug: {KNOWN_BUGS[bug_key]}")
    assert matched, (
        f"[{row['lang']}] {row['utterance']!r}: expected {expected_intent!r} in message types, got {types!r}"
    )
