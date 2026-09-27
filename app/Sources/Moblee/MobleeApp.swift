import SwiftUI

@main
struct MobleeApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var delegate
    @StateObject private var flow = Flow()
    @ObservedObject private var shape = WindowShape.shared
    @ObservedObject private var textSize = TextSize.shared

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
            // The size the owner reads at, read from their settings before a
            // single word is drawn. `--text-scale <0, 1 or 2>` draws a screen
            // at a size nobody asked for, without touching what is kept.
            _ = TextSize.shared
            if let v = Flow.value(after: "--text-scale", in: args) {
                guard let n = Int(v), let step = TextSize.Step(rawValue: n) else {
                    print("--text-scale takes 0 (normal), 1 (bigger) or 2 (biggest); nothing was done.")
                    exit(2)
                }
                TextSize.shared.drawAt(step)
            }
            // Asks for the latest release exactly as a returning owner's app
            // does, prints what came back and how long it took, and stops.
            if args.contains("--ask-release") { NewerRelease.askAndReport() }
            Snapshots.runIfAsked()
        }
    }

    /// (v0.9.4) The window is no longer nailed to 720 by 520. It is that size
    /// at its smallest and can be made as large as the owner likes, because an
    /// owner who cannot read small words needs both the words and the window
    /// to grow with them.
    ///
    /// On macOS 26.6 a window group whose content has no size of its own makes
    /// no window at all: the app starts, draws nothing, makes no NSWindow and
    /// sits in an empty event loop. Bisected on 26 September 2026 against a
    /// build from before this change — a fixed size made a window every time;
    /// a least size, an ideal size, or both, made none. So the content is
    /// given a size, and that size is the window's own, watched from AppKit by
    /// `WindowLeastSize` below: the owner drags the window, the window says
    /// how big it now is, and the screens are drawn at that size. The same
    /// place holds the window to its least size, which grows with the words.
    var body: some Scene {
        WindowGroup("Moblee") {
            RootView()
                .environmentObject(flow)
                .environmentObject(flow.install)
                // (v0.9.4) `--rtl` lays the whole run out right to left, the way
                // macOS lays out an app on a Mac whose own language is read that
                // way. Without the switch nothing is said, so a released Moblee
                // follows the Mac itself.
                .frame(width: max(shape.size.width, Theme.leastWidth),
                       height: max(shape.size.height, Theme.leastHeight))
        }
        .windowStyle(.hiddenTitleBar)
    }
}

/// (v0.9.4) How big the window is now, in the room the screens are drawn in
/// (the title bar is hidden, but its strip is not drawn in).
@MainActor
final class WindowShape: ObservableObject {
    static let shared = WindowShape()
    @Published var size = CGSize(width: 720, height: 520)
}

/// The window itself: resizable, never smaller than the screens need at the
/// size the owner reads at, and saying how big it is whenever it changes.
/// (v0.9.4)
struct WindowLeastSize: NSViewRepresentable {
    let least: CGSize

    func makeNSView(context: Context) -> LeastSizeView { LeastSizeView() }
    func updateNSView(_ view: LeastSizeView, context: Context) { view.least = least }

    final class LeastSizeView: NSView {
        var least: CGSize = .zero {
            didSet { if least != oldValue { wordsChangedAt = Date(); apply() } }
        }
        private var watching: NSObjectProtocol?

        /// (v0.9.4) When the words last changed size, and the whole of how a
        /// window the owner sized is told from one the words made.
        ///
        /// A window that changes size just after the words did is the words
        /// taking it with them: the screens are drawn at a size of their own,
        /// that size grew, and SwiftUI grows the window to hold them before
        /// anything here is asked. A window that changes size at any other
        /// moment is the owner dragging its corner.
        ///
        /// Told apart any other way, it goes wrong. It used to be done by
        /// comparing the window with the size this last asked for, and SwiftUI
        /// having already grown it meant the app read its own growth as the
        /// owner's: an owner who dragged the window to 1200 by 800 and pressed
        /// "Bigger text" twice was given a window of 1080 by 780, and a third
        /// press took it to 720 by 520 — the doc below promised the opposite.
        private var wordsChangedAt = Date()
        /// How long after the words change a resize still counts as theirs.
        private static let settling: TimeInterval = 0.8

        override func viewDidMoveToWindow() {
            super.viewDidMoveToWindow()
            if let watching { NotificationCenter.default.removeObserver(watching) }
            watching = nil
            if let window {
                watching = NotificationCenter.default.addObserver(
                    forName: NSWindow.didResizeNotification, object: window, queue: .main) { [weak self] _ in
                        MainActor.assumeIsolated { self?.report() }
                    }
            }
            apply()
        }

        /// The window has changed size. The screens are told how much room
        /// they have (the room left by the hidden title bar, which is where
        /// SwiftUI puts them), and the size is taken as the owner's if it
        /// happened at a moment that had nothing to do with the words.
        private func report() {
            guard let window else { return }
            let room = window.contentLayoutRect.size
            guard room.width > 0, room.height > 0 else { return }
            WindowShape.shared.size = room
            if Date().timeIntervalSince(wordsChangedAt) > Self.settling { ownersOwn = room }
        }

        /// The same, without judging whose size it is: what this itself has
        /// just set the window to is nobody's choice but the words'.
        private func tellTheScreens() {
            guard let window else { return }
            let room = window.contentLayoutRect.size
            if room.width > 0, room.height > 0 { WindowShape.shared.size = room }
        }

        /// (v0.9.4) The size the owner dragged the window to, once they have.
        /// It is remembered rather than merely noticed, because the words may
        /// have to take the window up past it — at the biggest size the screens
        /// need 1080 by 780 — and when the words come down again the window
        /// must come back to the owner's size and not to the size the words
        /// alone would ask for.
        private var ownersOwn: CGSize?

        /// The owner may make the window as large as they like, and never
        /// smaller than the screens need: at the biggest size three cards side
        /// by side do not fit in the room two of them would take. Words made
        /// bigger take the window up with them, and words made smaller again
        /// bring it back down — unless the owner has sized the window
        /// themselves, in which case it is left exactly as they left it.
        private func apply() {
            // Never in the middle of the window being built or laid out: the
            // window is left to finish and settled a moment later.
            let least = self.least
            DispatchQueue.main.async { [weak self] in
                guard let self, let window = self.window, least.width > 0 else { return }
                window.styleMask.insert(.resizable)
                window.contentMinSize = least
                // SwiftUI would hold the window to the size of what is drawn
                // in it, which is the size the window already is; the largest
                // size is the owner's own business.
                window.contentMaxSize = CGSize(width: 100_000, height: 100_000)
                let now = window.contentLayoutRect.size
                // Big enough for the screens at the size the words are now, and
                // never smaller than the owner left it. Whose size the window is
                // now was settled when it changed; see `wordsChangedAt`.
                let floor = self.ownersOwn ?? .zero
                let want = CGSize(width: max(least.width, floor.width),
                                  height: max(least.height, floor.height))
                if abs(want.width - now.width) > 0.5 || abs(want.height - now.height) > 0.5 {
                    let strip = window.frame.height - now.height     // the hidden title bar
                    window.setContentSize(CGSize(width: want.width, height: want.height + strip))
                }
                self.tellTheScreens()
            }
        }
    }
}

/// The practice switches (`--home`, `--pack`, `--pretend-missing`, `--snapshot`,
/// `--rehearse`, `--self-drive`, `--check-logic`, `--dark`, `--owner`, `--step`, `--fresh`,
/// `--text-scale` for drawing a screen at a bigger size than the owner has set,
/// `--rtl` for laying the whole run out right to left as macOS does on a Mac
/// whose own language is read that way,
/// and `--latest`, `--release-url`, `--live-release`, `--ask-release` for the
/// check for a newer Moblee) exist for testing. They are read only when the environment says this is a practice
/// run (MOBLEE_PRACTICE=1, which the test scripts set), so that a released,
/// signed Moblee cannot be pointed at some other folder of scripts, or at some
/// other home, by whoever starts it. Without it the app sees no switches at all.
enum Practice {
    static let on = ProcessInfo.processInfo.environment["MOBLEE_PRACTICE"] == "1"
    static let args: [String] = on ? CommandLine.arguments : []
    static let switches: Set<String> = ["--home", "--pack", "--pretend-missing", "--snapshot", "--rehearse",
                                        "--self-drive", "--dark", "--owner", "--step", "--fresh", "--icon",
                                        "--move-to", "--move-break", "--check-logic", "--fixtures",
                                        "--latest", "--release-url", "--live-release", "--ask-release",
                                        "--text-scale", "--rtl"]
}

/// Quitting half-way through a build, an update or a repair would leave it half
/// done, so the app waits for the engine to finish; one window, and closing it
/// quits.
final class AppDelegate: NSObject, NSApplicationDelegate {
    @MainActor static weak var install: InstallRun?
    /// The move to Applications is half-way through: closing now would leave a half-made copy.
    @MainActor static var moving = false

    /// (v0.9.4) A repair is half-way through (`HomeModel.repair`). It changes
    /// the owner's Mac exactly as an install does — the safety script is
    /// writing into ~/.claude, the skills script into the skills folder — and
    /// it was the one of the three that could be cut off. The concrete way:
    /// the owner presses Repair in the copy in Applications, then opens a
    /// freshly downloaded Moblee and presses "Move it there"; that one finds
    /// this copy (`Placement.others(at:)`) and asks it to quit, and this copy
    /// said yes. The diary was then left with "repair: started" and no ending
    /// line, the Trust step was never set waiting even where the guard's entry
    /// had just been added, and the check afterwards never ran. So a repair
    /// refuses a quit exactly as an install does.
    @MainActor static var repairing = false

    /// (v0.9.5) How many drops are copying into the wiki this moment.
    ///
    /// A drop is not instant. A 90 MB scan takes a noticeable while to copy,
    /// and for that while the wiki's inbox is being written to — which is
    /// exactly the state `Inbox` refuses a drop for when an install, an update
    /// or a repair is the one writing. It was not the other way round: an owner
    /// who dropped a big PDF and pressed Update a second later had the pack's
    /// scripts rewrite and commit the wiki while the copy was still running,
    /// and the copy's last step landed in the middle of that commit. Quitting
    /// mid-drop was allowed too, which left one of Moblee's own hidden
    /// half-made copies in the owner's inbox and gave them no receipt at all.
    /// A count and not a flag, because two drops can be in flight at once.
    ///
    /// (v0.9.6) Kept on `Dropped.shared`, which a screen can watch, so that a
    /// control which greys itself while a drop is copying really does grey
    /// itself. Read and written through here, because that is where the rest of
    /// the app already asks.
    @MainActor static var dropsInFlight: Int {
        get { Dropped.shared.inFlight }
        set { Dropped.shared.inFlight = newValue }
    }

    /// Work a DROP must wait for: the three that run the pack's own scripts
    /// over the wiki and commit it. A drop never waits for another drop; see
    /// `Dropped.arrived`.
    @MainActor static var busyMakingOrMending: Bool {
        AppDelegate.install?.phase == .running || AppDelegate.moving || AppDelegate.repairing
    }

    /// Work that must not be cut off half-way, and what to say about it. The
    /// wording is what the copy asking to quit puts on its own screen when it
    /// is refused (`Placement.refusal`), so it has to be true of all of these.
    @MainActor static var busyWithWork: Bool {
        busyMakingOrMending || AppDelegate.dropsInFlight > 0
    }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        let busy = MainActor.assumeIsolated { AppDelegate.busyWithWork }
        if busy { NSSound.beep(); return .terminateCancel }
        return .terminateNow
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    /// (v0.9.5) A file given to Moblee from outside — a drop on the Dock icon —
    /// arrives at `onOpenURL` on the screens, not here. See `MobleeApp.body`
    /// and `DockDrop`.
    func application(_ application: NSApplication, open urls: [URL]) {
        // SwiftUI has already taken the files and passes an empty list here.
        // Nothing may be done with it: acting on an empty list showed the owner
        // "there was nothing in that to put in your wiki" over a file that had
        // just landed. Left in place, doing nothing, so that nobody adds the
        // handling back here without reading this.
        _ = urls
    }

    /// A proof of the guard still running when the window closes is ended with
    /// everything it started: nobody is left to read its answer, and it would
    /// go on using the owner's ChatGPT allowance for minutes.
    func applicationWillTerminate(_ notification: Notification) {
        MainActor.assumeIsolated { GuardProof.stop() }
    }
}

/// (v0.9.5) Every file in one drop on the Dock icon.
///
/// THE FAULT THIS EXISTS FOR. Letting go of four scans over Moblee's icon is
/// ONE thing the owner did and ONE Apple event carrying four file URLs.
/// SwiftUI's `onOpenURL` is handed one URL at a time, and only the first ever
/// arrived: in a real drop of "Scan 1.pdf" through "Scan 4.pdf" on a built app
/// (26 September 2026, twice, with Moblee open and with Moblee closed) exactly
/// "Scan 1.pdf" reached the inbox, and the owner was shown a receipt naming it
/// and saying it was in their wiki. That receipt is worse than no receipt at
/// all: an owner told the drop worked stops looking for the other three. The
/// same four opened one at a time all landed, so nothing was wrong with the
/// copying — only with how many of them Moblee was ever told about.
///
/// The rest are read out of the event macOS is handling at the moment it calls
/// `onOpenURL`, which is where they have been all along.
///
/// Moblee does NOT take that event over. Registering its own handler for it was
/// tried first and made the app open no window at all, some launches out of
/// several: there is one handler for an event, SwiftUI keeps its own, and two
/// of them racing at launch is not a thing to ship to anyone. Reading the
/// event that SwiftUI is already handling asks nobody for anything.
@MainActor
enum DockDrop {
    /// The files of the last drop this took, and when. Only ever set for a drop
    /// of more than one file, and only so that a macOS which one day calls
    /// `onOpenURL` once per URL cannot make four drops out of one. Today it
    /// calls it once, which is the whole fault above.
    /// Which event they came in, so that a second drop of the same file a
    /// moment later is never mistaken for a repeat and thrown away. Dropping
    /// the same thing twice in a row is an owner's to do, and losing it in
    /// silence is the fault this whole route exists to end.
    private static var alreadyTaken: (event: Int16, files: Set<String>)?
    private static var takenAt = Date.distantPast
    /// How long a drop stays remembered. Long enough to cover the run of calls
    /// one event could make, and no longer.
    private static let remembered: TimeInterval = 5

    static func everyFile(alongside url: URL) -> [URL] {
        let event = NSAppleEventManager.shared().currentAppleEvent
        if let alreadyTaken, let event, alreadyTaken.event == event.returnID,
           Date().timeIntervalSince(takenAt) < remembered, alreadyTaken.files.contains(url.path) {
            return []                              // this one came in with that same drop
        }
        guard let event,
              event.eventClass == AEEventClass(kCoreEventClass),
              event.eventID == AEEventID(kAEOpenDocuments),
              let given = event.paramDescriptor(forKeyword: keyDirectObject)
        else { return [url] }
        var files: [URL] = []
        if given.numberOfItems > 0 {
            for at in 1...given.numberOfItems {
                if let one = given.atIndex(at)?.fileURLValue { files.append(one) }
            }
        } else if let one = given.fileURLValue {
            files.append(one)
        }
        // Whatever macOS says, the URL this was called with is part of the drop
        // and must land: a list that somehow came back without it would lose
        // the very file the owner can see they dropped.
        if !files.contains(where: { $0.standardizedFileURL == url.standardizedFileURL }) {
            files.append(url)
        }
        if files.count > 1 {
            alreadyTaken = (event.returnID, Set(files.map(\.path)))
            takenAt = Date()
        }
        return files
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
    ///
    /// (v0.9.6) And the check-up, which the owner runs from the home screen and
    /// which takes the whole window while it runs: it has a report to show and a
    /// file to send, and neither belongs in a corner of a screen about something
    /// else.
    enum Mode { case install, home, update, clinic }

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
    var trustStart: TrustScreen.Stage = Trust.firstStage

    /// (v0.9.6) The example wiki, while an owner is reading it. Nil at every
    /// other moment: the reader is made when the example is opened and thrown
    /// away when it is closed, so the map of its pages is built once per read
    /// and nothing about the example outlives it.
    ///
    /// It is held on the flow rather than on a screen because it is reached from
    /// two screens at opposite ends of the app — the welcome screen and the home
    /// screen — and closing it must put the owner back on whichever of them they
    /// came from. Nothing here changes `mode` or `step`, so that happens by
    /// itself: an owner with no wiki is returned to the install and an owner who
    /// has one to the home screen.
    @Published var example: ExampleReader?

    /// The pages of the example inside the app, found once. A build with no pack
    /// behind it has none, and then there is no way in on any screen: a button
    /// that opened an empty reader would be worse than no button.
    lazy var examplePages: ExamplePages? = ExamplePages.found(inPack: bundledPack)

    var hasExample: Bool { examplePages != nil }

    func openExample() {
        guard let pages = examplePages else { return }
        example = ExampleReader(pages: pages)
    }

    func closeExample() { example = nil }

    /// Where the move screen starts, and why it failed if it starts failed.
    /// Only the picture-file drawing sets these: the states they reach are
    /// otherwise only reachable by really moving the app on a real Mac, which
    /// is why none of them had ever been looked at.
    var moveStart: PlacementScreen.Stage = .asking
    var moveWhy: Placement.Failure?

    func beginUpdate(changingAssistant: Bool = false) {
        // The updater this app carries is never run on a wiki that a newer
        // Moblee made or updated: it would put older tools, skills and guard
        // over newer ones and write its own, older, version into the wiki. No
        // screen offers it then; this is the same refusal where it cannot be
        // walked round. Nor is the assistant changed while something is being
        // added, since both would be writing the same settings at once.
        if homeModel.wikiIsNewerThanApp { return }
        if changingAssistant && !homeModel.canChangeAssistant { return }
        // (v0.9.5) Nor while something dropped on Moblee is still being copied
        // into the wiki. The updater's scripts rewrite the wiki and commit it,
        // and a copy finishing in the middle of that commit is the very thing
        // `Dropped.arrived` refuses a drop for when the update is the one
        // already running. A drop is over in a moment and its receipt takes the
        // whole screen the instant it is, so the owner presses Update again on
        // the screen they are put back to; an update started over a half-copied
        // file cannot be undone.
        if AppDelegate.busyWithWork { return }
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
    /// (v0.9.6) The owner's own check-up: one press, the pack's read-only
    /// check-up, and the report saved where the clinic process looks for it.
    let clinic = Clinic()

    /// Whether "Check my wiki" can be pressed. It cannot while a wiki is being
    /// made, updated, repaired or written into by a dropped file, because
    /// findings taken from a wiki in the middle of being changed would describe
    /// neither the wiki before nor the wiki after.
    ///
    /// The button reads this and greys itself, and it matters that it does. A
    /// repair takes the corner off the home screen altogether, so that one is
    /// covered; **a drop does not**. The count goes up before the copying starts
    /// and the receipt only goes on the screen once it has finished, so a big
    /// file dropped on the window leaves the owner looking at the home screen,
    /// with this button on it, for as long as the copy takes. Refusing in
    /// `beginClinic` alone made that a button that did nothing at all when
    /// pressed, which is the one thing every other refusal in this app is
    /// written to avoid.
    var canBeginClinic: Bool { !AppDelegate.busyWithWork }

    /// The check-up starts from the home screen. The refusal is kept here as
    /// well as on the button, because a keyboard press and a click arrive by
    /// different roads and the work must not start down either of them.
    func beginClinic() {
        guard canBeginClinic else { return }
        clinic.forget()
        mode = .clinic
    }

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
        // (v0.9.5) A drop, from either route, needs to know which home folder
        // this run is using and whether the app is busy. Set here, the way
        // `AppDelegate.install` is, and held weakly there.
        Dropped.shared.flow = self
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

    /// When the last move between screens was made. While one screen slides
    /// out its button is still there to be pressed, so a second press inside
    /// the slide (a double click, or a slow Mac) would skip the screen sliding
    /// in. The question of which assistant must never be skipped that way.
    private var lastMove = Date.distantPast

    func next() {
        guard Date().timeIntervalSince(lastMove) > 0.5 else { return }
        // Nothing leaves the question without an answer, whoever asks.
        if step == .assistant && assistant == nil { return }
        if var s = Step(rawValue: step.rawValue + 1) {
            lastMove = Date()
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
    @ObservedObject private var textSize = TextSize.shared
    @ObservedObject private var shape = WindowShape.shared
    /// (v0.9.5) Something dropped on the window or on the Dock icon, and the
    /// receipt waiting to be read.
    @ObservedObject private var dropped = Dropped.shared

    var body: some View {
        ZStack(alignment: .top) {
            Theme.background.ignoresSafeArea()

            VStack(spacing: 0) {
                topStrip
                screen
            }
        }
        // (v0.9.5) A drop anywhere on the window lands in the wiki's inbox. It
        // goes here, on the whole of the window's contents, because an owner
        // aiming at a window does not aim at a part of it.
        .takesADrop()
        // (v0.9.5) Files dropped on Moblee's icon in the Dock. This is the
        // second of the two routes into the wiki's inbox, and the one an owner
        // finds without being told: the app does not have to be open, and the
        // Dock icon is a thing they already know how to aim at.
        //
        // macOS only offers the drop at all because `app/Info.plist` says
        // Moblee will take files; see the comment there for what is declared
        // and why it is the careful version of it. From here on it is the same
        // code the window's own drop runs, so the two routes cannot differ.
        //
        // (v0.9.5) AND EVERY FILE IN THE DROP, not the one URL this is handed.
        // `onOpenURL` gives one URL at a time, and a drop of four scans on the
        // Dock icon is ONE event carrying four; three of them were lost in
        // silence while the owner was shown a receipt saying the first was in
        // their wiki. `DockDrop.everyFile` reads the rest out of the event
        // macOS is handling this very moment. See `DockDrop`.
        .onOpenURL { url in
            let files = DockDrop.everyFile(alongside: url)
            guard !files.isEmpty else { return }
            Dropped.shared.arrived(files: files, text: nil)
        }
        // (v0.9.5) One window, always. A `WindowGroup` given something from
        // outside opens a SECOND window for it by default, and an owner who
        // dropped a PDF on the Dock icon was left with two Moblee windows, the
        // receipt on one of them — which also broke the walk below, since a
        // second window starts a second walk. This says the window already open
        // takes anything given to the app, so no second one is made. Said on
        // the screens (the View form) and not on the scene: the scene form,
        // tried first, stopped the file reaching `onOpenURL` at all and the
        // Dock route went dead (26 September 2026). The walk counts the windows
        // after a Dock drop so that neither can come back unnoticed.
        .handlesExternalEvents(preferring: ["*"], allowing: ["*"])
        // (v0.9.4) `--rtl` lays the screens out right to left, the way macOS
        // lays out any app on a Mac whose own language is read that way.
        // Without the switch nothing is said, so a released Moblee follows the
        // Mac itself. It goes here, on the screens, and not on the window's own
        // content, where it stopped the window being made at all; see
        // `MirrorIfAsked`.
        .mirrorIfAsked()
        // Drawn at the size the window is now, and the window held to its
        // least size, which grows with the words. A size of its own is also
        // what makes the window exist at all; see `MobleeApp`. (v0.9.4)
        .background(WindowLeastSize(least: CGSize(width: Theme.leastWidth, height: Theme.leastHeight)))
        .task {
            if SelfDrive.asked { await SelfDrive.run(flow) }
        }
    }

    /// (v0.9.4) The strip along the very top, on every screen and once only.
    /// "Bigger text" sits in the corner the reading ends at: the top of the
    /// window is where it is dragged by, so nothing may be put in the strip
    /// above this one, and the middle is the practice badge's. The screen below
    /// starts where this ends, so a long sentence can never run under either.
    ///
    /// The corner is named in `Layout` and is SwiftUI's own trailing, so it is
    /// the left corner once the layout is mirrored — which is the far corner
    /// there too, and still out of the way of the sentence and the badge.
    private var topStrip: some View {
        ZStack {
            if flow.isTestMode {
                Text(SelfDrive.asked ? "Practice run, driving itself" : "Practice run")
                    .font(Theme.font(11, .semibold, .default))
                    .padding(.horizontal, Theme.pt(10)).padding(.vertical, Theme.pt(3))
                    .background(.orange.opacity(0.85), in: Capsule())
                    .foregroundStyle(.white)
            }
            BiggerTextButton()
                .frame(maxWidth: .infinity, alignment: Layout.biggerTextCorner)
        }
        .frame(height: Theme.topStrip)
        .padding(.horizontal, Theme.pt(12))
    }

    private var screen: some View {
        ZStack(alignment: .top) {
            Group {
                // (v0.9.5) The receipt comes first of all, before even the offer
                // to move to Applications: the owner has just dropped something
                // and is owed an answer about it, and a drop on the Dock icon
                // arrives whatever screen they were on.
                if let landing = dropped.showing { DropScreen(landing: landing) }
                else if flow.offerMove { PlacementScreen(start: flow.moveStart, why: flow.moveWhy) }
                // (v0.9.6) The example wiki takes the place of whatever screen
                // the owner opened it from, and closing it puts that screen back
                // exactly as it was: nothing here touches `mode` or `step`.
                else if let reader = flow.example { ExampleScreen(reader: reader) } else {
                switch flow.mode {
                case .home: HomeScreen()
                case .update:
                    if flow.askingAssistant { AssistantScreen(purpose: .update) } else { UpdateScreen() }
                case .clinic: ClinicScreen(clinic: flow.clinic)
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
            // (v0.9.4) A new screen arrives from the side "on" is on, and the
            // one before it leaves by the other. The two edges are named in
            // `Layout`; they are SwiftUI's own semantic edges, which it turns
            // round itself when the layout is mirrored, so a mirrored screen
            // still comes from the direction its owner reads towards.
            .transition(.asymmetric(
                insertion: .move(edge: Layout.arrives).combined(with: .opacity),
                removal: .move(edge: Layout.leaves).combined(with: .opacity)))
        }
    }
}
