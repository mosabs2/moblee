import SwiftUI
import AVFoundation

/// (v0.9.4) How big the words are.
///
/// Several of Moblee's owners are older and some have poor eyesight, and until
/// now there was nothing at all they could do about it: the window was fixed at
/// 720 by 520 and every size in the app is written in points, so macOS's own
/// text-size setting reached not one word of it. Three steps are enough —
/// normal, a quarter bigger, half as big again — and the choice is kept in the
/// owner's own settings under a key of Moblee's own, so it is still there the
/// next time the app is opened.
///
/// Every size the app draws goes through `Theme.font` and `Theme.pt`, which
/// read the step from here. A view that draws anything sized says so, by
/// holding this object, so that it is drawn again the moment the step changes;
/// a screen whose words grew but whose cards did not would be worse than none.
@MainActor
final class TextSize: ObservableObject {
    enum Step: Int, CaseIterable, Identifiable {
        case normal = 0, bigger, biggest

        var id: Int { rawValue }

        var scale: CGFloat {
            switch self {
            case .normal: return 1.00
            case .bigger: return 1.25
            case .biggest: return 1.50
            }
        }

        /// As the owner reads it.
        var name: String {
            switch self {
            case .normal: return "Normal"
            case .bigger: return "Bigger"
            case .biggest: return "Biggest"
            }
        }

        /// One press of "Bigger text" moves on one step, and round again from
        /// the biggest, so one control is the whole of it: there is no second
        /// button to find, and no way to get stuck at a size.
        var next: Step { Step(rawValue: rawValue + 1) ?? .normal }
    }

    /// Moblee's own key, in Moblee's own settings. Nothing else kept there is
    /// read or written.
    static let key = "moblee.textSize"

    /// A practice run keeps the choice in a store of its own, so that a test
    /// which really presses the control on the real window never changes the
    /// settings of the Moblee the person at this Mac uses.
    static let store: UserDefaults = Practice.on
        ? (UserDefaults(suiteName: "moblee.practice") ?? .standard)
        : .standard

    static let shared = TextSize()

    @Published var step: Step {
        didSet {
            Theme.scale = step.scale
            if !drawing { Self.write(step, to: Self.store) }
        }
    }

    /// Set only while a screen is being drawn to a picture file at a size
    /// nobody asked for (`--text-scale`): the kept choice is not touched.
    private var drawing = false

    private init() {
        let kept = Self.read(from: Self.store)
        step = kept
        Theme.scale = kept.scale
    }

    /// No setting at all, or one written by some later Moblee that this one
    /// does not know, is read as normal rather than refused: the words the
    /// owner reads are never left to a number that cannot be understood.
    static func read(from store: UserDefaults) -> Step {
        guard store.object(forKey: key) != nil else { return .normal }
        return Step(rawValue: store.integer(forKey: key)) ?? .normal
    }

    static func write(_ step: Step, to store: UserDefaults) { store.set(step.rawValue, forKey: key) }

    func drawAt(_ step: Step) {
        drawing = true
        self.step = step
        drawing = false
    }
}

/// (v0.9.4) Which way the screens are laid out.
///
/// macOS lays a user interface out right to left when the Mac's own language is
/// read that way — Arabic, Hebrew, Persian, Urdu — and Moblee had never once
/// been looked at in that state, so nobody knew what it did. `--rtl` (a
/// practice switch) puts a whole run in the mirrored layout, so every screen
/// can be drawn and read the way such an owner meets it. Without the switch
/// nothing at all is said about the direction, which is the only way a released
/// Moblee can take the direction the Mac itself is set to.
///
/// What SwiftUI mirrors by itself, tried on this Mac on 26 September 2026 and
/// therefore not done here: leading and trailing anywhere (padding, frame
/// alignment, the order of an HStack), `.offset(x:)`, `.position(x:)`, the
/// coordinates of a drawn path, and the edge a `.move` transition slides from.
/// What it does not mirror, and so is decided here: a symbol that names a side
/// rather than a direction (`chevron.left` goes on pointing left; only
/// `chevron.backward` turns round), and an arrow typed into a sentence as a
/// letter.
enum Layout {
    /// The side of the window a thing really ends up on, so that a test can say
    /// which side it is rather than only which word was written.
    enum Side { case left, right }

    static let mirrored = Practice.args.contains("--rtl")

    /// The way back. A back arrow must point the way back really goes, which is
    /// the other way once the layout is mirrored. SF Symbols' own `backward`
    /// and `forward` names turn themselves round with the words; `left` and
    /// `right` do not, and `chevron.left.circle.fill` went on pointing left on
    /// a mirrored screen, where back is to the right.
    static let backSymbol = "chevron.backward.circle.fill"

    /// "To there": the app moving into Applications. `arrow.right` stayed
    /// pointing right when mirrored, which then meant backwards.
    static let onwardsSymbol = "arrow.forward"

    /// The two arrows that are letters inside a sentence rather than pictures —
    /// "0.8.1 → 0.9.4" and "Wiki ▸ Sam Wiki" — are NOT turned round, and this
    /// says so because it is the opposite of what it looks like it should be.
    /// A sentence keeps the direction of its own words: SwiftUI reads a Text's
    /// direction from the first letter in it and not from the layout around it,
    /// so an English sentence on a mirrored screen still runs left to right,
    /// and an arrow in it still has the old version on the left and the new one
    /// on the right. Turned round, it was drawn as "0.7.0 ← 0.8.1" on a line
    /// still read left to right, which says the wrong thing (26 September 2026,
    /// tried and looked at). Only a symbol standing on its own in a row that
    /// mirrors — the one above — turns with the row.
    static let versionsArrow = "→"
    static let intoAFolder = "▸"

    /// A new screen arrives from the side that "on" is on, and the one before
    /// it leaves by the other: said as SwiftUI's own semantic edges, which it
    /// turns round itself.
    static let arrives: Edge = .trailing
    static let leaves: Edge = .leading

    /// The corner each of the two quiet lines at the bottom of the home screen
    /// sits in, and the corner "Bigger text" sits in at the top. Written as
    /// SwiftUI's own alignments, so they mirror themselves.
    static let assistantCorner: Alignment = .bottomTrailing
    static let newerReleaseCorner: Alignment = .bottomLeading
    static let biggerTextCorner: Alignment = .trailing

    /// Which side of the window a semantic edge, or a corner, really is.
    static func side(of edge: Edge, mirrored: Bool) -> Side {
        (edge == .trailing) != mirrored ? .right : .left
    }

    static func side(ofCorner corner: Alignment, mirrored: Bool) -> Side {
        let towardsTheEnd = [Alignment.trailing, .topTrailing, .bottomTrailing].contains(corner)
        return towardsTheEnd != mirrored ? .right : .left
    }
}

/// (v0.9.4) Mirrors the screens when `--rtl` was given, and says nothing at all
/// when it was not, so that a released Moblee is laid out the way the Mac itself
/// is set to — which is the only way it can be right on somebody else's Mac —
/// and never the way this app decided.
///
/// It goes on the screens INSIDE the window and never on the window's own
/// content. On macOS 26.6 a window group whose content carries this makes no
/// window at all: the app starts, draws nothing, makes no NSWindow and sits in
/// an empty event loop, which is the same fault `MobleeApp` records against a
/// content with no size of its own. Found the same way, on 26 September 2026:
/// the mirrored run made its window and the ordinary one made none.
struct MirrorIfAsked: ViewModifier {
    func body(content: Content) -> some View {
        if Layout.mirrored {
            content.environment(\.layoutDirection, .rightToLeft)
        } else {
            content
        }
    }
}

extension View {
    func mirrorIfAsked() -> some View { modifier(MirrorIfAsked()) }
}

/// (v0.9.4) The owner's own words, put into one of Moblee's sentences.
///
/// An owner's Mac may be in English while the owner's own name is Arabic. Left
/// to itself, a name read right to left inside a sentence read left to right
/// drags the punctuation beside it to the wrong side: a full stop after the
/// name lands in front of it, and the quotes round it swap over. Unicode has
/// invisible marks for exactly this — the isolates — which say "this piece
/// stands on its own", and let the name settle its own direction without
/// disturbing the sentence around it.
///
/// There are two cases, and they do NOT want the same mark. (v0.9.4, 26
/// September 2026: the second of them was wrong in the one instruction an owner
/// has to match against Finder.)
///
///  * A name on its own — "Hi, نور." — wants the FIRST-STRONG isolate. The name
///    is all one script, and first-strong is what lets it be read its own way
///    whichever script it turns out to be in.
///
///  * A wiki folder's name — "نور Wiki" — must not be isolated that way. The
///    first strong letter is Arabic, so first-strong makes the whole thing a
///    right-to-left piece and draws it "Wiki نور", while Finder, three inches
///    away on the same screen, shows "نور Wiki". Moblee's whole hand-off is
///    "find this folder", and it was naming the folder backwards for every
///    owner whose name is not written in English.
///
///    A folder's name is left with no isolate of its own, so it takes the
///    direction of the line it sits in. Moblee's lines are in English and keep
///    the direction of their own words, mirrored app or not — the same rule
///    that leaves the arrow in "0.8.1 → 0.9.4" alone, see `Layout` — so the
///    line reads left to right and the name comes first, exactly as Finder
///    writes it. The punctuation is safe: the quotes and commas beside the
///    folder name sit between it and English words, so they settle to the
///    line's own direction, which is where they belong. Looked at in the
///    drawn screens, in both appearances and both directions:
///    03g-promise-arabic-name and 07d-handoff-arabic-name.
///
/// Every place a name, or a wiki folder named after one, goes into a sentence
/// the owner reads goes through here. Nowhere else: never into a folder name,
/// a path, an argument given to the scripts, or the diary, and never into what
/// is read aloud, so that nothing invisible can reach a file or a voice.
enum OwnWords {
    static let isolate = "\u{2068}"      // first-strong isolate
    static let pop = "\u{2069}"          // pop directional isolate

    /// A name by itself, inside one of Moblee's sentences.
    static func standingAlone(_ text: String) -> String {
        text.isEmpty ? text : isolate + text + pop
    }

    /// The name of a folder the owner has to find in Finder, inside one of
    /// Moblee's sentences: left exactly as Finder will show it. The call is
    /// here, and does nothing, so that every name still goes through one place
    /// and the reason this one is left alone is written down beside it.
    static func asFinderShowsIt(_ folderName: String) -> String { folderName }
}

enum Theme {
    static let accent = Color(red: 0.16, green: 0.38, blue: 0.86)

    /// Colours that carry words are darker in light mode and lighter in dark
    /// mode, so that small text on a card clears 4.5 to 1 either way. The
    /// bright versions are for large symbols only.
    static let good = Color(red: 0.13, green: 0.62, blue: 0.38)
    static let waiting = Color(red: 0.93, green: 0.58, blue: 0.10)
    static let goodText = adaptive(light: (0.05, 0.42, 0.24), dark: (0.45, 0.86, 0.62))
    static let waitingText = adaptive(light: (0.62, 0.33, 0.00), dark: (1.00, 0.74, 0.35))
    static let badText = adaptive(light: (0.72, 0.10, 0.10), dark: (1.00, 0.55, 0.52))

    /// Cards sit on the window background. In dark mode the system's control
    /// background is almost the same black as the window, so cards get their
    /// own lighter grey there, and a hairline edge in both modes.
    static let card = adaptive(light: (1.0, 1.0, 1.0), dark: (0.17, 0.18, 0.21))
    static let cardEdge = Color.primary.opacity(0.08)

    /// (v0.9.4) The ring that says which control the keyboard is on. macOS
    /// draws its own for some controls only, and only when Full Keyboard
    /// Access has been switched on, so Moblee draws its own: a strong blue on
    /// white, a pale blue on near-black, three points thick, outside the
    /// control so it never sits over its words.
    static let focusRing = adaptive(light: (0.04, 0.26, 0.70), dark: (0.58, 0.82, 1.00))

    static func adaptive(light: (Double, Double, Double), dark: (Double, Double, Double)) -> Color {
        Color(nsColor: NSColor(name: nil) { appearance in
            let isDark = appearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua
            let c = isDark ? dark : light
            return NSColor(srgbRed: c.0, green: c.1, blue: c.2, alpha: 1)
        })
    }

    static var background: some View {
        ZStack {
            Color(nsColor: .windowBackgroundColor)
            LinearGradient(
                colors: [accent.opacity(0.0), accent.opacity(0.10)],
                startPoint: .top, endPoint: .bottom)
        }
    }

    /// (v0.9.4) What every size in the app is multiplied by. It mirrors the
    /// step the owner has set in `TextSize`, and is kept here as a plain
    /// number so that every part of the drawing can read it, a ButtonStyle
    /// among them, which is not a view and cannot hold the setting itself.
    static var scale: CGFloat = TextSize.Step.normal.scale

    /// The one place a size becomes a number. Every font in the app is asked
    /// for here, so that "Bigger text" moves all of them together.
    static func font(_ size: CGFloat, _ weight: Font.Weight = .regular,
                     _ design: Font.Design = .rounded) -> Font {
        .system(size: (size * scale).rounded(), weight: weight, design: design)
    }

    /// The same for a width, a height, a padding or a gap, so that cards and
    /// the spaces between them grow with the words inside them.
    static func pt(_ points: CGFloat) -> CGFloat { (points * scale).rounded() }

    /// The window's smallest size. 720 by 520 at the normal size, and larger
    /// steps need a larger window: three cards side by side cannot be drawn
    /// half as big again in the room two of them would take.
    static var leastWidth: CGFloat { pt(720) }
    static var leastHeight: CGFloat { pt(520) }

    /// The strip along the top of every screen, which holds the practice badge
    /// in the middle and "Bigger text" in the corner. The screen below it
    /// starts where it ends, so nothing is ever drawn under either of them.
    static var topStrip: CGFloat { pt(28) }
}

/// The card every tile is drawn on.
struct CardBackground: View {
    @ObservedObject private var textSize = TextSize.shared
    var corner: CGFloat = 22
    var dimmed = false
    var body: some View {
        RoundedRectangle(cornerRadius: Theme.pt(corner), style: .continuous)
            .fill(Theme.card)
            .overlay(RoundedRectangle(cornerRadius: Theme.pt(corner), style: .continuous)
                .stroke(Theme.cardEdge, lineWidth: 1))
            .shadow(color: .black.opacity(dimmed ? 0.04 : 0.10), radius: 10, y: 4)
    }
}

/// (v0.9.4) Which control the keyboard is on. The self-drive walk reads this to
/// say whether Tab really reached a button, rather than only that the code says
/// it should — and the app itself reads it to know when the keyboard has been
/// left with nowhere to go. It is one of Moblee's own fixed words for a
/// control ("back", "bigger-text"), never anything of the owner's.
@MainActor
enum FocusedControl {
    static var id: String?

    /// The keyboard has come off a control. If nothing else has taken it a
    /// moment later, the window is told to hold nobody, so that the next Tab
    /// starts the loop afresh.
    ///
    /// (v0.9.4, 26 September) A control the keyboard is on goes away with its
    /// screen — the card on "Which assistant?" does, the moment it is answered
    /// — and SwiftUI keeps hold of the window's first responder when that
    /// happens. Tab then moves nowhere at all. An owner who had just made their
    /// wiki from the keyboard arrived at the home screen and could not reach a
    /// single thing on it; a click anywhere put it right, which is why it was
    /// never seen until the install was walked from the keyboard.
    ///
    /// Waiting a moment is what makes this safe: an ordinary Tab from one
    /// control to the next comes off the first and lands on the second, and by
    /// the time this looks, something is on it and nothing is done.
    static func letGoIfNothingTookIt() {
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) {
            MainActor.assumeIsolated {
                guard id == nil, let window = NSApp.keyWindow else { return }
                // A box the owner is typing in has the keyboard properly, and
                // says so through its own field editor rather than through the
                // controls here. It is never taken off them.
                if window.firstResponder is NSText { return }
                window.makeFirstResponder(nil)
            }
        }
    }

    /// Which control's ring to draw in a picture file. A ring shows only while
    /// the keyboard is on the control, and no picture file can press Tab, so
    /// the ring could not be looked at in light and in dark without this. Set
    /// only by the picture-file drawing; a released app draws no ring it was
    /// not given by the keyboard.
    static var drawnRing: String?
}

/// A control the keyboard can reach: it takes focus in the order it is drawn,
/// it shows a ring that can be seen in light and in dark, it can be found by
/// name, and in a practice run it says when the keyboard is on it.
struct KeyboardReachable: ViewModifier {
    let id: String
    var corner: CGFloat = 10
    /// What Space does when the keyboard is on this control. macOS presses a
    /// focused button with Space, and SwiftUI does not do it for us, so it is
    /// done here. Return is deliberately left alone, so that the big button's
    /// own Return goes on working wherever the keyboard happens to be.
    var press: (() -> Void)?
    @FocusState private var focused: Bool

    func body(content: Content) -> some View {
        content
            .focusable()
            .focused($focused)
            .onKeyPress(.space) {
                guard let press else { return .ignored }
                press()
                return .handled
            }
            .overlay(
                RoundedRectangle(cornerRadius: Theme.pt(corner) + 3, style: .continuous)
                    .strokeBorder(Theme.focusRing, lineWidth: 3)
                    .padding(-3)
                    .opacity(focused || (Practice.on && FocusedControl.drawnRing == id) ? 1 : 0)
                    .allowsHitTesting(false))
            .onChange(of: focused) { _, now in
                if now {
                    FocusedControl.id = id
                } else if FocusedControl.id == id {
                    FocusedControl.id = nil
                    FocusedControl.letGoIfNothingTookIt()
                }
            }
            .accessibilityIdentifier(id)
            .background(DrawnAt(id: id))
    }
}

extension View {
    func keyboardReachable(_ id: String, corner: CGFloat = 10,
                           press: (() -> Void)? = nil) -> some View {
        modifier(KeyboardReachable(id: id, corner: corner, press: press))
    }
}

/// (v0.9.4) "Bigger text", in the top corner of every screen, once. One press
/// makes every word on every screen a quarter bigger, a second press half as
/// big again, a third puts it back; the window grows with it. The choice is
/// kept, so an owner who needs bigger words sets it once and never again.
struct BiggerTextButton: View {
    @ObservedObject private var textSize = TextSize.shared

    private func bigger() {
        withAnimation(.easeOut(duration: 0.15)) { textSize.step = textSize.step.next }
    }

    var body: some View {
        Button(action: bigger) {
            HStack(spacing: Theme.pt(5)) {
                Image(systemName: "textformat.size")
                Text("Bigger text")
            }
            .font(Theme.font(12, .semibold))
            .padding(.horizontal, Theme.pt(9)).padding(.vertical, Theme.pt(4))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .foregroundStyle(Theme.accent)
        .help("Make every word bigger. Press again for bigger still, and again to go back to normal.")
        .accessibilityLabel("Bigger text")
        .accessibilityValue(textSize.step.name)
        .keyboardReachable("bigger-text", corner: 8, press: bigger)
    }
}

/// (v0.9.5) Which of the Mac's own voices reads a piece of words.
///
/// Until now there was one listen control in the app and it was nailed to
/// `en-GB`, which is wrong twice over. On a Mac with no British voice installed
/// it asked for a voice that is not there, and macOS then reads the words in
/// whatever it likes. And it was used for the owner's own name, so an owner
/// called نور had their own name read out by an English voice, letter by letter,
/// as nonsense.
///
/// So the choice is made from two things, and never from one:
///
///  * WHOSE WORDS THEY ARE. Moblee's own sentences are written in British
///    English, so they ask for a British voice, and fall back to the voice the
///    Mac itself is set to where that is another English, then to any English
///    voice, then to nothing at all — and "nothing at all" is not a failure: an
///    utterance with no voice is read by macOS in the voice the Mac itself
///    would use, which is the best thing left to do.
///
///  * WHAT THE WORDS ARE, where they are the owner's own: their name, their
///    wiki's folder name, a skill they wrote, the name of a file they dropped.
///    These are read in a voice chosen for the letters they are written in, so
///    an Arabic name gets an Arabic voice. The script is what decides, not the
///    app and not the Mac: the whole point is that the owner's Mac may be in
///    English while the owner is not.
///
/// What this CANNOT do, said plainly because it looks as though it should. The
/// script tells Arabic from English and Japanese from Chinese, and it cannot
/// tell French from English, because they are written in the same letters.
/// Where the owner's own words are in Latin letters, the voice the Mac itself
/// is set to is used if that language is written in Latin letters too — so a
/// French Mac reads "Étienne" in French — and Moblee's own voice otherwise.
/// And macOS does not offer an app the particular voice the owner has chosen
/// under Spoken Content, only the language the Mac is set to, so that is what
/// is read here.
enum Voices {
    /// Whose words a piece is, which is half of what chooses the voice.
    enum Whose: Equatable { case mobleesOwn, theOwners }

    /// The languages the Mac has a voice for, asked once. Asking macOS for its
    /// voices walks every voice on the Mac, which is slow enough to be felt on
    /// a screen being drawn, and the answer cannot change while the app is open.
    static let onThisMac: [String] = AVSpeechSynthesisVoice.speechVoices().map(\.language)

    /// The language the Mac itself is set to read in.
    static let macLanguage: String = AVSpeechSynthesisVoice.currentLanguageCode()

    /// The language part of a voice's tag: "en" of "en-GB". A Mac may have
    /// "ar-001" where another has "ar-SA", and either will read Arabic.
    static func base(_ tag: String) -> String {
        String(tag.split(separator: "-").first ?? "").lowercased()
    }

    /// The languages that are NOT written in Latin letters, so that "the voice
    /// the Mac is set to" is used for the owner's Latin-lettered words only
    /// where it would not mangle them. Written out rather than worked out:
    /// there is no way to ask macOS which script a language is written in.
    static let notWrittenInLatin: Set<String> = ["ar", "fa", "ur", "he", "yi", "ru", "uk", "bg", "sr", "mk",
                                                 "el", "hy", "ka", "am", "hi", "mr", "ne", "bn", "pa", "gu",
                                                 "ta", "te", "kn", "ml", "si", "th", "lo", "my", "km",
                                                 "ja", "zh", "ko", "yue"]

    static func writtenInLatin(_ tag: String) -> Bool { !notWrittenInLatin.contains(base(tag)) }

    /// Which letters say which language. Only the scripts that a Mac is likely
    /// to have a voice for, and only where the script names one language: Latin
    /// is deliberately absent, because it names dozens.
    private static let byScript: [(range: ClosedRange<UInt32>, language: String)] = [
        (0x0590...0x05FF, "he"),                                        // Hebrew
        (0x0600...0x06FF, "ar"), (0x0750...0x077F, "ar"),               // Arabic, and its supplement
        (0x08A0...0x08FF, "ar"), (0xFB50...0xFDFF, "ar"), (0xFE70...0xFEFF, "ar"),
        (0x0370...0x03FF, "el"),                                        // Greek
        (0x0400...0x04FF, "ru"),                                        // Cyrillic
        (0x0530...0x058F, "hy"), (0x10A0...0x10FF, "ka"),               // Armenian, Georgian
        (0x0900...0x097F, "hi"), (0x0980...0x09FF, "bn"),               // Devanagari, Bengali
        (0x0B80...0x0BFF, "ta"), (0x0D00...0x0D7F, "ml"),               // Tamil, Malayalam
        (0x0E00...0x0E7F, "th"), (0x1780...0x17FF, "km"),               // Thai, Khmer
        (0x3040...0x30FF, "ja"),                                        // Hiragana and Katakana
        (0xAC00...0xD7AF, "ko"), (0x1100...0x11FF, "ko"),               // Hangul
        (0x4E00...0x9FFF, "zh"),                                        // the Han characters
    ]

    /// The languages written with the Han characters, which are shared and so
    /// can never say on their own which of them a piece of words is in.
    /// (v0.9.5)
    static let shareTheHanCharacters: Set<String> = ["zh", "ja", "yue"]

    /// The language a piece of the owner's own words is written in, or nothing
    /// at all where the letters say nothing (Latin letters, digits, a file
    /// ending on its own). The letters are counted rather than the first one
    /// taken, so "Gym plan.pdf" is not called Arabic by one stray character —
    /// and Japanese wins over Chinese wherever its own letters appear at all,
    /// because Japanese is written with the Han characters too.
    ///
    /// (v0.9.5) BE PLAIN ABOUT WHAT THIS CANNOT DO. Kana say Japanese. The Han
    /// characters say nothing: 日本語 is Japanese and 中文 is Chinese and they
    /// are written with characters from one shared set, so no rule over the
    /// letters alone can tell them apart, and this answers "zh" for both. That
    /// is a guess, not a finding, and it is the wrong guess for a Japanese
    /// owner whose name is written in kanji. `choose` does not leave it there:
    /// where the letters can only be one of the two, the Mac's own language
    /// settles it, which on a Japanese owner's Mac is Japanese.
    static func language(ofScriptIn words: String) -> String? {
        var counted: [String: Int] = [:]
        for scalar in words.unicodeScalars {
            for entry in byScript where entry.range.contains(scalar.value) {
                counted[entry.language, default: 0] += 1
                break
            }
        }
        if counted["ja"] != nil { return "ja" }
        return counted.max { a, b in a.value == b.value ? a.key > b.key : a.value < b.value }?.key
    }

    /// The voice to read one piece of words in, as a language tag, or nothing
    /// at all to leave it to the voice the Mac itself would use. Given the
    /// Mac's voices and the Mac's own language rather than asking for them, so
    /// that every rule above can be checked without a Mac set up to match.
    static func choose(_ words: String, _ whose: Whose,
                       have: [String], macLanguage: String) -> String? {
        var wanted: [String] = []
        if whose == .theOwners {
            if let script = language(ofScriptIn: words) {
                // (v0.9.5) The Han characters are shared, so "zh" here means
                // "one of the languages written with them" and not "Chinese".
                // On a Mac set to one of those languages, that is the one the
                // owner reads and writes in, and it is a far better answer than
                // the guess: a Japanese owner whose name is in kanji had it
                // read out in Mandarin. Only where the letters really are
                // ambiguous — kana in the words make it Japanese outright and
                // this never fires.
                if script == "zh", shareTheHanCharacters.contains(base(macLanguage)) {
                    wanted.append(macLanguage)
                }
                wanted.append(script)
            } else if writtenInLatin(macLanguage) {
                wanted.append(macLanguage)
            }
        }
        // Moblee's own sentences are British English, so a British voice comes
        // first, then the Mac's own where the Mac is set to another English,
        // then any English at all.
        wanted.append("en-GB")
        if base(macLanguage) == "en" { wanted.append(macLanguage) }
        wanted.append("en")
        for want in wanted {
            if let exact = have.first(where: { $0.caseInsensitiveCompare(want) == .orderedSame }) { return exact }
            if let sameLanguage = have.first(where: { base($0) == base(want) }) { return sameLanguage }
        }
        return nil
    }

    /// The same, of this Mac.
    static func voice(for words: String, _ whose: Whose) -> AVSpeechSynthesisVoice? {
        guard let tag = choose(words, whose, have: onThisMac, macLanguage: macLanguage) else { return nil }
        return AVSpeechSynthesisVoice(language: tag)
    }
}

/// (v0.9.5) What one listen control will say, in pieces, so that a sentence of
/// Moblee's with the owner's own name inside it is read in two voices rather
/// than one: "Pick your wiki. Wiki ▸ " in Moblee's, and "نور Wiki" in Arabic.
///
/// The pieces are the very words on the screen beside the control, cut where
/// the owner's own words begin and end, and never a second copy of them written
/// out for the voice. That is what lets a check say "this control reads THAT
/// sentence" rather than "this control reads a sentence somebody typed twice".
struct Speech: Equatable {
    struct Piece: Equatable {
        let words: String
        let whose: Voices.Whose

        init(_ words: String, _ whose: Voices.Whose) {
            // The invisible marks that let a name stand on its own in a written
            // sentence must never reach a voice; see `OwnWords`. A voice would
            // not say them, but they have no business in a string handed to the
            // system, and this is the one place every spoken word goes through.
            self.words = words
                .replacingOccurrences(of: OwnWords.isolate, with: "")
                .replacingOccurrences(of: OwnWords.pop, with: "")
                .trimmingCharacters(in: .whitespacesAndNewlines)
            self.whose = whose
        }
    }

    var pieces: [Piece]

    /// Pieces with no letter and no digit in them are dropped: cutting "Hi, نور."
    /// at the name leaves a full stop on its own, and an utterance of one full
    /// stop is a voice clearing its throat for nothing.
    init(pieces: [Piece]) {
        self.pieces = pieces.filter { $0.words.contains { $0.isLetter || $0.isNumber } }
    }

    /// The ordinary case: a sentence of Moblee's own.
    init(_ words: String) { self.init(pieces: [Piece(words, .mobleesOwn)]) }

    static func mine(_ words: String) -> Speech { Speech(pieces: [Piece(words, .mobleesOwn)]) }
    static func theirs(_ words: String) -> Speech { Speech(pieces: [Piece(words, .theOwners)]) }

    static func + (first: Speech, second: Speech) -> Speech {
        Speech(pieces: first.pieces + second.pieces)
    }

    /// The whole of it as one line, which is what a check compares with the
    /// sentence on the screen.
    ///
    /// (v0.9.5) The pieces are put back together with a space between them,
    /// EXCEPT where the next one begins with a mark that belongs to the word
    /// before it. Each piece is trimmed as it is made, so a sentence cut at the
    /// owner's own words — "…called Sam Wiki. Three, say:…" — came back as
    /// "…called Sam Wiki . Three, say:…", with a space in front of the full
    /// stop, and a check comparing this with the screen's own sentence could
    /// never hold. The voice was never affected: it reads the pieces one at a
    /// time and says no marks at all. This is so that what a check compares is
    /// the sentence the screen really shows.
    var plain: String {
        var line = ""
        for piece in pieces {
            if !line.isEmpty, !(piece.words.first.map(Self.leansOnTheWordBefore) ?? false) {
                line += " "
            }
            line += piece.words
        }
        return line
    }

    /// The marks that close a word rather than open one, so a piece starting
    /// with any of them is joined straight on to the piece before.
    static func leansOnTheWordBefore(_ mark: Character) -> Bool {
        ".,;:!?)]}…’”\"'".contains(mark)
    }
    var isEmpty: Bool { pieces.isEmpty }

    /// One of Moblee's sentences with the owner's own words inside it, cut into
    /// the part before, the owner's words, and the part after. The first place
    /// the words appear is the one that is cut; a folder name that also appears
    /// inside a longer word later in the same sentence is not chased.
    static func sentence(_ whole: String, theirs: String) -> Speech {
        guard !theirs.isEmpty, let found = whole.range(of: theirs) else { return .mine(whole) }
        return .mine(String(whole[whole.startIndex..<found.lowerBound]))
            + .theirs(theirs)
            + .mine(String(whole[found.upperBound...]))
    }
}

/// Reads a block of words aloud, on the Mac, when the owner asks. Nothing
/// leaves the Mac, and it never starts by itself.
///
/// (v0.9.5) One voice at a time, and the control that is speaking says so. The
/// app used to know only "something is speaking", which was enough while there
/// was one listen control in the whole of it; with one beside every block of
/// words, the screen has to show WHICH one is reading, and pressing a second
/// must stop the first rather than be ignored. So what is kept is the name of
/// the control that is speaking, and pressing that same one again stops it.
@MainActor
final class Speaker: NSObject, ObservableObject, AVSpeechSynthesizerDelegate {
    static let shared = Speaker()

    /// The name of the control that is reading now, or nothing at all. Every
    /// listen control watches this: the one that matches draws a stop sign, and
    /// every other one draws a speaker.
    @Published private(set) var speakingId: String?

    /// How many times the owner has asked for something to be read since the
    /// app opened. Nothing anywhere in the app starts a voice, so a screen that
    /// has been drawn, walked and left with this still at nought is the proof
    /// that nothing speaks unasked — which a test can read, where it cannot
    /// listen.
    private(set) var timesAsked = 0

    private let synth = AVSpeechSynthesizer()

    /// The utterances of the press that is speaking now. A block read in two
    /// voices is two utterances, and the control must go on saying it is
    /// speaking until the last of them has finished — while an utterance
    /// cancelled by the NEXT press must not put the next press's control out.
    /// Told apart by which utterance it is, since that is the one thing the
    /// delegate is handed.
    private var mine: Set<ObjectIdentifier> = []

    override init() { super.init(); synth.delegate = self }

    /// The owner pressed a listen control. Pressing the one that is already
    /// reading stops it; pressing any other stops that one and starts this.
    func toggle(_ id: String, _ speech: Speech) {
        let wasSpeaking = speakingId == id
        stop()
        if wasSpeaking { return }
        guard !speech.isEmpty else { return }
        timesAsked += 1
        speakingId = id
        for piece in speech.pieces {
            let utterance = AVSpeechUtterance(string: piece.words)
            utterance.voice = Voices.voice(for: piece.words, piece.whose)
            // A shade under the Mac's ordinary pace. Several of Moblee's owners
            // are older, and one would rather be told than read; the default
            // rate is pitched at somebody skimming.
            utterance.rate = AVSpeechUtteranceDefaultSpeechRate * 0.92
            mine.insert(ObjectIdentifier(utterance))
            synth.speak(utterance)
        }
    }

    /// Stops whatever is reading. Called by every button that leaves a screen,
    /// and by the screen itself going away.
    func stop() {
        mine.removeAll()
        if synth.isSpeaking || synth.isPaused { synth.stopSpeaking(at: .immediate) }
        speakingId = nil
    }

    private func finished(_ utterance: AVSpeechUtterance) {
        guard mine.remove(ObjectIdentifier(utterance)) != nil else { return }
        if mine.isEmpty { speakingId = nil }
    }

    nonisolated func speechSynthesizer(_ s: AVSpeechSynthesizer, didFinish u: AVSpeechUtterance) {
        Task { @MainActor in self.finished(u) }
    }
    nonisolated func speechSynthesizer(_ s: AVSpeechSynthesizer, didCancel u: AVSpeechUtterance) {
        Task { @MainActor in self.finished(u) }
    }
}

/// (v0.9.5) "Read it to me", beside one block of words — and there is one of
/// these beside every block of words in the app now, not only beside the big
/// sentence at the top of each screen.
///
/// An owner who would rather be told than read used to get the headline and
/// nothing else: the words on every card, the tiles and their reasons, the
/// check-up's findings, the skill they are about to add, the receipt for what
/// they dropped, the five steps in ChatGPT — all of it was silent.
///
/// Three things make one of these safe to put on a full screen:
///
///  * it is drawn in an OVERLAY on the card or beside the line, so it takes no
///    room in the layout at all and cannot push anything off the window at the
///    biggest text size, in either direction;
///  * it carries a name of its own, so the keyboard ring, the screen reader and
///    the self-drive walk can each tell six of them apart;
///  * it says what it will read, so a screen reader does not announce six
///    buttons all called "Read it to me".
struct ListenButton: View {
    /// The name the keyboard ring is recorded under and the walk finds it by.
    /// Always one of Moblee's own fixed words, never anything of the owner's.
    let id: String
    /// What it will read, in the voices the words themselves ask for.
    let speech: Speech
    /// Which words these are, for the label a screen reader reads out. Short,
    /// and the words themselves where they are short enough to be the name of
    /// the block ("Trip planning"), otherwise where they are ("the first card").
    let what: String
    /// How big the symbol is drawn. The one beside a screen's big sentence is
    /// the largest; the ones on cards and in lists are smaller, so that they
    /// belong to their words without shouting over them.
    var size: CGFloat = 16

    @ObservedObject private var speaker = Speaker.shared
    /// Drawn again when the owner presses "Bigger text". (v0.9.4)
    @ObservedObject private var textSize = TextSize.shared

    private var speaking: Bool { speaker.speakingId == id }

    private func press() { speaker.toggle(id, speech) }

    var body: some View {
        Button(action: press) {
            Image(systemName: speaking ? "stop.circle.fill" : "speaker.wave.2.circle.fill")
                .font(Theme.font(size))
                // The one that is speaking is a stop sign AND a different
                // colour, so it is told from its neighbours by shape as well as
                // by hue: several of Moblee's owners have poor eyesight.
                .foregroundStyle(speaking ? Theme.waitingText : Theme.accent)
                .contentShape(Circle())
        }
        .buttonStyle(.plain)
        .help(speaking ? "Stop reading" : "Read it to me")
        .accessibilityLabel(speaking ? "Stop reading \(what)" : "Read \(what) to me")
        .keyboardReachable(id, corner: size * 0.65, press: press)
    }
}

/// (v0.9.5) What the listen control beside a screen's big sentence will read.
/// Kept out of `ScreenFrame` so that a check can ask it, screen by screen, what
/// each headline would say — against the screen's own sentence and not a copy.
enum Headline {
    static func speech(sentence: String, spoken: String?, speech: Speech?) -> Speech {
        if let speech { return speech }
        if let spoken { return Speech(spoken) }
        return Speech(sentence)
    }
}

/// (v0.9.4) Escape does what "Not now" does — and only that. The quiet place
/// under the big button is not always a "not now": on the home screen it is
/// "Open Claude", at the hand-off "What did Moblee make?", on the Trust screen
/// "Later". Escape must press none of those.
enum QuietWords {
    static func escapeCancels(_ quietTitle: String?) -> Bool { quietTitle == "Not now" }
}

/// Every screen has the same skeleton: the sentence first, since it is the
/// instruction; then the picture; then one big button. A second, quiet action
/// can sit under the big one.
struct ScreenFrame<Picture: View>: View {
    let sentence: String
    let buttonTitle: String
    var buttonEnabled: Bool = true
    /// (v0.9.4) Whether this screen has a way back, said by the screen itself.
    /// It used to be worked out here as "unless the owner is on the welcome
    /// screen", which is a different question: while the welcome screen slid
    /// out and the check-up slid in, the welcome screen — still on the window —
    /// grew a back arrow for a third of a second, because by then the owner was
    /// no longer on it. The welcome screen now simply says it has none.
    var showsBack: Bool = true
    var quietTitle: String? = nil
    var quietAction: (() -> Void)? = nil
    /// A second large button beside the first. Both are then a little narrower.
    /// Two screens use it: the hand-off, which sends an owner to either of two
    /// apps, and the home screen, whose second button opens the example wiki
    /// (v0.9.6) — an owner who already has a wiki and still does not know what
    /// one is for needs it as much as an owner who has none.
    var secondTitle: String? = nil
    var secondAction: (() -> Void)? = nil
    /// What "Read it to me" says, if it should say more than the sentence.
    var spoken: String? = nil
    /// (v0.9.5) The same, where the sentence has the owner's own words in it and
    /// so has to be read in more than one voice.
    var speech: Speech? = nil
    /// (v0.9.6) What a screen reader calls the words the listen control beside
    /// the heading reads. It is "the sentence" on every screen but one: on a page
    /// of the example wiki that control reads the whole page, and "Read the
    /// sentence to me" would then be untrue of the only thing it does.
    var reads: String = "the sentence"
    /// (v0.9.6) What the way back does, where it is not a step of the install.
    /// The arrow used to be nailed to `flow.back()`, which is right on every
    /// screen of the install and wrong inside the example wiki: back there means
    /// back to the page before, and moving the install a screen backwards behind
    /// an owner who is reading would be the worst kind of surprise. The arrow
    /// itself, its ring, its name and which side it sits on are unchanged.
    var backAction: (() -> Void)? = nil
    /// The room the picture is given. One screen (the proof that found the
    /// guard not running) has a one-line sentence and a taller picture.
    var pictureHeight: CGFloat = 280
    let action: () -> Void
    @ViewBuilder let picture: () -> Picture

    @EnvironmentObject var flow: Flow
    @ObservedObject private var speaker = Speaker.shared
    @ObservedObject private var textSize = TextSize.shared

    var body: some View {
        VStack(spacing: 0) {
            // The gap above the sentence is small because the strip that holds
            // the practice badge and "Bigger text" sits above this, and gives
            // the screen its top margin. (v0.9.4)
            Spacer(minLength: Theme.pt(6))
            HStack(alignment: .firstTextBaseline, spacing: Theme.pt(10)) {
                Text(sentence)
                    .font(Theme.font(24, .semibold))
                    .multilineTextAlignment(.center)
                    .fixedSize(horizontal: false, vertical: true)
                    // (v0.9.4) Three lines, and a sentence that needs more is
                    // drawn a little smaller instead of growing past the edge
                    // of the window. The longest sentence in the app (an
                    // update whose commit was refused) took four lines and was
                    // already running off the bottom before the words could be
                    // made bigger at all; it is the only one this touches.
                    .lineLimit(3)
                    .minimumScaleFactor(0.7)
                    // A window made wider must not turn the sentence into one
                    // long line across the whole of it: it stays a column of
                    // about the width it has always had, in the middle.
                    .frame(maxWidth: Theme.pt(600))
                    .accessibilityAddTraits(.isHeader)
                // (v0.9.4) "Read it to me" is on every screen in the app, and
                // an owner who cannot use a mouse is exactly the owner most
                // likely to want it read to them; it had no way to the keyboard.
                // (v0.9.5) It is now one of many on a screen rather than the
                // only one, so it is the same control as the rest, drawn larger.
                ListenButton(id: "read-aloud",
                             speech: Headline.speech(sentence: sentence, spoken: spoken, speech: speech),
                             what: reads, size: 22)
            }
            .padding(.horizontal, Theme.pt(48))
            Spacer(minLength: Theme.pt(10))
            picture()
                .frame(maxWidth: .infinity)
                .frame(height: Theme.pt(pictureHeight))
            Spacer(minLength: Theme.pt(10))
            HStack {
                if showsBack {
                    // (v0.9.6) Where back goes is the screen's own to say; the
                    // install's screens say nothing and get the step before.
                    let goBack = { speaker.stop(); (backAction ?? flow.back)() }
                    Button(action: goBack) {
                        // (v0.9.4) The arrow points the way back goes, which is
                        // the other way once the layout is mirrored; see `Layout`.
                        Image(systemName: Layout.backSymbol)
                            .font(Theme.font(30))
                            .frame(width: Theme.pt(44), height: Theme.pt(44))
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(.secondary)
                    .accessibilityLabel("Back")
                    // (v0.9.4) Says where it really is, so the self-drive walk
                    // can read which side of the big button it sits on — and,
                    // since 26 September 2026, takes the keyboard like every
                    // other control: the way back was a mouse-only arrow on
                    // every screen that has one.
                    .keyboardReachable("back", corner: 22, press: goBack)
                }
                Button(action: { speaker.stop(); action() }) {
                    Text(buttonTitle)
                        .font(Theme.font(19, .semibold))
                        .frame(minWidth: Theme.pt(secondTitle == nil ? 220 : 170), minHeight: Theme.pt(50))
                }
                .buttonStyle(BigButtonStyle())
                .disabled(!buttonEnabled)
                // The big button is the window's default action, so Return
                // presses it from anywhere on the screen, whatever the keyboard
                // is on and whether or not Full Keyboard Access is switched on.
                // That is how it is reached from the keyboard, and it is why it
                // is the one control here with no ring of its own: a ring that
                // can never be moved on to would say something untrue. macOS
                // gives a greyed-out button nothing, so Return does nothing on
                // a screen that has not been answered yet. (v0.9.4)
                .keyboardShortcut(.defaultAction)
                .accessibilityIdentifier("main-button")
                // (v0.9.4) The big button says where it really is, so that the
                // self-drive walk presses the button rather than the place the
                // button used to be. The window can now be made bigger, and
                // the words with it, so no sum worked out here would hold.
                .background(DrawnAt(id: "main-button"))
                if let secondTitle, let secondAction {
                    Button(action: { speaker.stop(); secondAction() }) {
                        Text(secondTitle)
                            .font(Theme.font(19, .semibold))
                            .frame(minWidth: Theme.pt(170), minHeight: Theme.pt(50))
                    }
                    .buttonStyle(BigButtonStyle())
                    // (v0.9.4) The second big button — "Open Claude" on the
                    // hand-off — is not the window's default action, so Return
                    // does not reach it and nothing else did either. It takes
                    // the keyboard like the rest.
                    .keyboardReachable("second-button", corner: 16,
                                       press: { speaker.stop(); secondAction() })
                }
                if showsBack {
                    // Balances the back arrow so the big button stays centred.
                    Color.clear.frame(width: Theme.pt(44), height: Theme.pt(44))
                }
            }
            Group {
                if let quietTitle, let quietAction {
                    // (v0.9.5) The quiet words get a listen control of their own.
                    // They are a button's label rather than a sentence, but they
                    // are also the only thing on the screen that says what the
                    // small blue word under the big button will do — "Not now",
                    // "Later", "Open Claude", "Show what happened" — and an
                    // owner who would rather be told than read had no way at all
                    // to find out which of them it was.
                    HStack(spacing: Theme.pt(6)) {
                        QuietButton(title: quietTitle, cancels: QuietWords.escapeCancels(quietTitle),
                                    action: { speaker.stop(); quietAction() })
                        ListenButton(id: "listen-quiet", speech: Speech(quietTitle),
                                     what: "the small button", size: 14)
                    }
                } else {
                    Color.clear
                }
            }
            .frame(height: Theme.pt(26))
            .padding(.top, Theme.pt(6))
            .padding(.bottom, Theme.pt(16))
        }
        // (v0.9.5) Leaving a screen stops it reading. Every button on the frame
        // already stopped it before doing its own work, but a screen can also be
        // left without one of them being pressed — the home screen swaps itself
        // for an explanation, a drop receipt takes the place of whatever was
        // there, a repair finishes — and a voice reading the screen the owner has
        // just left is a voice reading words that are no longer in front of them.
        .onDisappear { speaker.stop() }
    }
}

struct QuietButton: View {
    let title: String
    /// The name the self-drive walk finds it by, and the name the keyboard
    /// ring is recorded under.
    var id: String = "quiet"
    /// Escape presses it. True only where the words are "Not now".
    var cancels: Bool = false
    let action: () -> Void

    @ObservedObject private var textSize = TextSize.shared

    var body: some View {
        // A little room round the words: the ring that shows the keyboard is
        // on this button would otherwise sit on the letters, and the whole
        // padded box takes the click rather than the letters alone. (v0.9.4)
        let button = Button(action: action) {
            Text(title)
                .font(Theme.font(14, .semibold))
                .padding(.horizontal, Theme.pt(9)).padding(.vertical, Theme.pt(3))
                .contentShape(Rectangle())
        }
            .buttonStyle(.plain)
            .foregroundStyle(Theme.accent)
            .keyboardReachable(id, corner: 8, press: action)
        if cancels {
            button.keyboardShortcut(.cancelAction)
        } else {
            button
        }
    }
}

struct BigButtonStyle: ButtonStyle {
    @Environment(\.isEnabled) private var isEnabled

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .padding(.horizontal, Theme.pt(26))
            .foregroundStyle(.white)
            .background(
                RoundedRectangle(cornerRadius: Theme.pt(16), style: .continuous)
                    .fill(isEnabled ? Theme.accent : Color.gray.opacity(0.45)))
            .scaleEffect(configuration.isPressed ? 0.97 : 1)
            .animation(.easeOut(duration: 0.12), value: configuration.isPressed)
    }
}
