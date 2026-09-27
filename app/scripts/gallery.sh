#!/bin/bash
# Draw every screen the app can draw, in every appearance and both directions,
# onto one page to look at.
#
#   bash app/scripts/gallery.sh
#
# Builds the app, then draws the whole set of screens twelve times over — light
# and dark, laid out left to right and right to left, at each of the three sizes
# the words can be set to — and writes one HTML page that puts every version of
# a screen beside every other version of the same screen. Open the page and look
# at it: that is the whole point of it. The page can be searched by screen name,
# jumped around by screen name, and narrowed to one appearance, one direction or
# one size at a time.
#
# The page says at the top when it was drawn, which Moblee it came from, and how
# many screens each of the twelve runs produced. If the runs do not all produce
# the same screens it says so in red at the top and names the ones that are
# missing, because a screen that draws one way round and not the other is
# exactly the fault this page exists to find.
#
# Everything it makes is kept OUTSIDE the Moblee folder, under
# ../gallery (or $MOBLEE_GALLERY_DIR). Each run gets a fresh folder, so a screen
# that has since been taken out can never linger in a newer page; the newest
# page's path is written to ../gallery/latest.txt. The script refuses to write
# anywhere inside the Moblee folder. Old runs are left where they are — a run is
# about 200 MB, and this script deletes nothing; prune them by hand when the
# folder gets heavy.
#
# The practice home the drawing runs need is made fresh under $TMPDIR and
# nothing outside it is touched. The size the words are drawn at is passed on
# the command line for every run, so the size the person at this Mac has set is
# neither read nor written. (v0.9.5)
#
#   --sizes 0,2     draw only some of the three sizes (0 normal, 1 bigger,
#                   2 biggest); the default is all three
#   --no-build      use the app already built, rather than building first
#   --no-open       write the page but do not open it
set -u

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pack_root="$(dirname "$(dirname "$here")")"

sizes="0,1,2"
build=yes
open_it=yes
while [ $# -gt 0 ]; do
    case "$1" in
        --sizes)
            # A switch that takes a value has to be told when it has not been
            # given one. `shift 2` with a single argument left shifts nothing
            # at all and reports a failure nobody is reading, so the loop turns
            # for ever on the same switch and the tool simply hangs. A tool
            # that hangs is worse than one that stops and says why. (v0.9.5)
            [ $# -ge 2 ] || { echo "gallery.sh: --sizes needs a value, for example --sizes 0,2."; exit 2; }
            case "$2" in
                # A switch where the value should be is nearly always a value
                # left out by mistake, and swallowing it would quietly turn off
                # something the person asked for. (v0.9.5)
                -?*) echo "gallery.sh: --sizes was given $2, which is a switch and not a size. For example: --sizes 0,2."; exit 2 ;;
            esac
            sizes="$2"; shift 2 ;;
        --no-build) build=no; shift ;;
        --no-open) open_it=no; shift ;;
        *) echo "gallery.sh: unknown switch $1"; exit 2 ;;
    esac
done

size_list=""
for s in $(printf '%s\n' "$sizes" | tr ',' ' '); do
    case "$s" in
        0|1|2) ;;
        *) echo "gallery.sh: --sizes takes 0 (normal), 1 (bigger) and 2 (biggest), separated by commas."; exit 2 ;;
    esac
    # The same size asked for twice would draw the same four runs twice over,
    # one on top of the other, and put the same picture on the page twice. Once
    # each is what was meant by it. (v0.9.5)
    case " $size_list " in *" $s "*) continue ;; esac
    size_list="$size_list $s"
done
[ -n "$size_list" ] || { echo "gallery.sh: --sizes was empty; nothing to draw."; exit 2; }

size_name() { case "$1" in 0) echo normal ;; 1) echo bigger ;; 2) echo biggest ;; esac; }
size_words() { case "$1" in 0) echo "Normal" ;; 1) echo "Bigger" ;; 2) echo "Biggest" ;; esac; }

# Work out where a path really is without needing it to be there yet. Walk up
# to the deepest folder that does exist, ask the filesystem for that one's real
# name, and put the rest of the path back on the end. The plain `cd` to the
# parent this used to do came back empty whenever the parent did not exist, and
# an empty answer matches nothing, so the one check that keeps output out of
# the Moblee folder passed on exactly the run that needed it most: the first
# one, before anything had been made. This says no when it cannot tell, which
# for a check like this is the only safe way round. (v0.9.5)
where_is() {
    local head rest up
    rest=""
    case "$1" in /*) head="$1" ;; *) head="$PWD/$1" ;; esac
    while [ ! -d "$head" ]; do
        rest="/$(basename "$head")$rest"
        up="$(dirname "$head")"
        [ "$up" = "$head" ] && break
        head="$up"
    done
    head="$(cd "$head" 2>/dev/null && pwd -P)" || return 1
    [ -n "$head" ] || return 1
    printf '%s' "${head%/}$rest"
}

# The page and its pictures go outside the Moblee folder and stay there. A
# gallery inside the folder would be committed by somebody sooner or later, and
# the app carries the folder's committed files inside itself, so it would end up
# inside the app as well. (v0.9.5)
OUT_ROOT="${MOBLEE_GALLERY_DIR:-$(dirname "$pack_root")/gallery}"
out_really="$(where_is "$OUT_ROOT")" || {
    echo "gallery.sh: could not work out where $OUT_ROOT is. Nothing was done."; exit 2; }
pack_really="$(where_is "$pack_root")" || {
    echo "gallery.sh: could not work out where the Moblee folder $pack_root is. Nothing was done."; exit 2; }
case "$out_really" in
    "$pack_really"|"$pack_really"/*)
        echo "gallery.sh: $OUT_ROOT is inside the Moblee folder. Nothing was done."
        exit 2 ;;
esac

if [ "$build" = yes ]; then
    echo "Building the app…"
    bash "$here/build-app.sh" > /dev/null || { echo "gallery.sh: the app did not build. Run: bash app/scripts/build-app.sh"; exit 1; }
fi
APP="$(cat "${MOBLEE_BUILD_DIR:-$HOME/Library/Caches/moblee-build}/latest.txt" 2>/dev/null)"
[ -n "$APP" ] && [ -x "$APP/Contents/MacOS/Moblee" ] || { echo "gallery.sh: no built app found. Run: bash app/scripts/build-app.sh"; exit 1; }
BIN="$APP/Contents/MacOS/Moblee"

pack_version="$(cat "$pack_root/VERSION" 2>/dev/null || echo unknown)"
app_version="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$APP/Contents/Info.plist" 2>/dev/null || echo unknown)"
app_build="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleVersion' "$APP/Contents/Info.plist" 2>/dev/null || echo unknown)"

stamp="$(date '+%Y%m%d-%H%M%S')"
# Every run gets a folder nothing has been drawn into before, which is what
# keeps a screen that has since been taken out from lingering in a newer page.
# The stamp is only good to the second, so two runs started inside one second
# would otherwise share a folder and the older one's pictures would turn up on
# the newer one's page. The counting stops rather than turning for ever if
# something is badly wrong with the runs folder. (v0.9.5)
OUT="$OUT_ROOT/runs/$stamp"
again=2
while [ -e "$OUT" ]; do
    [ "$again" -le 99 ] || { echo "gallery.sh: could not find an unused folder under $OUT_ROOT/runs"; exit 1; }
    OUT="$OUT_ROOT/runs/$stamp-$again"
    again=$((again + 1))
done
mkdir -p "$OUT/screens" || { echo "gallery.sh: could not write to $OUT"; exit 1; }

# Nothing outside this is written by the drawing runs, as in test-app.sh.
WORK="$(mktemp -d "${TMPDIR:-/tmp}/moblee-gallery.XXXXXX")"
mkdir -p "$WORK/home"
export MOBLEE_PRACTICE=1

echo "Moblee gallery. Drawing into $OUT"
echo "Practice home: $WORK/home"

runs=""          # folder names, in the order they were drawn
run_counts=""    # "folder count" lines
order_from=""    # the run whose drawing order the page follows
failed=0

for s in $size_list; do
    sn="$(size_name "$s")"
    for appearance in light dark; do
        for direction in ltr rtl; do
            run="$sn-$appearance-$direction"
            switches=""
            [ "$appearance" = dark ] && switches="$switches --dark"
            [ "$direction" = rtl ] && switches="$switches --rtl"
            # Exactly as test-app.sh invokes it: MOBLEE_PRACTICE=1 in the
            # environment, a practice home, and --snapshot for the folder.
            # shellcheck disable=SC2086
            "$BIN" --home "$WORK/home" --text-scale "$s" $switches --snapshot "$OUT/screens/$run" \
                > "$WORK/$run.log" 2>&1
            rc=$?
            n="$(ls "$OUT/screens/$run" 2>/dev/null | grep -c '\.png$')"
            [ "$rc" -eq 0 ] || { echo "  $run: the app exited $rc (see $WORK/$run.log)"; failed=1; }
            echo "  $run: $n screens"
            runs="$runs $run"
            run_counts="$run_counts$run $n
"
            [ -z "$order_from" ] && [ "$n" -gt 0 ] && order_from="$run"
            # The drawing order is the order an owner meets the screens, which
            # is a better order to read the page in than alphabetical.
            ls "$OUT/screens/$run" 2>/dev/null | sed -n 's/\.png$//p' | sort > "$WORK/$run.names"
        done
    done
done

[ -n "$order_from" ] || { echo "gallery.sh: no screens were drawn at all. See $WORK"; exit 1; }

# The order the page is read in comes out of one run's own log. `--icon` says
# "drew …" too and is the only line that names a whole path, so a name with a
# slash in it is not a screen and is not taken for one. (v0.9.5)
sed -n 's/^drew \([^/]*\)\.png$/\1/p' "$WORK/$order_from.log" > "$WORK/order-drawn"
# Anything drawn by some run but not by the one whose order is followed still
# belongs on the page; it is appended, and the mismatch is reported above it.
cat "$WORK"/*.names | sort -u > "$WORK/all-names"
# A count of nothing here would be reported at the top of the page as all the
# runs agreeing, which is the one thing this page must never say wrongly, so
# a listing that came back empty stops the run instead. (v0.9.5)
[ -s "$WORK/all-names" ] || { echo "gallery.sh: the screens that were drawn could not be listed. See $WORK"; exit 1; }
# This used to read the order file through a process substitution while
# appending to that same file in the same command. It came out right only
# because `sort` has to swallow the whole of its input before it can say a
# word, so the appending could not begin until the reading had finished;
# nothing in the shell promises that, and a reader that passed lines along as
# it went would have read back what was being written to it. Reading one file
# and writing another says plainly what was meant. The names are thinned to
# the first time each is seen as well, because a name drawn twice inside one
# run would otherwise be a screen that appears twice on the page. (v0.9.5)
{
    cat "$WORK/order-drawn"
    comm -13 <(sort -u "$WORK/order-drawn") "$WORK/all-names"
} | awk '!seen[$0]++' > "$WORK/order"
screens="$(cat "$WORK/order")"
total="$(printf '%s\n' "$screens" | grep -c .)"

# Do the runs agree? Every name every run drew, against every run.
mismatch=""
for run in $runs; do
    missing="$(comm -23 "$WORK/all-names" "$WORK/$run.names" | tr '\n' ' ')"
    if [ -n "$missing" ]; then
        mismatch="$mismatch<li><b>$run</b> did not draw: <code>$(printf '%s' "$missing" | sed 's/ $//; s/ /<\/code> <code>/g')</code></li>
"
    fi
done

# (v0.9.5) A screen the app draws at a size of its own comes out the same
# picture whatever size the run was given — the three drawn at the biggest size
# inside every run are like this. Saying which ones they are stops the size
# switch looking broken on them, and would say so too if a screen stopped
# growing with the words when it ought to.
fixed=""
first_size="$(size_name "$(printf '%s' "$size_list" | tr ' ' '\n' | grep . | head -1)")"
if [ "$(printf '%s' "$size_list" | tr ' ' '\n' | grep -c .)" -gt 1 ]; then
    while read -r name; do
        [ -n "$name" ] || continue
        same=yes
        for s in $size_list; do
            cmp -s "$OUT/screens/$first_size-light-ltr/$name.png" "$OUT/screens/$(size_name "$s")-light-ltr/$name.png" || same=no
        done
        [ "$same" = yes ] && fixed="$fixed $name"
    done < "$WORK/order"
fi

page="$OUT/index.html"
esc() { printf '%s' "$1" | sed 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g'; }

{
cat <<'HTML'
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Moblee screens</title>
<style>
/* No font, no picture and no script comes from anywhere but this folder: the
   page has to open on a Mac with nothing switched on. (v0.9.5) */
:root { color-scheme: light dark; --edge: #c9ccd2; --quiet: #6b7280; --bg: #f6f7f9; --card: #fff; --ink: #14161a; }
@media (prefers-color-scheme: dark) {
  :root { --edge: #3a3f47; --quiet: #9aa1ab; --bg: #16181c; --card: #1f2227; --ink: #e9ebee; }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink);
       font: 15px/1.45 -apple-system, BlinkMacSystemFont, "Helvetica Neue", Arial, sans-serif; }
header { padding: 20px 24px 8px; }
h1 { font-size: 22px; margin: 0 0 6px; }
.facts { color: var(--quiet); font-size: 13px; }
.facts b { color: var(--ink); font-weight: 600; }
.counts { margin: 10px 0 0; display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: 12px; color: var(--quiet); }
.counts span { white-space: nowrap; }
.agree { margin: 12px 0 0; padding: 10px 14px; border-radius: 8px; font-size: 14px;
         background: #e8f5ec; color: #14532d; border: 1px solid #b9dfc6; }
.alarm { margin: 12px 0 0; padding: 14px 16px; border-radius: 8px;
         background: #fdeaea; color: #7f1d1d; border: 2px solid #dc2626; }
.alarm h2 { margin: 0 0 6px; font-size: 17px; }
.alarm ul { margin: 6px 0 0 18px; padding: 0; }
.alarm code { background: rgba(0,0,0,.07); border-radius: 4px; padding: 1px 4px; }
@media (prefers-color-scheme: dark) {
  .agree { background: #10291a; color: #b7e4c7; border-color: #2c5b3b; }
  .alarm { background: #2c1214; color: #fca5a5; }
}
.bar { position: sticky; top: 0; z-index: 9; display: flex; flex-wrap: wrap; align-items: center;
       gap: 8px 18px; padding: 10px 24px; background: var(--card);
       border-bottom: 1px solid var(--edge); }
.bar label { font-size: 13px; color: var(--quiet); }
.bar input[type=search], .bar select { font: inherit; font-size: 13px; padding: 5px 8px;
       border: 1px solid var(--edge); border-radius: 6px; background: var(--bg); color: var(--ink); }
.bar input[type=search] { width: 230px; }
.set { display: inline-flex; border: 1px solid var(--edge); border-radius: 6px; overflow: hidden; }
.set button { font: inherit; font-size: 13px; padding: 5px 11px; border: 0; cursor: pointer;
       background: var(--bg); color: var(--ink); border-left: 1px solid var(--edge); }
.set button:first-child { border-left: 0; }
.set button[aria-pressed=true] { background: #2f68e0; color: #fff; }
.tally { margin-left: auto; font-size: 13px; color: var(--quiet); }
main { padding: 8px 24px 80px; }
.screen { margin: 26px 0 0; scroll-margin-top: 108px; }
.screen h2 { font-size: 15px; margin: 0 0 8px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.screen h2 a { color: var(--quiet); text-decoration: none; font-family: inherit; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
body.one-up .grid { grid-template-columns: 1fr; max-width: 1180px; }
figure { margin: 0; background: var(--card); border: 1px solid var(--edge); border-radius: 10px;
         padding: 8px; }
figcaption { font-size: 12px; color: var(--quiet); padding: 2px 2px 8px;
             display: flex; justify-content: space-between; gap: 10px; }
/* Every screen is drawn on a window of 720 by 520 points whatever the size of
   the words, so the box a picture will fill is known before the picture has
   loaded. Saying so keeps the page from growing under the eye as pictures
   arrive — without it, jumping to a screen lands somewhere else a moment later.
   The moment a picture has loaded its own shape takes over, so a screen that
   really did come out a different shape is shown as it is and not squashed into
   the one expected. (v0.9.5) */
figure img { display: block; width: 100%; height: auto; border-radius: 6px; aspect-ratio: 720 / 520;
             background: repeating-conic-gradient(#0000 0 25%, #8884 0 50%) 0 0/16px 16px; }
figure img.ready { aspect-ratio: auto; }
figure.gone img { outline: 3px solid #dc2626; }
/* A version that was never drawn takes up exactly the room the picture would
   have, so the hole is the shape of what is missing. (v0.9.5) */
.missing { display: grid; place-items: center; aspect-ratio: 720 / 520; font-size: 13px;
           color: #dc2626; border: 2px dashed #dc2626; border-radius: 6px; }
.screen.hide { display: none; }
body[data-appearance=light] figure[data-appearance=dark],
body[data-appearance=dark]  figure[data-appearance=light],
body[data-direction=ltr]    figure[data-direction=rtl],
body[data-direction=rtl]    figure[data-direction=ltr] { display: none; }
/* One size at a time. All three are on the page — the biggest is where a screen
   gets cut off, so it must be here and not behind another run — but four
   pictures of one screen can be compared at a glance and twelve cannot, so the
   size is a switch and the appearance and the direction are the grid. (v0.9.5) */
body[data-size=normal]  figure:not([data-size=normal]),
body[data-size=bigger]  figure:not([data-size=bigger]),
body[data-size=biggest] figure:not([data-size=biggest]) { display: none; }
.nothing { padding: 40px 0; color: var(--quiet); }
</style>
</head>
<body data-appearance="both" data-direction="both" data-size="">
HTML

echo "<header>"
echo "<h1>Moblee screens</h1>"
printf '<p class="facts">Drawn <b>%s</b> · pack VERSION <b>%s</b> · app CFBundleShortVersionString <b>%s</b> (build %s)<br>App: <code>%s</code></p>\n' \
    "$(date '+%A %-d %B %Y, %H:%M')" "$(esc "$pack_version")" "$(esc "$app_version")" "$(esc "$app_build")" "$(esc "$APP")"
echo '<p class="counts">'
printf '%s' "$run_counts" | while read -r r n; do
    [ -n "$r" ] && printf '<span><b>%s</b> %s screens</span>\n' "$r" "$n"
done
echo '</p>'
if [ -n "$mismatch" ]; then
    echo '<div class="alarm"><h2>The runs did NOT all draw the same screens.</h2>'
    printf '<p>%s screens were drawn by at least one run. These runs are short:</p>\n<ul>\n%s</ul>\n' "$total" "$mismatch"
    echo '<p>A screen that draws in one appearance, one direction or one size and not another is a fault. The versions that are missing are marked in red below.</p></div>'
else
    printf '<p class="agree">All runs drew the same %s screens.</p>\n' "$total"
fi
if [ -n "$fixed" ]; then
    printf '<p class="facts">%s of them come out the same picture at every text size, because the app draws them at a size of its own whatever the run was given: <code>%s</code>. The pixel size beside each picture says which size it really is.</p>\n' \
        "$(printf '%s' "$fixed" | wc -w | tr -d ' ')" "$(printf '%s' "$fixed" | sed 's/^ //; s/ /<\/code> <code>/g')"
fi
echo "</header>"

echo '<div class="bar">'
echo '<input type="search" id="find" placeholder="Filter by screen name  (press /)" autocomplete="off">'
echo '<select id="jump"><option value="">Jump to a screen…</option>'
printf '%s\n' "$screens" | while read -r name; do
    [ -n "$name" ] && printf '<option value="%s">%s</option>\n' "$name" "$name"
done
echo '</select>'
echo '<label>Appearance</label><div class="set" id="appearance">'
echo '<button data-v="both" aria-pressed="true">Both</button><button data-v="light" aria-pressed="false">Light</button><button data-v="dark" aria-pressed="false">Dark</button></div>'
echo '<label>Direction</label><div class="set" id="direction">'
echo '<button data-v="both" aria-pressed="true">Both</button><button data-v="ltr" aria-pressed="false">Left&nbsp;to&nbsp;right</button><button data-v="rtl" aria-pressed="false">Right&nbsp;to&nbsp;left</button></div>'
echo '<label>Text size</label><div class="set" id="size">'
first=yes
for s in $size_list; do
    printf '<button data-v="%s" aria-pressed="%s">%s</button>' "$(size_name "$s")" "$([ "$first" = yes ] && echo true || echo false)" "$(size_words "$s")"
    first=no
done
echo '</div>'
echo '<span class="tally" id="tally"></span>'
echo '</div>'

echo '<main id="all">'
printf '%s\n' "$screens" | while read -r name; do
    [ -n "$name" ] || continue
    printf '<section class="screen" id="s-%s" data-name="%s"><h2>%s.png <a href="#s-%s">#</a></h2><div class="grid">\n' \
        "$name" "$name" "$name" "$name"
    for s in $size_list; do
        sn="$(size_name "$s")"
        for direction in ltr rtl; do
            for appearance in light dark; do
                run="$sn-$appearance-$direction"
                dir_words="$([ "$direction" = ltr ] && echo "left to right" || echo "right to left")"
                printf '<figure data-size="%s" data-appearance="%s" data-direction="%s"' "$sn" "$appearance" "$direction"
                if [ -f "$OUT/screens/$run/$name.png" ]; then
                    printf '><figcaption><span>%s · %s</span><span class="dim"></span></figcaption>' "$appearance" "$dir_words"
                    printf '<a href="screens/%s/%s.png" target="_blank"><img loading="lazy" alt="%s, %s, %s" src="screens/%s/%s.png"></a></figure>\n' \
                        "$run" "$name" "$name" "$appearance" "$dir_words" "$run" "$name"
                else
                    printf ' class="gone"><figcaption><span>%s · %s</span></figcaption><div class="missing">not drawn in %s</div></figure>\n' \
                        "$appearance" "$dir_words" "$run"
                fi
            done
        done
    done
    echo '</div></section>'
done
echo '<p class="nothing" id="nothing" hidden>No screen has that in its name.</p>'
echo '</main>'

cat <<'HTML'
<script>
// The page is looked at, not read: everything here is about getting one screen,
// or one appearance, in front of the eye quickly. (v0.9.5)
var body = document.body, all = document.getElementById('all');
var screens = [].slice.call(document.querySelectorAll('.screen'));
var find = document.getElementById('find'), jump = document.getElementById('jump');
var tally = document.getElementById('tally'), nothing = document.getElementById('nothing');

function set(group, value) {
  var box = document.getElementById(group);
  [].forEach.call(box.querySelectorAll('button'), function (b) {
    b.setAttribute('aria-pressed', b.dataset.v === value ? 'true' : 'false');
  });
  body.dataset[group] = value;
  body.classList.toggle('one-up', body.dataset.appearance !== 'both' && body.dataset.direction !== 'both');
  count();
}
['appearance', 'direction', 'size'].forEach(function (group) {
  document.getElementById(group).addEventListener('click', function (e) {
    if (e.target.dataset.v) set(group, e.target.dataset.v);
  });
});
set('size', document.querySelector('#size button').dataset.v);

function count() {
  var shown = screens.filter(function (s) { return !s.classList.contains('hide'); });
  var visible = 0;
  if (shown.length) {
    visible = [].filter.call(shown[0].querySelectorAll('figure'), function (f) {
      return getComputedStyle(f).display !== 'none';
    }).length;
  }
  tally.textContent = shown.length + ' of ' + screens.length + ' screens · ' + visible + ' per screen';
  nothing.hidden = shown.length > 0;
}

find.addEventListener('input', function () {
  var q = find.value.trim().toLowerCase();
  screens.forEach(function (s) { s.classList.toggle('hide', q !== '' && s.dataset.name.indexOf(q) < 0); });
  count();
});
jump.addEventListener('change', function () {
  if (!jump.value) return;
  find.value = ''; screens.forEach(function (s) { s.classList.remove('hide'); }); count();
  var t = document.getElementById('s-' + jump.value);
  if (t) { history.replaceState(null, '', '#s-' + jump.value); t.scrollIntoView({ behavior: 'smooth' }); }
});
document.addEventListener('keydown', function (e) {
  if (e.key === '/' && document.activeElement !== find) { e.preventDefault(); find.focus(); find.select(); }
  if (e.key === 'Escape' && document.activeElement === find) { find.value = ''; find.dispatchEvent(new Event('input')); find.blur(); }
});

// Each picture says how big it really is once it has loaded. A screen drawn at
// a size the rest of its run was not drawn at is the sign of words that grew
// while the window did not, which is how a screen ends up cut off.
[].forEach.call(document.querySelectorAll('figure img'), function (img) {
  function said() {
    img.classList.add('ready');
    var d = img.closest('figure').querySelector('.dim');
    if (d) d.textContent = img.naturalWidth + '×' + img.naturalHeight;
  }
  if (img.complete && img.naturalWidth) said(); else img.addEventListener('load', said);
});
count();
</script>
</body>
</html>
HTML
} > "$page"

# A page that was cut short — the disk filled, say — still ends with a path
# printed and still gets written into latest.txt, and the next person opens
# half a page believing it whole. The closing tag is the last thing written,
# so its being there says the whole of it arrived. (v0.9.5)
tail -c 200 "$page" 2>/dev/null | grep -q '</html>' || {
    echo "gallery.sh: the page was not written in full — $page is cut short. Nothing was recorded as newest."
    exit 1; }

mkdir -p "$OUT_ROOT"
printf '%s\n' "$page" > "$OUT_ROOT/latest.txt" || {
    echo "gallery.sh: the page is at $page, but $OUT_ROOT/latest.txt could not be written."; exit 1; }

echo ""
if [ -n "$mismatch" ]; then
    echo "THE RUNS DID NOT ALL DRAW THE SAME SCREENS — the page says which, in red at the top."
else
    echo "All runs drew the same $total screens."
fi
echo "Page: $page"
echo "Logs and practice home: $WORK"
[ "$open_it" = yes ] && open "$page"
[ "$failed" -eq 0 ] && [ -z "$mismatch" ]
