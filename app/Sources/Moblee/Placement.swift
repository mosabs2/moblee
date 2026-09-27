import SwiftUI
import AppKit

/// Where the app lives.
///
/// An owner unzips Moblee in Downloads and opens it there. macOS then runs it
/// from a temporary, read-only copy ("translocation"), so its own location
/// changes at every launch and it can never replace itself with a newer
/// version; an owner who tidies Downloads throws the app away; and the
/// companion's standing instruction, "press Command and Space, type Moblee",
/// depends on it being somewhere Spotlight looks. On the first stranger's run
/// (20 September 2026) the app stayed in Downloads, twice over. So the app
/// offers, once per launch, to move itself to Applications.
///
/// The order is what keeps an owner from ever being left with no app: the new
/// copy is made beside its final place under a temporary name, checked, and
/// has its download mark cleared; only then is an older Moblee set aside, the
/// new one given its name, and the one that was opened put in the Bin. Until
/// the last of those, a failure leaves everything as it was.
enum Placement {
    static let appName = "Moblee.app"

    struct Plan {
        var destinationFolder: URL
        /// Where things that are set aside go: nil is the Mac's own Bin, from
        /// which they can be put back. A practice run gives a scratch folder.
        var bin: URL?
        var reopen: Bool
    }

    enum Outcome: Equatable {
        case moved(URL)             // this app now lives there
        case alreadyThere(URL)      // the same Moblee, or a newer one, was already there: that one is used
    }

    enum Failure: Error, CaseIterable {
        case copyIncomplete, somethingElseThere, anotherMobleeIsOpen, markNotCleared
        /// The copy at the destination was asked to quit and said no. It only
        /// ever says no while it is building, updating or repairing a wiki,
        /// putting something dropped on it into one, or moving itself
        /// (`AppDelegate.busyWithWork`), so the owner is told that, and not to
        /// go and close it by hand in the middle of it.
        case otherMobleeIsBusy
    }

    private static func practice(_ flag: String) -> String? {
        let args = Practice.args
        guard let i = args.firstIndex(of: flag), i + 1 < args.count else { return nil }
        return args[i + 1]
    }

    /// A practice run can rehearse the move into a scratch folder
    /// (`--move-to <folder>`): everything but the Mac's own Bin (a scratch
    /// folder beside it stands in) and the reopening.
    static var practiceFolder: URL? { practice("--move-to").map { URL(fileURLWithPath: $0, isDirectory: true) } }
    /// `--move-break copy` makes the check of the new copy fail, so a test can
    /// see that an older Moblee at the destination is then left exactly as it was.
    static var practiceBreak: String? { practice("--move-break") }

    static var running: URL { Bundle.main.bundleURL }

    static func isTranslocated(_ url: URL) -> Bool { url.path.contains("/AppTranslocation/") }

    static func inApplications(_ url: URL) -> Bool {
        let p = url.resolvingSymlinksInPath().path
        let mine = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Applications").resolvingSymlinksInPath().path
        return p.hasPrefix("/Applications/") || p.hasPrefix(mine + "/")
    }

    /// Whether to offer the move at all. Judged by where the app really is,
    /// not by the temporary place macOS may be running it from: an app that is
    /// already in Applications but still carries its download mark must never
    /// be offered a move onto itself. Never from a build folder, where the
    /// maintainer and the tests run it, and never for something that is not an
    /// app bundle (the bare program run by `swift run`).
    static var shouldOffer: Bool {
        if practiceFolder != nil { return true }
        if Practice.on { return false }
        let url = running
        guard url.pathExtension == "app" else { return false }
        if isTranslocated(url), original(of: url) == nil { return false }   // cannot tell where it is: leave well alone
        let real = original(of: url) ?? url
        let p = real.path
        if p.contains("/Library/Caches/") || p.contains("/DerivedData/") || p.contains("/.build/") { return false }
        return !inApplications(real)
    }

    /// /Applications for someone who may write there; their own Applications
    /// folder for someone who may not (a standard account). Spotlight and
    /// `open -a Moblee` find both.
    static func plan() -> Plan {
        if let practice = practiceFolder {
            return Plan(destinationFolder: practice,
                        bin: practice.deletingLastPathComponent().appendingPathComponent("practice-bin", isDirectory: true),
                        reopen: false)
        }
        let fm = FileManager.default
        let shared = URL(fileURLWithPath: "/Applications", isDirectory: true)
        let folder = fm.isWritableFile(atPath: shared.path)
            ? shared : fm.homeDirectoryForCurrentUser.appendingPathComponent("Applications", isDirectory: true)
        return Plan(destinationFolder: folder, bin: nil, reopen: true)
    }

    /// The app as the owner sees it in Finder. A translocated app knows only
    /// its temporary path; the system can say where it really is. The call is
    /// looked up by name so that a Mac without it simply gets no answer, and
    /// the answer is trusted only if it is this same app.
    static func original(of url: URL) -> URL? {
        guard isTranslocated(url) else { return url }
        guard let handle = dlopen("/System/Library/Frameworks/Security.framework/Security", RTLD_LAZY) else { return nil }
        defer { dlclose(handle) }
        guard let symbol = dlsym(handle, "SecTranslocateCreateOriginalPathForURL") else { return nil }
        typealias Call = @convention(c) (CFURL, UnsafeMutablePointer<Unmanaged<CFError>?>?) -> Unmanaged<CFURL>?
        let call = unsafeBitCast(symbol, to: Call.self)
        guard let answer = call(url as CFURL, nil)?.takeRetainedValue() else { return nil }
        let found = answer as URL
        guard !isTranslocated(found), found.pathExtension == "app",
              FileManager.default.fileExists(atPath: found.path),
              identifier(of: found) == Bundle.main.bundleIdentifier else { return nil }
        return found
    }

    private static func info(of app: URL) -> NSDictionary? {
        NSDictionary(contentsOf: app.appendingPathComponent("Contents/Info.plist"))
    }
    static func identifier(of app: URL) -> String? { info(of: app)?["CFBundleIdentifier"] as? String }
    static func version(of app: URL) -> String { (info(of: app)?["CFBundleShortVersionString"] as? String) ?? "0" }
    /// The version, then the build number: two builds that carry the same
    /// version are told apart by their build, so a later build of the same
    /// version still replaces an earlier one (they did share a number once,
    /// in testing, and the older build was silently kept).
    static func fullVersion(of app: URL) -> String {
        version(of: app) + "." + ((info(of: app)?["CFBundleVersion"] as? String) ?? "0")
    }
    static var ourFullVersion: String {
        let i = Bundle.main.infoDictionary
        return ((i?["CFBundleShortVersionString"] as? String) ?? "0") + "." + ((i?["CFBundleVersion"] as? String) ?? "0")
    }

    /// 0.10.0 is newer than 0.9.2: compared number by number, not as text.
    static func newer(_ a: String, than b: String) -> Bool {
        let pa = a.split(separator: ".").map { Int($0) ?? 0 }, pb = b.split(separator: ".").map { Int($0) ?? 0 }
        for i in 0..<max(pa.count, pb.count) {
            let x = i < pa.count ? pa[i] : 0, y = i < pb.count ? pb[i] : 0
            if x != y { return x > y }
        }
        return false
    }

    /// Into the Bin (or the practice stand-in), never deleted.
    private static func setAside(_ url: URL, _ plan: Plan) throws {
        let fm = FileManager.default
        guard let bin = plan.bin else { try fm.trashItem(at: url, resultingItemURL: nil); return }
        try fm.createDirectory(at: bin, withIntermediateDirectories: true)
        let name = url.deletingPathExtension().lastPathComponent
        try fm.moveItem(at: url, to: bin.appendingPathComponent("\(name)-\(UUID().uuidString.prefix(8)).app"))
    }

    /// The copies of Moblee open right now that are the one at `destination`,
    /// this process excepted. Judged by where each is running FROM, as
    /// `reopen` already judges it: an owner may have a second Moblee open in
    /// Downloads or on a disk image, and that one is not in the way of a move
    /// into Applications. Before v0.9.4 the filter was on the bundle
    /// identifier alone, so any second Moblee anywhere refused the move.
    static func others(at destination: URL) -> [NSRunningApplication] {
        let me = ProcessInfo.processInfo.processIdentifier
        let there = destination.resolvingSymlinksInPath().path
        return NSRunningApplication.runningApplications(withBundleIdentifier: Bundle.main.bundleIdentifier ?? "")
            .filter { $0.processIdentifier != me && $0.bundleURL?.resolvingSymlinksInPath().path == there }
    }

    /// How long the copy at the destination is given to close itself.
    static let quitWait: TimeInterval = 8

    /// Asks the older copy to quit, the ordinary way one Mac app asks another
    /// (`terminate()` sends the Quit Apple event), and waits a little for it to
    /// go. That way round it gets to save what it is doing and, more to the
    /// point, gets to REFUSE: a Moblee in the middle of building, updating or
    /// repairing a wiki says no (`AppDelegate.busyWithWork`), and must not be
    /// killed from under an owner's install or repair. Nothing is forced; if it
    /// will not go, the move does not happen and the screen says which of the
    /// two it was.
    static func askToQuit(_ apps: [NSRunningApplication], wait: TimeInterval = quitWait) -> Failure? {
        var sent = true
        for app in apps where !app.isTerminated {
            if !app.terminate() { sent = false }
        }
        let by = Date().addingTimeInterval(wait)
        while Date() < by, apps.contains(where: { !$0.isTerminated }) {
            Thread.sleep(forTimeInterval: 0.2)
        }
        guard apps.contains(where: { !$0.isTerminated }) else { return nil }
        return refusal(requestsSent: sent)
    }

    /// What it means that the other copy is still open after being asked. A
    /// Moblee says no to a quit in one case only: it is building, updating or
    /// repairing a wiki, or moving itself (`AppDelegate.busyWithWork`). So a
    /// request that was taken and not acted on means work in progress, and the
    /// owner is told THAT, rather than being sent to close an app in the middle
    /// of their own install. A request that could not be sent at all says
    /// nothing more than "something is open".
    static func refusal(requestsSent: Bool) -> Failure {
        requestsSent ? .otherMobleeIsBusy : .anotherMobleeIsOpen
    }

    /// `asking` is called, once, just before the older copy at the destination
    /// is asked to quit, so the screen can say what is happening. It is called
    /// on whichever thread the move is running on.
    static func move(_ plan: Plan, asking: @escaping () -> Void = {}) throws -> Outcome {
        let fm = FileManager.default
        let from = running
        let first = original(of: from)                  // what the owner opened, if it can be told
        let folder = plan.destinationFolder
        let to = folder.appendingPathComponent(appName, isDirectory: true)
        let mine = Bundle.main.bundleIdentifier
        let ourVersion = (Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String) ?? "0"

        // Never onto itself.
        if let first, first.resolvingSymlinksInPath().path == to.resolvingSymlinksInPath().path { return .alreadyThere(to) }

        let somethingThere = fm.fileExists(atPath: to.path)
        if somethingThere {
            // Something else that happens to be called Moblee is not ours to touch.
            guard identifier(of: to) == mine else { throw Failure.somethingElseThere }
            // The same Moblee or a newer one is already in place (an old zip
            // opened again): that one is used, and nothing is copied over it.
            if !newer(ourFullVersion, than: fullVersion(of: to)) { return .alreadyThere(to) }
            // An older one that is open right now cannot be moved from under
            // itself, so it is asked to close first. Only the copy at the
            // destination is in the way; another Moblee open somewhere else is
            // left alone.
            let inTheWay = others(at: to)
            if !inTheWay.isEmpty {
                asking()
                if let refused = askToQuit(inTheWay) { throw refused }
            }
        }

        try fm.createDirectory(at: folder, withIntermediateDirectories: true)
        // A half-made copy from an earlier try that was cut short (the window
        // closed mid-move) is our own, hidden, and of no use: cleared first.
        for name in (try? fm.contentsOfDirectory(atPath: folder.path)) ?? [] where name.hasPrefix(".Moblee-incoming-") {
            try? fm.removeItem(at: folder.appendingPathComponent(name))
        }
        let incoming = folder.appendingPathComponent(".Moblee-incoming-\(UUID().uuidString.prefix(8)).app", isDirectory: true)
        do {
            try fm.copyItem(at: from, to: incoming)
            // The copy must be whole, and free of its download mark, before anything else is touched.
            let program = incoming.appendingPathComponent("Contents/MacOS/Moblee")
            guard practiceBreak != "copy", fm.isExecutableFile(atPath: program.path),
                  identifier(of: incoming) == mine, version(of: incoming) == ourVersion
            else { throw Failure.copyIncomplete }
            try clearDownloadMark(incoming)
        } catch {
            try? fm.removeItem(at: incoming)            // our own unfinished copy, made a moment ago
            throw error
        }

        // Only now is anything the owner had moved. If giving the new copy its
        // name fails, the older one stays where it is.
        if somethingThere {
            // A name the owner can see and understand: it is what they will find
            // in the Bin if they ever want the older one back, and a hidden
            // name would be invisible there.
            var old = folder.appendingPathComponent("Moblee older \(version(of: to)).app", isDirectory: true)
            if fm.fileExists(atPath: old.path) {
                old = folder.appendingPathComponent("Moblee older \(version(of: to)) \(UUID().uuidString.prefix(4)).app", isDirectory: true)
            }
            do { try fm.moveItem(at: to, to: old) }     // locked in Finder, or not ours to rename: nothing has changed yet
            catch { try? fm.removeItem(at: incoming); throw error }
            do { try fm.moveItem(at: incoming, to: to) }
            catch {
                try? fm.moveItem(at: old, to: to)       // put back exactly as it was
                try? fm.removeItem(at: incoming)
                throw error
            }
            try? setAside(old, plan)
        } else {
            do { try fm.moveItem(at: incoming, to: to) }
            catch { try? fm.removeItem(at: incoming); throw error }
        }

        // The one that was opened goes to the Bin, last of all, and only when
        // it is ours to move: not on a disk image, not in a locked folder.
        if let first, first.resolvingSymlinksInPath().path != to.resolvingSymlinksInPath().path,
           !inApplications(first),
           fm.isWritableFile(atPath: first.deletingLastPathComponent().path) {
            try? setAside(first, plan)
        }
        return .moved(to)
    }

    /// The mark macOS puts on anything downloaded. Gatekeeper has already
    /// checked this app (it is running), and a copy that kept the mark would
    /// be run from a temporary place like the original was, so a mark that
    /// will not come off is a failed move, not a finished one.
    private static func clearDownloadMark(_ app: URL) throws {
        let name = "com.apple.quarantine"
        removexattr(app.path, name, XATTR_NOFOLLOW)
        if let walk = FileManager.default.enumerator(at: app, includingPropertiesForKeys: nil) {
            for case let item as URL in walk { removexattr(item.path, name, XATTR_NOFOLLOW) }
        }
        if getxattr(app.path, name, nil, 0, 0, XATTR_NOFOLLOW) >= 0 { throw Failure.markNotCleared }
    }

    /// Opens the app in Applications and only then closes this one. If it
    /// will not open, this one stays, and says where Moblee now is.
    static func reopen(_ app: URL, failed: @escaping @MainActor () -> Void) {
        // If the Moblee in Applications is already open (the owner opened an old
        // copy from Downloads while it was running), that one is brought to the
        // front; a second Moblee is never started beside it.
        let me = ProcessInfo.processInfo.processIdentifier
        let there = app.resolvingSymlinksInPath().path
        if let open = NSRunningApplication.runningApplications(withBundleIdentifier: Bundle.main.bundleIdentifier ?? "")
            .first(where: { $0.processIdentifier != me && $0.bundleURL?.resolvingSymlinksInPath().path == there }) {
            open.activate(options: [.activateAllWindows])
            DispatchQueue.main.async { NSApp.terminate(nil) }
            return
        }
        let config = NSWorkspace.OpenConfiguration()
        config.createsNewApplicationInstance = true
        NSWorkspace.shared.openApplication(at: app, configuration: config) { opened, error in
            DispatchQueue.main.async {
                MainActor.assumeIsolated {
                    if opened != nil, error == nil { NSApp.terminate(nil) } else { failed() }
                }
            }
        }
    }
}

/// "Moblee should live in Applications." One button.
struct PlacementScreen: View {
    /// Drawn again when the owner presses "Bigger text". (v0.9.4)
    @ObservedObject private var textSize = TextSize.shared
    @EnvironmentObject var flow: Flow
    enum Stage { case asking, moving, askingTheOtherOne, failed, movedButNotOpened }
    @State private var stage: Stage
    @State private var why: Placement.Failure?

    /// `start` and `why` are only ever set by the picture-file drawing, which
    /// has no way to reach these states otherwise: the move happens on the
    /// Mac's own files. The same treatment `TrustScreen` has.
    init(start: Stage = .asking, why: Placement.Failure? = nil) {
        _stage = State(initialValue: start)
        _why = State(initialValue: why)
    }

    static func sentence(failed why: Placement.Failure?) -> String {
        // One sentence per reason: the general advice, given for the wrong
        // reason, would have told an owner to drag Moblee over some other
        // app that merely shares its name.
        switch why {
        case .anotherMobleeIsOpen: return "The Moblee in Applications would not close. Close it yourself, then open this one again."
        // (v0.9.4) A repair now refuses a quit as an install does, so this
        // sentence, which is what the owner is shown when the refusal comes
        // back, has to be true of a repair too.
        // (v0.9.5) And of a drop, which refuses a quit for the same reason:
        // something is being written into the wiki this moment. The four are no
        // longer named one by one — "making, updating or repairing a wiki" left
        // a drop out, and naming a fourth would make a sentence nobody reads to
        // the end. "Busy with your wiki" is true of all four and is what the
        // owner needs to know.
        case .otherMobleeIsBusy: return "The Moblee in Applications is busy with your wiki. Let it finish, then open this one again."
        case .somethingElseThere: return "Something else called Moblee is already in Applications. Moblee will work from here."
        default: return "Moblee could not move itself. Nothing was changed. Drag it into Applications in Finder."
        }
    }

    private var sentence: String {
        switch stage {
        case .asking, .moving: return "Moblee should live in Applications, so you can always find it."
        case .askingTheOtherOne: return "Asking the Moblee in Applications to close…"
        case .failed: return Self.sentence(failed: why)
        case .movedButNotOpened: return "Moblee is now in Applications. Open it from there next time."
        }
    }

    /// The move has not been made or refused yet: the big button still offers it.
    private var beforeTheMove: Bool { stage == .asking || stage == .moving || stage == .askingTheOtherOne }
    /// The move is under way, so nothing may be pressed.
    private var busy: Bool { stage == .moving || stage == .askingTheOtherOne }

    var body: some View {
        ScreenFrame(sentence: sentence,
                    buttonTitle: beforeTheMove ? "Move it there" : "Carry on",
                    buttonEnabled: !busy, showsBack: false,
                    quietTitle: stage == .asking ? "Not now" : nil,
                    quietAction: stage == .asking ? { flow.moveSettled() } : nil,
                    action: {
                        guard stage == .asking else { flow.moveSettled(); return }
                        stage = .moving
                        AppDelegate.moving = true      // quitting half-way through would leave a half-made copy
                        let plan = Placement.plan()
                        DispatchQueue.global(qos: .userInitiated).async {
                            let result = Result {
                                try Placement.move(plan, asking: {
                                    DispatchQueue.main.async {
                                        MainActor.assumeIsolated { if stage == .moving { stage = .askingTheOtherOne } }
                                    }
                                })
                            }
                            DispatchQueue.main.async { MainActor.assumeIsolated { finished(result, plan) } }
                        }
                    }) {
            HStack(spacing: Theme.pt(26)) {
                Image(systemName: "books.vertical.fill")
                    .font(Theme.font(76, .medium, .default)).foregroundStyle(Theme.accent)
                // (v0.9.4) The arrow points from Moblee to where it is going,
                // and the three sit in the order they are read, so both turn
                // round together when the layout is mirrored. `arrow.right`
                // went on pointing right there, back the way it came.
                Image(systemName: Layout.onwardsSymbol)
                    .font(Theme.font(40, .semibold, .default)).foregroundStyle(.secondary)
                VStack(spacing: Theme.pt(6)) {
                    Image(systemName: stage == .failed ? "folder.fill.badge.questionmark" : "folder.fill")
                        .font(Theme.font(96, .regular, .default)).foregroundStyle(stage == .failed ? Theme.waiting : Theme.accent)
                    Text("Applications")
                        .font(Theme.font(17, .semibold))
                }
            }
            .accessibilityHidden(true)
        }
    }

    private func finished(_ result: Result<Placement.Outcome, Error>, _ plan: Placement.Plan) {
        switch result {
        case .failure(let error):
            AppDelegate.moving = false
            why = error as? Placement.Failure
            stage = .failed
        case .success(let outcome):
            AppDelegate.moving = false
            let app: URL
            switch outcome { case .moved(let u), .alreadyThere(let u): app = u }
            flow.moveOutcome = outcome
            if plan.reopen { Placement.reopen(app) { stage = .movedButNotOpened } }
            else { flow.moveSettled() }
        }
    }
}
