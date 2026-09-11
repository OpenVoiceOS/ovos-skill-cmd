"""End-to-end intent-routing tests for ovos-skill-cmd (en-US).

These assert *per-utterance* that the Padatious pipeline routes an utterance
to the ``RunScriptCommandIntent`` handler and that the skill speaks the
configured alias back. They deliberately use subset assertions over the
captured message stream rather than a strict full-sequence match: the exact
ordered sequence drifts across ovos-core / ovoscope releases (e.g. an extra
``ovos.intent.matched`` message, or ``speak`` vs ``ovos.utterance.speak``),
which is orthogonal to what this skill is responsible for.

``RunScriptCommandIntent`` is trained from ``RunScriptCommandIntent.intent``,
with the ``{script}`` slot filled from a Padatious entity that is registered
dynamically from the skill's ``alias`` setting. The suite therefore seeds a
settings file with a couple of aliases under a private XDG config root
*before* the MiniCroft loads the skill, so ``initialize()`` registers the
matching entity.

Run:
    uv run pytest test/end2end/ -v
"""
import json
import os
import tempfile
from unittest import TestCase

SKILL_ID = "ovos-skill-cmd.openvoiceos"
LANG = "en-US"
RUN_INTENT = f"{SKILL_ID}:RunScriptCommandIntent"
ALIASES = {"backup": "echo backup", "weather": "echo weather"}


def _seed_settings() -> None:
    """Write a skill settings file with aliases under a private XDG root.

    Must run before the MiniCroft loads the skill so ``initialize()`` picks up
    the aliases and registers the ``script`` entity the intent requires.
    """
    root = tempfile.mkdtemp(prefix="ovos-skill-cmd-e2e-")
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
    session = Session(f"e2e-en_us-cmd-{tag}")
    session.lang = LANG
    session.pipeline = PADACIOSO_PIPELINE
    return session


def _utterance(utt: str, session: Session) -> Message:
    return Message(
        "recognizer_loop:utterance",
        {"utterances": [utt], "lang": LANG},
        {"session": session.serialize(), "source": "A", "destination": "B"},
    )


class _RunRoutingMixin:
    """Shared MiniCroft wiring for the cmd skill."""

    @classmethod
    def setUpClass(cls):
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

    def assertRoutesToRun(self, utterance: str, alias: str):
        messages = self._capture(utterance)
        types = [m.msg_type for m in messages]
        self.assertIn(
            RUN_INTENT, types,
            f"expected {RUN_INTENT!r} to be matched for {utterance!r}, "
            f"got {types}",
        )
        spoken = self._spoken(messages)
        self.assertTrue(
            any(f"running {alias}" in utt for utt in spoken),
            f"expected a spoken response mentioning {alias!r} for "
            f"{utterance!r}, got {spoken}",
        )


class TestRunScriptCommandIntent(_RunRoutingMixin, TestCase):
    """RunScriptCommandIntent routes across the RunScriptCommandIntent.intent phrasings."""

    def test_run_command_alias(self):
        self.assertRoutesToRun("run command backup", "backup")

    def test_execute_script_alias(self):
        self.assertRoutesToRun("execute script weather", "weather")

    def test_launch_command_alias(self):
        self.assertRoutesToRun("launch command backup", "backup")

    def test_run_the_backup_script(self):
        self.assertRoutesToRun("run the backup script", "backup")

    def test_run_backup_script_reversed_slot(self):
        self.assertRoutesToRun("run backup script", "backup")

    def test_start_the_backup_script(self):
        self.assertRoutesToRun("start the backup script", "backup")

    def test_start_script_backup(self):
        self.assertRoutesToRun("start script backup", "backup")

    def test_execute_the_backup_command(self):
        self.assertRoutesToRun("execute the backup command", "backup")

    def test_launch_the_weather_script(self):
        self.assertRoutesToRun("launch the weather script", "weather")

    def test_run_my_backup_script(self):
        self.assertRoutesToRun("run my backup script", "backup")

    def test_unknown_alias_does_not_run(self):
        messages = self._capture("run script that does not exist")
        self.assertIn(RUN_INTENT, [m.msg_type for m in messages])
        spoken = self._spoken(messages)
        self.assertTrue(
            any("don't know a script" in utt for utt in spoken),
            f"expected the unknown-script dialog to be spoken, got {spoken}",
        )
        self.assertFalse(
            any("running" in utt for utt in spoken),
            f"did not expect the running dialog to be spoken, got {spoken}",
        )
