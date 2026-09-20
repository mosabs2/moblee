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

    enum Failure: Error { case copyIncomplete, somethingElseThere, anotherMobleeIsOpen, markNotCleared }

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

    static func move(_ plan: Plan) throws -> Outcome {
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
            if !newer(ourVersion, than: version(of: to)) { return .alreadyThere(to) }
            // An older one that is open right now cannot be moved from under itself.
            let me = ProcessInfo.processInfo.processIdentifier
            let others = NSRunningApplication.runningApplications(withBundleIdentifier: mine ?? "")
                .filter { $0.processIdentifier != me }
            guard others.isEmpty else { throw Failure.anotherMobleeIsOpen }
        }

        try fm.createDirectory(at: folder, withIntermediateDirectories: true)
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
            let old = folder.appendingPathComponent(".Moblee-outgoing-\(UUID().uuidString.prefix(8)).app", isDirectory: true)
            try fm.moveItem(at: to, to: old)
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
    @EnvironmentObject var flow: Flow
    enum Stage { case asking, moving, failed, movedButNotOpened }
    @State private var stage: Stage = .asking

    private var sentence: String {
        switch stage {
        case .asking, .moving: return "Moblee should live in Applications, so you can always find it."
        case .failed: return "Moblee could not move itself. Nothing was changed. Drag it into Applications in Finder."
        case .movedButNotOpened: return "Moblee is now in Applications. Open it from there next time."
        }
    }

    var body: some View {
        ScreenFrame(sentence: sentence,
                    buttonTitle: stage == .asking || stage == .moving ? "Move it there" : "Carry on",
                    buttonEnabled: stage != .moving, showsBack: false,
                    quietTitle: stage == .asking ? "Not now" : nil,
                    quietAction: stage == .asking ? { flow.moveSettled() } : nil,
                    action: {
                        guard stage == .asking else { flow.moveSettled(); return }
                        stage = .moving
                        let plan = Placement.plan()
                        DispatchQueue.global(qos: .userInitiated).async {
                            let result = Result { try Placement.move(plan) }
                            DispatchQueue.main.async { MainActor.assumeIsolated { finished(result, plan) } }
                        }
                    }) {
            HStack(spacing: 26) {
                Image(systemName: "books.vertical.fill")
                    .font(.system(size: 76, weight: .medium)).foregroundStyle(Theme.accent)
                Image(systemName: "arrow.right")
                    .font(.system(size: 40, weight: .semibold)).foregroundStyle(.secondary)
                VStack(spacing: 6) {
                    Image(systemName: stage == .failed ? "folder.fill.badge.questionmark" : "folder.fill")
                        .font(.system(size: 96)).foregroundStyle(stage == .failed ? Theme.waiting : Theme.accent)
                    Text("Applications")
                        .font(.system(size: 17, weight: .semibold, design: .rounded))
                }
            }
            .accessibilityHidden(true)
        }
    }

    private func finished(_ result: Result<Placement.Outcome, Error>, _ plan: Placement.Plan) {
        switch result {
        case .failure:
            stage = .failed
        case .success(let outcome):
            let app: URL
            switch outcome { case .moved(let u), .alreadyThere(let u): app = u }
            flow.moveOutcome = outcome
            if plan.reopen { Placement.reopen(app) { stage = .movedButNotOpened } }
            else { flow.moveSettled() }
        }
    }
}
