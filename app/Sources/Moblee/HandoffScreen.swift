import SwiftUI
import AppKit

/// The last screen: into Claude, at the new wiki, with the opening words ready.
/// Claude's app cannot be opened at a folder from outside, so the three clicks
/// are shown as pictures and the words are put on the clipboard.
struct HandoffScreen: View {
    /// Drawn again when the owner presses "Bigger text". (v0.9.4)
    @ObservedObject private var textSize = TextSize.shared
    @EnvironmentObject var flow: Flow
    @EnvironmentObject var install: InstallRun
    @State private var opened = false
    /// With both assistants: which of the two has been opened so far.
    @State private var openedApps: Set<Assistant> = []
    @State private var showingReceipt = false

    private var wikiFolderName: String {
        guard let p = install.vaultPath else { return flow.wikiName }
        return URL(fileURLWithPath: p).lastPathComponent
    }

    /// (v0.9.4) The same name, laid out the way Finder is laying it out on the
    /// same screen: this is the one instruction the owner has to match against
    /// what they see in Finder, so it is left to take the direction of the line
    /// it is in and given no isolate of its own. Told to stand alone,
    /// "نور Wiki" was drawn "Wiki نور" and Finder showed "نور Wiki".
    /// Only for words on the screen; see `OwnWords`.
    private var wikiOnItsOwn: String { OwnWords.asFinderShowsIt(wikiFolderName) }

    /// Claude's screen is as it has always been, word for word. ChatGPT's app
    /// may open at a folder from outside (by a `codex://` link, a scheme
    /// registered by the ChatGPT app on the Mac this was built on; untested
    /// until the testdev run), but if
    /// the link is not taken the app is simply opened, so the sentence says
    /// what to do in words that are true either way. With both, there is a
    /// button for each.
    private var assistant: Assistant { flow.assistant ?? .claude }

    private var sentence: String {
        if showingReceipt { return "This is everything Moblee made on your Mac." }
        return Self.sentence(for: assistant, opened: opened)
    }

    private var spoken: String? {
        if showingReceipt { return nil }
        return Self.spoken(for: assistant, wiki: wikiFolderName)
    }

    /// (v0.9.5) The same words, cut where the wiki folder's name is, so that a
    /// name written in the owner's own script is read by a voice for that script
    /// and not spelled out as nonsense by an English one.
    private var headline: Speech? {
        guard let spoken else { return nil }
        return Speech.sentence(spoken, theirs: wikiFolderName)
    }

    /// The words of the hand-off, kept where the logic check can read them.
    ///
    /// In ChatGPT the wiki is opened by the File menu's Open Folder, and by no
    /// other way: an owner once sent to open it from inside a project that was
    /// rooted elsewhere ended with the wiki as an outside folder, and every
    /// write to it then needed their approval (a real install, 21 September 2026).
    ///
    /// Then the switch at the top of ChatGPT's window, which says Chat or Work.
    /// Set to Work, the chat runs in the opened wiki folder. Set to Chat,
    /// ChatGPT offers to "Continue in Work", and that goes on in a folder of
    /// ChatGPT's own making, outside the wiki, where the wiki's rules are not
    /// loaded (a test on 21 September 2026). The Open ChatGPT button opens the
    /// wiki folder but cannot set that switch, so the owner is told to, before
    /// the words are said and again once the words are copied.
    static func sentence(for assistant: Assistant, opened: Bool) -> String {
        switch assistant {
        case .claude:
            return opened ? "The words are copied. Paste them to Claude." : "Last step. Do these three in Claude."
        case .chatgpt:
            return opened ? "The words are copied. In ChatGPT choose Work at the top, then paste them."
                          : "Last step. Open your wiki folder in ChatGPT, choose Work at the top, then say the words."
        case .both:
            return opened ? "The words are copied. Paste them to your assistant."
                          : "Last step. Open your wiki in either assistant, then say the words."
        }
    }

    /// Claude's Code tab is not on the free plan. An owner on the free plan who
    /// is sent to click Code finds nothing there and has no way of knowing why:
    /// `docs/02-install.md` has said this since the app route was written, and
    /// the app itself never did. Said in the same words as the document.
    ///
    /// It goes UNDER the three pictures, in the place `PromiseScreen` puts its
    /// own extra line, and not inside a card: a card's words are 196 points
    /// wide with room for three short lines, and this is a sentence.
    static let paidPlan = "The Code tab in Claude's app needs a paid Claude plan."

    /// Only where the owner is being sent to the Code tab. An owner of ChatGPT
    /// alone never opens Claude, and telling them about a plan they do not need
    /// would be one more thing to read for nothing.
    static func planNote(for assistant: Assistant) -> String? {
        switch assistant {
        case .claude, .both: return paidPlan
        case .chatgpt: return nil
        }
    }

    static func spoken(for assistant: Assistant, wiki: String) -> String {
        switch assistant {
        case .claude:
            return "Last step. In Claude: one, click Code at the top. Two, pick your wiki, called \(wiki). "
                + "Three, say: \(Flow.openingWords). " + paidPlan
        case .chatgpt:
            return "Last step. In ChatGPT: one, open the File menu, choose Open Folder and pick your wiki folder, called \(wiki). "
                + "Two, choose Work at the top of the window, not Chat. "
                + "Three, say: \(Flow.openingWords)."
        case .both:
            return "Last step. With Claude: click Code at the top, then pick your wiki, called \(wiki). "
                + "With ChatGPT: in the File menu choose Open Folder, pick your wiki folder, and choose Work at the top. "
                + "In either, say: \(Flow.openingWords). " + paidPlan
        }
    }

    /// One of the three pictures: its symbol and the words under it.
    struct Card: Equatable { let symbol, title, detail: String }

    /// (v0.9.4) The mark between a folder and the folder inside it is a letter
    /// in an English line, so it is the same mark on a mirrored screen: a line
    /// keeps the direction of its own words. See `Layout.intoAFolder`. The
    /// symbol for Claude's Code tab is `</>`, two characters of a keyboard, and
    /// so is one of the few symbols that must NOT turn round; it does not.
    static func cards(for assistant: Assistant, wiki: String) -> [Card] {
        let say = Card(symbol: "text.bubble.fill", title: "Say", detail: "“\(Flow.openingWords)”")
        let into = Layout.intoAFolder
        switch assistant {
        case .claude:
            return [Card(symbol: "chevron.left.forwardslash.chevron.right",
                         title: "Click Code", detail: "at the top of Claude"),
                    Card(symbol: "folder.fill", title: "Pick your wiki", detail: "Wiki \(into) \(wiki)"),
                    say]
        case .chatgpt:
            return [Card(symbol: "folder.fill",
                         title: "Open your wiki folder", detail: "File menu, Open Folder, then Wiki \(into) \(wiki)"),
                    Card(symbol: "switch.2", title: "Choose Work", detail: "at the top of the window, not Chat"),
                    say]
        case .both:
            return [Card(symbol: Assistant.claude.symbol,
                         title: "With Claude", detail: "Click Code at the top, then pick your wiki"),
                    Card(symbol: Assistant.chatgpt.symbol,
                         title: "With ChatGPT",
                         detail: "File menu, Open Folder, pick your wiki folder, and choose Work at the top"),
                    say]
        }
    }

    private var buttonTitle: String {
        if showingReceipt { return "Back" }
        if opened { return "Finish" }
        return assistant == .chatgpt ? "Open ChatGPT" : "Open Claude"
    }

    /// The second large button: with both assistants, the one not opened yet.
    private var secondTitle: String? {
        guard assistant == .both, !showingReceipt else { return nil }
        if !opened { return "Open ChatGPT" }
        if !openedApps.contains(.chatgpt) { return "Open ChatGPT" }
        if !openedApps.contains(.claude) { return "Open Claude" }
        return nil
    }

    var body: some View {
        ScreenFrame(
            sentence: sentence,
            buttonTitle: buttonTitle,
            showsBack: false,
            quietTitle: showingReceipt ? "Show the folder" : "What did Moblee make?",
            quietAction: {
                if showingReceipt, let p = install.vaultPath, !flow.isTestMode {
                    NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: p)])
                } else {
                    withAnimation(.easeInOut(duration: 0.25)) { showingReceipt = true }
                }
            },
            secondTitle: secondTitle,
            secondAction: { open(secondTitle == "Open Claude" ? .claude : .chatgpt) },
            spoken: spoken,
            speech: headline,
            action: act
        ) {
            if showingReceipt {
                HStack(alignment: .top, spacing: Theme.pt(18)) {
                    HandoffCard(number: 1, symbol: "folder.fill", title: "Your wiki",
                                detail: "“\(wikiOnItsOwn)”, inside “Wiki” in your home folder",
                                ownWords: wikiFolderName)
                    HandoffCard(number: 2, symbol: "lock.shield.fill", title: "The guard and skills",
                                detail: receiptDetail)
                    HandoffCard(number: 3, symbol: "doc.text.fill", title: "A diary of the install",
                                detail: "No names in it. Safe to send if you ever need help.")
                }
                .padding(.horizontal, Theme.pt(30))
            } else {
                VStack(spacing: Theme.pt(8)) {
                    HStack(alignment: .top, spacing: Theme.pt(18)) {
                        ForEach(Array(Self.cards(for: assistant, wiki: wikiOnItsOwn).enumerated()), id: \.offset) { i, card in
                            // (v0.9.5) The wiki folder's name is the owner's own
                            // and may be in their own script, so the card that
                            // carries it reads it in a voice chosen for it. The
                            // other two carry nothing of the owner's; naming the
                            // folder for all three is harmless, since a card
                            // whose words do not hold it is read in one voice.
                            HandoffCard(number: i + 1, symbol: card.symbol, title: card.title,
                                        detail: card.detail, ownWords: wikiFolderName)
                        }
                    }
                    if let note = Self.planNote(for: assistant) {
                        HStack(spacing: Theme.pt(8)) {
                            Text(note)
                                .font(Theme.font(13, .medium))
                                .foregroundStyle(Color.primary.opacity(0.8))
                                .multilineTextAlignment(.center)
                                .fixedSize(horizontal: false, vertical: true)
                            // (v0.9.5) A sentence of its own, under the cards, so
                            // it has a listen control of its own. An owner on the
                            // free plan who cannot read it is the very owner who
                            // will click Code and find nothing there.
                            ListenButton(id: "listen-plan", speech: Speech(note),
                                         what: "the line about plans", size: 14)
                        }
                    }
                }
                .padding(.horizontal, Theme.pt(30))
            }
        }
    }

    private var receiptDetail: String {
        switch assistant {
        case .claude: return "In Claude's own settings folder. Copies of anything replaced are kept."
        case .chatgpt: return "In ChatGPT's own settings folders. Copies of anything replaced are kept."
        case .both: return "In each assistant's own settings folders. Copies of anything replaced are kept."
        }
    }

    private func act() {
        if showingReceipt {
            withAnimation(.easeInOut(duration: 0.25)) { showingReceipt = false }
            return
        }
        if opened {
            NSApplication.shared.terminate(nil)
            return
        }
        open(assistant == .chatgpt ? .chatgpt : .claude)
    }

    /// The opening words go on the clipboard, then the app is opened. A
    /// practice run opens nothing.
    private func open(_ which: Assistant) {
        let board = NSPasteboard.general
        board.clearContents()
        board.setString(Flow.openingWords, forType: .string)
        if which == .chatgpt {
            ChatGPTApp.open(folder: install.vaultPath, practice: flow.isTestMode)
        } else if !flow.isTestMode,
           let url = NSWorkspace.shared.urlForApplication(withBundleIdentifier: "com.anthropic.claudefordesktop") {
            NSWorkspace.shared.openApplication(at: url, configuration: NSWorkspace.OpenConfiguration())
        }
        openedApps.insert(which)
        withAnimation(.easeInOut(duration: 0.3)) { opened = true }
    }
}

/// One numbered card. The cards in a row line up from the top, whatever the
/// length of their words, and each is read out as one thing.
struct HandoffCard: View {
    let number: Int
    let symbol: String
    let title: String
    let detail: String
    /// Three cards abreast are 196 wide. One card on its own (the Terminal
    /// explanation, which shows them one at a time) is given more room, so
    /// that its words are on fewer, longer lines. (v0.9.4)
    var width: CGFloat = 196
    /// (v0.9.5) The owner's own words inside this card, where there are any: the
    /// wiki folder's name, on the cards that send an owner to find it. Named so
    /// that the card can read its own words in two voices — Moblee's for the
    /// instruction, one chosen for the name itself.
    var ownWords: String? = nil

    @ObservedObject private var textSize = TextSize.shared

    /// (v0.9.5) What this card's listen control reads: the card's own title and
    /// detail, cut where the owner's words begin. Static, so that a check can
    /// ask it of a real card rather than of a second copy of its words.
    static func speech(title: String, detail: String, ownWords: String?) -> Speech {
        let whole = title + ". " + detail
        guard let ownWords else { return Speech(whole) }
        return Speech.sentence(whole, theirs: ownWords)
    }

    /// The name the keyboard ring is recorded under and the walk finds it by.
    /// Three cards abreast are numbered 1, 2, 3, so the number tells them apart.
    static func listenId(number: Int) -> String { "listen-card-\(number)" }

    var body: some View {
        VStack(spacing: Theme.pt(10)) {
            Text("\(number)")
                .font(Theme.font(17, .bold))
                .foregroundStyle(.white)
                .frame(width: Theme.pt(32), height: Theme.pt(32))
                .background(Circle().fill(Theme.accent))
            Image(systemName: symbol)
                .font(Theme.font(40, .medium, .default))
                .foregroundStyle(Theme.accent)
                .frame(height: Theme.pt(60))
            Text(title)
                .font(Theme.font(18, .semibold))
                .multilineTextAlignment(.center)
                .lineLimit(2).minimumScaleFactor(0.85)
            Text(detail)
                .font(Theme.font(14, .medium))
                .foregroundStyle(Color.primary.opacity(0.8))
                .multilineTextAlignment(.center)
                .lineLimit(3)
                .minimumScaleFactor(0.85)
            Spacer(minLength: Theme.pt(0))
        }
        .padding(.horizontal, Theme.pt(12)).padding(.top, Theme.pt(18)).padding(.bottom, Theme.pt(10))
        .frame(width: Theme.pt(width), height: Theme.pt(236), alignment: .top)
        // The card's own words are one thing to a screen reader, and the listen
        // control beside them is a second: said in this order so that the
        // control is a button of its own and not swallowed by the card. (v0.9.5)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Step \(number). \(title). \(detail)")
        .background(CardBackground())
        // (v0.9.5) In the corner the card's own words never reach: the number
        // sits in the middle of the top, the symbol under it, and the words
        // under that. An overlay takes no room in the layout, so nothing on the
        // card moves and nothing can be pushed off the window at the biggest
        // text size, in either direction.
        .overlay(alignment: .topTrailing) {
            ListenButton(id: Self.listenId(number: number),
                         speech: Self.speech(title: title, detail: detail, ownWords: ownWords),
                         what: title)
                .padding(Theme.pt(8))
        }
    }
}
