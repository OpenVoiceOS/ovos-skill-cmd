#   Copyright 2024 Åke Forslund
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

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
            for lang in self.native_langs:
                self.register_vocabulary(alias, 'Script', lang=lang)

    @intent_handler(IntentBuilder('RunScriptCommandIntent')
                    .require('Script').require('Run'))
    def run(self, message):
        self.acknowledge()
        script = message.data.get('Script')
        script = self.alias.get(script, script)
        shell = self.settings.get('shell', True)
        args = script.split(' ') if shell else script
        try:
            LOG.info(f'Running {args}')
            if self.uid and self.gid:
                subprocess.Popen(args, preexec_fn=set_user(self.uid, self.gid), shell=shell)
            else:
                subprocess.Popen(args, shell=shell)
        except Exception:
            LOG.exception('Could not run script ' + script)
            self.play_audio("snd/error.mp3", instant=True)
