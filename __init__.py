from pwd import getpwnam
import os
import subprocess

from ovos_utils.log import LOG
from ovos_workshop.skills import OVOSSkill
from ovos_workshop.intents import IntentBuilder


def set_user(uid, gid):
    LOG.info(f'Setting group and user to {gid}:{uid}')
    os.setgid(gid)
    os.setuid(uid)


class CmdSkill(OVOSSkill):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.uid = None
        self.gid = None
        self.alias = {}

    def initialize(self):
        user = self.settings.get('user')
        if user:
            pwnam = getpwnam(user)
            self.uid = pwnam.pw_uid
            self.gid = pwnam.pw_gid
        self.alias = self.settings.get('alias') or {}

        for alias in self.alias:
            self.log.info("Adding {}".format(alias))
            self.register_vocabulary(alias, 'Script')

        intent = IntentBuilder('RunScriptCommandIntent')\
            .require('Script').require('Run').build()
        self.register_intent(intent, self.run)

        self.add_event('CmdSkillRun', self.run)

    def run(self, message):
        script = message.data.get('Script')
        script = self.alias.get(script, script)
        args = script.split(' ')
        try:
            if self.uid and self.gid:
                subprocess.Popen(args, preexec_fn=set_user(self.uid, self.gid))
            else:
                self.log.info('Running {}'.format(args))
                subprocess.Popen(args)
        except Exception:
            self.log.debug('Could not run script ' + script, exc_info=True)
