import Foundation

/// The install diary, `~/.config/moblee/install-diary.txt`.
///
/// It is append-only, and it is the one file an owner is told is safe to send
/// when something is wrong: the check-up reads it (`moblee-doctor.py`,
/// `check_diary`) and the app's "Show what happened" puts it on the screen.
/// `scripts/install.sh` and `scripts/update.sh` each keep it while they run.
///
/// Repair is the third thing that changes an owner's Mac, and until now it
/// wrote nothing at all, so a Mac whose guard or skills had been put back
/// carried no record of it. Repair is driven from the app rather than from a
/// script of its own, and the two scripts it runs are also run by the installer
/// and the updater (which already keep the diary themselves, and would then
/// have it written twice). So the app writes these lines, with the scripts'
/// own redaction rules copied exactly.
///
/// REDACTION. A wiki is very often named after its owner, so the wiki's place
/// and the wiki's folder name both become `<wiki>`, and the home folder becomes
/// `~`, before anything is written. An owner's name must never reach this file,
/// and the folder name is the way it would.
enum Diary {
    static func file(home: URL) -> URL {
        home.appendingPathComponent(".config/moblee/install-diary.txt")
    }

    /// The same three substitutions `diary()` makes in `scripts/install.sh` and
    /// `scripts/update.sh`, in the same order: the wiki's place (with and
    /// without the `/private` macOS sometimes puts in front of it), then the
    /// wiki's folder name, then the home folder.
    static func redact(_ text: String, home: URL, vault: URL?) -> String {
        var line = text
        if let vault {
            let place = vault.path
            if !place.isEmpty, place != "/" {
                line = line.replacingOccurrences(of: "/private" + place, with: "<wiki>")
                line = line.replacingOccurrences(of: place, with: "<wiki>")
            }
            let name = vault.lastPathComponent
            if !name.isEmpty, name != "/" {
                line = line.replacingOccurrences(of: name, with: "<wiki>")
            }
        }
        let house = home.path
        if !house.isEmpty, house != "/" {
            line = line.replacingOccurrences(of: "/private" + house, with: "~")
            line = line.replacingOccurrences(of: house, with: "~")
        }
        return line
    }

    private static let stamp: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd HH:mm:ss"
        f.locale = Locale(identifier: "en_GB_POSIX")
        return f
    }()

    /// One line, timestamped and redacted, added to the end. Never throws:
    /// a diary that cannot be written must not stop a repair.
    static func write(_ text: String, home: URL, vault: URL?, now: Date = Date()) {
        let line = stamp.string(from: now) + "  " + redact(text, home: home, vault: vault) + "\n"
        append(line, home: home)
    }

    /// A step's own output, kept as it was printed, each line marked so it
    /// cannot be mistaken for one of the diary's own.
    static func writeOutput(_ output: String, home: URL, vault: URL?, limit: Int = 30) {
        let lines = output.split(separator: "\n", omittingEmptySubsequences: false)
            .map { String($0).trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }
        for l in lines.prefix(limit) { write("    | " + l, home: home, vault: vault) }
        if lines.count > limit {
            write("    | (\(lines.count - limit) more line(s) not kept)", home: home, vault: vault)
        }
    }

    private static func append(_ line: String, home: URL) {
        let url = file(home: home)
        guard let data = line.data(using: .utf8) else { return }
        let fm = FileManager.default
        try? fm.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        if let handle = try? FileHandle(forWritingTo: url) {
            defer { try? handle.close() }
            _ = try? handle.seekToEnd()
            try? handle.write(contentsOf: data)
        } else {
            try? data.write(to: url)
        }
    }
}
