"""End-to-end proof that ``RunScriptCommandIntent`` is a Padatious ``.intent``
match, not an Adapt keyword match.

The session pipeline is pinned to ``PADACIOSO_PIPELINE`` only (Adapt excluded),
so this test can only pass if the intent is trained from
``RunScriptCommandIntent.intent`` and the ``{script}`` slot is populated from
a dynamically registered Padatious entity (the skill's ``alias`` setting).

Run:
    uv run pytest test/end2end/test_intent_file_migration.py -v
"""
import json
import os
import tempfile
from unittest import TestCase

SKILL_ID = "ovos-skill-cmd.openvoiceos"
LANG = "en-US"
RUN_INTENT = f"{SKILL_ID}:RunScriptCommandIntent"
ALIASES = {"backup": "echo backup"}


def _seed_settings() -> None:
    root = tempfile.mkdtemp(prefix="ovos-skill-cmd-e2e-intentfile-")
    os.environ["XDG_CONFIG_HOME"] = os.path.join(root, "config")
    settings_dir = os.path.join(root, "config", "mycroft", "skills", SKILL_ID)
    os.makedirs(settings_dir, exist_ok=True)
    with open(os.path.join(settings_dir, "settings.json"), "w") as handle:
        json.dump(
            {"alias": ALIASES, "__mycroft_skill_firstrun": False}, handle
        )


_seed_settings()

from ovos_bus_client.message import Message  # noqa: E402
from ovos_bus_client.session import Session  # noqa: E402
from ovoscope import get_minicroft, CaptureSession, PADACIOSO_PIPELINE  # noqa: E402


def _session(tag: str) -> Session:
    session = Session(f"e2e-en_us-cmd-intentfile-{tag}")
    session.lang = LANG
    session.pipeline = PADACIOSO_PIPELINE
    return session


def _utterance(utt: str, session: Session) -> Message:
    return Message(
        "recognizer_loop:utterance",
        {"utterances": [utt], "lang": LANG},
        {"session": session.serialize(), "source": "A", "destination": "B"},
    )


class TestRunScriptCommandIntentFile(TestCase):
    """RunScriptCommandIntent must route via Padatious/.intent alone."""

    @classmethod
    def setUpClass(cls):
        cls.minicroft = get_minicroft([SKILL_ID])

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "minicroft", None):
            cls.minicroft.stop()

    def test_run_script_backup_padatious_only(self):
        session = _session("run-script-backup")
        capture = CaptureSession(self.minicroft)
        capture.capture(
            _utterance("run script backup", session), timeout=30
        )
        messages = capture.finish()
        types = [m.msg_type for m in messages]
        self.assertIn(
            RUN_INTENT, types,
            f"expected {RUN_INTENT!r} to be matched via the Adapt-less "
            f"(Padatious-only) pipeline for 'run script backup', got {types}",
        )
        spoken = [
            m.data.get("utterance", "")
            for m in messages
            if m.msg_type in ("speak", "ovos.utterance.speak")
        ]
        self.assertTrue(
            any("running backup" in utt for utt in spoken),
            f"expected a spoken response mentioning 'backup', got {spoken}",
        )
