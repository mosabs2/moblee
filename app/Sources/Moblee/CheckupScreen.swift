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
        let args = CommandLine.arguments
        guard let i = args.firstIndex(of: "--pretend-missing"), i + 1 < args.count else { return [] }
        return Set(args[i + 1].split(separator: ",").map(String.init))
    }()

    private var timer: Timer?

    init() { look() }

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
        for need in needs {
            let found: Bool
            switch need.kind {
            case .developerTools:
                found = !pretendMissing.contains("tools") && Self.developerToolsInstalled()
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

    static func developerToolsInstalled() -> Bool {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/usr/bin/xcode-select")
        p.arguments = ["-p"]
        p.standardOutput = Pipe()
        p.standardError = Pipe()
        do { try p.run() } catch { return false }
        p.waitUntilExit()
        return p.terminationStatus == 0
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
                : "Your Mac needs these first. Tap Get.",
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

    @State private var spin = false

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
            Text(need.name)
                .font(.system(size: 17, weight: .semibold, design: .rounded))
            Group {
                if present == true {
                    Text("Here").foregroundStyle(Theme.good)
                } else if asked {
                    Text("Waiting…").foregroundStyle(Theme.waiting)
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
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .frame(width: 170, height: 236)
        .background(
            RoundedRectangle(cornerRadius: 22, style: .continuous)
                .fill(Color(nsColor: .controlBackgroundColor))
                .shadow(color: .black.opacity(0.10), radius: 10, y: 4))
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
                .rotationEffect(.degrees(spin ? 360 : 0))
                .onAppear {
                    withAnimation(.linear(duration: 1.6).repeatForever(autoreverses: false)) {
                        spin = true
                    }
                }
        } else if present == false {
            Image(systemName: "arrow.down.circle.fill")
                .font(.system(size: 30))
                .foregroundStyle(.white, Theme.accent)
        }
    }
}
