import SwiftUI
import AppKit

/// The last screen: into Claude, at the new wiki, with the opening words ready.
/// Claude's app cannot be opened at a folder from outside, so the three clicks
/// are shown as pictures and the words are put on the clipboard.
struct HandoffScreen: View {
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

    /// The words of the hand-off, kept where the logic check can read them.
    ///
    /// In ChatGPT the wiki is opened by the File menu's Open Folder, and by no
    /// other way: an owner once sent to open it from inside a project that was
    /// rooted elsewhere ended with the wiki as an outside folder, and every
    /// write to it then needed their approval (a real install, 21 September 2026).
    static func sentence(for assistant: Assistant, opened: Bool) -> String {
        switch assistant {
        case .claude:
            return opened ? "The words are copied. Paste them to Claude." : "Last step. Do these three in Claude."
        case .chatgpt:
            return opened ? "The words are copied. Paste them to ChatGPT."
                          : "Last step. In ChatGPT's File menu choose Open Folder, pick your wiki folder, then say the words."
        case .both:
            return opened ? "The words are copied. Paste them to your assistant."
                          : "Last step. Open your wiki in either assistant, then say the words."
        }
    }

    static func spoken(for assistant: Assistant, wiki: String) -> String {
        switch assistant {
        case .claude:
            return "Last step. In Claude: one, click Code at the top. Two, pick your wiki, called \(wiki). "
                + "Three, say: \(Flow.openingWords)."
        case .chatgpt:
            return "Last step. In ChatGPT: one, open the File menu and choose Open Folder. "
                + "Two, pick your wiki folder, called \(wiki). "
                + "Three, say: \(Flow.openingWords)."
        case .both:
            return "Last step. With Claude: click Code at the top, then pick your wiki, called \(wiki). "
                + "With ChatGPT: in the File menu choose Open Folder, then pick your wiki folder. "
                + "In either, say: \(Flow.openingWords)."
        }
    }

    /// One of the three pictures: its symbol and the words under it.
    struct Card: Equatable { let symbol, title, detail: String }

    static func cards(for assistant: Assistant, wiki: String) -> [Card] {
        let say = Card(symbol: "text.bubble.fill", title: "Say", detail: "“\(Flow.openingWords)”")
        switch assistant {
        case .claude:
            return [Card(symbol: "chevron.left.forwardslash.chevron.right",
                         title: "Click Code", detail: "at the top of Claude"),
                    Card(symbol: "folder.fill", title: "Pick your wiki", detail: "Wiki ▸ \(wiki)"),
                    say]
        case .chatgpt:
            return [Card(symbol: "filemenu.and.selection",
                         title: "File menu, Open Folder", detail: "at the top of your screen"),
                    Card(symbol: "folder.fill", title: "Pick your wiki folder", detail: "Wiki ▸ \(wiki)"),
                    say]
        case .both:
            return [Card(symbol: Assistant.claude.symbol,
                         title: "With Claude", detail: "Click Code at the top, then pick your wiki"),
                    Card(symbol: Assistant.chatgpt.symbol,
                         title: "With ChatGPT", detail: "In the File menu choose Open Folder, then pick your wiki folder"),
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
            action: act
        ) {
            if showingReceipt {
                HStack(alignment: .top, spacing: 18) {
                    HandoffCard(number: 1, symbol: "folder.fill", title: "Your wiki",
                                detail: "“\(wikiFolderName)”, inside “Wiki” in your home folder")
                    HandoffCard(number: 2, symbol: "lock.shield.fill", title: "The guard and skills",
                                detail: receiptDetail)
                    HandoffCard(number: 3, symbol: "doc.text.fill", title: "A diary of the install",
                                detail: "No names in it. Safe to send if you ever need help.")
                }
                .padding(.horizontal, 30)
            } else {
                HStack(alignment: .top, spacing: 18) {
                    ForEach(Array(Self.cards(for: assistant, wiki: wikiFolderName).enumerated()), id: \.offset) { i, card in
                        HandoffCard(number: i + 1, symbol: card.symbol, title: card.title, detail: card.detail)
                    }
                }
                .padding(.horizontal, 30)
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

    var body: some View {
        VStack(spacing: 10) {
            Text("\(number)")
                .font(.system(size: 17, weight: .bold, design: .rounded))
                .foregroundStyle(.white)
                .frame(width: 32, height: 32)
                .background(Circle().fill(Theme.accent))
            Image(systemName: symbol)
                .font(.system(size: 40, weight: .medium))
                .foregroundStyle(Theme.accent)
                .frame(height: 60)
            Text(title)
                .font(.system(size: 18, weight: .semibold, design: .rounded))
                .multilineTextAlignment(.center)
                .lineLimit(2).minimumScaleFactor(0.85)
            Text(detail)
                .font(.system(size: 14, weight: .medium, design: .rounded))
                .foregroundStyle(Color.primary.opacity(0.8))
                .multilineTextAlignment(.center)
                .lineLimit(3)
                .minimumScaleFactor(0.85)
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 12).padding(.top, 18).padding(.bottom, 10)
        .frame(width: 196, height: 236, alignment: .top)
        .background(CardBackground())
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Step \(number). \(title). \(detail)")
    }
}
