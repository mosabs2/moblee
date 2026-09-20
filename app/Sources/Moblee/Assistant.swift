import SwiftUI
import AppKit

/// Which assistant the wiki is for. The pack's scripts keep the choice as one
/// word in `~/.config/moblee/assistant`; a Mac with no such file was set up
/// before the question existed, and the scripts then take it to mean Claude.
enum Assistant: String, CaseIterable, Identifiable {
    case claude, chatgpt, both

    var id: String { rawValue }

    /// As the owner reads it.
    var name: String {
        switch self {
        case .claude: return "Claude"
        case .chatgpt: return "ChatGPT"
        case .both: return "Both"
        }
    }

    var symbol: String {
        switch self {
        case .claude: return "sparkles"
        case .chatgpt: return "ellipsis.bubble.fill"
        case .both: return "bubble.left.and.bubble.right.fill"
        }
    }

    var wantsClaude: Bool { self != .chatgpt }
    var wantsChatGPT: Bool { self != .claude }

    /// The one to name where a sentence sends the owner to talk to somebody.
    /// An owner with both is sent to Claude, as the sentences always have.
    var talksTo: String { self == .chatgpt ? "ChatGPT" : "Claude" }

    static func file(home: URL) -> URL { home.appendingPathComponent(".config/moblee/assistant") }

    /// The choice on record, or nil when there is none: no file, or a file
    /// whose first line is not a word the installer and the updater know.
    /// Read as they read it (the first line, spaces dropped, small letters
    /// only), so that the app never takes as settled a word they would not.
    static func stored(home: URL) -> Assistant? {
        guard let text = try? String(contentsOf: file(home: home), encoding: .utf8) else { return nil }
        let word = (text.split(separator: "\n", omittingEmptySubsequences: false).first.map(String.init) ?? "")
            .filter { !$0.isWhitespace }
        return Assistant(rawValue: word)
    }

    /// What the scripts will take the choice to be.
    static func onRecord(home: URL) -> Assistant { stored(home: home) ?? .claude }

    /// An update asks the question first only when no choice is on record.
    static func mustAsk(home: URL) -> Bool { stored(home: home) == nil }

    /// What is added to the updater's command line: the option when the owner
    /// has just answered the question, and nothing at all otherwise, so that a
    /// choice already on record is never restated or changed by the app.
    static func updateOption(answered: Assistant?) -> [String] {
        guard let answered else { return [] }
        return ["--assistant", answered.rawValue]
    }
}

/// Opening ChatGPT at the wiki's folder.
enum ChatGPTApp {
    static let path = "/Applications/ChatGPT.app"
    static let bundleID = "com.openai.codex"

    static var location: URL? {
        if FileManager.default.fileExists(atPath: path) { return URL(fileURLWithPath: path, isDirectory: true) }
        return NSWorkspace.shared.urlForApplication(withBundleIdentifier: bundleID)
    }

    static var installed: Bool { location != nil }

    /// `codex://new?path=<absolute path>`, the link OpenAI documents for
    /// opening a folder from outside. Everything in the path but letters,
    /// digits, `-._~` and `/` is percent-encoded. Nil for a path that is not
    /// absolute, which the link does not take.
    static func link(toFolder folder: String) -> URL? {
        guard folder.hasPrefix("/") else { return nil }
        // ASCII letters and digits only: an accented letter is encoded too.
        let allowed = CharacterSet(charactersIn:
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~/")
        guard let encoded = folder.addingPercentEncoding(withAllowedCharacters: allowed) else { return nil }
        return URL(string: "codex://new?path=" + encoded)
    }

    /// Tries the link first. If nothing on the Mac takes it, or it fails to
    /// open, the ChatGPT app is simply opened, and the owner follows the steps
    /// on the screen, which are true either way. A practice run opens nothing.
    @MainActor
    static func open(folder: String?, practice: Bool) {
        guard !practice else { return }
        if let folder, let url = link(toFolder: folder),
           NSWorkspace.shared.urlForApplication(toOpen: url) != nil {
            NSWorkspace.shared.open(url, configuration: NSWorkspace.OpenConfiguration()) { _, error in
                if error != nil { DispatchQueue.main.async { MainActor.assumeIsolated { openApp() } } }
            }
        } else {
            openApp()
        }
    }

    @MainActor
    static func openApp() {
        guard let app = location else { return }
        NSWorkspace.shared.openApplication(at: app, configuration: NSWorkspace.OpenConfiguration())
    }
}

/// "Which assistant do you use?" Three large choices, one tap, then the big
/// button. Nothing is chosen for the owner beforehand. Asked once in the
/// install, after the name; asked before an update on a Mac that has no choice
/// on record; and asked again whenever the owner presses Change at home.
///
/// If the chosen assistant's app is not on the Mac, the same screen shows it
/// with a Get button, as the check-up does, before going on.
struct AssistantScreen: View {
    enum Purpose { case install, update }
    let purpose: Purpose

    @EnvironmentObject var flow: Flow
    @StateObject private var checkup = Checkup()
    @State private var showingNeeds = false

    private var choice: Assistant? { purpose == .install ? flow.assistant : flow.updateAssistant }

    var body: some View {
        ScreenFrame(
            sentence: sentence,
            buttonTitle: "Next",
            buttonEnabled: showingNeeds ? checkup.readyToGoOn : choice != nil,
            showsBack: purpose == .install && !showingNeeds,
            quietTitle: quietTitle,
            quietAction: quietAction,
            spoken: showingNeeds ? nil : "Which assistant do you use? Claude, ChatGPT, or both.",
            action: act
        ) {
            if showingNeeds {
                HStack(spacing: 22) {
                    ForEach(checkup.needs) { need in
                        NeedTile(need: need, present: checkup.present[need.name],
                                 asked: checkup.asked.contains(need.name), fix: { checkup.fix(need) })
                    }
                }
                .padding(.horizontal, 40)
            } else {
                HStack(spacing: 22) {
                    ForEach(Assistant.allCases) { a in
                        AssistantChoice(assistant: a, chosen: choice == a) { choose(a) }
                    }
                }
                .padding(.horizontal, 40)
            }
        }
        .onDisappear { checkup.stop() }
    }

    private var sentence: String {
        guard showingNeeds else { return "Which assistant do you use?" }
        if !checkup.asked.isEmpty && !checkup.readyToGoOn { return "Install it from the page that opened, then come back here." }
        if checkup.readyToGoOn { return "Your Mac is ready." }
        return checkup.needs.count == 1 ? "Your Mac needs this first. Tap Get." : "Your Mac needs these first. Tap Get."
    }

    private var quietTitle: String? {
        if showingNeeds { return "Choose again" }
        return purpose == .update ? "Not now" : nil
    }

    private var quietAction: (() -> Void)? {
        if showingNeeds { return { checkup.stop(); withAnimation(.easeInOut(duration: 0.25)) { showingNeeds = false } } }
        return purpose == .update ? { flow.cancelUpdateQuestion() } : nil
    }

    private func choose(_ a: Assistant) {
        withAnimation(.easeOut(duration: 0.15)) {
            if purpose == .install { flow.assistant = a } else { flow.updateAssistant = a }
        }
    }

    private func act() {
        guard let choice else { return }
        if !showingNeeds {
            let missing = checkup.missing(choice.appKinds)
            if !missing.isEmpty {
                checkup.kinds = missing
                checkup.start()
                withAnimation(.easeInOut(duration: 0.25)) { showingNeeds = true }
                return
            }
        }
        checkup.stop()
        if purpose == .install { flow.next() } else { flow.updateQuestionAnswered() }
    }
}

extension Assistant {
    /// The apps this choice needs on the Mac.
    var appKinds: [Need.Kind] {
        switch self {
        case .claude: return [.claude]
        case .chatgpt: return [.chatgpt]
        case .both: return [.claude, .chatgpt]
        }
    }
}

/// One of the three large choices.
struct AssistantChoice: View {
    let assistant: Assistant
    let chosen: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(spacing: 14) {
                ZStack(alignment: .bottomTrailing) {
                    Image(systemName: assistant.symbol)
                        .font(.system(size: 46, weight: .medium))
                        .foregroundStyle(Theme.accent)
                        .frame(width: 96, height: 96)
                    if chosen {
                        Image(systemName: "checkmark.circle.fill")
                            .font(.system(size: 30))
                            .foregroundStyle(.white, Theme.accent)
                            .offset(x: 6, y: 6)
                            .transition(.scale.combined(with: .opacity))
                    }
                }
                .accessibilityHidden(true)
                Text(assistant.name)
                    .font(.system(size: 20, weight: .semibold, design: .rounded))
                    .foregroundStyle(.primary)
            }
            .frame(width: 170, height: 236)
            .background(CardBackground())
            .overlay(RoundedRectangle(cornerRadius: 22, style: .continuous)
                .stroke(Theme.accent, lineWidth: chosen ? 3 : 0))
            .contentShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
        }
        .buttonStyle(.plain)
        .accessibilityLabel(assistant.name)
        .accessibilityAddTraits(chosen ? [.isSelected] : [])
        .accessibilityIdentifier("assistant-" + assistant.rawValue)
    }
}
