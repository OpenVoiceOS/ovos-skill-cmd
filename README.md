# Commands Skill

A Simple OVOS skill for running shell scripts and other commands. The commands will run quietly without any confirmation from OVOS.

## Usage

*Hey Mycroft, launch command echo TEST*

*Hey Mycroft, run script generate report*

## Configuration

The skill can be configured to run scripts from easily pronounceable human utterances, such as "generate report" by adding the following to the skill `settings.json`

```json
{
  "alias": {
    "generate report": "/home/forslund/scripts/generate_report.sh"
  }
}
```

The configuration above will launch `/home/forslund/scripts/generate_report.sh` when "run script generate report" is said by the user.
