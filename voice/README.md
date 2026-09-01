# Moblee voice stack (macOS)

Give Claude a voice. After installing, every Claude Code reply is read aloud,
and Claude nudges you audibly when it is waiting on your input or a permission
click — useful the moment you look away from the screen.

**Works out of the box, free.** The stack uses the built-in macOS voice by
default. If you later add an ElevenLabs API key (a paid text-to-speech service
with strikingly natural voices), the same stack upgrades itself automatically —
no reinstall.

## Install

```
python3 voice/install-voice.py
```

Safe to re-run; it backs up your Claude settings first and never duplicates or
removes existing hooks.

## Everyday commands (in Terminal)

| Command | What it does |
|---|---|
| `voice off` / `voice on` | Mute / unmute the automatic read-aloud |
| `voice stop` | Cut whatever is currently being spoken |
| `voice last` | Re-read the latest reply (short version) |
| `voice full` | Read the latest reply **in full** (up to ~4 minutes) |
| `voice say hello there` | Speak arbitrary text |
| `voice paste` | Read the clipboard aloud |
| `voice status` | Muted or on? |

Replies are spoken in a shortened form (about the first 400 characters,
finishing the sentence, then "And more."). When you want the whole thing,
`voice full`.

**Tip:** make macOS Shortcuts for `voice stop` and `voice full` (a "Run Shell
Script" action containing `"$HOME/.claude/hooks/voice" stop` or `… full`) so
they are one click from anywhere.

## Upgrading to ElevenLabs

1. Create an account at elevenlabs.io and copy an API key.
2. In Terminal:
   ```
   security add-generic-password -s elevenlabs_api_key -a elevenlabs -w
   ```
   Paste the key at the hidden prompt.
3. That's it — the next reply speaks in the ElevenLabs voice. The default voice
   is George (a warm British storyteller); ask Claude to change the voice, the
   speed, or the reply cap — they are plain tunables at the top of
   `~/.claude/hooks/speak-elevenlabs.py`.

The key lives only in your macOS Keychain. If the key is missing or the API
errs, the stack falls back to the built-in voice rather than failing.
