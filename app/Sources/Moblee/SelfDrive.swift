import SwiftUI

/// `--self-drive` (only with `--home <practice folder>`) opens the real window
/// and walks through every screen by itself, doing a real install into the
/// practice home folder on the way, then quits. Exit code 0 means every screen
/// opened and the install finished; a crash or a failed install is non-zero.
///
/// The picture-file drawing and the rehearsal never open a window, so they
/// cannot catch a fault that only happens while SwiftUI is drawing live
/// screens. This does. It is run before the app is ever put in front of a
/// person.
@MainActor
enum SelfDrive {
    static var asked: Bool { CommandLine.arguments.contains("--self-drive") }

    static func run(_ flow: Flow) async {
        guard flow.isTestMode else {
            print("--self-drive only runs with --home <practice folder>; nothing was done.")
            exit(2)
        }
        func say(_ s: String) { print("self-drive: \(s)"); fflush(stdout) }
        func pause(_ seconds: Double) async {
            try? await Task.sleep(nanoseconds: UInt64(seconds * 1_000_000_000))
        }

        say("welcome"); await pause(1.5)
        flow.next(); say("check-up"); await pause(7)      // long enough for two re-looks
        flow.next(); say("name"); await pause(1)
        flow.ownerName = "Tom & Sam"; await pause(1)
        flow.back(); say("back to check-up"); await pause(4)
        flow.next(); say("name again"); await pause(1)
        flow.next(); say("build")

        let deadline = Date().addingTimeInterval(180)
        while (flow.install.phase == .idle || flow.install.phase == .running) && Date() < deadline {
            await pause(0.2)
        }
        say("build ended: \(flow.install.phase)")
        await pause(1.5)
        flow.next(); say("hand-off"); await pause(2)

        guard flow.install.phase == .finished, let vaultPath = flow.install.vaultPath else {
            say("the install did not finish"); exit(1)
        }

        // Now the home screen, as the owner would meet it on a later day: two
        // things agreed with Claude are waiting. One the app adds by itself,
        // the other needs a Terminal window (which a practice run never opens).
        let requests = """
        {"requests": [
          {"kind": "item", "key": "trips", "why": "You said you travel most months.", "asked": "2026-09-19", "status": "waiting"},
          {"kind": "item", "key": "videos", "why": "You save videos to watch later.", "asked": "2026-09-19", "status": "waiting"}
        ]}
        """
        let dir = URL(fileURLWithPath: vaultPath).appendingPathComponent(".moblee", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        try? requests.write(to: dir.appendingPathComponent("requests.json"), atomically: true, encoding: .utf8)

        flow.homeModel.load(home: flow.home, bundledPack: flow.bundledPack)
        flow.mode = .home
        say("home")
        let loadBy = Date().addingTimeInterval(30)
        while !flow.homeModel.loaded && Date() < loadBy { await pause(0.2) }
        await pause(1.5)
        say("tiles waiting: \(flow.homeModel.tiles.map(\.key).joined(separator: ", "))")

        guard let trips = flow.homeModel.tiles.first(where: { $0.key == "trips" }),
              let videos = flow.homeModel.tiles.first(where: { $0.key == "videos" }) else {
            say("the waiting tiles did not appear"); exit(1)
        }
        flow.homeModel.press(trips); say("pressed Add on trips")
        let addBy = Date().addingTimeInterval(120)
        while flow.homeModel.tiles.first(where: { $0.key == "trips" })?.state == .running && Date() < addBy {
            await pause(0.3)
        }
        let tripsState = flow.homeModel.tiles.first(where: { $0.key == "trips" })?.state
        say("trips ended: \(String(describing: tripsState))")

        flow.homeModel.press(videos); say("explaining the Terminal window"); await pause(2)
        if let t = flow.homeModel.explaining { flow.homeModel.openTerminal(for: t); flow.homeModel.explaining = nil }
        await pause(1.5)
        let videosState = flow.homeModel.tiles.first(where: { $0.key == "videos" })?.state
        say("videos ended: \(String(describing: videosState))")

        let skillThere = FileManager.default.fileExists(
            atPath: flow.home.appendingPathComponent(".claude/skills/trips/SKILL.md").path)
        let ok = tripsState == .done && videosState == .handedOver && skillThere
        say(ok ? "every screen opened, the install finished, and a waiting item was added"
               : "the home screen did not behave as expected")
        exit(ok ? 0 : 1)
    }
}
