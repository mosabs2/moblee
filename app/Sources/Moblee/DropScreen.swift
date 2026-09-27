import SwiftUI
import AppKit
import UniformTypeIdentifiers

/// (v0.9.5) The receipt an owner sees when something has been dropped on
/// Moblee — and the refusal when it could not be taken.
///
/// It takes the place of whatever screen was there, the way the offer to move to
/// Applications does, because a drop on the Dock icon arrives wherever the owner
/// happens to be and the answer has to reach them from all of them. One button,
/// which puts them back where they were.
struct DropScreen: View {
    /// Drawn again when the owner presses "Bigger text". (v0.9.4)
    @ObservedObject private var textSize = TextSize.shared
    @ObservedObject private var dropped = Dropped.shared
    let landing: Inbox.Landing

    /// How many names are shown on the receipt. An owner who does not read much
    /// is not helped by a list of forty, and the count in the sentence above has
    /// already told them how many there were. The same three
    /// `HomeModel.foreignSkillSentence` names, for the same reason.
    static let namesShown = 4

    /// What the one button says. Kept here rather than written inside the
    /// screen's body so that a check can ask the screen itself what its button
    /// says; the check that used to stand for this read `anythingLanded` back
    /// out of the very landing it had just handed in, and would have held just
    /// as well with the two words swapped over. (v0.9.5)
    static func buttonTitle(for landing: Inbox.Landing) -> String {
        // "Done" wherever anything at all landed, even if something else did
        // not: what the owner does next is the same either way, and the card
        // under the sentence already names what did not go.
        landing.anythingLanded ? "Done" : "Carry on"
    }

    var body: some View {
        ScreenFrame(sentence: Inbox.sentence(for: landing, talksTo: dropped.talksTo),
                    buttonTitle: Self.buttonTitle(for: landing),
                    showsBack: false,
                    // (v0.9.5) The names are the owner's own — a file they named
                    // themselves, in whatever language they name things in — so
                    // the headline is read in pieces, Moblee's sentence in
                    // Moblee's voice and each name in one chosen for that name.
                    speech: headline,
                    action: { dropped.readIt() }) {
            if landing.anythingLanded {
                whatLanded
            } else {
                Image(systemName: Self.symbol(for: landing.firstRefusal ?? .nothingToTake))
                    .font(Theme.font(96, .regular, .default))
                    .foregroundStyle(Self.colour(for: landing.firstRefusal ?? .nothingToTake))
                    .accessibilityHidden(true)
            }
        }
    }

    /// Read aloud, a list of names is worth having in full up to the same four;
    /// the sentence alone would say "3 things" and not which. In pieces:
    /// Moblee's sentence in Moblee's voice, and each name in a voice chosen for
    /// the letters the owner named it in. (v0.9.5)
    ///
    /// There is no `spoken` beside this. `Headline.speech` gives a `speech`
    /// back before it looks at `spoken` at all, and this screen always has one,
    /// so the `spoken` that used to sit here was a second copy of these very
    /// words that nothing could ever read — and a copy nobody reads is a copy
    /// that drifts.
    private var headline: Speech {
        var said = Speech(Inbox.sentence(for: landing, talksTo: dropped.talksTo))
        guard landing.anythingLanded else { return said }
        for name in landing.landed.prefix(Self.namesShown) { said = said + .theirs(name) }
        return said
    }

    /// (v0.9.5) What the card of names reads: every row on it, each name in a
    /// voice chosen for the name, and each refusal's reason in Moblee's own.
    ///
    /// One control for the card rather than one for each row, and the reason is
    /// the rows themselves: a row is a file's name on one line, up to eight of
    /// them on a card 560 points wide, and eight speakers down the side of a list
    /// of names would be a column of buttons rather than a receipt. Read
    /// together they are one answer to one question — what happened to what I
    /// dropped — which is what the card is.
    static func landedSpeech(for landing: Inbox.Landing, talksTo: String) -> Speech {
        var said = Speech(pieces: [])
        for name in landing.landed.prefix(namesShown) { said = said + .theirs(name) }
        if landing.landed.count > namesShown {
            said = said + Speech(moreLine(landing.landed.count - namesShown))
        }
        for turned in landing.turnedAway.prefix(namesShown) {
            said = said + .theirs(turned.name) + Speech(Inbox.turnedAwayWords(turned.why, talksTo: talksTo))
        }
        return said
    }

    static func moreLine(_ count: Int) -> String { "and \(count) more" }

    /// What landed, by name, and under it anything that did not. The names are
    /// the ones now in the inbox, which is what the owner will see in Finder and
    /// what their assistant will read out, so a name that got a number shows the
    /// number.
    private var whatLanded: some View {
        VStack(spacing: Theme.pt(10)) {
            Image(systemName: "tray.and.arrow.down.fill")
                .font(Theme.font(44, .medium, .default))
                .foregroundStyle(Theme.accent)
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: Theme.pt(6)) {
                ForEach(Array(landing.landed.prefix(Self.namesShown)), id: \.self) { name in
                    row("checkmark.circle.fill", Theme.good, Theme.goodText,
                        // A name the owner will look for in Finder is left
                        // exactly as Finder shows it; see `OwnWords`.
                        OwnWords.asFinderShowsIt(name))
                }
                if landing.landed.count > Self.namesShown {
                    Text(Self.moreLine(landing.landed.count - Self.namesShown))
                        .font(Theme.font(14, .medium))
                        .foregroundStyle(.secondary)
                }
                ForEach(landing.turnedAway.prefix(Self.namesShown), id: \.name) { turned in
                    row("exclamationmark.circle.fill", .red, Theme.badText,
                        OwnWords.asFinderShowsIt(turned.name) + " — "
                            + Inbox.turnedAwayWords(turned.why, talksTo: dropped.talksTo))
                }
            }
            .padding(Theme.pt(16))
            .frame(width: Theme.pt(560), alignment: .leading)
            .background(CardBackground())
            // In the corner, as an overlay: the rows are as wide as the card and
            // the card is as tall as its rows, so there is nowhere inside it a
            // control could go without taking a row's room. (v0.9.5)
            .overlay(alignment: .topTrailing) {
                ListenButton(id: "listen-landed",
                             speech: Self.landedSpeech(for: landing, talksTo: dropped.talksTo),
                             what: "the list of names")
                    .padding(Theme.pt(8))
            }
        }
        .accessibilityElement(children: .contain)
    }

    private func row(_ symbol: String, _ tint: Color, _ words: Color, _ text: String) -> some View {
        HStack(spacing: Theme.pt(8)) {
            Image(systemName: symbol)
                .font(Theme.font(16, .regular, .default))
                .foregroundStyle(tint)
                .accessibilityHidden(true)
            Text(text)
                .font(Theme.font(15, .medium))
                .foregroundStyle(words)
                .lineLimit(1).truncationMode(.middle)
        }
    }

    /// One picture for each way a drop is refused. The two that carry a meaning
    /// of their own — there is no wiki yet, and it was a folder — get the
    /// picture that says so; the rest share the app's own "something is wrong"
    /// triangle, which is what every other screen uses for exactly that.
    static func symbol(for why: Inbox.Refusal) -> String {
        switch why {
        case .noWikiYet: return "books.vertical.fill"
        case .isAFolder: return "folder.fill.badge.questionmark"
        case .busy: return "clock.fill"
        default: return "exclamationmark.triangle.fill"
        }
    }

    static func colour(for why: Inbox.Refusal) -> Color {
        switch why {
        case .couldNotCopy, .cannotRead: return .red
        default: return Theme.waiting
        }
    }
}

/// (v0.9.5) The whole window takes a drop.
///
/// SwiftUI's own `onDrop` is used rather than an AppKit view registered for
/// dragged types: an NSView put behind the screens is never the view a drag
/// hit-tests to, and one put in front of them would have to refuse every mouse
/// click to let the screens work, which is the same hit test. This is on the
/// root, above every screen, so a drop anywhere on the window lands — an owner
/// aiming at a window does not aim at a part of it.
///
/// Three kinds are asked for: a file (which is nearly always what is dropped),
/// a picture's own bytes, and plain words.
///
/// (v0.9.5) The picture is new, and it is the fix for a promise that was not
/// being kept. `README.md`, `CHANGELOG.md` and the wiki's own
/// `raw/HOW-TO-ADD-CONTENT.md` all tell owners to "drag a file, a photo or a
/// piece of text", and an image dragged out of a web page or a Preview window
/// carries no file at all — only the picture's bytes. Asking macOS for files
/// and words alone meant SwiftUI never called this for such a drag: it bounced
/// back, and nothing was said. The comment that used to sit here claimed it
/// "is refused out loud rather than half-taken", and it was not refused out
/// loud; it was not refused at all, because Moblee never heard about it. A drag
/// that says nothing is the one outcome this feature may not have, so the
/// picture is taken and written into the inbox; see `Inbox.Picture`.
///
/// What is still not taken, plainly: a drag that hands over only a PROMISE of a
/// file (some apps' own galleries work that way) carries none of the three, so
/// macOS does not offer it here and the drag bounces. Dragging the picture out
/// to the desktop first and dropping the file is the way through, and the two
/// routes an owner is most likely to use — a file from Finder, and an image
/// from a web page — both land.
extension View {
    func takesADrop() -> some View {
        onDrop(of: [UTType.fileURL] + Inbox.pictureTypes + [UTType.plainText],
               isTargeted: nil) { providers in
            Inbox.read(providers) { files, text, pictures in
                Dropped.shared.arrived(files: files, text: text, pictures: pictures)
            }
            return true
        }
    }
}
