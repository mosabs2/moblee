import Foundation

/// Whether a newer Moblee has been published: a returning owner's app asks
/// GitHub's public list of releases, once a day once it has had an answer,
/// and says so in one quiet line if there is one.
///
/// What it does not do matters as much. It never runs during an install (only
/// a wiki that already exists is checked for). It downloads nothing and runs
/// nothing: the line's Download button opens the new version's page in the
/// browser, and macOS checks the signature when the owner opens what they
/// downloaded, exactly as it does today. It sends nothing about the owner: it
/// reads a public page. It never waits on the answer or reports a failure: no
/// network, a slow answer (five seconds) or a reply it cannot read all end the
/// same way, with nothing shown and the app as it always was.
///
/// The one thing taken from the reply is a version number, and only a plain
/// one (digits and dots). The download address is built here from that number,
/// never taken from the reply, so a reply that was tampered with cannot send an
/// owner anywhere but this project's own releases page.
enum NewerRelease {
    static let latestURL = URL(string: "https://api.github.com/repos/mosabs2/moblee/releases/latest")!

    /// Digits and dots, two to four parts of at most four digits each.
    static func isPlainVersion(_ s: String) -> Bool {
        let parts = s.split(separator: ".", omittingEmptySubsequences: false)
        guard (2...4).contains(parts.count) else { return false }
        return parts.allSatisfy { p in !p.isEmpty && p.count <= 4 && p.allSatisfy { $0.isASCII && $0.isNumber } }
    }

    /// A release tag ("v0.9.3", or "0.9.3") as a plain version, or nothing.
    static func version(fromTag tag: String) -> String? {
        let v = tag.hasPrefix("v") ? String(tag.dropFirst()) : tag
        return isPlainVersion(v) ? v : nil
    }

    /// The version in GitHub's answer for the latest release, or nothing.
    /// A draft or a pre-release is never offered, and neither is a release
    /// that does not yet carry the app itself (`Moblee-<version>.zip`), so
    /// Download never opens a file that is not there. Only a yes or no is
    /// taken from the list of files; the address is still built here.
    static func version(fromResponse data: Data) -> String? {
        guard let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let tag = object["tag_name"] as? String else { return nil }
        if (object["draft"] as? Bool) == true || (object["prerelease"] as? Bool) == true { return nil }
        guard let v = version(fromTag: tag) else { return nil }
        let names = (object["assets"] as? [[String: Any]] ?? []).compactMap { $0["name"] as? String }
        return names.contains("Moblee-\(v).zip") ? v : nil
    }

    /// Where a look goes, or nowhere. A released app always asks GitHub. A
    /// practice run asks nobody unless told: `--release-url <url>` asks that
    /// address, `--live-release` asks GitHub. (`--latest <v>` never reaches
    /// here: it stands in for the answer itself.)
    static func source(practice: Bool, args: [String]) -> URL? {
        guard practice else { return latestURL }
        if let i = args.firstIndex(of: "--release-url"), i + 1 < args.count { return URL(string: args[i + 1]) }
        return args.contains("--live-release") ? latestURL : nil
    }

    /// What the Download button opens: the app itself, straight from this
    /// project's releases, so there is no page on which to pick GitHub's
    /// "Source code" archive by mistake. Built only from a plain version.
    static func downloadURL(for version: String) -> URL? {
        guard isPlainVersion(version) else { return nil }
        return URL(string: "https://github.com/mosabs2/moblee/releases/download/v\(version)/Moblee-\(version).zip")
    }

    // MARK: - Remembering, in the owner's own Moblee settings folder

    /// The last answer and the day it was asked for: "2026-09-24 0.9.3".
    static func noteFile(home: URL) -> URL {
        home.appendingPathComponent(".config/moblee/latest-release")
    }

    /// The version the owner said Not now to. A newer one is offered again.
    static func setAsideFile(home: URL) -> URL {
        home.appendingPathComponent(".config/moblee/release-set-aside")
    }

    static func today(_ date: Date = Date()) -> String {
        let f = DateFormatter()
        f.calendar = Calendar(identifier: .gregorian)
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = .current
        f.dateFormat = "yyyy-MM-dd"
        return f.string(from: date)
    }

    /// Today's answer if one was already had today; otherwise nothing, and the
    /// caller asks. Only an answer is noted, so a Mac that was offline (or was
    /// turned away by GitHub) asks again the next time the app is opened: one
    /// small request in the background, with nothing shown if it fails again.
    static func askedToday(home: URL, now: Date = Date()) -> (asked: Bool, version: String?) {
        guard let text = try? String(contentsOf: noteFile(home: home), encoding: .utf8) else { return (false, nil) }
        let parts = text.trimmingCharacters(in: .whitespacesAndNewlines).split(separator: " ").map(String.init)
        guard parts.count == 2, parts[0] == today(now), let v = version(fromTag: parts[1]) else { return (false, nil) }
        return (true, v)
    }

    static func note(home: URL, version: String, now: Date = Date()) {
        guard isPlainVersion(version) else { return }
        let file = noteFile(home: home)
        try? FileManager.default.createDirectory(at: file.deletingLastPathComponent(), withIntermediateDirectories: true)
        try? (today(now) + " " + version + "\n").write(to: file, atomically: true, encoding: .utf8)
    }

    static func setAside(home: URL) -> String? {
        guard let text = try? String(contentsOf: setAsideFile(home: home), encoding: .utf8) else { return nil }
        return version(fromTag: text.trimmingCharacters(in: .whitespacesAndNewlines))
    }

    static func setAside(_ version: String, home: URL) {
        guard isPlainVersion(version) else { return }
        let file = setAsideFile(home: home)
        try? FileManager.default.createDirectory(at: file.deletingLastPathComponent(), withIntermediateDirectories: true)
        try? (version + "\n").write(to: file, atomically: true, encoding: .utf8)
    }

    /// The version to offer, given what GitHub says, this Moblee's own version
    /// and what the owner set aside: only a newer one, and not the one they
    /// already said Not now to.
    static func offer(latest: String?, current: String, setAside: String?) -> String? {
        guard let latest, isPlainVersion(latest), isPlainVersion(current),
              HomeModel.isNewer(latest, than: current) else { return nil }
        if let setAside, !HomeModel.isNewer(latest, than: setAside) { return nil }
        return latest
    }

    // MARK: - Asking

    /// Practice only (`--ask-release`, with `--release-url <url>` to ask some
    /// other address): the same request the app makes, reported as one line,
    /// "release: 0.9.3 in 0.4s" or "release: none in 5.0s", then exit 0.
    @MainActor static func askAndReport() -> Never {
        let source = Flow.value(after: "--release-url", in: Practice.args).flatMap(URL.init(string:)) ?? latestURL
        let started = Date()
        let done = DispatchSemaphore(value: 0)
        let box = ResultBox()
        fetch(from: source) { v in box.value = v; done.signal() }
        done.wait()
        print(String(format: "release: %@ in %.1fs", box.value ?? "none", Date().timeIntervalSince(started)))
        exit(0)
    }

    private final class ResultBox: @unchecked Sendable { var value: String? }

    /// Ask GitHub, off the main thread, and hand back the latest plain version
    /// or nothing. Never throws, never waits more than `timeout` seconds, and
    /// sends no cookies or stored credentials.
    static func fetch(from url: URL = latestURL, timeout: TimeInterval = 5,
                      completion: @escaping @Sendable (String?) -> Void) {
        let config = URLSessionConfiguration.ephemeral
        config.timeoutIntervalForRequest = timeout
        config.timeoutIntervalForResource = timeout
        config.waitsForConnectivity = false
        // A fixed language, so not even the owner's language preference goes.
        config.httpAdditionalHeaders = ["Accept": "application/vnd.github+json", "User-Agent": "Moblee",
                                        "Accept-Language": "en"]
        let session = URLSession(configuration: config)
        session.dataTask(with: url) { data, response, _ in
            defer { session.finishTasksAndInvalidate() }
            guard let data, (response as? HTTPURLResponse)?.statusCode == 200 else { completion(nil); return }
            completion(version(fromResponse: data))
        }.resume()
    }
}
