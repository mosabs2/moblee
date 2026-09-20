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
/// The move copies the app, checks the copy, clears the download mark from
/// the copy (without that the copy would be translocated too), puts the
/// original in the Bin, where it can be got back, and opens the copy.
enum Placement {
    static let appName = "Moblee.app"

    struct Plan {
        var destinationFolder: URL
        var binTheOriginal: Bool
        var reopen: Bool
    }

    /// A practice run can rehearse the move into a scratch folder
    /// (`--move-to <folder>`): everything but the Bin and the reopening.
    static var practiceFolder: URL? {
        let args = Practice.args
        guard let i = args.firstIndex(of: "--move-to"), i + 1 < args.count else { return nil }
        return URL(fileURLWithPath: args[i + 1], isDirectory: true)
    }

    static var running: URL { Bundle.main.bundleURL }

    static func isTranslocated(_ url: URL) -> Bool { url.path.contains("/AppTranslocation/") }

    static func inApplications(_ url: URL) -> Bool {
        let p = url.resolvingSymlinksInPath().path
        let mine = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Applications").path
        return p.hasPrefix("/Applications/") || p.hasPrefix(mine + "/")
    }

    /// Whether to offer the move at all. Never from a build folder, where the
    /// maintainer and the tests run it, and never for something that is not
    /// an app bundle (the bare program run by `swift run`).
    static var shouldOffer: Bool {
        if practiceFolder != nil { return true }
        if Practice.on { return false }
        let url = running
        guard url.pathExtension == "app" else { return false }
        let p = url.path
        if p.contains("/Library/Caches/") || p.contains("/DerivedData/") || p.contains("/.build/") { return false }
        return !inApplications(url)
    }

    /// /Applications for someone who may write there; their own Applications
    /// folder for someone who may not (a standard account). Spotlight and
    /// `open -a Moblee` find both.
    static func plan() -> Plan {
        if let practice = practiceFolder {
            return Plan(destinationFolder: practice, binTheOriginal: false, reopen: false)
        }
        let fm = FileManager.default
        let shared = URL(fileURLWithPath: "/Applications", isDirectory: true)
        let folder = fm.isWritableFile(atPath: shared.path)
            ? shared : fm.homeDirectoryForCurrentUser.appendingPathComponent("Applications", isDirectory: true)
        return Plan(destinationFolder: folder, binTheOriginal: true, reopen: true)
    }

    /// The app as the owner sees it in Finder. A translocated app knows only
    /// its temporary path; the system can say where it really is. The call is
    /// looked up by name so that a Mac without it simply gets no answer, and
    /// then nothing is put in the Bin.
    static func original(of url: URL) -> URL? {
        guard isTranslocated(url) else { return url }
        guard let handle = dlopen("/System/Library/Frameworks/Security.framework/Security", RTLD_LAZY) else { return nil }
        defer { dlclose(handle) }
        guard let symbol = dlsym(handle, "SecTranslocateCreateOriginalPathForURL") else { return nil }
        typealias Call = @convention(c) (CFURL, UnsafeMutablePointer<Unmanaged<CFError>?>?) -> Unmanaged<CFURL>?
        let call = unsafeBitCast(symbol, to: Call.self)
        guard let answer = call(url as CFURL, nil)?.takeRetainedValue() else { return nil }
        let found = answer as URL
        guard !isTranslocated(found), FileManager.default.fileExists(atPath: found.path) else { return nil }
        return found
    }

    enum Failure: Error { case copyIncomplete }

    /// Returns where the app now is. Throws before anything has been put in
    /// the Bin if the copy cannot be made or does not check out.
    static func move(_ plan: Plan) throws -> URL {
        let fm = FileManager.default
        let from = running
        let to = plan.destinationFolder.appendingPathComponent(appName, isDirectory: true)
        try fm.createDirectory(at: plan.destinationFolder, withIntermediateDirectories: true)

        // An older Moblee already there goes to the Bin first (never deleted).
        if fm.fileExists(atPath: to.path) {
            if plan.binTheOriginal { try fm.trashItem(at: to, resultingItemURL: nil) }
            else {
                let aside = plan.destinationFolder.appendingPathComponent("Moblee-before-\(Int(Date().timeIntervalSince1970)).app")
                try fm.moveItem(at: to, to: aside)
            }
        }
        try fm.copyItem(at: from, to: to)

        // The copy must be whole before anything else is touched.
        let program = to.appendingPathComponent("Contents/MacOS/Moblee")
        let ours = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String
        let theirs = (NSDictionary(contentsOf: to.appendingPathComponent("Contents/Info.plist"))?["CFBundleShortVersionString"]) as? String
        guard fm.isExecutableFile(atPath: program.path), ours == theirs else { throw Failure.copyIncomplete }

        clearDownloadMark(to)

        if plan.binTheOriginal, let first = original(of: from), first.path != to.path,
           !inApplications(first), fm.isWritableFile(atPath: first.deletingLastPathComponent().path) {
            try? fm.trashItem(at: first, resultingItemURL: nil)     // a disk image or a locked folder: left where it is
        }
        return to
    }

    /// The mark macOS puts on anything downloaded. Gatekeeper has already
    /// checked this app (it is running), and a copy that kept the mark would
    /// be run from a temporary place like the original was.
    private static func clearDownloadMark(_ app: URL) {
        let name = "com.apple.quarantine"
        removexattr(app.path, name, XATTR_NOFOLLOW)
        if let walk = FileManager.default.enumerator(at: app, includingPropertiesForKeys: nil) {
            for case let item as URL in walk { removexattr(item.path, name, XATTR_NOFOLLOW) }
        }
    }

    static func reopen(_ app: URL) {
        let config = NSWorkspace.OpenConfiguration()
        config.createsNewApplicationInstance = true
        NSWorkspace.shared.openApplication(at: app, configuration: config) { _, _ in
            DispatchQueue.main.async { NSApp.terminate(nil) }
        }
    }
}

/// "Moblee should live in Applications." One button.
struct PlacementScreen: View {
    @EnvironmentObject var flow: Flow
    @State private var failed = false
    @State private var moving = false

    var body: some View {
        ScreenFrame(sentence: failed ? "Moblee could not move itself. Drag it into Applications in Finder."
                                     : "Moblee should live in Applications, so you can always find it.",
                    buttonTitle: failed ? "Carry on" : "Move it there",
                    buttonEnabled: !moving, showsBack: false,
                    quietTitle: failed ? nil : "Not now",
                    quietAction: failed ? nil : { flow.offerMove = false },
                    action: {
                        if failed { flow.offerMove = false; return }
                        moving = true
                        let plan = Placement.plan()
                        DispatchQueue.global(qos: .userInitiated).async {
                            let result = Result { try Placement.move(plan) }
                            DispatchQueue.main.async {
                                MainActor.assumeIsolated {
                                    moving = false
                                    switch result {
                                    case .success(let app):
                                        flow.movedTo = app
                                        if plan.reopen { Placement.reopen(app) } else { flow.offerMove = false }
                                    case .failure:
                                        failed = true
                                    }
                                }
                            }
                        }
                    }) {
            HStack(spacing: 26) {
                Image(systemName: "books.vertical.fill")
                    .font(.system(size: 76, weight: .medium)).foregroundStyle(Theme.accent)
                Image(systemName: "arrow.right")
                    .font(.system(size: 40, weight: .semibold)).foregroundStyle(.secondary)
                VStack(spacing: 6) {
                    Image(systemName: failed ? "folder.fill.badge.questionmark" : "folder.fill")
                        .font(.system(size: 96)).foregroundStyle(failed ? Theme.waiting : Theme.accent)
                    Text("Applications")
                        .font(.system(size: 17, weight: .semibold, design: .rounded))
                }
            }
            .accessibilityHidden(true)
        }
    }
}
