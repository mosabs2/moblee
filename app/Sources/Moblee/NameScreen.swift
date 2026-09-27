import SwiftUI

/// The only typed question in the whole install. The question is the screen's
/// sentence, which sits directly above the box it is asking about.
struct NameScreen: View {
    /// Drawn again when the owner presses "Bigger text". (v0.9.4)
    @ObservedObject private var textSize = TextSize.shared
    @EnvironmentObject var flow: Flow
    @FocusState private var focused: Bool
    @Environment(\.stillPicture) private var still

    /// The question of which assistant comes after this one, so the sentence
    /// names none, and reads the same for everyone.
    static let words = "What should your assistant call you?"
    private var question: String { Self.words }

    var body: some View {
        ScreenFrame(
            sentence: question,
            buttonTitle: "Next",
            buttonEnabled: !flow.trimmedName.isEmpty,
            action: flow.next
        ) {
            VStack(spacing: Theme.pt(22)) {
                nameField
                    .font(Theme.font(28, .medium))
                    .multilineTextAlignment(.center)
                    .padding(.vertical, Theme.pt(14))
                    .frame(width: Theme.pt(380))
                    .background(CardBackground(corner: 16))
                    .focused($focused)
                    .accessibilityLabel(question)
                HStack(alignment: .bottom, spacing: Theme.pt(10)) {
                    HStack(alignment: .bottom, spacing: Theme.pt(14)) {
                        Image(systemName: "sparkles")
                            .font(Theme.font(36, .medium, .default))
                            .foregroundStyle(Theme.accent)
                            .frame(width: Theme.pt(64), height: Theme.pt(64))
                            .background(Circle().fill(Theme.card)
                                .overlay(Circle().stroke(Theme.cardEdge, lineWidth: 1))
                                .shadow(color: .black.opacity(0.12), radius: 8, y: 3))
                        // (v0.9.4) The name stands on its own inside the greeting, so
                        // that a name read right to left keeps the full stop after
                        // it rather than in front of it; see `OwnWords`.
                        Text(Self.greeting(flow.trimmedName))
                            .font(Theme.font(22, .semibold))
                            .padding(.horizontal, Theme.pt(20)).padding(.vertical, Theme.pt(14))
                            .background(
                                RoundedRectangle(cornerRadius: Theme.pt(20), style: .continuous)
                                    .fill(Theme.accent.opacity(0.14)))
                            .animation(.easeOut(duration: 0.15), value: flow.trimmedName)
                    }
                    .accessibilityHidden(true)
                    // (v0.9.5) The greeting read back, which is the one place in
                    // the app where an owner can hear their own name said before
                    // they commit to it — and the plainest case of picking the
                    // voice by the words: "Hi," is Moblee's and is read in
                    // Moblee's voice, the name is theirs and is read in a voice
                    // chosen for the letters it is written in. It sits beside the
                    // picture rather than inside it, because a control a screen
                    // reader cannot see is no control, and the picture is hidden
                    // from one.
                    ListenButton(id: "listen-greeting", speech: Self.greetingSpeech(flow.trimmedName),
                                 what: "the greeting")
                        .padding(.bottom, Theme.pt(16))
                }
            }
        }
        .onAppear { focused = true }
    }

    /// The greeting as it is drawn, in one place, so that what is shown and what
    /// is read cannot drift apart. (v0.9.5)
    static func greeting(_ name: String) -> String {
        name.isEmpty ? "Hi…" : "Hi, \(OwnWords.standingAlone(name))."
    }

    /// The greeting read aloud: Moblee's word in Moblee's voice, the owner's name
    /// in one chosen for the name, and none of the invisible marks that let it
    /// stand on its own on the screen. (v0.9.5)
    static func greetingSpeech(_ name: String) -> Speech {
        name.isEmpty ? Speech("Hi") : Speech.sentence(greeting(name), theirs: name)
    }

    /// A real text field cannot be drawn to a picture file, so the drawn
    /// version shows the same words as plain text. Return is left to the big
    /// button (it is the window's default action), so it is handled once.
    ///
    /// (v0.9.4) The box's words are in the middle, and the box is left to
    /// macOS's own natural direction, which settles itself from what has been
    /// typed: a name typed in Arabic reads right to left inside the box, and one
    /// typed in English left to right, whichever way the app around it is laid
    /// out. The drawn version says the name stands on its own for the same
    /// reason, so that a name beginning in Arabic is not laid out by the
    /// sentence around it; there is no sentence around it here.
    @ViewBuilder private var nameField: some View {
        if still {
            Text(flow.ownerName.isEmpty ? "Your name" : OwnWords.standingAlone(flow.ownerName))
                .foregroundStyle(flow.ownerName.isEmpty ? .tertiary : .primary)
                .frame(maxWidth: .infinity)
        } else {
            TextField("Your name", text: $flow.ownerName)
                .textFieldStyle(.plain)
        }
    }
}

/// Said before anything is made: exactly what Moblee is about to put on this
/// Mac, and where. A beginner is being asked to let an app from the internet
/// change Claude's settings; this is the plain statement that earns it.
struct PromiseScreen: View {
    /// Drawn again when the owner presses "Bigger text". (v0.9.4)
    @ObservedObject private var textSize = TextSize.shared
    @EnvironmentObject var flow: Flow

    var body: some View {
        let place = flow.resumePlace ?? flow.chosenPlace ?? flow.freeLocation()
        let words = Self.words(for: flow.assistant ?? .claude)
        ScreenFrame(
            sentence: words.sentence,
            buttonTitle: flow.resumePlace == nil ? "Make it" : "Finish it",
            spoken: Self.spoken(place: place.name, words: words),
            // (v0.9.5) The wiki folder is called after the owner and may be
            // written in their own script, so the headline is cut at the name and
            // the name read in a voice chosen for it.
            speech: Speech.sentence(Self.spoken(place: place.name, words: words), theirs: place.name),
            action: flow.next
        ) {
            VStack(spacing: Theme.pt(8)) {
                HStack(alignment: .top, spacing: Theme.pt(18)) {
                    // (v0.9.4) The folder is named after the owner, and this is
                    // the name they will look for in Finder, so it is laid out
                    // the way Finder will lay it out: no isolate of its own, and
                    // the direction of the line it is in. See `OwnWords`.
                    // What is read aloud is left plain.
                    HandoffCard(number: 1, symbol: "folder.fill", title: "Your wiki",
                                detail: "A folder called “\(OwnWords.asFinderShowsIt(place.name))” inside “Wiki”, in your home folder",
                                ownWords: place.name)
                    HandoffCard(number: 2, symbol: "lock.shield.fill", title: "A guard",
                                detail: words.guardCard)
                    HandoffCard(number: 3, symbol: "graduationcap.fill", title: words.skillsTitle,
                                detail: words.skillsCard)
                }
                // With ChatGPT one more thing is touched, and the screen that
                // says "nothing else" says what it is. It sits under the cards
                // because the sentence above has room for two lines, not four.
                if let alsoTouched = words.alsoTouched {
                    HStack(spacing: Theme.pt(8)) {
                        Text(alsoTouched)
                            .font(Theme.font(13, .medium))
                            .foregroundStyle(Color.primary.opacity(0.8))
                            .multilineTextAlignment(.center)
                            .fixedSize(horizontal: false, vertical: true)
                        // (v0.9.5) A sentence of its own, under the cards, so it
                        // has a listen control of its own. It is the one place
                        // this screen says something is touched besides the three.
                        ListenButton(id: "listen-also-touched", speech: Speech(alsoTouched),
                                     what: "the line under the cards", size: 14)
                    }
                }
            }
            .padding(.horizontal, Theme.pt(30))
        }
    }

    /// What the headline's listen control reads: the three things, in order, in
    /// words of their own rather than the cards' clipped ones. Kept here so a
    /// check can ask for it. (v0.9.5: was written into the screen.)
    static func spoken(place: String, words: Words) -> String {
        "Here is what Moblee will make. One: a folder for your wiki, called \(place). "
            + "Two: a guard, \(words.guardSpoken). "
            + "Three: \(words.skillsSpoken). \(words.closingSpoken)"
    }

    struct Words {
        let guardCard, guardSpoken, skillsTitle, skillsCard, skillsSpoken: String
        /// The sentence at the top, and how "Read it to me" ends.
        var sentence = "Here is what Moblee will make. Nothing else is touched."
        var closingSpoken = "Nothing else on your Mac is touched."
        /// Shown under the cards when something besides the three is touched.
        var alsoTouched: String? = nil
    }

    /// For ChatGPT the installer adds one line to ChatGPT's own settings
    /// (`project_doc_max_bytes` in `~/.codex/config.toml`), so "nothing else is
    /// touched" would not be true on its own.
    static let chatgptSetting = "One setting is added in ChatGPT's own folder, so it can read your whole rules file. Nothing else is touched."

    /// Claude's words are as they have always been. With ChatGPT the guard's
    /// promise holds once the owner has trusted it there, and the card says so:
    /// the Trust screen after the build is where they do it.
    static func words(for assistant: Assistant) -> Words {
        switch assistant {
        case .claude:
            return Words(guardCard: "So Claude can never delete anything in it",
                         guardSpoken: "so Claude can never delete anything in it",
                         skillsTitle: "Claude's skills",
                         skillsCard: "What Claude needs to keep your wiki",
                         skillsSpoken: "the skills Claude needs to keep it")
        case .chatgpt:
            return Words(guardCard: "So ChatGPT cannot delete anything in it, once you have pressed Trust in ChatGPT",
                         guardSpoken: "so ChatGPT cannot delete anything in it, once you have pressed Trust in ChatGPT",
                         skillsTitle: "ChatGPT's skills",
                         skillsCard: "What ChatGPT needs to keep your wiki",
                         skillsSpoken: "the skills ChatGPT needs to keep it",
                         sentence: "Here is what Moblee will make.",
                         closingSpoken: chatgptSetting,
                         alsoTouched: chatgptSetting)
        case .both:
            return Words(guardCard: "So neither can delete anything in it. In ChatGPT you press Trust first",
                         guardSpoken: "so neither assistant can delete anything in it. In ChatGPT you press Trust first",
                         skillsTitle: "The skills",
                         skillsCard: "What each assistant needs to keep your wiki",
                         skillsSpoken: "the skills each assistant needs to keep it",
                         sentence: "Here is what Moblee will make.",
                         closingSpoken: chatgptSetting,
                         alsoTouched: chatgptSetting)
        }
    }
}
