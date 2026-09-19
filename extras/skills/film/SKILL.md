---
name: film
description: Make or edit a video from a plain-words description, end to end, with Claude doing every step and the owner only watching finished drafts. Covers cutting, trimming and splicing clips, crossfades, title cards, moving text, captions and subtitles, music and narration under picture, and colour. Simple cuts run through ffmpeg; composed pieces are built as a Remotion project in the studio folder <vault>/outputs/film/<project>/. Trigger when the owner says "make a film", "make a video", "edit this video", "cut these clips together", "trim this clip", "join these videos", "add a title", "add captions", "add subtitles", "put music under this", "add narration", "colour grade this", "make it brighter", "re-cut", "try another version", or hands over a video file with an instruction about how it should look. Do not trigger on watching or summarising a video (the watch plugin does that), on audio-only work (the audio skill), on still pictures (the pictures skill), or on PDF renders (wiki-to-pdf).
---

# film

The owner describes the film; Claude makes it and shows a finished draft. The owner never opens an editor, drags a clip or types a command. Every step below is Claude's, and the only thing the owner does is watch a draft and say, in ordinary words, what should change.

## Before starting: check the tools

Run these checks once per session, before the first edit. Each prints a path or a count; an empty answer or a zero means the tool is missing.

```bash
command -v ffmpeg
command -v ffprobe
command -v node
command -v npx
grep -c "remotion@remotion" ~/.claude/plugins/installed_plugins.json
grep -c "watch@" ~/.claude/plugins/installed_plugins.json
```

If ffmpeg is missing, nothing in this skill can run: say so plainly and tell the owner that the Moblee setup adds it, by running `python3 scripts/moblee-setup.py` from the Moblee pack folder, whose location is recorded in `~/.config/moblee/package-path`. If only Node or the Remotion plugin is missing, simple cuts still work through ffmpeg, but titles with movement and designed captions do not; say which part is unavailable and point to the same setup command. The Remotion plugin supplies the `remotion-*` skills (best practice for compositions, captions, rendering); read the relevant one before writing any composition.

## The studio folder

Every film gets its own folder inside the vault, created on first use:

```
<vault>/outputs/film/<project>/
  sources/     copies of clips, music and pictures that came from outside the vault
  work/        intermediate files: trims, joins, filter files, stills for checking
  out/         drafts the owner sees: draft-1.mp4, draft-2.mp4, ...
  remotion/    the Remotion project, only when the film needs one
```

`<vault>` is the vault root (the folder holding `CLAUDE.md` and `wiki/`). Name `<project>` from the owner's description in a few plain words ("Garden Party", "Lisbon Trip"). Create it with `mkdir -p "outputs/film/Garden Party/sources"`, run from the vault root, and the same for `work` and `out`. Quote every path: the folder name has spaces. The studio sits inside the vault because the vault's delete guard refuses to copy vault material out of the vault, and because drafts belong with the wiki that describes them.

**Originals are never touched.** A source already inside the vault (in `raw/`, say) is read where it is, with `ffmpeg -i "raw/<file>"`, which never writes to it. A source from anywhere else (the Desktop, Downloads, Photos exports) is copied in first with `cp -n "<original>" "outputs/film/<project>/sources/"`, and only the copy is used. Nothing is ever deleted or overwritten: every ffmpeg command carries `-n` (refuse to overwrite), every new version gets a new filename, and a rejected draft stays in `out/` beside the next one. If a folder fills up, move old work into `work/old/`; never remove it.

## Which tool does what

**ffmpeg** for anything that is only cutting or adjusting: trims, joins, crossfades, speed changes, colour, swapping or mixing sound, simple fixed titles and burned-in subtitles. It is fast, and an untouched soundtrack can be copied straight across.

**Remotion** for anything designed on screen: titles that move, captions that appear word by word, lower-third name straps, end cards, picture-in-picture, or a film laid out on a timeline. Create the project inside `remotion/` following the plugin's `remotion-create` skill (the first install fetches packages from the internet and takes a minute or two). Put the prepared footage in the project's `public/` folder, register each film as a composition, and render with the `remotion-render` skill's guidance.

The usual shape is ffmpeg first to build a clean cut, then Remotion over it for the text layer.

**Remotion licence.** Remotion is free for an individual, for a for-profit organisation with up to three employees, for a non-profit, and for anyone evaluating it; a for-profit company above three employees needs a paid company licence (remotion.dev/license, which points to the licence file in the Remotion repository; wording checked 19 September 2026). If the owner mentions making films for an employer or a business, say this once before building a Remotion project.

## The run

1. **Look before planning.** Probe each source for length, size and frame rate, find its natural cut points, and make a contact sheet to look at (commands below). Count on what the file says, not on what the owner remembers.
2. **Say the plan in a few plain sentences**: what will be cut, what goes on screen, what the sound will be. A request framed as an idea ("let's make a film about the trip") wants the owner's go-ahead before building; a direct instruction on a file already handed over does not.
3. **Build in small steps that can be checked.** For Remotion, type-check (`npx tsc --noEmit`) and render stills of the frames that matter before any full render.
4. **Render the draft** to `out/draft-N.mp4`.
5. **Verify the actual file**, not the exit code: duration and streams with ffprobe, then a strip of frames at the title, each join, a few captions and the last seconds. Check that text clears faces and sits inside the frame. Listen to the joins for clicks and to the music level against any speech.
6. **Show the owner the film** by giving its full path and opening it (`open "<path to draft>"`, which plays it in QuickTime). Say what was checked and what is left to the owner's eye and ear, then take the reaction in plain words and make the next draft.

## Tested ffmpeg recipes

These were run on ffmpeg 9.0 before the skill shipped. Replace the file names; keep the shape. The paths are relative to the project folder, and each shell call starts afresh, so begin each command with `cd "<vault>/outputs/film/<project>" &&`, with the vault's real path written out.

```bash
# Length, size and frame rate of a clip
ffprobe -v error -show_entries format=duration:stream=codec_type,width,height,r_frame_rate -of compact "sources/clip.mp4"

# Find the cuts already in the footage (prints a time for each scene change)
ffmpeg -hide_banner -i "sources/clip.mp4" -vf "scdet=threshold=10" -f null -

# Contact sheet: one frame a second, eight to a sheet
ffmpeg -n -i "sources/clip.mp4" -vf "fps=1,scale=320:-1,tile=4x2" -frames:v 1 "work/sheet.png"

# Trim: from 2 s, keep 4 s, re-encoded so the cut lands on the exact frame
ffmpeg -n -ss 2 -i "sources/clip.mp4" -t 4 -c:v libx264 -crf 18 -pix_fmt yuv420p -c:a aac -b:a 192k "work/trim-1.mp4"

# Join trims end to end (list the files, in order, in work/cuts.txt as lines: file 'trim-1.mp4')
ffmpeg -n -f concat -safe 0 -i "work/cuts.txt" -c copy "work/joined.mp4"

# Crossfade two clips over 1 s (offset = first clip's length minus 1)
ffmpeg -n -i "work/trim-1.mp4" -i "work/trim-2.mp4" -filter_complex "[0:v][1:v]xfade=transition=fade:duration=1:offset=3[v];[0:a][1:a]acrossfade=d=1[a]" -map "[v]" -map "[a]" -c:v libx264 -crf 18 -pix_fmt yuv420p -c:a aac "work/joined-fade.mp4"

# Fixed title for the first 3 s, fading in and out
ffmpeg -n -i "work/joined.mp4" -vf "drawtext=fontfile=/System/Library/Fonts/Supplemental/Arial.ttf:text='A Day Out':fontsize=72:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2:enable='between(t,0,3)':alpha='if(lt(t,0.5),t/0.5,if(gt(t,2.5),(3-t)/0.5,1))'" -c:a copy "out/draft-1.mp4"

# Burn in subtitles from an .srt file
ffmpeg -n -i "work/joined.mp4" -vf "subtitles=work/captions.srt:force_style='FontName=Arial,FontSize=22,Outline=2'" -c:a copy "out/draft-2.mp4"

# Colour: a little more contrast and warmth
ffmpeg -n -i "work/joined.mp4" -vf "eq=contrast=1.08:saturation=1.15:gamma=0.97,colorbalance=rs=0.04:bs=-0.04" -c:a copy "work/graded.mp4"

# Music under the picture's own sound, music at a quarter volume, fading out
ffmpeg -n -i "work/joined.mp4" -i "sources/music.mp3" -filter_complex "[1:a]volume=0.25,afade=t=out:st=5:d=2[m];[0:a][m]amix=inputs=2:duration=first:normalize=0[a]" -map 0:v -map "[a]" -c:v copy -c:a aac -shortest "out/draft-3.mp4"

# Replace the sound entirely with a narration track
ffmpeg -n -i "work/joined.mp4" -i "work/narration.m4a" -map 0:v -map 1:a -c:v copy -c:a aac -shortest "out/draft-4.mp4"

# One still from 1.5 s in, for checking
ffmpeg -n -ss 1.5 -i "out/draft-1.mp4" -frames:v 1 -update 1 "work/check-title.png"
```

Titles: the font path must exist; `/System/Library/Fonts/Supplemental/Arial.ttf` ships with macOS. An apostrophe inside title text breaks the quoting, so put the words in a text file and use `textfile=work/title.txt` in place of `text=...`. Anything longer than a short filter goes into a filter file written with the Write tool and passed with `-/filter_complex "work/filter.txt"` (the leading `-/` tells ffmpeg to read the option from a file; the older `-filter_complex_script` is gone from current ffmpeg), which keeps the command plain. Name the output streams in the file (for example `[v]`) and pick them with `-map "[v]"`.

## Captions and subtitles

Words on screen are claims, so they are never guessed. There are three routes, in this order:

1. **The owner supplies the words** (a script, a lyric sheet, a speech they wrote). Claude times them against the sound.
2. **Transcription**, only if a transcription key exists. The watch plugin transcribes a local file from its own captions or, failing that, through a Whisper service (Groq or OpenAI) using a key kept in `~/.config/watch/.env`. Check for a key without revealing it: `grep -c -E "^(GROQ|OPENAI)_API_KEY=." ~/.config/watch/.env` (a count of 1 or 2 means a key is set). Transcription sends the extracted sound, not the video, to that service.
3. **No key**: ask. The owner can supply the words, set up a key through the watch plugin's own setup, or go without captions. Do not transcribe by ear from frames.

Write the timed words as an `.srt` file in `work/` with the Write tool, show the owner the full text before burning it in when anything is uncertain, and mark doubtful lines. Any stretch of more than six seconds with speech but no caption is a gap to check, not an assumption. For a script that is not Latin (Arabic, Hebrew and others), split by word, never by letter, and prefer a Remotion caption component over burned-in `.srt`, since right-to-left layout is easier to control there.

## Narration and music

Narration can be made free with the macOS voice (see the audio skill, which covers `say`, levelling and ducking music under a voice). A paid voice through a connected ElevenLabs connector is used only if the owner has connected it and agrees to the cost for this film. Record and measure narration first, then cut the pictures to fit it. Music under speech sits well below the voice; measure the mix rather than trusting a volume number, and aim for about -16 LUFS overall with peaks below -1 dB.

## Standing rules

- **A real person's likeness is never generated, altered or uploaded to a service without the owner's explicit word.** Use footage that already exists.
- **Keep the original sound as a straight copy** (`-c:a copy`) whenever the soundtrack is not being changed.
- **Match before joining**: when clips from different cameras are cut together, compare a still from each side and grade them towards each other.
- **Plain commands only**: no `$(...)`, no backticks, no heredocs, no `rm`. Longer logic goes in a file written with the Write tool.
- **New footage generation** (a clip made from a text prompt) happens only through a paid service the owner has connected and only on the owner's say-so for that clip, with the price stated first.

## After each film

If the owner corrected the approach, or a tool behaved differently from what is written here, say so and offer to update this file. If the owner wants the film remembered in the wiki, offer to capture a short note of it (title, date, where the file is) with the wiki-capture skill; the film itself stays in the studio folder.
