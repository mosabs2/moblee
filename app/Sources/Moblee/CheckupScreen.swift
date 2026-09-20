import SwiftUI
import AppKit

/// One thing the Mac needs before the wiki can be built.
struct Need: Identifiable {
    enum Kind { case developerTools, claude, obsidian }
    let kind: Kind
    let symbol: String
    let name: String
    let fixTitle: String
    let optional: Bool
    var id: String { name }
}

@MainActor
final class Checkup: ObservableObject {
    @Published var present: [String: Bool] = [:]
    @Published var asked: Set<String> = []

    let needs: [Need] = [
        Need(kind: .developerTools, symbol: "wrench.and.screwdriver.fill",
             name: "Apple's tools", fixTitle: "Get", optional: false),
        Need(kind: .claude, symbol: "sparkles",
             name: "Claude", fixTitle: "Get", optional: false),
        Need(kind: .obsidian, symbol: "books.vertical.fill",
             name: "Obsidian", fixTitle: "Get", optional: true),
    ]

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
        if let known = Self.knownBeforeDrawing {
            toolsInstalled = known
            apply()
        }
    }

    var readyToGoOn: Bool {
        needs.filter { !$0.optional }.allSatisfy { present[$0.name] == true }
    }

    func start() {
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
            let found: Bool
            switch need.kind {
            case .developerTools:
                found = !pretendMissing.contains("tools") && toolsInstalled
            case .claude:
                found = !pretendMissing.contains("claude")
                    && Self.appInstalled("com.anthropic.claudefordesktop")
            case .obsidian:
                found = !pretendMissing.contains("obsidian") && Self.appInstalled("md.obsidian")
            }
            if present[need.name] != found {
                withAnimation(.spring(response: 0.4, dampingFraction: 0.7)) {
                    present[need.name] = found
                }
            }
        }
    }

    func fix(_ need: Need) {
        asked.insert(need.name)
        askedAt[need.name] = Date()
        switch need.kind {
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
    @EnvironmentObject var flow: Flow
    @StateObject private var checkup = Checkup()

    var body: some View {
        ScreenFrame(
            sentence: checkup.readyToGoOn
                ? "Your Mac is ready."
                : (checkup.asked.isEmpty
                   ? "Your Mac needs these first. Tap Get."
                   : "Say yes in the window that opened. It takes a few minutes."),
            buttonTitle: "Next",
            buttonEnabled: checkup.readyToGoOn,
            action: flow.next
        ) {
            HStack(spacing: 22) {
                ForEach(checkup.needs) { need in
                    NeedTile(need: need,
                             present: checkup.present[need.name],
                             asked: checkup.asked.contains(need.name),
                             fix: { checkup.fix(need) })
                }
            }
            .padding(.horizontal, 40)
        }
        .onAppear { checkup.start() }
        .onDisappear { checkup.stop() }
    }
}

struct NeedTile: View {
    let need: Need
    let present: Bool?
    let asked: Bool
    let fix: () -> Void

    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        VStack(spacing: 12) {
            ZStack(alignment: .bottomTrailing) {
                Image(systemName: need.symbol)
                    .font(.system(size: 46, weight: .medium))
                    .foregroundStyle(present == true ? Theme.good : Theme.accent)
                    .frame(width: 96, height: 96)
                badge
                    .offset(x: 6, y: 6)
            }
            .accessibilityHidden(true)
            Text(need.name)
                .font(.system(size: 17, weight: .semibold, design: .rounded))
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
                }
            }
            .font(.system(size: 15, weight: .semibold, design: .rounded))
            .frame(height: 32)
            Text(need.optional ? "Can wait" : " ")
                .font(.system(size: 13, weight: .medium, design: .rounded))
                .foregroundStyle(.secondary)
        }
        .frame(width: 170, height: 236)
        .background(CardBackground())
        .accessibilityElement(children: .contain)
        .accessibilityLabel(need.name + (need.optional ? ", can wait" : ""))
        .accessibilityValue(present == true ? "here" : (asked ? "downloading" : "missing"))
    }

    @ViewBuilder private var badge: some View {
        if present == true {
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 30))
                .foregroundStyle(.white, Theme.good)
                .transition(.scale.combined(with: .opacity))
        } else if asked {
            Image(systemName: "arrow.triangle.2.circlepath.circle.fill")
                .font(.system(size: 30))
                .foregroundStyle(.white, Theme.waiting)
                .symbolEffect(.pulse, options: .repeating, isActive: !reduceMotion)
        } else if present == false {
            Image(systemName: "arrow.down.circle.fill")
                .font(.system(size: 30))
                .foregroundStyle(.white, Theme.accent)
        }
    }
}
