# OVOS Cmd Skill

This OVOS skill runs shell scripts and other commands. The commands run without asking for confirmation.

## Install

```bash
pip install ovos-skill-cmd
```

## Usage

Trigger a command with a spoken phrase:

- "Hey Mycroft, launch command echo TEST"
- "Hey Mycroft, run script generate report"

## Configuration

Configure the skill in `settings.json`. Map a spoken phrase to a script or command under `alias`. For example:

```json
{
  "alias": {
    "generate report": "/home/forslund/scripts/generate_report.sh"
  }
}
```

With this setting, the phrase "run script generate report" makes the skill execute `/home/forslund/scripts/generate_report.sh`.

### user

Set `user` to run commands under a specific user's privileges:

```json
{
  "user": "ovos"
}
```

### shell

Set `shell` to control whether commands run through a shell. It defaults to `true`:

```json
{
  "shell": false
}
```

### Full example

```json
{
  "user": "ovos",
  "alias": {
    "generate report": "/home/forslund/scripts/generate_report.sh",
    "update system": "sudo apt update && sudo apt upgrade -y",
    "reboot device": "sudo reboot"
  },
  "shell": true
}
```

## Security notes

- Running commands through a shell allows complex operations but can expose security risks. If your commands do not need shell features, set `shell` to `false`.
- A command can run under a specific user through the `user` field. Make sure that user has the permissions the command needs.
- Do not configure dangerous commands, such as `rm -rf`, without additional safeguards.

## Docker containers

Commands run only inside the Docker container. If a command also needs an effect outside the container, use an additional mechanism, such as a named pipe.

This example steers Kodi, which runs outside the container, from `ovos-skill-cmd`:

```json
{
    "alias": {
        "kodi restart": "echo \"systemctl restart kodi\" > /home/ovos/.config/mycroft/joespipe",
        "kodi mute": "echo \"kodi-send --action=\\\"Mute\\\"\" > /home/ovos/.config/mycroft/joespipe",
        "kodi unmute": "echo \"kodi-send --action=\\\"Mute\\\"\"  > /home/ovos/.config/mycroft/joespipe",
        "kodi louder": "echo \"kodi-send --action=\\\"VolumeUp\\\"\" > /home/ovos/.config/mycroft/joespipe",
        "kodi lower": "echo \"kodi-send --action=\\\"VolumeDown\\\"\" > /home/ovos/.config/mycroft/joespipe",
        "kodi pause": "echo \"kodi-send --action=\\\"PlayerControl(Play)\\\"\" > /home/ovos/.config/mycroft/joespipe",
        "kodi resume": "echo \"kodi-send --action=\\\"PlayerControl(Play)\\\"\" > /home/ovos/.config/mycroft/joespipe",
        "kodi stop": "echo \"kodi-send --action=\\\"PlayerControl(Stop)\\\"\" > /home/ovos/.config/mycroft/joespipe"
    },
    "shell": true,
    "__mycroft_skill_firstrun": false
}
```

`/home/ovos/.config/mycroft/joespipe` is a named pipe in the shared volume of the OVOS config folder. Outside the container, a small script watches the pipe for commands:

```bash
#!/bin/bash
while true; do eval "$(cat /storage/ovos/config/joespipe)"; done
```

Read more about this named-pipe approach on [Stack Overflow](https://stackoverflow.com/questions/32163955/how-to-run-shell-script-on-host-from-docker-container).

## Related projects

- [OpenVoiceOS/OpenVoiceOS](https://github.com/OpenVoiceOS/OpenVoiceOS) — the OVOS platform this skill runs on.

## License

Apache License 2.0. See [LICENSE.txt](LICENSE.txt).
