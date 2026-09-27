import SwiftUI
import AppKit

/// One thing the Mac needs before the wiki can be built.
struct Need: Identifiable {
    enum Kind { case developerTools, claude, chatgpt, obsidian }
    let kind: Kind
    let symbol: String
    let name: String
    let fixTitle: String
    let optional: Bool
    var id: String { name }

    /// (v0.9.4) What this need's Get button is called: the name the keyboard
    /// ring is recorded under, and the name the self-drive walk finds it by.
    /// Written out rather than made from the name, because the name is words an
    /// owner reads and may be changed.
    var getId: String {
        switch kind {
        case .developerTools: return "get-apple-tools"
        case .claude: return "get-claude"
        case .chatgpt: return "get-chatgpt"
        case .obsidian: return "get-obsidian"
        }
    }
}

@MainActor
final class Checkup: ObservableObject {
    @Published var present: [String: Bool] = [:]
    @Published var asked: Set<String> = []

    /// What this screen is looking for. The check-up before the install looks
    /// for the first three, as it always has; an owner who says there that
    /// they use ChatGPT gets ChatGPT's app in Claude's place; and the question
    /// of which assistant looks only for the chosen assistant's app.
    @Published var kinds: [Need.Kind] = [.developerTools, .claude, .obsidian] {
        didSet { if kinds != oldValue { apply() } }
    }

    var needs: [Need] { kinds.map(Self.need) }

    static func need(_ kind: Need.Kind) -> Need {
        switch kind {
        case .developerTools:
            return Need(kind: .developerTools, symbol: "wrench.and.screwdriver.fill",
                        name: "Apple's tools", fixTitle: "Get", optional: false)
        case .claude:
            return Need(kind: .claude, symbol: "sparkles", name: "Claude", fixTitle: "Get", optional: false)
        case .chatgpt:
            return Need(kind: .chatgpt, symbol: "ellipsis.bubble.fill", name: "ChatGPT", fixTitle: "Get", optional: false)
        case .obsidian:
            return Need(kind: .obsidian, symbol: "books.vertical.fill", name: "Obsidian", fixTitle: "Get", optional: true)
        }
    }

    /// Practice runs can pretend something is missing: `--pretend-missing tools,claude`.
    private let pretendMissing: Set<String> = {
        let args = Practice.args
        guard let i = args.firstIndex(of: "--pretend-missing"), i + 1 < args.count else { return [] }
        return Set(args[i + 1].split(separator: ",").map(String.init))
    }()

    private var timer: Timer?
    private var looking = false

    /// Whether Apple's tools are there, as last found out. Finding out means
    /// running a small program and waiting for it, and waiting on the main
    /// thread while SwiftUI is drawing a screen aborts the app (the crash of
    /// 19 September 2026). So the question is only ever asked in the
    /// background, and the answer is kept here.
    private var toolsInstalled = false

    /// Picture-file drawing has no time to wait for a background answer, so it
    /// finds out once, before any drawing starts, and leaves the answer here.
    static var knownBeforeDrawing: Bool?

    init() {
        // The picture of the older-app case is of a check-up that looks for ChatGPT.
        if Self.pretendOlderChatGPT { kinds = [.developerTools, .chatgpt, .obsidian] }
        if let known = Self.knownBeforeDrawing {
            toolsInstalled = known
            apply()
        }
    }

    var readyToGoOn: Bool {
        needs.filter { !$0.optional }.allSatisfy { present[$0.name] == true }
    }

    func start() {
        timer?.invalidate()
        look()
        timer = Timer.scheduledTimer(withTimeInterval: 3, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.look() }
        }
    }

    func stop() { timer?.invalidate(); timer = nil }

    func look() {
        guard !looking else { return }
        looking = true
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let tools = Checkup.developerToolsInstalled()
            DispatchQueue.main.async {
                MainActor.assumeIsolated {
                    guard let self else { return }
                    self.looking = false
                    self.toolsInstalled = tools
                    self.apply()
                }
            }
        }
    }

    /// When each Get was pressed. If the thing is still missing a while later
    /// (Apple's window was cancelled, there was no internet, the download page
    /// was closed), the Get button comes back, so nobody is left at a dead end.
    private var askedAt: [String: Date] = [:]
    private let patience: TimeInterval = 75

    private func apply() {
        for (name, when) in askedAt where present[name] != true && Date().timeIntervalSince(when) > patience {
            askedAt[name] = nil
            asked.remove(name)
        }
        for need in needs {
            let found = isThere(need.kind)
            if present[need.name] != found {
                withAnimation(.spring(response: 0.4, dampingFraction: 0.7)) {
                    present[need.name] = found
                }
            }
        }
    }

    /// ChatGPT is being looked for, and the ChatGPT app on this Mac is an
    /// older one that has no agent inside it: the screen then says so, since
    /// "ChatGPT is missing" would puzzle an owner who can see it in Applications.
    var chatgptIsOlder: Bool {
        kinds.contains(.chatgpt) && present["ChatGPT"] == false && chatgptState == .older
    }

    /// Picture-file drawing can show the older-app case without one on the Mac.
    static var pretendOlderChatGPT = false

    private var chatgptState: ChatGPTApp.State {
        if Self.pretendOlderChatGPT || pretendMissing.contains("chatgpt-older") { return .older }
        if pretendMissing.contains("chatgpt") { return .missing }
        return ChatGPTApp.state
    }

    private func isThere(_ kind: Need.Kind) -> Bool {
        switch kind {
        case .developerTools:
            return !pretendMissing.contains("tools") && toolsInstalled
        case .claude:
            return !pretendMissing.contains("claude") && Self.appInstalled("com.anthropic.claudefordesktop")
        case .chatgpt:
            return chatgptState == .ready
        case .obsidian:
            return !pretendMissing.contains("obsidian") && Self.appInstalled("md.obsidian")
        }
    }

    /// Which of these apps are not on the Mac, asked at the moment of a tap.
    /// For apps only: whether Apple's tools are there is never asked this way,
    /// because finding that out means waiting for a program.
    func missing(_ apps: [Need.Kind]) -> [Need.Kind] {
        apps.filter { $0 != .developerTools && !isThere($0) }
    }

    func fix(_ need: Need) {
        asked.insert(need.name)
        askedAt[need.name] = Date()
        switch need.kind {
        case .chatgpt:
            NSWorkspace.shared.open(URL(string: "https://chatgpt.com/download")!)
        case .developerTools:
            // Apple's own dialogue does the download; this only asks for it.
            let p = Process()
            p.executableURL = URL(fileURLWithPath: "/usr/bin/xcode-select")
            p.arguments = ["--install"]
            try? p.run()
        case .claude:
            NSWorkspace.shared.open(URL(string: "https://claude.ai/download")!)
        case .obsidian:
            NSWorkspace.shared.open(URL(string: "https://obsidian.md/download")!)
        }
    }

    /// Never call this on the main thread: it waits for a program to finish.
    ///
    /// `xcode-select -p` alone is not enough: after a macOS upgrade it can
    /// still name a tools folder whose programs have gone, and the build would
    /// then stop with no cause given. So the folder it names must really hold
    /// git and python3. The files are looked for directly and never run, since
    /// running the stand-in `/usr/bin/git` on a Mac without the tools pops up
    /// Apple's install window, and this check repeats every few seconds.
    nonisolated static func developerToolsInstalled() -> Bool {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/usr/bin/xcode-select")
        p.arguments = ["-p"]
        let out = Pipe()
        p.standardOutput = out
        p.standardError = Pipe()
        do { try p.run() } catch { return false }
        let data = out.fileHandleForReading.readDataToEndOfFile()
        p.waitUntilExit()
        guard p.terminationStatus == 0,
              let folder = String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines),
              !folder.isEmpty else { return false }
        let fm = FileManager.default
        return fm.isExecutableFile(atPath: folder + "/usr/bin/git")
            && fm.isExecutableFile(atPath: folder + "/usr/bin/python3")
    }

    static func appInstalled(_ bundleID: String) -> Bool {
        NSWorkspace.shared.urlForApplication(withBundleIdentifier: bundleID) != nil
    }
}

struct CheckupScreen: View {
    /// Drawn again when the owner presses "Bigger text". (v0.9.4)
    @ObservedObject private var textSize = TextSize.shared
    @EnvironmentObject var flow: Flow
    @StateObject private var checkup = Checkup()

    var body: some View {
        ScreenFrame(
            sentence: checkup.readyToGoOn
                ? "Your Mac is ready."
                : (checkup.asked.isEmpty
                   ? (checkup.chatgptIsOlder ? ChatGPTApp.olderSentence : "Your Mac needs these first. Tap Get.")
                   : "Say yes in the window that opened. It takes a few minutes."),
            buttonTitle: "Next",
            buttonEnabled: checkup.readyToGoOn,
            quietTitle: quietTitle,
            quietAction: quietTitle == nil ? nil : switchAssistant,
            action: flow.next
        ) {
            HStack(spacing: Theme.pt(22)) {
                ForEach(checkup.needs) { need in
                    NeedTile(need: need,
                             present: checkup.present[need.name],
                             asked: checkup.asked.contains(need.name),
                             fix: { checkup.fix(need) })
                }
            }
            .padding(.horizontal, Theme.pt(40))
        }
        .onAppear {
            if flow.assistant == .chatgpt { checkup.kinds = [.developerTools, .chatgpt, .obsidian] }
            checkup.start()
        }
        .onDisappear { checkup.stop() }
    }

    /// The question of which assistant comes after this screen, and this screen
    /// asks for Claude's app. An owner who uses ChatGPT alone, and has no
    /// Claude, would be stopped here for an app they will never use; so when
    /// Claude is the thing missing, they can say so, and ChatGPT's app is
    /// looked for in its place. The question screen then shows their answer
    /// already chosen.
    private var lookingForChatGPT: Bool { checkup.kinds.contains(.chatgpt) }

    private var quietTitle: String? {
        if lookingForChatGPT { return "I use Claude" }
        return checkup.present["Claude"] == false ? "I use ChatGPT" : nil
    }

    private func switchAssistant() {
        if lookingForChatGPT {
            flow.assistant = .claude
            checkup.kinds = [.developerTools, .claude, .obsidian]
        } else {
            flow.assistant = .chatgpt
            checkup.kinds = [.developerTools, .chatgpt, .obsidian]
        }
    }
}

struct NeedTile: View {
    /// Drawn again when the owner presses "Bigger text". (v0.9.4)
    @ObservedObject private var textSize = TextSize.shared
    let need: Need
    let present: Bool?
    let asked: Bool
    let fix: () -> Void

    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        VStack(spacing: Theme.pt(12)) {
            ZStack(alignment: .bottomTrailing) {
                Image(systemName: need.symbol)
                    .font(Theme.font(46, .medium, .default))
                    .foregroundStyle(present == true ? Theme.good : Theme.accent)
                    .frame(width: Theme.pt(96), height: Theme.pt(96))
                badge
                    .offset(x: 6, y: 6)
            }
            .accessibilityHidden(true)
            Text(need.name)
                .font(Theme.font(17, .semibold))
            Group {
                if present == true {
                    Text("Here").foregroundStyle(Theme.goodText)
                } else if asked {
                    Text("Downloading…").foregroundStyle(Theme.waitingText)
                } else {
                    Button(need.fixTitle, action: fix)
                        .buttonStyle(.borderedProminent)
                        .tint(Theme.accent)
                        .controlSize(.large)
                        // (v0.9.4) macOS only puts an ordinary button like this
                        // in the keyboard's way when Full Keyboard Access has
                        // been switched on, which no owner of Moblee's will
                        // have done. So it takes the keyboard the same way
                        // every other control in the app does.
                        .keyboardReachable(need.getId, corner: 8, press: fix)
                }
            }
            .font(Theme.font(15, .semibold))
            .frame(height: Theme.pt(32))
            Text(need.optional ? "Can wait" : " ")
                .font(Theme.font(13, .medium))
                .foregroundStyle(.secondary)
        }
        .frame(width: Theme.pt(170), height: Theme.pt(236))
        .background(CardBackground())
        .accessibilityElement(children: .contain)
        .accessibilityLabel(need.name + (need.optional ? ", can wait" : ""))
        .accessibilityValue(present == true ? "here" : (asked ? "downloading" : "missing"))
        // (v0.9.5) The check-up's own findings, read aloud one card at a time.
        // This screen is where an owner is stopped until their Mac has three
        // things on it, and the only words saying WHICH of the three is missing
        // are on the cards. In the top corner, as an overlay, so the card is
        // laid out exactly as it was at every text size.
        .overlay(alignment: .topTrailing) {
            ListenButton(id: Self.listenId(need), speech: Self.speech(need, present: present, asked: asked),
                         what: need.name)
                .padding(Theme.pt(8))
        }
    }

    /// The name the keyboard ring is recorded under and the walk finds it by,
    /// beside the Get button's own name. (v0.9.5)
    static func listenId(_ need: Need) -> String { "listen-" + need.getId }

    /// What the card says: what it is, whether it can wait, and where it has got
    /// to. Static, so a check can ask it of a real need. (v0.9.5)
    static func speech(_ need: Need, present: Bool?, asked: Bool) -> Speech {
        let state = present == true ? "Here." : (asked ? "Downloading." : "Not on this Mac yet. Press Get.")
        return Speech(need.name + ". " + (need.optional ? "Can wait. " : "") + state)
    }

    @ViewBuilder private var badge: some View {
        if present == true {
            Image(systemName: "checkmark.circle.fill")
                .font(Theme.font(30, .regular, .default))
                .foregroundStyle(.white, Theme.good)
                .transition(.scale.combined(with: .opacity))
        } else if asked {
            Image(systemName: "arrow.triangle.2.circlepath.circle.fill")
                .font(Theme.font(30, .regular, .default))
                .foregroundStyle(.white, Theme.waiting)
                .symbolEffect(.pulse, options: .repeating, isActive: !reduceMotion)
        } else if present == false {
            Image(systemName: "arrow.down.circle.fill")
                .font(Theme.font(30, .regular, .default))
                .foregroundStyle(.white, Theme.accent)
        }
    }
}
