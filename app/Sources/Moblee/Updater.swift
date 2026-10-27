import Foundation
import Sparkle

/// (v0.15.0) Moblee updates itself.
///
/// THE FAULT THIS EXISTS FOR. Until 0.14 the newer-version line opened the new
/// zip in the browser and left the rest to the owner: unzip it, find the new
/// app, put it where the old one was, open it. On 27 October 2026 an owner did
/// exactly that over 0.12 and saw the old screen: the old Moblee was still open,
/// so macOS brought it forward instead of starting the new copy, and the new
/// copy sat in Downloads beside the old one in Applications. Every ordinary Mac
/// app avoids this with an updater that replaces itself; Moblee now has one.
///
/// Sparkle, pinned in Package.swift, does the work: it reads the list of
/// releases (the "appcast", published beside each release's zip), shows what
/// is new, and on Install downloads the zip, checks it, replaces the app
/// wherever it lives and opens the new one. The owner presses one button.
///
/// THE SAFEGUARDS, from the plan of 23 September 2026 (the wiki's Moblee
/// Auto-Update Plan). An updater is a standing road from the maintainer's
/// account to every owner's Mac, so it is fenced:
///
///   1. A signature only the maintainer's Mac can make. Every zip, and the
///      appcast itself, is signed with an EdDSA key kept in the maintainer's
///      keychain; the public half is in Info.plist (SUPublicEDKey). The zip is
///      checked BEFORE it is unpacked (SUVerifyUpdateBeforeExtraction) and an
///      unsigned or tampered appcast is refused (SURequireSignedFeed), so
///      someone who took over the GitHub account alone can neither offer a
///      false update nor rewrite the list. The new app must also carry a
///      valid Apple signature, since this one does. (Sparkle on its own would
///      take EITHER a matching Apple signature OR the update key, to allow a
///      key to be changed; the two settings above make the key the gate.)
///   2. Never backwards. Sparkle offers only newer versions, and
///      `shouldProceedWithUpdate` below refuses anything that is not newer in
///      both numbers, said out loud, whatever the appcast claims.
///   3. A way to stop a release that has gone out: `app/scripts/withdraw-release.sh`
///      marks it a pre-release, so GitHub's "latest" and its appcast fall back
///      to the release before, and nobody not yet updated is offered it.
///   4. The private key never leaves the keychain: `generate_appcast` reads it
///      there, nothing writes it to a file, and the release script refuses to
///      run if a key-shaped file is in the repository.
///
/// It never checks by itself (SUEnableAutomaticChecks is off). The owner asks,
/// by pressing Install on the newer-version line, which appears only on the
/// ordinary home screen and never during an install, an update or a repair,
/// or by "Check for Updates…" in the Moblee menu. Replacing the app needs it to
/// quit, and a quit is refused while work is running (`AppDelegate.busyForQuit`),
/// so an update can never cut a build, a repair, a drop, an item being added,
/// Look again or a Hub send in half.
@MainActor
final class Updater: NSObject, SPUUpdaterDelegate {
    static let shared = Updater()

    /// A practice run's own appcast (`--sparkle-feed <url>`), for the update
    /// test against a local copy. A released app always reads Info.plist's.
    let practiceFeed: String?
    private var controller: SPUStandardUpdaterController?

    private override init() {
        practiceFeed = Flow.value(after: "--sparkle-feed", in: Practice.args)
        super.init()
    }

    /// Made at launch, so that an update downloaded earlier and waiting to be
    /// put in place is finished. It checks nothing by itself.
    func start() {
        guard controller == nil else { return }
        controller = SPUStandardUpdaterController(startingUpdater: true, updaterDelegate: self, userDriverDelegate: nil)
    }

    /// The owner asked: look for a newer Moblee and, on their Install, put it in place.
    /// (0.15.1) A practice run looks only at its own list (`--sparkle-feed`) and
    /// otherwise at nothing. The guard is here, where every way in arrives:
    /// until 0.15.1 the Install button had it and the menu item did not, so a
    /// practice run's "Check for Updates…" read the real list on GitHub.
    func checkForUpdates() {
        guard !Practice.on || practiceFeed != nil else { return }
        start()
        controller?.checkForUpdates(nil)
    }

    // MARK: - SPUUpdaterDelegate

    nonisolated func feedURLString(for updater: SPUUpdater) -> String? {
        MainActor.assumeIsolated { practiceFeed }
    }

    /// Safeguard 2: never backwards. Both numbers must be newer than this app's:
    /// the build number Sparkle compares (CFBundleVersion) and the version the
    /// owner reads (CFBundleShortVersionString).
    nonisolated func updater(_ updater: SPUUpdater, shouldProceedWithUpdate updateItem: SUAppcastItem,
                             updateCheck: SPUUpdateCheck) throws {
        let info = Bundle.main.infoDictionary ?? [:]
        let ourBuild = Int(info["CFBundleVersion"] as? String ?? "") ?? 0
        let ourVersion = info["CFBundleShortVersionString"] as? String ?? "0"
        let theirBuild = Int(updateItem.versionString) ?? 0
        let theirVersion = updateItem.displayVersionString
        if !Updater.isNewer(build: theirBuild, version: theirVersion, than: ourBuild, ourVersion) {
            throw NSError(domain: "Moblee", code: 1, userInfo: [NSLocalizedDescriptionKey:
                "Moblee \(theirVersion) is not newer than this Moblee (\(ourVersion)), so it was not installed. Moblee never goes back to an older version."])
        }
    }

    /// Newer only if the build number is higher AND the version reads higher.
    nonisolated static func isNewer(build: Int, version: String, than ourBuild: Int, _ ourVersion: String) -> Bool {
        build > ourBuild && Versions.newer(version, than: ourVersion, strict: true)
    }
}
