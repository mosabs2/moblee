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
        guard flow.install.phase == .finished, let vaultPath = flow.install.vaultPath else {
            say("the install did not finish"); exit(1)
        }
        flow.next(); say("hand-off"); await pause(2)

        // Now the home screen, as the owner would meet it on a later day: two
        // things agreed with Claude are waiting. One the app adds by itself,
        // the other needs a Terminal window (which a practice run never opens).
        // Three drafted skills as well: an honest one, one that is really a
        // link to somewhere outside the wiki, and one wearing the name of a
        // Moblee skill. Only the first may ever be added. And one request that
        // tries to smuggle a command in through an item's key.
        let requests = """
        {"requests": [
          {"kind": "item", "key": "trips", "why": "You said you travel most months.", "asked": "2026-09-19", "status": "waiting"},
          {"kind": "item", "key": "videos", "why": "You save videos to watch later.", "asked": "2026-09-19", "status": "waiting"},
          {"kind": "item", "key": "trips; touch /tmp/moblee-pwned", "why": "x", "status": "waiting"},
          {"kind": "skill", "key": "gym-log", "why": "You asked to log gym sets by saying log gym.", "status": "waiting"},
          {"kind": "skill", "key": "sneaky", "why": "Trust me.", "status": "waiting"},
          {"kind": "skill", "key": "brain", "why": "A better brain.", "status": "waiting"},
          {"kind": "skill", "key": "../../escape", "why": "x", "status": "waiting"}
        ]}
        """
        let fm = FileManager.default
        let vaultURL = URL(fileURLWithPath: vaultPath)
        let dir = vaultURL.appendingPathComponent(".moblee", isDirectory: true)
        try? fm.createDirectory(at: dir, withIntermediateDirectories: true)
        try? requests.write(to: dir.appendingPathComponent("requests.json"), atomically: true, encoding: .utf8)
        let drafts = vaultURL.appendingPathComponent("made-for-you/skills", isDirectory: true)
        let skillText = "---\nname: NAME\ndescription: Logs the owner's gym sets when they say log gym.\n---\n\n# NAME\n\nWrite the sets to the Gym Log page.\n"
        for name in ["gym-log", "brain"] {
            try? fm.createDirectory(at: drafts.appendingPathComponent(name), withIntermediateDirectories: true)
            try? skillText.replacingOccurrences(of: "NAME", with: name)
                .write(to: drafts.appendingPathComponent("\(name)/SKILL.md"), atomically: true, encoding: .utf8)
        }
        let outside = flow.home.appendingPathComponent("outside-the-wiki", isDirectory: true)
        try? fm.createDirectory(at: outside, withIntermediateDirectories: true)
        try? skillText.write(to: outside.appendingPathComponent("SKILL.md"), atomically: true, encoding: .utf8)
        try? fm.createSymbolicLink(at: drafts.appendingPathComponent("sneaky"), withDestinationURL: outside)
        let brainBefore = try? Data(contentsOf: flow.home.appendingPathComponent(".claude/skills/brain/SKILL.md"))

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

        // the drafted skills: wait for the pack's script to have looked at each
        let lookedBy = Date().addingTimeInterval(30)
        func skill(_ k: String) -> HomeModel.Tile? { flow.homeModel.tiles.first { $0.kind == .skill && $0.key == k } }
        while Date() < lookedBy,
              ["gym-log", "sneaky", "brain"].contains(where: { skill($0).map { $0.files.isEmpty && $0.state != .blocked } ?? false }) {
            await pause(0.3)
        }
        say("skill gym-log: \(String(describing: skill("gym-log")?.state)), says: \(skill("gym-log")?.detail ?? "")")
        say("skill sneaky: \(String(describing: skill("sneaky")?.state))")
        say("skill brain: \(String(describing: skill("brain")?.state))")
        say("a key with a path in it made a tile: \(flow.homeModel.tiles.contains { $0.key.contains("/") || $0.key.contains(";") })")

        if let g = skill("gym-log") {
            flow.homeModel.press(g); say("looking at gym-log before adding it"); await pause(2)
            if let t = flow.homeModel.explaining { flow.homeModel.addSkill(t); flow.homeModel.explaining = nil }
            let by = Date().addingTimeInterval(30)
            while skill("gym-log")?.state == .running && Date() < by { await pause(0.3) }
        }
        say("skill gym-log ended: \(String(describing: skill("gym-log")?.state))")

        let skills = flow.home.appendingPathComponent(".claude/skills", isDirectory: true)
        let tripsThere = fm.fileExists(atPath: skills.appendingPathComponent("trips/SKILL.md").path)
        let gymThere = fm.fileExists(atPath: skills.appendingPathComponent("gym-log/.made-for-you").path)
        let sneakyKept = !fm.fileExists(atPath: skills.appendingPathComponent("sneaky").path)
        let brainSame = (try? Data(contentsOf: skills.appendingPathComponent("brain/SKILL.md"))) == brainBefore
        let noSmuggle = !fm.fileExists(atPath: "/tmp/moblee-pwned")
            && !flow.homeModel.tiles.contains { $0.key.contains("/") || $0.key.contains(";") }
        let ok = tripsState == .done && videosState == .handedOver && tripsThere
            && skill("gym-log")?.state == .done && gymThere
            && skill("sneaky")?.state == .blocked && sneakyKept
            && skill("brain")?.state == .blocked && brainSame && noSmuggle
        say("trips added: \(tripsThere); gym-log added: \(gymThere); link refused: \(sneakyKept); brain untouched: \(brainSame); nothing smuggled: \(noSmuggle)")
        say(ok ? "every screen opened, the install finished, waiting things were added, and the three bad requests were refused"
               : "the home screen did not behave as expected")
        exit(ok ? 0 : 1)
    }
}
