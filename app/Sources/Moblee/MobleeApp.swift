import SwiftUI

@main
struct MobleeApp: App {
    @StateObject private var flow = Flow()

    init() {
        MainActor.assumeIsolated { Snapshots.runIfAsked() }
    }

    var body: some Scene {
        WindowGroup("Moblee") {
            RootView()
                .environmentObject(flow)
                .environmentObject(flow.install)
                .frame(width: 720, height: 520)
        }
        .windowResizability(.contentSize)
        .windowStyle(.hiddenTitleBar)
    }
}

/// The screens, in the order the owner meets them.
enum Step: Int, CaseIterable {
    case welcome
    case checkup
    case name
    case build
    case handoff
}

/// Where the owner is, what they have answered, and the settings a run was
/// started with.
@MainActor
final class Flow: ObservableObject {
    /// A Mac with no wiki yet gets the install; a Mac that has one gets the
    /// home screen (what is waiting to be added, an update, a repair).
    enum Mode { case install, home, update }

    @Published var mode: Mode = .install
    @Published var step: Step = .welcome
    @Published var ownerName: String = ""
    let install = InstallRun()
    let homeModel = HomeModel()

    /// Practice run: `--home <folder>` (or MOBLEE_TEST_HOME) makes the whole run
    /// treat that folder as the home folder, so an install can be rehearsed
    /// without touching the real one.
    let home: URL
    let isTestMode: Bool

    /// The words that start the first conversation in Claude.
    static let openingWords = "get me started"

    init() {
        let args = CommandLine.arguments
        var chosen: String? = ProcessInfo.processInfo.environment["MOBLEE_TEST_HOME"]
        if let v = Self.value(after: "--home", in: args) { chosen = v }
        if let chosen, !chosen.isEmpty {
            home = URL(fileURLWithPath: chosen, isDirectory: true)
            isTestMode = true
        } else {
            home = FileManager.default.homeDirectoryForCurrentUser
            isTestMode = false
        }
        if let v = Self.value(after: "--step", in: args), let n = Int(v), let s = Step(rawValue: n) {
            step = s
        }
        if let v = Self.value(after: "--owner", in: args) { ownerName = v }
        if HomeModel.existingVault(home: home) != nil && !args.contains("--fresh") {
            mode = .home
            homeModel.load(home: home, bundledPack: bundledPack)
        }
    }

    static func value(after flag: String, in args: [String]) -> String? {
        guard let i = args.firstIndex(of: flag), i + 1 < args.count else { return nil }
        return args[i + 1]
    }

    /// The pack inside the app, or `--pack <folder>` while developing.
    var bundledPack: URL? {
        if let v = Self.value(after: "--pack", in: CommandLine.arguments) {
            return URL(fileURLWithPath: v, isDirectory: true)
        }
        guard let r = Bundle.main.resourceURL?.appendingPathComponent("pack", isDirectory: true),
              FileManager.default.fileExists(atPath: r.appendingPathComponent("scripts/install.sh").path)
        else { return nil }
        return r
    }

    var trimmedName: String { ownerName.trimmingCharacters(in: .whitespacesAndNewlines) }

    /// One question only: the wiki is named after its owner, and lives in a
    /// "Wiki" folder in the home folder. A name already taken gets a number.
    var wikiName: String {
        let first = trimmedName.split(separator: " ").first.map(String.init) ?? "My"
        let safe = first.filter { $0.isLetter || $0.isNumber }
        return (safe.isEmpty ? "My" : safe) + " Wiki"
    }

    func freeLocation() -> (name: String, url: URL) {
        let root = home.appendingPathComponent("Wiki", isDirectory: true)
        var n = 1
        while true {
            let name = n == 1 ? wikiName : "\(wikiName) \(n)"
            let url = root.appendingPathComponent(name, isDirectory: true)
            if !FileManager.default.fileExists(atPath: url.path) { return (name, url) }
            n += 1
        }
    }

    func next() {
        if let s = Step(rawValue: step.rawValue + 1) {
            withAnimation(.easeInOut(duration: 0.35)) { step = s }
        }
    }

    func back() {
        if let s = Step(rawValue: step.rawValue - 1) {
            withAnimation(.easeInOut(duration: 0.35)) { step = s }
        }
    }
}

struct RootView: View {
    @EnvironmentObject var flow: Flow

    var body: some View {
        ZStack(alignment: .top) {
            Theme.background.ignoresSafeArea()

            Group {
                switch flow.mode {
                case .home: HomeScreen()
                case .update: UpdateScreen()
                case .install:
                    switch flow.step {
                    case .welcome: WelcomeScreen()
                    case .checkup: CheckupScreen()
                    case .name: NameScreen()
                    case .build: BuildScreen()
                    case .handoff: HandoffScreen()
                    }
                }
            }
            .environmentObject(flow.homeModel)
            .transition(.asymmetric(
                insertion: .move(edge: .trailing).combined(with: .opacity),
                removal: .move(edge: .leading).combined(with: .opacity)))

            if flow.isTestMode {
                Text(SelfDrive.asked ? "Practice run, driving itself" : "Practice run")
                    .font(.caption.weight(.semibold))
                    .padding(.horizontal, 10).padding(.vertical, 4)
                    .background(.orange.opacity(0.85), in: Capsule())
                    .foregroundStyle(.white)
                    .padding(.top, 10)
            }
        }
        .task {
            if SelfDrive.asked { await SelfDrive.run(flow) }
        }
    }
}
