---
name: pictures
description: Edit photos and pictures from a plain-words request, with the assistant doing every step and the owner only looking at the finished files. Covers cropping, resizing, converting (HEIC to JPG, PNG, WebP, PDF), making files smaller for email or the web, rotating and straightening sideways phone photos, adding text or a caption, borders and frames, contact sheets, putting pictures side by side or into one PDF, and removing a plain background where the picture allows it. Uses ImageMagick (`magick`); results go to outputs/pictures/ in the vault. New images are generated only through a paid service the owner has connected, and only on the owner's say-so. Trigger when the owner says "crop this photo", "resize these", "make this smaller", "convert these HEIC files", "turn these into JPGs", "rotate this", "add a caption", "put text on this picture", "add a border", "make a contact sheet", "put these side by side", "make a PDF of these photos", "remove the background", "make a picture of", or hands over a picture with an instruction. Do not trigger on video (the film skill), on sound (the audio skill), on reading or describing what is in a picture (answer directly), on charts (the dashboard or dataviz work), or on brand design (design-your-brand).
---

# pictures

The owner says what the picture should look like; the assistant makes it and shows the finished file. The owner never opens an image editor. Every command below is the assistant's to run.

## Before starting: check the tool

```bash
command -v magick
magick -version
```

If `magick` is missing, say so plainly and tell the owner that the Moblee setup adds it, by running `python3 scripts/moblee-setup.py` from the Moblee pack folder, whose location is recorded in `~/.config/moblee/package-path`. Do not fall back to older tool names (`convert`, `mogrify`): `mogrify` edits files in place, which this skill never does.

## Where files go

Find the vault root in this order: the `MOBLEE_VAULT` environment variable; the path in `~/.config/moblee/vault-path`; otherwise walk up from the working directory to a folder holding `wiki/Index.md`. If none of these finds a vault, say so and stop rather than guess.

Each job gets its own folder under `outputs/pictures/`, named date-first from the request: `outputs/pictures/2026-09-19 Holiday Crops/`, with `sources/` for copies of the owner's pictures, `work/` for in-between files, and the finished pictures at the top of the job folder. `outputs/` is not tracked by git; if a picture should become a source for the wiki, copy it into `raw/` and say so.

**Originals are never touched.** Copy each picture in with `cp -n "<original>" "<job folder>/sources/"` and work on the copies. ImageMagick overwrites an existing file without asking, so **every output gets a new filename** that does not exist yet (`crop-1.jpg`, then `crop-2.jpg`); check with `ls` before writing when unsure. Nothing is deleted; earlier attempts stay beside the new one, or move into `work/old/`. Each shell call starts afresh, so begin each command with `cd "<vault>/outputs/pictures/<job>" &&`.

## The run

1. **Look first.** Read each picture (Claude can view images directly) and check its size and format with `magick identify`. Photos from a phone often carry a rotation flag rather than rotated pixels; `-auto-orient` settles that.
2. **Say what will be done** in a sentence when there is a real choice (where to crop, what size to aim for). A clear instruction needs no confirmation.
3. **Make it**, then **look at the result** before handing it over: check that the crop kept the heads, that text is legible and inside the frame, and that a compressed file still looks right.
4. **Hand it over** with its full path and open it (`open "<file>"`, which shows it in Preview). For a batch, show a contact sheet of the results rather than twenty separate files. Take the reaction in plain words.

## Tested recipes

Run on ImageMagick 7.1 before the skill shipped. Replace the file names; keep the shape. The `>` in a size means "only shrink, never enlarge" and must stay inside the quotes.

```bash
# Size, format and colour of a picture
magick identify -format "%f %wx%h %m %[colorspace]\n" "sources/photo.jpg"

# HEIC (iPhone) to JPG, turned the right way up
magick "sources/IMG_1234.HEIC" -auto-orient -quality 90 "IMG_1234.jpg"

# Crop the centre 800 x 600 (use +X+Y offsets with -gravity northwest for any other area)
magick "sources/photo.jpg" -gravity center -crop 800x600+0+0 +repage "crop-1.jpg"

# Resize to fit inside 600 x 600, keeping the shape
magick "sources/photo.jpg" -resize 600x600 "small-1.jpg"

# Make smaller for email: no larger than 1600 px, metadata stripped, quality 80
magick "sources/photo.jpg" -auto-orient -resize "1600x1600>" -strip -quality 80 "email-1.jpg"

# Rotate a quarter turn clockwise
magick "sources/photo.jpg" -rotate 90 "rotated-1.jpg"

# Text near the bottom, white with a thin dark outline
magick "sources/photo.jpg" -gravity south -fill white -stroke black -strokewidth 2 -font /System/Library/Fonts/Supplemental/Arial.ttf -pointsize 48 -annotate +0+30 "Summer 2026" "titled-1.jpg"

# A caption bar across the bottom that wraps long text to the picture's width (1200 here)
magick "sources/photo.jpg" -gravity south -background "#00000099" -fill white -font /System/Library/Fonts/Supplemental/Arial.ttf -size 1200x -pointsize 36 caption:"A longer caption that wraps on its own" -composite "captioned-1.jpg"

# White mount with a thin grey edge
magick "sources/photo.jpg" -bordercolor white -border 40 -bordercolor "#cccccc" -border 2 "framed-1.jpg"

# Side by side, or one above the other
magick "a.jpg" "b.jpg" +append "side-by-side.jpg"
magick "a.jpg" "b.jpg" -background white -gravity center -append "stacked.jpg"

# Contact sheet, three across, each labelled with its filename (-label must come before the files)
magick montage -label "%f" -font /System/Library/Fonts/Supplemental/Arial.ttf -pointsize 14 "a.jpg" "b.jpg" "c.jpg" "d.jpg" -tile 3x -geometry 300x300+10+10 -background white "contact-sheet.jpg"

# Several pictures into one PDF, a page each
magick "a.jpg" "b.jpg" "c.jpg" "album.pdf"

# Remove a plain white background: every near-white pixel becomes clear (output must be PNG)
magick "sources/logo.png" -fuzz 10% -transparent white "logo-clear.png"

# Remove only the background touching the edges, keeping white inside the subject
magick "sources/logo.png" -alpha set -bordercolor white -border 1 -fill none -fuzz 10% -draw "color 0,0 floodfill" -shave 1x1 "logo-clear-edge.png"
```

For many files at once, write the list of commands into a script file under `work/` with the Write tool, one plain `magick` line per picture, and run it with `bash "work/batch.sh"`; do not build the list with shell loops over substituted names. A small batch can simply be run as separate commands.

## What is and is not feasible

**Background removal** works well on a logo, a product shot or a signature on a plain, even background (the two recipes above; raise `-fuzz` a little if a halo remains, lower it if the subject starts to vanish). It does not work on a person against a busy scene: ImageMagick has no subject detection. Say so plainly rather than hand over a poor cut-out, and offer the alternatives: a connected image service that edits pictures (paid, see below), or the free built-in route on the Mac, where the owner opens the copy in Preview and uses its Remove Background command (macOS 14 and later) [Unverified on every macOS version]. That last one is the owner's step, so offer it, never assume it.

**Straightening a tilted horizon** is feasible with a small rotation and a centre crop to remove the corners (`-rotate 2 -gravity center -crop 1100x740+0+0 +repage` on a 1200 x 800 picture); judge the angle by looking, then check the result.

**Colour and brightness**: `-auto-level` stretches a flat photo's range; `-modulate 105,110` raises brightness by 5 per cent and saturation by 10 per cent. Small steps, then look.

## Making new pictures

ImageMagick edits pictures; it does not invent them. A new image from a description (an illustration, a mock-up, a background) is made only through an image-generation service the owner has connected to Claude (for example an ElevenLabs connector, or another the owner has added), and only when the owner asks for it for this picture. With ChatGPT: Moblee does not set this up for ChatGPT yet. Such services cost money: say so, and state the price if the service shows one, before generating. If nothing suitable is connected, say that plainly; do not reach for an unconnected service or ask the owner for a key to one. A real person's likeness is never generated or altered without the owner's explicit word. A generated picture is saved into the job folder like any other result and labelled as generated in its filename (`generated-1.png`).

## Standing rules

- **Plain commands only**: no `$(...)`, no backticks, no heredocs, no `rm`. Anything longer goes in a file written with the Write tool.
- **Never overwrite, never delete, never edit in place.** New names for new versions; no `mogrify`.
- **Private metadata**: phone photos carry the place they were taken. When a picture is being prepared to send or publish, strip it (`-strip`) and say that it was stripped; when it is being kept for the owner, leave it.

## After each job

If the owner corrected the approach, or a tool behaved differently from what is written here, say so and offer to update this file.
