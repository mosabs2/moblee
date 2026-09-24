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
    static var asked: Bool { Practice.args.contains("--self-drive") }

    static func run(_ flow: Flow) async {
        guard flow.isTestMode else {
            print("--self-drive only runs with --home <practice folder>; nothing was done.")
            exit(2)
        }
        func say(_ s: String) { print("self-drive: \(s)"); fflush(stdout) }
        func pause(_ seconds: Double) async {
            try? await Task.sleep(nanoseconds: UInt64(seconds * 1_000_000_000))
        }

        // The controls themselves are pressed, with real mouse and key events
        // put into the app's own event queue: the big button by clicking where
        // it is drawn, the name by typing it, Return by pressing Return. A
        // button that draws but does not work, or a key that does two things,
        // fails here. (Added 20 September 2026: until then this walk drove the
        // model from the inside and never touched a control.)
        // macOS slows an app it judges to be in the background (App Nap), and a
        // window covered by another app's stops drawing its slides between
        // screens. The app that starts this test is usually in front of it, so
        // a screen could still be half-way in when the walk tapped where its
        // cards would be. For the length of the walk the app says it is doing
        // something the user asked for, and its window is kept in front of the
        // others whether or not macOS lets the app become the active one.
        let awake = ProcessInfo.processInfo.beginActivity(
            options: [.userInitiated, .latencyCritical], reason: "Moblee's self-drive test")
        defer { ProcessInfo.processInfo.endActivity(awake) }
        NSApp.activate(ignoringOtherApps: true)
        await pause(1.0)
        guard let window = NSApp.windows.first(where: { $0.isVisible }) else { say("no window opened"); exit(1) }
        window.level = .floating
        window.orderFrontRegardless()
        window.makeKeyAndOrderFront(nil)
        let bigButton = CGPoint(x: window.frame.width / 2, y: 73)     // window coordinates, from the bottom left

        func click(_ p: CGPoint) {
            for type in [NSEvent.EventType.leftMouseDown, .leftMouseUp] {
                if let e = NSEvent.mouseEvent(with: type, location: p, modifierFlags: [],
                                              timestamp: ProcessInfo.processInfo.systemUptime,
                                              windowNumber: window.windowNumber, context: nil,
                                              eventNumber: 0, clickCount: 1, pressure: type == .leftMouseDown ? 1 : 0) {
                    NSApp.postEvent(e, atStart: false)
                }
            }
        }
        func key(_ chars: String, code: UInt16 = 0) {
            for type in [NSEvent.EventType.keyDown, .keyUp] {
                if let e = NSEvent.keyEvent(with: type, location: .zero, modifierFlags: [],
                                            timestamp: ProcessInfo.processInfo.systemUptime,
                                            windowNumber: window.windowNumber, context: nil,
                                            characters: chars, charactersIgnoringModifiers: chars,
                                            isARepeat: false, keyCode: code) {
                    NSApp.postEvent(e, atStart: false)
                }
            }
        }
        func expect(_ what: String, within seconds: Double = 3, _ test: () -> Bool) async {
            let by = Date().addingTimeInterval(seconds)
            while !test() && Date() < by { await pause(0.1) }
            if !test() { say("FAILED: \(what)"); exit(1) }
            say("ok: \(what)")
        }
        /// Where a small control is drawn right now, as the control itself
        /// recorded it (`DrawnAt`, practice runs only), turned into the window
        /// coordinates a click needs (from the bottom left). Nothing if it is
        /// not on the screen.
        func control(_ id: String) -> CGPoint? {
            guard let r = DrawnPlaces.frames[id], r.width > 0, let content = window.contentView else { return nil }
            return CGPoint(x: r.midX, y: content.bounds.height - r.midY)
        }

        // Started with --move-to <practice folder>, the app first offers to move
        // itself to Applications, as it does when opened from Downloads. This
        // is a short run of its own, made from a scratch copy of the app that
        // the test script has put in a pretend Downloads: the real button is
        // pressed and the run ends there, because a moved app goes on living in
        // a bundle that is now in the Bin, which the real app never does (it
        // reopens from Applications). The test script reads the folders after.
        // Everything is the real code but the Mac's own Bin (a scratch folder
        // stands in) and the reopening.
        if let folder = Placement.practiceFolder {
            await expect("opened outside Applications, the app offers to move itself first") { flow.offerMove }
            await expect("and nothing else has started behind the offer") { !flow.homeModel.loaded && flow.install.phase == .idle }
            say("move to Applications"); await pause(1.0)
            click(bigButton)
            if Placement.practiceBreak != nil {
                // The new copy is made to fail its check. The screen must stay,
                // say so, and leave everything as it was; Carry on then goes on.
                await pause(6)
                await expect("a copy that fails its check is not called a move") { flow.offerMove && flow.moveOutcome == nil }
                click(bigButton)             // "Carry on"
                await expect("Carry on goes on to the welcome screen") { !flow.offerMove && flow.step == .welcome }
                say("the broken move changed nothing and the app carried on"); exit(0)
            }
            await expect("clicking Move it there settles where Moblee lives and carries on", within: 60) {
                !flow.offerMove && flow.moveOutcome != nil
            }
            let there = folder.appendingPathComponent("Moblee.app", isDirectory: true)
            say(flow.moveOutcome == .moved(there) ? "moved" : "already there, and that one is used"); exit(0)
        }

        say("welcome"); await pause(1.5)
        click(bigButton)
        await expect("clicking Start opens the check-up") { flow.step == .checkup }
        say("check-up"); await pause(7)      // long enough for two re-looks
        click(bigButton)
        await expect("clicking Next opens the name screen") { flow.step == .name }
        say("name"); await pause(1.0)
        click(bigButton)                     // the button is greyed out until a name is typed
        await pause(0.8)
        await expect("a greyed-out Next does nothing") { flow.step == .name }
        // Typed letters go to whichever app has the keyboard. If the person at
        // the Mac clicked elsewhere while this was running, they never arrive
        // (seen once, 20 September 2026), so the keyboard is taken back first.
        // Asked for until it is really had: macOS may not hand the keyboard over
        // at once to an app started from a script, least of all straight after
        // another copy of it has just quit (seen on the mini the same day).
        let keyboardBy = Date().addingTimeInterval(10)
        repeat {
            NSRunningApplication.current.activate(options: [.activateAllWindows])
            NSApp.activate(ignoringOtherApps: true)
            window.makeKeyAndOrderFront(nil)
            await pause(0.5)
        } while !(NSApp.isActive && window.isKeyWindow) && Date() < keyboardBy
        say(NSApp.isActive && window.isKeyWindow ? "has the keyboard" : "was not given the keyboard within ten seconds")
        // The box takes the typing by itself when its screen appears in front.
        // If the screen appeared while another app was in front it does not,
        // and a person would click in the box; so the box is found where it is
        // drawn and clicked, with the same real mouse events as the buttons.
        func editableBox(in view: NSView?) -> NSTextField? {
            guard let view else { return nil }
            if let field = view as? NSTextField, field.isEditable { return field }
            for sub in view.subviews { if let found = editableBox(in: sub) { return found } }
            return nil
        }
        if let box = editableBox(in: window.contentView) {
            let r = box.convert(box.bounds, to: nil)
            click(CGPoint(x: r.midX, y: r.midY)); await pause(0.4)
            say("clicked in the name box")
        } else {
            say("the name box was not found on the screen")
        }
        for ch in "Tom & Sam" { key(String(ch)); await pause(0.05) }
        await expect("typing reaches the name box") { flow.ownerName == "Tom & Sam" }
        flow.back(); say("back to check-up"); await pause(4)
        flow.next(); say("name again"); await pause(1)
        await expect("the name is still there after going back") { flow.ownerName == "Tom & Sam" }
        key("\r", code: 36)                  // Return
        await pause(1.5)
        await expect("Return moves on exactly one screen, to the question of which assistant") { flow.step == .assistant }
        say("assistant"); await pause(1.0)
        await expect("nothing is chosen for the owner beforehand") { flow.assistant == nil }
        click(bigButton)                     // greyed out until one of the three is tapped
        await pause(0.8)
        say("after the greyed-out Next: step \(flow.step), chosen \(String(describing: flow.assistant))")
        await expect("a greyed-out Next does nothing on the question either") { flow.step == .assistant && flow.assistant == nil }
        // The three choices are drawn side by side in the middle of the window:
        // cards 170 wide with 22 between them, so their centres are 192 apart,
        // Claude's on the left. The middle of the picture area is 269 up from
        // the bottom when the sentence takes one line; a card is 236 tall, so
        // there is room to spare either way.
        let claudeCard = CGPoint(x: window.frame.width / 2 - 192, y: 269)
        // A window that is not the key window takes its first click as "come
        // to the front" and gives the card nothing, which is ordinary macOS
        // behaviour and not a fault in the screen. Another app can take the
        // front at any moment while this runs (the one that started the test
        // does, each time it prints), so the front is taken back and the tap
        // made again, and the log says how many taps it took.
        var taps = 0
        while flow.assistant != .claude && taps < 4 {
            if !window.isKeyWindow {
                NSApp.activate(ignoringOtherApps: true)
                window.makeKeyAndOrderFront(nil)
                await pause(0.6)
            }
            click(claudeCard); taps += 1
            await pause(0.8)
            if flow.assistant != .claude {
                say("tap \(taps) did not reach the card: key window \(window.isKeyWindow), app active \(NSApp.isActive), " +
                    "window seen \(window.occlusionState.contains(.visible)), step \(flow.step)")
            }
        }
        say("the Claude card took \(taps) tap(s)")
        if flow.assistant != .claude && !NSApp.isActive {
            // macOS decides which app may be in front, and refuses one that the
            // person at the Mac did not bring forward while they are using
            // another. A window that is not in front takes a click as "come
            // forward" and passes nothing to its controls, so the rest of the
            // walk would fail for a reason that is not the app's. That is said
            // plainly, with its own exit code, and is never counted as a pass.
            say("NOT RUN: macOS would not let this window come to the front, because another app is being used. " +
                "The walk stopped at the question of which assistant; nothing is known to be wrong with the app. " +
                "Run the test again when nobody is using the Mac.")
            exit(3)
        }
        await expect("tapping the Claude card answers the question") { flow.assistant == .claude }
        await pause(0.6)
        click(bigButton)                     // Next, now that it is live
        await expect("clicking Next after answering opens the promise") { flow.step == .promise }
        say("promise"); await pause(1.0)
        click(bigButton)
        await expect("clicking Make it starts the build") { flow.step == .build }
        say("build")

        let deadline = Date().addingTimeInterval(180)
        while (flow.install.phase == .idle || flow.install.phase == .running) && Date() < deadline {
            await pause(0.2)
        }
        say("build ended: \(flow.install.phase)")
        await pause(1.5)
        guard flow.install.phase == .finished, let vaultPath = flow.install.vaultPath else {
            say("the install did not finish"); exit(1)
        }
        await expect("the answer went to the installer as --assistant claude") {
            let a = flow.install.lastArguments
            guard let i = a.firstIndex(of: "--assistant"), i + 1 < a.count else { return false }
            return a[i + 1] == "claude" && a.contains { $0.hasSuffix("scripts/install.sh") }
        }
        await expect("the installer kept the answer on record") { Assistant.stored(home: flow.home) == .claude }
        await expect("an install for Claude asks for no Trust step") {
            !flow.install.trustNeeded && !Trust.pending(home: flow.home)
        }
        click(bigButton)
        await expect("clicking Next after the build opens the hand-off") { flow.step == .handoff }
        say("hand-off"); await pause(2)

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
          {"kind": "item", "key": "google", "why": "Your calendar lives in Google.", "asked": "2026-09-20", "status": "waiting"},
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

        // The note that tells Claude and the check-up where the Moblee folder is,
        // left pointing somewhere stale, as it was on a fresh account after a
        // newer build was opened: the app must put it right by itself.
        let pointer = flow.home.appendingPathComponent(".config/moblee/package-path")
        try? "/somewhere/an/older/moblee/was\n".write(to: pointer, atomically: true, encoding: .utf8)

        // The test starts this walk with --latest 99.0.0, standing in for GitHub
        // saying a newer Moblee is out. Through the whole install it must not
        // have been looked for: an install never shows or waits on it.
        let installOffered = flow.homeModel.newerRelease
        say("an install looked for a newer Moblee: \(installOffered != nil)")

        flow.homeModel.load(home: flow.home, bundledPack: flow.bundledPack)
        flow.mode = .home
        say("home")
        let loadBy = Date().addingTimeInterval(30)
        while !flow.homeModel.loaded && Date() < loadBy { await pause(0.2) }
        await pause(1.5)
        say("tiles waiting: \(flow.homeModel.tiles.map(\.key).joined(separator: ", "))")
        await expect("at home the wiki is known to be for Claude, and an update would ask nothing") {
            flow.homeModel.assistant == .claude && !Assistant.mustAsk(home: flow.home) && !flow.homeModel.trustPending
        }

        guard flow.homeModel.tiles.contains(where: { $0.key == "trips" }),
              flow.homeModel.tiles.contains(where: { $0.key == "videos" }) else {
            say("the waiting tiles did not appear"); exit(1)
        }
        // The big button adds the next thing, and it is pressed for real.
        await expect("the big button offers the first thing, trips") { flow.homeModel.nextTile?.key == "trips" }
        click(bigButton); say("clicked the big button (Add the first one)")
        await expect("the click started adding trips", within: 5) {
            let s = flow.homeModel.tiles.first(where: { $0.key == "trips" })?.state
            return s == .running || s == .done
        }
        let addBy = Date().addingTimeInterval(120)
        while flow.homeModel.tiles.first(where: { $0.key == "trips" })?.state == .running && Date() < addBy {
            await pause(0.3)
        }
        let tripsState = flow.homeModel.tiles.first(where: { $0.key == "trips" })?.state
        say("trips ended: \(String(describing: tripsState))")

        await expect("the big button moves on to videos") { flow.homeModel.nextTile?.key == "videos" }
        click(bigButton); say("explaining the Terminal window")
        await expect("the click opened the explanation first, and nothing else") { flow.homeModel.explaining?.key == "videos" }
        await pause(1.0)
        click(bigButton)                      // "Open it"
        await expect("Open it hands the item over") {
            flow.homeModel.tiles.first(where: { $0.key == "videos" })?.state == .handedOver
        }
        let videosState = flow.homeModel.tiles.first(where: { $0.key == "videos" })?.state
        say("videos ended: \(String(describing: videosState))")

        // Clicks inside Claude (Google): the owner must be shown where to go,
        // what to switch on by name and how to tell it worked, and must be able
        // to say Done afterwards, since nothing outside Claude can see those
        // connections. On the first stranger's run the tile said none of this
        // and could never finish. (Done is pressed through the model here: the
        // small button's place on the tile is not fixed.)
        await expect("the big button moves on to Google") { flow.homeModel.nextTile?.key == "google" }
        click(bigButton); say("explaining the clicks inside Claude")
        await expect("the three cards are the pack's own: where, what by name, how to tell it worked") {
            guard let t = flow.homeModel.explaining, t.key == "google", t.steps.count == 3 else { return false }
            return t.steps[1][1].contains("Gmail") && t.steps[2][1].contains("calendar")
        }
        await pause(1.0)
        click(bigButton)                      // "Show me"
        await expect("Show me hands the item over") {
            flow.homeModel.tiles.first(where: { $0.key == "google" })?.state == .handedOver
        }
        if let g = flow.homeModel.tiles.first(where: { $0.key == "google" }) { flow.homeModel.markDone(g) }
        // Then the home screen is read afresh, as it is when Moblee is next
        // opened: the tile must come back as done from the owner's saved word
        // alone, since nothing else can ever say so for clicks inside Claude.
        if let i = flow.homeModel.tiles.firstIndex(where: { $0.key == "google" }) { flow.homeModel.tiles[i].state = .waiting }
        await pause(5)                        // longer than one re-read of the requests
        await expect("read afresh, the Google tile is still done, from the owner's word alone") {
            flow.homeModel.tiles.first(where: { $0.key == "google" })?.state == .done
        }
        let googleState = flow.homeModel.tiles.first(where: { $0.key == "google" })?.state
        say("google ended: \(String(describing: googleState))")

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

        await expect("the big button moves on to the drafted skill") { flow.homeModel.nextTile?.key == "gym-log" }
        click(bigButton); say("looking at gym-log before adding it")
        await expect("the skill is shown first, the whole of it, and nothing is added yet", within: 10) {
            flow.homeModel.explaining?.key == "gym-log"
                && (flow.homeModel.explaining?.body.contains("Write the sets to the Gym Log page") ?? false)
                && !fm.fileExists(atPath: flow.home.appendingPathComponent(".claude/skills/gym-log").path)
        }
        await pause(1.0)
        click(bigButton)                      // "Add it"
        let by = Date().addingTimeInterval(30)
        while skill("gym-log")?.state != .done && Date() < by { await pause(0.3) }
        say("skill gym-log ended: \(String(describing: skill("gym-log")?.state))")

        let pointsAt = ((try? String(contentsOf: pointer, encoding: .utf8)) ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        let pointerRight = pointsAt.contains("Application Support/Moblee/pack-")
            && fm.fileExists(atPath: pointsAt + "/scripts/moblee-doctor.py")
        say("the note of where Moblee is was put right: \(pointerRight)")

        // A guard that is switched on but is an older copy than this Moblee's:
        // the app must say so, and its Repair button, really pressed, must bring
        // it level (the old one is kept in the backups folder by the pack).
        let installedGuard = flow.home.appendingPathComponent(".claude/hooks/bash-guard.py")
        let packGuard = URL(fileURLWithPath: pointsAt + "/safety/bash-guard.py")
        if let h = try? FileHandle(forWritingTo: installedGuard) {
            h.seekToEndOfFile(); h.write("\n# an older guard\n".data(using: .utf8)!); try? h.close()
        }
        flow.homeModel.checkSafety()
        await expect("a guard that is on but older than this Moblee's is noticed") {
            flow.homeModel.guardStale && flow.homeModel.needsRepair
        }
        // "Not now" sets such a repair aside for this opening of the app, so an
        // owner who changed their guard on purpose can still reach their tiles.
        flow.homeModel.repairSetAside = true
        await expect("Not now sets a repair about differing copies aside") { !flow.homeModel.needsRepair }
        flow.homeModel.repairSetAside = false
        await expect("and it is offered again when not set aside") { flow.homeModel.needsRepair }
        await pause(1.0)
        click(bigButton)                      // "Repair"
        await expect("pressing Repair brings the guard level", within: 60) {
            !flow.homeModel.needsRepair && (try? Data(contentsOf: installedGuard)) == (try? Data(contentsOf: packGuard))
        }
        let guardLevel = !flow.homeModel.needsRepair
        say("stale guard repaired: \(guardLevel)")

        // The other way round: the wiki was updated by a NEWER Moblee than this
        // app, and this app is an old copy the owner happened to open. Its guard
        // and skills are the older ones. It must not offer to "repair" with them,
        // and must not point the note of where Moblee is at its own, older folder.
        try? "9.9.9\n".write(to: vaultURL.appendingPathComponent("VERSION"), atomically: true, encoding: .utf8)
        try? "/where/the/newer/moblee/lives\n".write(to: pointer, atomically: true, encoding: .utf8)
        if let h = try? FileHandle(forWritingTo: installedGuard) {
            h.seekToEndOfFile(); h.write("\n# a newer guard than this app carries\n".data(using: .utf8)!); try? h.close()
        }
        flow.homeModel.load(home: flow.home, bundledPack: flow.bundledPack)
        await pause(5)
        let newerLeftAlone = !flow.homeModel.needsRepair && !flow.homeModel.guardStale && !flow.homeModel.updateAvailable
            && ((try? String(contentsOf: pointer, encoding: .utf8)) ?? "").contains("/where/the/newer/moblee/lives")
        say("a wiki newer than this app is left alone (no repair with older copies, note not re-pointed): \(newerLeftAlone)")
        // the practice home put back as it was, for the checks the test script makes afterwards
        try? (flow.homeModel.packVersion + "\n").write(to: vaultURL.appendingPathComponent("VERSION"), atomically: true, encoding: .utf8)
        try? (pointsAt + "\n").write(to: pointer, atomically: true, encoding: .utf8)
        if let level = try? Data(contentsOf: packGuard) { try? level.write(to: installedGuard) }

        // (v0.9.3) The line saying a newer Moblee is out, on the real window.
        // The home screen is loaded again over the put-back wiki, found by
        // its controls, and its Not now pressed for real.
        flow.homeModel.load(home: flow.home, bundledPack: flow.bundledPack)
        let reloadBy = Date().addingTimeInterval(30)
        while !flow.homeModel.loaded && Date() < reloadBy { await pause(0.2) }
        await expect("at home, a newer Moblee is offered, and the install before it never looked") {
            flow.homeModel.newerRelease == "99.0.0" && installOffered == nil
        }
        await pause(1.0)
        if control("download-newer") == nil {
            // Which small controls are drawn, and a picture of the window, so
            // a failure here says whether the line was missing or merely not found.
            say("small controls drawn: \(DrawnPlaces.frames.keys.sorted().joined(separator: ", "))")
            if let view = window.contentView, let rep = view.bitmapImageRepForCachingDisplay(in: view.bounds) {
                view.cacheDisplay(in: view.bounds, to: rep)
                let file = flow.home.appendingPathComponent("home-at-release-line.png")
                try? rep.representation(using: .png, properties: [:])?.write(to: file)
                say("picture of the window: \(file.path)")
            }
        }
        await expect("the line is on the screen, with Download and Not now", within: 5) {
            control("download-newer") != nil && control("newer-not-now") != nil
        }
        if let p = control("newer-not-now") { click(p) }
        await expect("Not now takes the line away, and the version is remembered") {
            flow.homeModel.newerRelease == nil && NewerRelease.setAside(home: flow.home) == "99.0.0"
        }
        flow.homeModel.lookForNewerRelease()
        await pause(0.5)
        await expect("and the same version is not offered again") { flow.homeModel.newerRelease == nil }
        let releaseLine = true

        let skills = flow.home.appendingPathComponent(".claude/skills", isDirectory: true)
        let tripsThere = fm.fileExists(atPath: skills.appendingPathComponent("trips/SKILL.md").path)
        let gymThere = fm.fileExists(atPath: skills.appendingPathComponent("gym-log/.made-for-you").path)
        let sneakyKept = !fm.fileExists(atPath: skills.appendingPathComponent("sneaky").path)
        let brainSame = (try? Data(contentsOf: skills.appendingPathComponent("brain/SKILL.md"))) == brainBefore
        let noSmuggle = !fm.fileExists(atPath: "/tmp/moblee-pwned")
            && !flow.homeModel.tiles.contains { $0.key.contains("/") || $0.key.contains(";") }
        let ok = tripsState == .done && videosState == .handedOver && tripsThere && googleState == .done && pointerRight && guardLevel && newerLeftAlone && releaseLine
            && skill("gym-log")?.state == .done && gymThere
            && skill("sneaky")?.state == .blocked && sneakyKept
            && skill("brain")?.state == .blocked && brainSame && noSmuggle
        say("trips added: \(tripsThere); gym-log added: \(gymThere); link refused: \(sneakyKept); brain untouched: \(brainSame); nothing smuggled: \(noSmuggle)")
        say(ok ? "every screen opened, the install finished, waiting things were added, and the three bad requests were refused"
               : "the home screen did not behave as expected")
        exit(ok ? 0 : 1)
    }
}
