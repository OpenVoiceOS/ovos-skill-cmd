"""End-to-end coverage for ``list_scripts`` when no alias is configured."""
import json
import os
import tempfile
from unittest import TestCase

SKILL_ID = "ovos-skill-cmd.openvoiceos"
LANG = "en-US"
LIST_INTENT = f"{SKILL_ID}:list_scripts"


def _seed_settings() -> None:
    root = tempfile.mkdtemp(prefix="ovos-skill-cmd-e2e-list-empty-")
    os.environ["XDG_CONFIG_HOME"] = os.path.join(root, "config")
    settings_dir = os.path.join(root, "config", "mycroft", "skills", SKILL_ID)
    os.makedirs(settings_dir, exist_ok=True)
    with open(os.path.join(settings_dir, "settings.json"), "w") as handle:
        json.dump({"alias": {}, "__mycroft_skill_firstrun": False}, handle)


from ovos_bus_client.message import Message  # noqa: E402
from ovos_bus_client.session import Session  # noqa: E402
from ovoscope import get_minicroft, CaptureSession, PADACIOSO_PIPELINE  # noqa: E402


class TestListScriptsIntentNoAlias(TestCase):
    """list_scripts.intent speaks the no.scripts dialog when unconfigured."""

    @classmethod
    def setUpClass(cls):
        _seed_settings()
        cls.minicroft = get_minicroft([SKILL_ID])

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "minicroft", None):
            cls.minicroft.stop()

    def test_no_scripts_configured(self):
        session = Session("e2e-en_us-cmd-list-empty")
        session.lang = LANG
        session.pipeline = PADACIOSO_PIPELINE
        capture = CaptureSession(self.minicroft)
        capture.capture(
            Message(
                "recognizer_loop:utterance",
                {"utterances": ["list my aliases"], "lang": LANG},
                {"session": session.serialize(), "source": "A", "destination": "B"},
            ),
            timeout=30,
        )
        messages = capture.finish()
        types = [m.msg_type for m in messages]
        self.assertIn(LIST_INTENT, types)
        spoken = [
            m.data.get("utterance", "")
            for m in messages
            if m.msg_type in ("speak", "ovos.utterance.speak")
        ]
        self.assertTrue(
            any(
                "don't have any scripts configured" in utt
                or "No commands are set up yet" in utt
                for utt in spoken
            ),
            f"expected the no.scripts dialog to be spoken, got {spoken}",
        )
