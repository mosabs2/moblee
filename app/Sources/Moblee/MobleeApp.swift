import SwiftUI

@main
struct MobleeApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var delegate
    @StateObject private var flow = Flow()

    init() {
        MainActor.assumeIsolated {
            // A practice switch without the practice environment is refused
            // before anything at all is looked at or touched.
            if !Practice.on, let used = CommandLine.arguments.first(where: { Practice.switches.contains($0) }) {
                print("\(used) is a practice switch, and this is not a practice run (MOBLEE_PRACTICE=1 is not set); nothing was done.")
                exit(2)
            }
            // The modes that do real work in a practice home refuse to start
            // without one, before anything at all has looked at the real home.
            let args = Practice.args
            let practice = Flow.value(after: "--home", in: args) != nil
            if args.contains("--check-logic") && !practice {
                print("--check-logic only runs with --home <practice folder>; nothing was done.")
                exit(2)
            }
            if (args.contains("--self-drive") || args.contains("--rehearse")) && !practice {
                print("--self-drive and --rehearse only run with --home <practice folder>; nothing was done.")
                exit(2)
            }
            Snapshots.runIfAsked()
        }
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

/// The practice switches (`--home`, `--pack`, `--pretend-missing`, `--snapshot`,
/// `--rehearse`, `--self-drive`, `--check-logic`, `--dark`, `--owner`, `--step`, `--fresh`) exist
/// for testing. They are read only when the environment says this is a practice
/// run (MOBLEE_PRACTICE=1, which the test scripts set), so that a released,
/// signed Moblee cannot be pointed at some other folder of scripts, or at some
/// other home, by whoever starts it. Without it the app sees no switches at all.
enum Practice {
    static let on = ProcessInfo.processInfo.environment["MOBLEE_PRACTICE"] == "1"
    static let args: [String] = on ? CommandLine.arguments : []
    static let switches: Set<String> = ["--home", "--pack", "--pretend-missing", "--snapshot", "--rehearse",
                                        "--self-drive", "--dark", "--owner", "--step", "--fresh", "--icon",
                                        "--move-to", "--move-break", "--check-logic", "--fixtures"]
}

/// Quitting half-way through a build or an update would leave it half done, so
/// the app waits for the engine to finish; one window, and closing it quits.
final class AppDelegate: NSObject, NSApplicationDelegate {
    @MainActor static weak var install: InstallRun?
    /// The move to Applications is half-way through: closing now would leave a half-made copy.
    @MainActor static var moving = false

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        let busy = MainActor.assumeIsolated { AppDelegate.install?.phase == .running || AppDelegate.moving }
        if busy { NSSound.beep(); return .terminateCancel }
        return .terminateNow
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    /// A proof of the guard still running when the window closes is ended with
    /// everything it started: nobody is left to read its answer, and it would
    /// go on using the owner's ChatGPT allowance for minutes.
    func applicationWillTerminate(_ notification: Notification) {
        MainActor.assumeIsolated { GuardProof.stop() }
    }
}

/// The screens, in the order the owner meets them.
enum Step: Int, CaseIterable {
    case welcome
    case checkup
    case name
    case assistant      // which assistant the wiki is for
    case promise
    case build
    case trust          // only when the run said ChatGPT is waiting for the owner's trust
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
    /// The app is somewhere it should not stay (Downloads, usually): before
    /// anything else, it offers to move itself to Applications.
    @Published var offerMove: Bool = Placement.shouldOffer
    var moveOutcome: Placement.Outcome?

    /// The move was made in practice, declined, or could not be made: carry on
    /// with what the app was opened for. The home screen's own work (settling
    /// the pack, reading the requests) starts only now, so that a move never
    /// cuts a half-made copy of the pack off in the middle.
    func moveSettled() {
        offerMove = false
        if mode == .home { homeModel.load(home: home, bundledPack: bundledPack) }
    }
    @Published var ownerName: String = "" {
        didSet { if oldValue != ownerName { chosenPlace = nil } }   // a new name means a new folder
    }
    /// Where this run's wiki goes, fixed at the first try so a second try finishes the same one.
    var chosenPlace: (name: String, url: URL)?

    /// The install's answer to "Which assistant do you use?". Nil until the
    /// owner has answered; nothing is chosen for them.
    @Published var assistant: Assistant?

    /// An update that asks the question first: on a Mac with no choice on
    /// record, and whenever the owner presses Change at home. The answer goes
    /// to the updater as `--assistant`; with no question asked, nothing goes.
    @Published var askingAssistant = false
    @Published var updateAssistant: Assistant?

    /// Where the Trust screen starts. Only the picture-file drawing sets this.
    var trustStart: TrustScreen.Stage = .steps

    func beginUpdate(changingAssistant: Bool = false) {
        // The updater this app carries is never run on a wiki that a newer
        // Moblee made or updated: it would put older tools, skills and guard
        // over newer ones and write its own, older, version into the wiki. No
        // screen offers it then; this is the same refusal where it cannot be
        // walked round. Nor is the assistant changed while something is being
        // added, since both would be writing the same settings at once.
        if homeModel.wikiIsNewerThanApp { return }
        if changingAssistant && !homeModel.canChangeAssistant { return }
        install.phase = .idle
        updateAssistant = nil
        askingAssistant = changingAssistant || Assistant.mustAsk(home: home)
        mode = .update
    }

    /// The update screen takes the place of the question, and starts the update as it appears.
    func updateQuestionAnswered() { askingAssistant = false }

    /// "Not now" on the question: back home, and no update was started.
    func cancelUpdateQuestion() {
        mode = .home
        updateAssistant = nil
        askingAssistant = false
    }
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
        let args = Practice.args
        let chosen = Self.value(after: "--home", in: args)
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
        AppDelegate.install = install
        if HomeModel.existingVault(home: home) != nil && !args.contains("--fresh") {
            mode = .home
            if !offerMove { homeModel.load(home: home, bundledPack: bundledPack) }
        } else {
            // A wiki that an earlier run started and never finished (the note is
            // written by the installer's first step and marked finished by its
            // last): this run finishes that one, and never makes a second beside it.
            let note = home.appendingPathComponent(".config/moblee/in-progress")
            if let text = try? String(contentsOf: note, encoding: .utf8),
               !text.contains("\nfinished "),
               let first = text.split(separator: "\n").first {
                let url = URL(fileURLWithPath: String(first), isDirectory: true)
                if FileManager.default.fileExists(atPath: url.path) {
                    resumePlace = (url.lastPathComponent, url)
                    // The unfinished run had its answer; it is shown already chosen.
                    assistant = Assistant.stored(home: home)
                }
            }
        }
    }

    /// Set when an unfinished wiki was found at launch.
    var resumePlace: (name: String, url: URL)?

    static func value(after flag: String, in args: [String]) -> String? {
        guard let i = args.firstIndex(of: flag), i + 1 < args.count else { return nil }
        return args[i + 1]
    }

    /// The pack inside the app, or `--pack <folder>` while developing.
    var bundledPack: URL? {
        if let v = Self.value(after: "--pack", in: Practice.args) {
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
        if var s = Step(rawValue: step.rawValue + 1) {
            // The Trust screen is only for a run that said ChatGPT is waiting for it.
            if s == .trust && !install.trustNeeded { s = .handoff }
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
                if flow.offerMove { PlacementScreen() } else {
                switch flow.mode {
                case .home: HomeScreen()
                case .update:
                    if flow.askingAssistant { AssistantScreen(purpose: .update) } else { UpdateScreen() }
                case .install:
                    switch flow.step {
                    case .welcome: WelcomeScreen()
                    case .checkup: CheckupScreen()
                    case .name: NameScreen()
                    case .assistant: AssistantScreen(purpose: .install)
                    case .promise: PromiseScreen()
                    case .build: BuildScreen()
                    case .trust:
                        TrustScreen(start: flow.trustStart, vault: flow.install.vaultPath) { flow.next() }
                    case .handoff: HandoffScreen()
                    }
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
