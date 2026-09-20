---
name: audio
description: Edit sound files from a plain-words request, with the assistant doing every step and the owner only listening to the finished file. Covers trimming, joining, fading, evening out loudness, taking out long silences, converting between formats (MP3, M4A, WAV, AIFF, FLAC), pulling the sound out of a video, laying a voice over music with the music dipping under the speech, and reading a wiki page, a brief or any text aloud into an audio file. Uses ffmpeg, the free macOS voice (`say`), and an ElevenLabs connector only if the owner connected one and agrees to the cost. Results go to outputs/audio/ in the vault. Trigger when the owner says "trim this recording", "cut the start off this", "join these audio files", "fade this out", "make this louder", "even out the volume", "take out the silences", "convert this to MP3", "get the sound from this video", "put my voice over this music", "read this page aloud", "turn this brief into audio", "make a podcast version of", or hands over a sound file with an instruction. Do not trigger on video editing (the film skill), on still pictures (the pictures skill), on the voice stack that reads Claude's chat replies aloud, or on transcribing a video to answer questions about it (the watch plugin).
---

# audio

The owner says what the sound should be; the assistant makes it and hands over a finished file to play. The owner never opens an audio editor. Every command below is the assistant's to run.

## Before starting: check the tools

```bash
command -v ffmpeg
command -v ffprobe
command -v say
```

If ffmpeg is missing, say so plainly and tell the owner that the Moblee setup adds it, by running `python3 scripts/moblee-setup.py` from the Moblee pack folder, whose location is recorded in `~/.config/moblee/package-path`. `say` is part of macOS and is always present on a Mac. Whether an ElevenLabs connector is available is shown by the tools in the current session (a speech-generation tool from ElevenLabs); if there is none, the free voice is the only voice, and that is fine.

## Where files go

Find the vault root in this order: the `MOBLEE_VAULT` environment variable; the path in `~/.config/moblee/vault-path`; otherwise walk up from the working directory to a folder holding `wiki/Index.md`. If none of these finds a vault, say so and stop rather than guess.

Each job gets its own folder under `outputs/audio/`, named date-first from the request: `outputs/audio/2026-09-19 Interview Trim/`, with `sources/` for copies of the owner's files, `work/` for in-between files, and the finished files at the top of the job folder. `outputs/` is not tracked by git, so nothing here enters the wiki's history; if the owner wants a recording kept as a source for the wiki, copy it into `raw/` and say so.

**Originals are never touched.** Copy each file in with `cp -n "<original>" "<job folder>/sources/"` and work on the copies. Nothing is deleted or overwritten: every ffmpeg command carries `-n` (refuse to overwrite), each new attempt gets a new filename (`take-2.m4a`), and earlier attempts stay beside it. Each shell call starts afresh, so begin each command with `cd "<vault>/outputs/audio/<job>" &&`.

## The run

1. **Look first.** Probe the file for length, format and loudness, and find the silences, before deciding anything.
2. **Say what will be done** in a sentence or two when the request leaves a real choice (how much silence to keep, how loud the music should sit). A clear instruction needs no confirmation.
3. **Make it**, in the fewest steps that each can be checked.
4. **Check the result**: length with ffprobe, loudness with the meter below, and for joins or cuts, the silences around each edit. Numbers are measured; whether a cut sounds natural is for the owner's ear, and saying so is part of handing it over.
5. **Hand it over** with its full path and play it (`open "<file>"`, which plays in the default player), then take the reaction in plain words.

## Tested recipes

Run on ffmpeg 9.0 and macOS `say` before the skill shipped. Replace the file names; keep the shape.

```bash
# Length and format
ffprobe -v error -show_entries format=duration,format_name:stream=codec_name,sample_rate,channels -of compact "sources/talk.m4a"

# Loudness of the whole file (the "I:" line in the summary is the figure, in LUFS)
ffmpeg -hide_banner -i "sources/talk.m4a" -af ebur128 -f null -

# Peak and average level
ffmpeg -hide_banner -i "sources/talk.m4a" -af volumedetect -f null -

# Where the silences are (quieter than -45 dB for 0.6 s or more)
ffmpeg -hide_banner -i "sources/talk.m4a" -af silencedetect=noise=-45dB:d=0.6 -f null -

# Trim: from 0.5 s, keep 8 s
ffmpeg -n -ss 0.5 -i "sources/talk.wav" -t 8 -c copy "work/trim-1.wav"

# Fade in over 2 s and out over the last 2 s of an 8 s file
ffmpeg -n -i "work/trim-1.wav" -af "afade=t=in:d=2,afade=t=out:st=6:d=2" "work/faded.wav"

# Shorten every long silence to 0.6 s
ffmpeg -n -i "sources/talk.wav" -af "silenceremove=start_periods=1:start_threshold=-45dB:stop_periods=-1:stop_duration=0.6:stop_threshold=-45dB" "work/tight.wav"

# Even out loudness to -16 LUFS with peaks under -1.5 dB (right for spoken word and podcasts)
ffmpeg -n -i "work/tight.wav" -af "loudnorm=I=-16:TP=-1.5:LRA=11" -ar 48000 "work/level.wav"

# Join files end to end, first bringing both to 48 kHz stereo (otherwise the join takes the first file's rate)
ffmpeg -n -i "work/part-1.wav" -i "work/part-2.mp3" -filter_complex "[0:a]aresample=48000,aformat=channel_layouts=stereo[a0];[1:a]aresample=48000,aformat=channel_layouts=stereo[a1];[a0][a1]concat=n=2:v=0:a=1[a]" -map "[a]" "work/joined.wav"

# Convert: to M4A (small, plays everywhere on Apple devices), MP3, or FLAC (lossless)
ffmpeg -n -i "work/level.wav" -c:a aac -b:a 160k "talk.m4a"
ffmpeg -n -i "work/level.wav" -c:a libmp3lame -q:a 2 "talk.mp3"
ffmpeg -n -i "work/level.wav" -c:a flac "talk.flac"

# Take the sound out of a video, unchanged
ffmpeg -n -i "sources/video.mp4" -vn -c:a copy "video-sound.m4a"

# Voice over music, the music dipping whenever the voice speaks, running to the end of the music
ffmpeg -n -i "work/voice.wav" -i "sources/music.mp3" -filter_complex "[0:a]aresample=48000,asplit=2[v1][v2];[v2]apad[key];[1:a]volume=0.5[m];[m][key]sidechaincompress=threshold=0.05:ratio=8:attack=20:release=400[duck];[duck][v1]amix=inputs=2:duration=first:normalize=0[out]" -map "[out]" -c:a aac -b:a 192k "voice-over-music.m4a"
```

Notes on the recipes. The loudness line measures the average over the file, so a recording that is mostly quiet room with a little speech will have its room noise raised; for such a file, take out the silences first, then level. In the voice-over recipe, `volume=0.5` sets how loud the music is before it dips and `ratio=8` how far it dips; fade the music out first (the fade recipe) so the end is not abrupt. Longer filters go in a file written with the Write tool and passed with `-/filter_complex "work/filter.txt"`.

## Reading text aloud

To turn a wiki page, a brief or any text into an audio file:

1. **Prepare a clean script.** Read the page and write a plain-text version with the Write tool to `work/script.txt`: no frontmatter, no markdown symbols, wikilinks reduced to their words, tables turned into sentences or left out (say which), and headings kept as short spoken lines. Abbreviations the voice would stumble on are written out. Read the script once for anything that would sound wrong before recording it.
2. **Choose the voice.** The free route is macOS `say`. `say -v '?'` lists the installed voices with their language; pick one that fits the text's language (Daniel is a British English voice present on most Macs). Better-sounding voices can be added free in System Settings, under Accessibility, Spoken Content, System Voice, Manage Voices; that is the owner's step if they want it, and optional.
3. **Record and convert:**

```bash
say -v Daniel -r 175 -f "work/script.txt" -o "work/voice.aiff"
ffmpeg -n -i "work/voice.aiff" -af "loudnorm=I=-16:TP=-1.5:LRA=11" -ar 48000 -c:a aac -b:a 160k "Page Title read aloud.m4a"
```

`-r` is words a minute (175 is a natural pace; 160 is slower and clearer). A long page records in well under a minute.

**The paid voice.** If an ElevenLabs connector is connected in the session, it can make a more natural reading, but it costs money. Offer it once, say that it is paid, and use it only if the owner agrees for this piece; never assume it, and never use it as a quiet default. When it is used, the script from step 1 is what gets sent, and the returned file is levelled and converted with the same ffmpeg line.

## Standing rules

- **Plain commands only**: no `$(...)`, no backticks, no heredocs, no `rm`. Anything longer goes in a file written with the Write tool.
- **Never overwrite, never delete.** New names for new versions; old versions stay. If a job folder grows untidy, move old takes into `work/old/`.
- **Someone else's voice is not cloned or imitated** with a paid voice service without that person's permission, which the owner must state.
- **Keep speech intelligible over everything else**: music sits under a voice, never level with it.

## After each job

If the owner corrected the approach, or a tool behaved differently from what is written here, say so and offer to update this file.
