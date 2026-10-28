"""End-to-end proof that ``run_script_command`` is a ``.intent`` file match,
not an Adapt keyword match.

The session pipeline is the m2v prototype pipeline only (Adapt excluded),
whose prototypes are built from the skill's ``.intent`` files, so this test
can only pass if the intent comes from ``run_script_command.intent`` and the
``{script}`` slot is populated (the skill's ``alias`` setting).

Run:
    uv run pytest test/end2end/test_intent_file_migration.py -v
"""
import json
import os
import tempfile
from unittest import TestCase

SKILL_ID = "ovos-skill-cmd.openvoiceos"
LANG = "en-US"
RUN_INTENT = f"{SKILL_ID}:run_script_command"
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
from ovoscope import CaptureSession  # noqa: E402
from ovoscope.routing import PIPELINE, TALLY, get_prototype_minicroft  # noqa: E402


def _session(tag: str) -> Session:
    session = Session(f"e2e-en_us-cmd-intentfile-{tag}")
    session.lang = LANG
    session.pipeline = PIPELINE
    return session


def _utterance(utt: str, session: Session) -> Message:
    return Message(
        "recognizer_loop:utterance",
        {"utterances": [utt], "lang": LANG},
        {"session": session.serialize(), "source": "A", "destination": "B"},
    )


class TestRunScriptCommandFile(TestCase):
    """run_script_command must route via its .intent file alone."""

    @classmethod
    def setUpClass(cls):
        cls.minicroft = get_prototype_minicroft([SKILL_ID], lang=LANG)

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "minicroft", None):
            cls.minicroft.stop()

    def test_run_script_backup_intent_file_only(self):
        session = _session("run-script-backup")
        capture = CaptureSession(self.minicroft)
        capture.capture(
            _utterance("run script backup", session), timeout=30
        )
        messages = capture.finish()
        TALLY.assert_routed("run script backup", RUN_INTENT, [m.msg_type for m in messages])
        spoken = [
            m.data.get("utterance", "")
            for m in messages
            if m.msg_type in ("speak", "ovos.utterance.speak")
        ]
        self.assertTrue(
            any("running backup" in utt for utt in spoken),
            f"expected a spoken response mentioning 'backup', got {spoken}",
        )
