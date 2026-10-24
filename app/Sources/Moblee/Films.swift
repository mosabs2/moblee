import SwiftUI
import AVKit
import CryptoKit

/// (v0.13.0) Two short films a new owner is offered at the end of the install:
/// what Moblee does, and the group's Hub. They are not inside the app, which
/// stays a small download: each is attached to this version's own release on
/// GitHub, fetched when the owner presses it, checked against the exact bytes
/// that were published, kept in the Mac's caches and played in the window.
/// Nothing is fetched unless the owner presses a film, and a film that does not
/// match what was published is never played.
enum Films {
    struct Film: Equatable, Identifiable {
        let id: String          // the file name on the release
        let title: String
        let what: String        // one line under the title
        let seconds: Int
        let bytes: Int
        let sha256: String
    }

    /// The release that shipped this app carries both, under these names. The
    /// release steps attach them (`app/scripts/attach-films.sh`), and the logic
    /// check holds this list to the hashes the films were published with.
    static let all: [Film] = [
        Film(id: "moblee-film-what-moblee-does.mp4", title: "What Moblee does",
             what: "A minute on what your wiki and your assistant do together.",
             seconds: 60, bytes: 26_654_352,
             sha256: "3e0d5da64f80d7e8b6e2b4f1033d0dd18b65b672ae2aa1de797a826708147bfa"),
        Film(id: "moblee-film-the-village-and-the-shelf.mp4", title: "The Village and the Shelf",
             what: "Two minutes on the Hub, where wikis share what they have made.",
             seconds: 128, bytes: 85_197_169,
             sha256: "e6838a4352458360a11aa82e44b29dddbcde48c416c701b2f0379e6cae51370c"),
    ]

    static let offerTitle = "Watch two short films"
    /// What its listen control says: the words, and what pressing them does.
    static let offerSaid = "Watch two short films. A minute on what Moblee does, and two minutes on the Hub. Nothing is fetched until you press one."

    /// The address of a film on the release of this app's own version.
    static func url(for film: Film, version: String) -> URL? {
        guard !version.isEmpty, version.allSatisfy({ $0.isNumber || $0 == "." }) else { return nil }
        return URL(string: "https://github.com/mosabs2/moblee/releases/download/v\(version)/\(film.id)")
    }

    /// Where to look, in order: this version's release, then the newest
    /// release, so a later release that forgot to carry the films still plays
    /// them. Either way the bytes are checked against this list.
    static func urls(for film: Film, version: String) -> [URL] {
        let latest = URL(string: "https://github.com/mosabs2/moblee/releases/latest/download/\(film.id)")
        return [url(for: film, version: version), latest].compactMap { $0 }
    }

    static func cache(home: URL) -> URL {
        home.appendingPathComponent("Library/Caches/moblee-films", isDirectory: true)
    }

    static func megabytes(_ film: Film) -> String { "\(Int((Double(film.bytes) / 1_000_000).rounded())) MB" }

    static func length(_ film: Film) -> String {
        film.seconds < 90 ? "\(Int((Double(film.seconds) / 60).rounded())) minute" : "\(Int((Double(film.seconds) / 60).rounded())) minutes"
    }

    /// The bytes are this film's, and no other's.
    nonisolated static func matches(_ url: URL, _ film: Film) -> Bool {
        guard let data = try? Data(contentsOf: url, options: .mappedIfSafe), data.count == film.bytes else { return false }
        return SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined() == film.sha256
    }
}

/// Fetches one film, or finds it already fetched, and says how far it has got.
///
/// The fingerprint is checked off the main thread: hashing 85 MB on it froze
/// the window for a moment (cold read, 24 October 2026). A file that fails the
/// check is never kept.
@MainActor
final class FilmFetch: NSObject, ObservableObject, URLSessionDownloadDelegate {
    enum State: Equatable { case idle, checking, fetching(Double), ready(URL), failed }
    @Published var state: State = .idle
    private var film: Films.Film?
    private var home: URL = FileManager.default.homeDirectoryForCurrentUser
    private var session: URLSession?
    /// The addresses still to try, this version's release first.
    private var addresses: [URL] = []
    /// Bumped by every begin and stop, so a check or a fetch that finishes after
    /// the owner has moved on never writes its answer over the newer one.
    private var run = 0

    /// `source`, in a practice run, is a folder holding the films: nothing then
    /// goes to the network, and with no folder a practice run fetches nothing.
    func begin(_ film: Films.Film, home: URL, version: String, practice: Bool, source: URL?) {
        stop()
        run += 1
        let mine = run
        self.film = film
        self.home = home
        let kept = Films.cache(home: home).appendingPathComponent(film.id)
        let local = source?.appendingPathComponent(film.id)
        state = .checking
        DispatchQueue.global(qos: .userInitiated).async {
            let cached = FileManager.default.fileExists(atPath: kept.path) && Films.matches(kept, film)
            let fromSource = !cached && practice && local.map { Films.matches($0, film) } == true
            DispatchQueue.main.async {
                MainActor.assumeIsolated {
                    guard mine == self.run else { return }
                    if cached { self.state = .ready(kept); return }
                    if practice {
                        self.state = fromSource ? .ready(local!) : .failed
                        return
                    }
                    self.addresses = Films.urls(for: film, version: version)
                    self.next()
                }
            }
        }
    }

    /// Tries the next address, or says the film could not be fetched.
    private func next() {
        guard !addresses.isEmpty else { state = .failed; return }
        let url = addresses.removeFirst()
        state = .fetching(0)
        let s = URLSession(configuration: .default, delegate: self, delegateQueue: .main)
        session = s
        s.downloadTask(with: url).resume()
    }

    func stop() {
        run += 1
        session?.invalidateAndCancel()
        session = nil
        addresses = []
    }

    nonisolated func urlSession(_ session: URLSession, downloadTask: URLSessionDownloadTask,
                                didWriteData bytesWritten: Int64, totalBytesWritten: Int64,
                                totalBytesExpectedToWrite: Int64) {
        MainActor.assumeIsolated {
            guard session === self.session else { return }
            // A server that gives no length is measured against the film's own size.
            let expected = totalBytesExpectedToWrite > 0 ? Double(totalBytesExpectedToWrite)
                                                         : Double(self.film?.bytes ?? 1)
            self.state = .fetching(min(1, Double(totalBytesWritten) / max(1, expected)))
        }
    }

    nonisolated func urlSession(_ session: URLSession, downloadTask: URLSessionDownloadTask,
                                didFinishDownloadingTo location: URL) {
        // The file at `location` lasts only until this returns, so it is moved
        // into the cache folder here, under a name of its own, and checked after.
        let status = (downloadTask.response as? HTTPURLResponse)?.statusCode ?? 0
        MainActor.assumeIsolated {
            guard session === self.session, let film = self.film else { return }
            guard status == 200 else { self.session = nil; self.next(); return }
            let folder = Films.cache(home: self.home)
            let kept = folder.appendingPathComponent(film.id)
            let incoming = folder.appendingPathComponent(film.id + ".incoming")
            let fm = FileManager.default
            do {
                try fm.createDirectory(at: folder, withIntermediateDirectories: true)
                if fm.fileExists(atPath: incoming.path) { try fm.removeItem(at: incoming) }
                try fm.moveItem(at: location, to: incoming)
            } catch { self.state = .failed; return }
            self.session = nil
            self.state = .checking
            let mine = self.run
            DispatchQueue.global(qos: .userInitiated).async {
                let good = Films.matches(incoming, film)
                var placed = false
                if good {
                    do {
                        if fm.fileExists(atPath: kept.path) {
                            _ = try fm.replaceItemAt(kept, withItemAt: incoming)
                        } else {
                            try fm.moveItem(at: incoming, to: kept)
                        }
                        placed = true
                    } catch { placed = false }
                } else {
                    // Not the film that was published: never kept, never played.
                    try? fm.removeItem(at: incoming)
                }
                DispatchQueue.main.async {
                    MainActor.assumeIsolated {
                        guard mine == self.run else { return }
                        self.state = placed ? .ready(kept) : .failed
                    }
                }
            }
        }
    }

    nonisolated func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
        guard error != nil else { return }
        MainActor.assumeIsolated {
            guard session === self.session else { return }
            self.session = nil
            self.next()
        }
    }
}

/// The two films as two cards, and the one being watched in their place.
struct FilmsPanel: View {
    @ObservedObject private var textSize = TextSize.shared
    @EnvironmentObject var flow: Flow
    @StateObject private var fetch = FilmFetch()
    /// The film being watched, held by the screen so that its own Back button
    /// returns to the two cards: one Back on the screen, never two.
    @Binding var chosen: Films.Film?
    @State private var player: AVPlayer?

    var body: some View {
        Group {
            if let chosen {
                watching(chosen)
            } else {
                HStack(spacing: Theme.pt(16)) {
                    ForEach(Films.all) { film in card(film) }
                }
            }
        }
        .onDisappear { player?.pause(); fetch.stop() }
        .onChange(of: chosen) { _, now in
            if now == nil { player?.pause(); player = nil; fetch.stop(); fetch.state = .idle }
        }
    }

    private func card(_ film: Films.Film) -> some View {
        Button {
            chosen = film
            fetch.begin(film, home: flow.home, version: Self.version, practice: flow.isTestMode, source: flow.filmsSource)
        } label: {
            VStack(alignment: .leading, spacing: Theme.pt(6)) {
                Image(systemName: "play.circle.fill")
                    .font(Theme.font(34, .regular, .default))
                    .foregroundStyle(Theme.accent)
                    .accessibilityHidden(true)
                Text(film.title).font(Theme.font(16, .semibold))
                Text(film.what).font(Theme.font(13)).foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                Text("\(Films.length(film)), \(Films.megabytes(film)) to fetch")
                    .font(Theme.font(12, .medium)).foregroundStyle(.secondary)
            }
            .padding(Theme.pt(16))
            .frame(width: Theme.pt(280), alignment: .topLeading)
            .background(CardBackground(corner: 18))
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("film-" + film.id)
        .accessibilityLabel("\(film.title). \(film.what) \(Films.length(film)).")
    }

    @ViewBuilder
    private func watching(_ film: Films.Film) -> some View {
        VStack(spacing: Theme.pt(10)) {
            switch fetch.state {
            case .idle, .checking, .fetching:
                let part: Double = { if case .fetching(let p) = fetch.state { return p }; return 0 }()
                ProgressView(value: part) {
                    Text(fetch.state == .checking ? "Getting \(film.title) ready" : "Fetching \(film.title)")
                        .font(Theme.font(14, .medium))
                }
                    .frame(width: Theme.pt(420))
            case .ready(let url):
                FilmView(player: player)
                    .frame(width: Theme.pt(560), height: Theme.pt(315))
                    .clipShape(RoundedRectangle(cornerRadius: Theme.pt(12)))
                    .onAppear {
                        let p = AVPlayer(url: url)
                        player = p
                        if !flow.isTestMode { p.play() }
                    }
            case .failed:
                Text(Self.couldNotFetch).font(Theme.font(14, .medium)).foregroundStyle(.secondary)
                    .multilineTextAlignment(.center).frame(width: Theme.pt(460))
            }
        }
    }

    static let couldNotFetch = "The film could not be fetched just now. Nothing is lost: go Back and press it again in a while."

    static var version: String {
        (Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String) ?? ""
    }
}

/// The Mac's own film view, with its usual controls. SwiftUI's `VideoPlayer`
/// is not used: in an app built as this one is, it could not find this view at
/// run time and the app quit the moment a film was pressed (found on screen,
/// 24 October 2026).
struct FilmView: NSViewRepresentable {
    let player: AVPlayer?

    func makeNSView(context: Context) -> AVPlayerView {
        let v = AVPlayerView()
        v.controlsStyle = .floating
        v.player = player
        return v
    }

    func updateNSView(_ v: AVPlayerView, context: Context) {
        if v.player !== player { v.player = player }
    }
}
