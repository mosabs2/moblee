import Foundation

/// (0.15.1) The one comparison of dotted version numbers: 0.10.0 is newer than
/// 0.9.6, compared number by number and not as text. Until 0.15.1 there were
/// three copies of it (the home screen's, the move to Applications' and the
/// updater's), and they did not agree on a part that is not a number.
enum Versions {
    /// Whether `a` is newer than `b`. A part that is not a plain number counts
    /// as 0, so a version read from a wiki's own files never stops a screen;
    /// `strict` refuses instead, for the updater, which never installs on a guess.
    static func newer(_ a: String, than b: String, strict: Bool = false) -> Bool {
        let pa = a.split(separator: ".").map { Int($0) }
        let pb = b.split(separator: ".").map { Int($0) }
        if strict && (pa.isEmpty || pb.isEmpty || pa.contains(nil) || pb.contains(nil)) { return false }
        for i in 0..<max(pa.count, pb.count) {
            let x = i < pa.count ? pa[i] ?? 0 : 0, y = i < pb.count ? pb[i] ?? 0 : 0
            if x != y { return x > y }
        }
        return false
    }
}
