#!/usr/bin/env python3
"""Voice-out for Claude Code, with a local `say` fallback (Moblee voice stack).

Runs as a Stop hook: reads the session transcript, takes the last assistant
text message, strips markdown/URL/code noise, caps the length, and speaks it.

Works out of the box with the built-in macOS voice (`say`). If an ElevenLabs
API key is present in the macOS Keychain (service "elevenlabs_api_key"), the
same text is spoken by an ElevenLabs voice instead. To add a key:
  security add-generic-password -s elevenlabs_api_key -a elevenlabs -w
(prompts for the key with hidden input). The key is read at call time and is
never stored in this file, the vault, or git.

Modes:
  (stdin JSON)                     Stop-hook mode: speak the latest assistant reply.
  speak-elevenlabs.py --last       Speak the latest reply on demand (ignores mute).
  speak-elevenlabs.py --last-full  Speak the latest reply IN FULL (PASTE_CAP,
                                   ~4 min max; `voice stop` cuts it).
  speak-elevenlabs.py "text"       Speak arbitrary text on demand (ignores mute).

Mute: if the file ~/.claude/voice-mute exists, Stop-hook mode stays silent
(manual modes still speak). Toggle with the `voice` helper.

Fails safe: missing key or API error -> local macOS `say`. Any error exits 0.

────────────────────────────────────────────────────────────────────────────
TUNABLES — edit these (or ask Claude to change any of them):
"""
VOICE_ID   = "JBFqnCBsd6RMkjVDRZzb"   # George — Warm British storyteller (ElevenLabs)
VOICE_NAME = "George"                  # (comment only; for humans reading this file)
MODEL_ID   = "eleven_turbo_v2_5"       # low-latency; "eleven_multilingual_v2" = richer, slower
CAP        = 400                       # soft cap: the sentence in flight completes, then "And more."
PASTE_CAP  = 5000                      # generous cap for `voice full` / `voice paste` (~4 min)
SPEED      = 1.1                       # 0.7 (slower) … 1.2 (faster)
STABILITY  = 0.5                       # 0 = expressive/variable, 1 = even/monotone
SIMILARITY = 0.75
STYLE      = 0.0
SPEAKER_BOOST = True
SAY_FALLBACK_RATE = 185                # words/min for the local `say` fallback
READ_DELAY = 0.7                       # seconds to wait for the transcript to flush
RECHECK_DELAY = 0.4                    # second read after this gap; the later read wins
# ────────────────────────────────────────────────────────────────────────────

import sys
import re, json, subprocess, tempfile, os, time, glob, urllib.request

MUTE_FLAG = os.path.expanduser("~/.claude/voice-mute")

def say_fallback(text):
    try:
        subprocess.run(["say", "-r", str(SAY_FALLBACK_RATE), text], check=False)
    except Exception:
        pass

def clean(text):
    t = text
    t = re.sub(r"```.*?```", " ", t, flags=re.S)
    t = re.sub(r"`[^`]*`", " ", t)
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", r"\1", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    t = re.sub(r"[*_#>|]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

# Speech normaliser: make text READ like speech, not a screen reader.
SPEAK_UNIT = {"mo": "month", "month": "month", "yr": "year", "year": "year",
              "wk": "week", "week": "week", "day": "day", "hr": "hour",
              "hour": "hour", "min": "minute"}

def normalise(t):
    t = t.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    t = re.sub(r"/\s*(mo|month|yr|year|wk|week|day|hr|hour|min)s?\b",
               lambda m: " a " + SPEAK_UNIT[m.group(1).lower()], t, flags=re.I)
    t = re.sub(r"(?<=\d)\s*/\s*(user|seat|person|license|email|contact|subscriber)s?\b",
               lambda m: " per " + m.group(1).lower(), t, flags=re.I)
    t = re.sub(r"\bper\s+(mo|yr|wk|hr)\b", lambda m: "per " + SPEAK_UNIT[m.group(1).lower()], t, flags=re.I)
    t = re.sub(r"(\w)\s*/\s*(\w)", r"\1 \2", t)
    t = re.sub(r"(\d)\s*%", r"\1 percent", t)
    t = re.sub(r"\s*&\s*", " and ", t)
    t = re.sub(r"(?<=[0-9kKmM])\s*\+(?!\d)", " plus", t)
    t = re.sub(r"~\s*(?=[\d$€£])", "about ", t)
    t = re.sub(r"\bvs\.?(?=\s|$)", "versus", t, flags=re.I)
    t = re.sub(r"\be\.g\.,?\s*", "for example, ", t)
    t = re.sub(r"\bi\.e\.,?\s*", "that is, ", t)
    t = re.sub(r"\s+[–—]\s+|\s+--\s+", ", ", t)
    t = re.sub(r"[•▪◦]", ",", t)
    t = re.sub(r"[\U0001F000-\U0001FAFF☀-➿⬀-⯿←-⇿]", "", t)
    return re.sub(r"\s{2,}", " ", t).strip()

def last_assistant_text(transcript_path):
    out = ""
    try:
        with open(transcript_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                if ev.get("type") != "assistant":
                    continue
                content = ev.get("message", {}).get("content", [])
                texts = [p.get("text", "") for p in content
                         if isinstance(p, dict) and p.get("type") == "text"]
                if texts:
                    out = "\n".join(texts)
    except Exception:
        return ""
    return out

def read_latest_with_delay(transcript_path):
    """Wait for the transcript to flush, then take the freshest assistant text."""
    time.sleep(READ_DELAY)
    first = last_assistant_text(transcript_path)
    time.sleep(RECHECK_DELAY)
    second = last_assistant_text(transcript_path)
    return second or first

def newest_transcript():
    files = glob.glob(os.path.expanduser("~/.claude/projects/**/*.jsonl"), recursive=True)
    return max(files, key=os.path.getmtime) if files else None

def get_key():
    try:
        r = subprocess.run(
            ["security", "find-generic-password", "-s", "elevenlabs_api_key", "-w"],
            capture_output=True, text=True, check=False)
        return r.stdout.strip()
    except Exception:
        return ""

def speak_elevenlabs(text, key):
    url = (f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
           f"?output_format=mp3_44100_128")
    body = json.dumps({
        "text": text,
        "model_id": MODEL_ID,
        "voice_settings": {
            "stability": STABILITY,
            "similarity_boost": SIMILARITY,
            "style": STYLE,
            "use_speaker_boost": SPEAKER_BOOST,
            "speed": SPEED,
        },
    }).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "xi-api-key": key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    })
    audio = urllib.request.urlopen(req, timeout=30).read()
    if not audio:
        raise RuntimeError("empty audio")
    fd, path = tempfile.mkstemp(suffix=".mp3", prefix="cc-voice-")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(audio)
        subprocess.run(["afplay", path], check=False)
    finally:
        try:
            os.remove(path)
        except Exception:
            pass

def speak(text, cap=CAP):
    text = normalise(clean(text))
    if not text:
        return
    if len(text) > cap:
        # Finish the sentence in flight rather than cutting mid-sentence.
        window = text[: cap + 150]
        ends = [m.end() for m in re.finditer(r'[.!?](?=[\s"”)\]]|$)', window)]
        if ends and ends[-1] >= cap * 0.5:
            text = window[: ends[-1]].rstrip() + " And more."
        else:
            text = text[:cap].rsplit(" ", 1)[0] + ", and more."
    key = get_key()
    if not key:
        say_fallback(text); return
    try:
        speak_elevenlabs(text, key)
    except Exception:
        say_fallback(text)

def main():
    args = sys.argv[1:]
    if args and args[0] == "--last":          # manual: re-read latest reply
        tp = newest_transcript()
        if tp:
            speak(last_assistant_text(tp))
        return
    if args and args[0] == "--last-full":     # manual: re-read latest reply in full
        tp = newest_transcript()
        if tp:
            speak(last_assistant_text(tp), cap=PASTE_CAP)
        return
    if args and args[0] == "--stdin":         # manual: speak piped text (voice paste)
        speak(sys.stdin.read(), cap=PASTE_CAP)
        return
    if args:                                   # manual: speak given text
        speak(" ".join(args))
        return
    # Stop-hook mode (stdin JSON)
    if os.path.exists(MUTE_FLAG):
        return
    _app = (os.environ.get("CLAUDE_CODE_ENTRYPOINT") == "claude-desktop"
            or os.environ.get("__CFBundleIdentifier") == "com.anthropic.claudefordesktop")
    if not (os.environ.get("TERM") or _app):   # neither terminal nor Claude app
        return                                 # headless run (cron/launchd): never speak
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    tp = data.get("transcript_path")
    if not tp:
        return
    speak(read_latest_with_delay(tp))

if __name__ == "__main__":
    main()
    sys.exit(0)
