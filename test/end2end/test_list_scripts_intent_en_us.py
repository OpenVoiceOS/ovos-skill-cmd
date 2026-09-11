"""End-to-end intent-routing tests for the ``list_scripts`` intent (en-US).

Asserts that phrasings from ``list_scripts.intent`` route to
``handle_list_scripts`` and that the skill speaks back the configured alias
names when present, or the ``no.scripts`` dialog when the ``alias`` setting
is empty.

Run:
    uv run pytest test/end2end/test_list_scripts_intent_en_us.py -v
"""
import json
import os
import tempfile
from unittest import TestCase

SKILL_ID = "ovos-skill-cmd.openvoiceos"
LANG = "en-US"
LIST_INTENT = f"{SKILL_ID}:list_scripts"
ALIASES = {"backup": "echo backup", "weather": "echo weather"}


def _seed_settings(alias) -> None:
    root = tempfile.mkdtemp(prefix="ovos-skill-cmd-e2e-list-")
    os.environ["XDG_CONFIG_HOME"] = os.path.join(root, "config")
    settings_dir = os.path.join(root, "config", "mycroft", "skills", SKILL_ID)
    os.makedirs(settings_dir, exist_ok=True)
    with open(os.path.join(settings_dir, "settings.json"), "w") as handle:
        json.dump({"alias": alias, "__mycroft_skill_firstrun": False}, handle)


from ovos_bus_client.message import Message  # noqa: E402
from ovos_bus_client.session import Session  # noqa: E402
from ovoscope import get_minicroft, CaptureSession, PADACIOSO_PIPELINE  # noqa: E402


def _session(tag: str) -> Session:
    session = Session(f"e2e-en_us-cmd-list-{tag}")
    session.lang = LANG
    session.pipeline = PADACIOSO_PIPELINE
    return session


def _utterance(utt: str, session: Session) -> Message:
    return Message(
        "recognizer_loop:utterance",
        {"utterances": [utt], "lang": LANG},
        {"session": session.serialize(), "source": "A", "destination": "B"},
    )


class TestListScriptsIntent(TestCase):
    """list_scripts.intent routes across its phrasings and speaks the aliases."""

    @classmethod
    def setUpClass(cls):
        _seed_settings(ALIASES)
        cls.minicroft = get_minicroft([SKILL_ID])

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "minicroft", None):
            cls.minicroft.stop()

    def _capture(self, utterance: str):
        session = _session(str(hash(utterance)))
        capture = CaptureSession(self.minicroft)
        capture.capture(_utterance(utterance, session), timeout=30)
        return capture.finish()

    def _spoken(self, messages):
        return [
            m.data.get("utterance", "")
            for m in messages
            if m.msg_type in ("speak", "ovos.utterance.speak")
        ]

    def assertRoutesToList(self, utterance: str):
        messages = self._capture(utterance)
        types = [m.msg_type for m in messages]
        self.assertIn(
            LIST_INTENT, types,
            f"expected {LIST_INTENT!r} to be matched for {utterance!r}, "
            f"got {types}",
        )
        spoken = self._spoken(messages)
        self.assertTrue(
            any("backup" in utt and "weather" in utt for utt in spoken),
            f"expected a spoken response mentioning both aliases for "
            f"{utterance!r}, got {spoken}",
        )

    def test_list_my_aliases(self):
        self.assertRoutesToList("list my aliases")

    def test_what_scripts_do_you_know(self):
        self.assertRoutesToList("what scripts do you know")

    def test_which_commands_can_you_run(self):
        self.assertRoutesToList("which commands can you run")

    def test_show_me_my_scripts(self):
        self.assertRoutesToList("show me my scripts")

    def test_tell_me_the_scripts_you_know(self):
        self.assertRoutesToList("tell me the scripts you know")

    def test_what_scripts_do_you_have(self):
        self.assertRoutesToList("what scripts do you have")
