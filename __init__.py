from pwd import getpwnam
import os
import subprocess

from ovos_utils.log import LOG
from ovos_workshop.skills import OVOSSkill
from ovos_workshop.intents import IntentBuilder
from ovos_workshop.decorators import intent_handler


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
            LOG.info(f"Adding script keyword: {alias}")
            self.register_vocabulary(alias, 'Script')

    @intent_handler(IntentBuilder('RunScriptCommandIntent')
                    .require('Script').require('Run'))
    def run(self, message):
        script = message.data.get('Script')
        script = self.alias.get(script, script)
        args = script.split(' ')
        try:
            if self.uid and self.gid:
                subprocess.Popen(args, preexec_fn=set_user(self.uid, self.gid))
            else:
                LOG.info(f'Running {args}')
                subprocess.Popen(args)
        except Exception:
            LOG.exception('Could not run script ' + script)
