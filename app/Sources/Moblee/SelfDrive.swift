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
///
/// (v0.9.4) With `--rtl` it is a short walk of its own instead: the window
/// mirrored, as macOS draws it on a Mac whose own language is read right to
/// left, with every side that carries a meaning read off the real screens.
@MainActor
enum SelfDrive {
    static var asked: Bool { Practice.args.contains("--self-drive") }

    /// (v0.9.5) The walk is begun by a screen appearing, so a second window
    /// would begin a second walk beside the first, and the two would click each
    /// other's buttons. That really happened: a file given to the app from
    /// outside used to open a second window (see `MobleeApp.body`), and the
    /// second walk started at the welcome screen while the first was at home.
    /// One walk to a run, whatever else opens.
    private static var walking = false

    static func run(_ flow: Flow) async {
        if walking { return }
        walking = true
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
        /// The big button, where it says it is drawn. (v0.9.4) This used to be
        /// a sum — the middle of the window, 73 points up from the bottom —
        /// which held only while the window was nailed to one size and the
        /// words to one size with it. Both can now be made bigger.
        ///
        /// Nothing if the button has not said where it is. There used to be a
        /// fall-back here of the middle of the window, which is exactly what
        /// three of the checks below compare this against — so a button that
        /// never said where it was, the very fault the button was made to say
        /// for, passed all three without being drawn at all. The way back
        /// beside it had it right, with `guard let`; these now match it.
        func bigButton() -> CGPoint? { control("main-button") }
        /// Waits for the button to say where it is — a screen sliding in takes
        /// a moment to report — and fails plainly if it never does.
        func clickBigButton(within seconds: Double = 4) async {
            let by = Date().addingTimeInterval(seconds)
            while bigButton() == nil && Date() < by { await pause(0.1) }
            guard let p = bigButton() else {
                say("FAILED: the big button did not say where it is drawn in \(Int(seconds)) seconds, "
                    + "so there was nothing to click; drawn: \(DrawnPlaces.frames.keys.sorted().joined(separator: ", "))")
                exit(1)
            }
            click(p)
        }
        /// Tab moves the keyboard on to the next control it can reach; the
        /// control itself says when it has it (`FocusedControl`). Nothing but
        /// the keyboard is used here.
        func tabUntil(_ id: String, taps: Int = 18) async -> Bool {
            for _ in 0..<taps {
                if FocusedControl.id == id { return true }
                // A window that is not the key window is given no key presses
                // at all, which is ordinary macOS behaviour and not a fault in
                // the screen; the front is taken back and the Tab made again.
                if !window.isKeyWindow {
                    NSApp.activate(ignoringOtherApps: true)
                    window.makeKeyAndOrderFront(nil)
                    await pause(0.5)
                }
                key("\t", code: 48)
                await pause(0.35)
            }
            say("Tab did not reach \(id): the keyboard is on \(FocusedControl.id ?? "nothing"), "
                + "key window \(window.isKeyWindow), app active \(NSApp.isActive), "
                + "first responder \(String(describing: window.firstResponder)), "
                + "in the window \(((window.firstResponder as? NSView)?.window != nil))")
            return FocusedControl.id == id
        }
        func pressSpace() { key(" ", code: 49) }
        func pressEscape() { key("\u{1b}", code: 53) }
        func pressReturn() { key("\r", code: 36) }
        /// The keyboard, really had. Typed letters and keys go to whichever app
        /// has it, and macOS may not hand it over at once to an app started
        /// from a script, least of all straight after another copy of it has
        /// just quit (seen on the mini, 20 September 2026). Asked for until it
        /// is really had. (v0.9.4: was written out at the name screen, and is
        /// now wanted from the welcome screen on, because the install is walked
        /// from the keyboard.)
        func takeTheKeyboard(within seconds: Double = 10) async {
            let by = Date().addingTimeInterval(seconds)
            repeat {
                NSRunningApplication.current.activate(options: [.activateAllWindows])
                NSApp.activate(ignoringOtherApps: true)
                window.makeKeyAndOrderFront(nil)
                await pause(0.5)
            } while !(NSApp.isActive && window.isKeyWindow) && Date() < by
            say(NSApp.isActive && window.isKeyWindow
                ? "has the keyboard" : "was not given the keyboard within \(Int(seconds)) seconds")
        }
        /// The middle of the window, in the same numbers `control` gives back.
        func middle() -> CGFloat { window.contentView?.bounds.midX ?? 0 }

        // (v0.9.4) `--rtl`: the real window, mirrored, as a Mac whose own
        // language is read right to left draws it. A short walk of its own,
        // because what it has to prove is where things are and not what they
        // do: every side that carries a meaning must have swapped over, and the
        // big button must still be in the middle. Nothing is clicked or typed
        // here, so it does not need the window to be the front one, and it can
        // be run straight from the test script.
        if Layout.mirrored {
            say("mirrored: the window is laid out right to left")
            await pause(1.5)
            await expect("mirrored: Bigger text sits in the top corner the reading ends at, which is the left one") {
                guard let b = control("bigger-text") else { return false }
                return b.x < middle()
            }
            // The welcome screen has no way back; the check-up is the first that has one.
            flow.next()
            await expect("mirrored: the check-up opened") { flow.step == .checkup }
            await pause(1.5)
            say("mirrored: the way back is at \(control("back").map { Int($0.x) } ?? -1), "
                + "the big button at \(bigButton().map { Int($0.x) } ?? -1), Bigger text at \(control("bigger-text").map { Int($0.x) } ?? -1), "
                + "the middle is \(Int(middle())); drawn: \(DrawnPlaces.frames.keys.sorted().joined(separator: ", "))")
            await expect("mirrored: the way back sits on the side the reading starts from, which is the right one") {
                guard let back = control("back"), let button = bigButton() else { return false }
                return back.x > button.x + Theme.pt(20)
            }
            await expect("mirrored: and the big button is still in the middle") {
                guard let button = bigButton() else { return false }
                return abs(button.x - middle()) < 10
            }
            // An owner whose Mac is in Arabic may well have an Arabic name. It
            // must reach the wiki's folder name whole, with none of the
            // invisible marks the screens put round it for the reading.
            let light = "نور"
            flow.next()
            await expect("mirrored: the name screen opened") { flow.step == .name }
            flow.ownerName = light
            await pause(1.0)
            await expect("mirrored: an Arabic name makes a wiki folder called after it, with nothing invisible in it") {
                flow.wikiName == light + " Wiki"
                    && !flow.wikiName.contains(OwnWords.isolate) && !flow.wikiName.contains(OwnWords.pop)
            }
            await expect("mirrored: and the screen with the name on it still draws, with the big button in the middle") {
                guard let button = bigButton() else { return false }
                return abs(button.x - middle()) < 10
            }
            say("mirrored: every side that means something is the right way round")
            exit(0)
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
            await clickBigButton()
            if Placement.practiceBreak != nil {
                // The new copy is made to fail its check. The screen must stay,
                // say so, and leave everything as it was; Carry on then goes on.
                await pause(6)
                await expect("a copy that fails its check is not called a move") { flow.offerMove && flow.moveOutcome == nil }
                await clickBigButton()             // "Carry on"
                await expect("Carry on goes on to the welcome screen") { !flow.offerMove && flow.step == .welcome }
                say("the broken move changed nothing and the app carried on"); exit(0)
            }
            await expect("clicking Move it there settles where Moblee lives and carries on", within: 60) {
                !flow.offerMove && flow.moveOutcome != nil
            }
            let there = folder.appendingPathComponent("Moblee.app", isDirectory: true)
            say(flow.moveOutcome == .moved(there) ? "moved" : "already there, and that one is used"); exit(0)
        }

        // (v0.9.4) The install is walked with the keyboard, screen by screen,
        // and every screen it gets past that way is written down here. The
        // app's promise is that everything in it can be reached from the
        // keyboard, and until 26 September 2026 that was not true of the
        // install at all: the three cards on "Which assistant?" took no
        // keyboard, and Next on that screen is greyed out until one of them is
        // chosen, so an owner who cannot use a mouse could not finish. Both
        // ways are still shown — the mouse presses the cards and the big button
        // further down — but the keyboard alone gets past all six screens.
        var passedByKeyboard: [String] = []

        say("welcome"); await pause(1.5)
        // (v0.9.5) Before anything has been pressed. There is a listen control
        // beside every block of words in the app now, and the one promise that
        // cannot be tested any other way is that not one of them ever starts by
        // itself: no screen appearing, no install finishing, no receipt arriving.
        // The count of how many times the owner has asked is read here, at the
        // very first screen, and again after the whole install.
        await expect("nothing has spoken on the welcome screen, because nothing speaks unasked") {
            Speaker.shared.timesAsked == 0 && Speaker.shared.speakingId == nil
        }
        await takeTheKeyboard()
        // Return presses the big button on every screen in the app: it is the
        // window's default action, so it works wherever the keyboard happens to
        // be and without macOS's Full Keyboard Access being switched on.
        pressReturn()
        await expect("Return alone opens the check-up") { flow.step == .checkup }
        passedByKeyboard.append("welcome")
        say("check-up"); await pause(7)      // long enough for two re-looks
        // (v0.9.4) The same two sides the mirrored walk reads, read here the
        // other way round, so that both directions are looked at on a real
        // window and not only in a picture file.
        await expect("the way back sits on the side the reading starts from, which is the left one") {
            guard let back = control("back"), let button = bigButton() else { return false }
            return back.x < button.x - Theme.pt(20)
        }
        await expect("and Bigger text sits in the top corner the reading ends at, which is the right one") {
            guard let b = control("bigger-text") else { return false }
            return b.x > middle()
        }
        pressReturn()
        await expect("Return alone opens the name screen") { flow.step == .name }
        passedByKeyboard.append("check-up")
        say("name"); await pause(1.0)
        await clickBigButton()                     // the button is greyed out until a name is typed
        await pause(0.8)
        await expect("a greyed-out Next does nothing") { flow.step == .name }
        pressReturn()                        // and Return does nothing on it either
        await pause(0.8)
        await expect("and neither does Return, which is what presses it when it is live") { flow.step == .name }
        // Typed letters go to whichever app has the keyboard. If the person at
        // the Mac clicked elsewhere while this was running, they never arrive
        // (seen once, 20 September 2026), so the keyboard is taken back first.
        await takeTheKeyboard()
        func editableBox(in view: NSView?) -> NSTextField? {
            guard let view else { return nil }
            if let field = view as? NSTextField, field.isEditable { return field }
            for sub in view.subviews { if let found = editableBox(in: sub) { return found } }
            return nil
        }
        /// The box is where the typing is going: `currentEditor` is the field
        /// editor macOS lends a text box while it has the keyboard.
        func keyboardIsInTheNameBox() -> Bool {
            editableBox(in: window.contentView)?.currentEditor() != nil
        }
        // (v0.9.4) The box takes the typing by itself when its screen appears
        // in front; if the screen appeared while another app was in front it
        // does not. This walk used to click in it at that point, which meant
        // the one screen of the install where something has to be TYPED had
        // never once been reached without a mouse. Tab reaches it — a text box
        // is in the keyboard's way on every Mac, whatever else is set — and the
        // click is kept only as a last resort, so that the line below can say
        // honestly whether a mouse was needed.
        var mouseNeededForTheBox = false
        var tabsToTheBox = 0
        while !keyboardIsInTheNameBox() && tabsToTheBox < 15 {
            if !window.isKeyWindow {
                NSApp.activate(ignoringOtherApps: true)
                window.makeKeyAndOrderFront(nil)
                await pause(0.5)
            }
            key("\t", code: 48); await pause(0.3); tabsToTheBox += 1
        }
        if keyboardIsInTheNameBox() {
            say("the keyboard is in the name box after \(tabsToTheBox) Tab(s)")
        } else if let box = editableBox(in: window.contentView) {
            let r = box.convert(box.bounds, to: nil)
            click(CGPoint(x: r.midX, y: r.midY)); await pause(0.4)
            mouseNeededForTheBox = true
            say("Tab did not reach the name box in 15 presses; clicked in it instead")
        } else {
            say("the name box was not found on the screen")
        }
        await expect("the name box is reached without a mouse") { !mouseNeededForTheBox }
        for ch in "Tom & Sam" { key(String(ch)); await pause(0.05) }
        await expect("typing reaches the name box") { flow.ownerName == "Tom & Sam" }
        // (v0.9.4) And a name that is not written in English. An owner's Mac may
        // be in English while their own name is Arabic, and the box had never
        // once been given one: the letters must arrive as typed, in the order
        // they were typed, and the wiki folder must be called after them with
        // none of the invisible marks the screens put round a name for reading.
        let arabicName = "نور"           // Arabic for "light", an ordinary given name
        flow.ownerName = ""
        await pause(0.5)
        for ch in arabicName { key(String(ch)); await pause(0.08) }
        await pause(0.5)
        say("an Arabic name typed into the box came out as: \(flow.ownerName)")
        await expect("a name typed in Arabic reaches the name box exactly as typed") { flow.ownerName == arabicName }
        await expect("and the wiki folder is called after it, with nothing invisible in the name") {
            flow.wikiName == arabicName + " Wiki"
                && !flow.wikiName.contains(OwnWords.isolate) && !flow.wikiName.contains(OwnWords.pop)
        }
        flow.ownerName = "Tom & Sam"     // the rest of the walk installs under this one
        await pause(0.5)
        // (v0.9.4) The way back, by the keyboard. This used to be done by
        // driving the model from the inside (`flow.back()`), and the arrow
        // itself had no way to the keyboard at all: it is on every screen but
        // the first, and it could only ever be pressed with a mouse.
        let onTheWayBack = await tabUntil("back")
        await expect("Tab reaches the way back") { onTheWayBack }
        pressSpace()
        say("back to check-up, by Tab and Space")
        await expect("and Space alone goes back one screen") { flow.step == .checkup }
        await pause(4)
        flow.next(); say("name again"); await pause(1)
        await expect("the name is still there after going back") { flow.ownerName == "Tom & Sam" }
        pressReturn()
        await pause(1.5)
        await expect("Return moves on exactly one screen, to the question of which assistant") { flow.step == .assistant }
        passedByKeyboard.append("name")
        say("assistant"); await pause(1.0)
        await expect("nothing is chosen for the owner beforehand") { flow.assistant == nil }
        await clickBigButton()                     // greyed out until one of the three is tapped
        await pause(0.8)
        pressReturn()
        await pause(0.8)
        say("after the greyed-out Next: step \(flow.step), chosen \(String(describing: flow.assistant))")
        await expect("a greyed-out Next does nothing on the question either, by mouse or by Return") {
            flow.step == .assistant && flow.assistant == nil
        }
        // The Claude card, where the card itself says it is drawn. (v0.9.4)
        // This used to be worked out here — cards 170 wide with 22 between
        // them, the middle of the picture area 269 up from the bottom when the
        // sentence takes one line — and that sum stopped holding the moment
        // the window could be made bigger and the words with it.
        say("window \(Int(window.frame.width))x\(Int(window.frame.height)), "
            + "content \(Int(window.contentView?.bounds.width ?? 0))x\(Int(window.contentView?.bounds.height ?? 0))")
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
            if let p = control("assistant-claude") { click(p) }
            taps += 1
            await pause(0.8)
            if flow.assistant != .claude {
                say("tap \(taps) did not reach the card: key window \(window.isKeyWindow), app active \(NSApp.isActive), " +
                    "window seen \(window.occlusionState.contains(.visible)), step \(flow.step), " +
                    "card at \(String(describing: control("assistant-claude"))), chosen \(String(describing: flow.assistant))")
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

        // (v0.9.4) And now the same screen with the keyboard alone. This is the
        // screen an owner cannot go round: Next is greyed out until one of the
        // three cards is chosen, and until 26 September 2026 the cards took no
        // keyboard — no way to focus them, no ring, nothing on Space. Without
        // macOS's own Full Keyboard Access, which no owner of Moblee's will
        // have switched on, the install could not be finished from the keyboard
        // at all, which is the very thing being able to work Moblee from the
        // keyboard exists to spare them. So: Tab to a card, Space to answer,
        // Tab to the next card, Space to change the answer, Return for Next.
        let onACard = await tabUntil("assistant-chatgpt")
        await expect("Tab alone reaches one of the three cards") { onACard }
        pressSpace()
        await expect("and Space alone answers the question", within: 5) { flow.assistant == .chatgpt }
        await pause(0.6)
        let onTheClaudeCard = await tabUntil("assistant-claude")
        await expect("Tab reaches the card beside it") { onTheClaudeCard }
        pressSpace()
        await expect("and Space alone changes the answer", within: 5) { flow.assistant == .claude }
        say("the question of which assistant was answered, changed and left at Claude with the keyboard alone")
        await pause(0.6)
        pressReturn()                        // Next, now that it is live
        await expect("Return after answering opens the promise") { flow.step == .promise }
        passedByKeyboard.append("which assistant")
        say("promise"); await pause(1.0)
        pressReturn()
        await expect("Return on the promise starts the build") { flow.step == .build }
        passedByKeyboard.append("promise")
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
        pressReturn()
        await expect("Return after the build opens the hand-off") { flow.step == .handoff }
        passedByKeyboard.append("build")
        say("hand-off"); await pause(2)
        // (v0.9.4) The whole of it, said once: an owner who cannot use a mouse
        // can make their wiki. Every screen of the install was got past with
        // the keyboard alone, on the real window — Return on the big button,
        // Tab into the name box and into the three cards, Space to choose.
        say("screens of the install got past with the keyboard alone: \(passedByKeyboard.joined(separator: ", "))")
        await expect("every screen of the install can be got past with the keyboard alone") {
            passedByKeyboard == ["welcome", "check-up", "name", "which assistant", "promise", "build"]
        }

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
        // (v0.9.4) The keyboard alone, before a single thing is added. Until
        // now the tile buttons and the quiet "Not now" could be worked by the
        // mouse and by nothing else, which shut out anybody who cannot use
        // one. Tab is pressed until the keyboard is on a tile's own button —
        // the button says when it has it — and then Space presses it. No mouse
        // is used anywhere in this passage.
        // (v0.9.5) "Read it to me", now beside every block of words, walked on the
        // real window with the keyboard alone: the whole install and the home
        // screen have been through, and still nothing has spoken.
        await expect("through the whole install and home again, nothing has spoken by itself") {
            Speaker.shared.timesAsked == 0 && Speaker.shared.speakingId == nil
        }
        let videosTile = flow.homeModel.tiles.first { $0.key == "videos" }!
        let tripsTile = flow.homeModel.tiles.first { $0.key == "trips" }!
        let onATileListen = await tabUntil(RequestTile.listenId(videosTile))
        say("Tab reached the videos tile's own listen control: \(onATileListen) "
            + "(the keyboard is on \(FocusedControl.id ?? "nothing"))")
        await expect("Tab alone reaches a tile's own listen control") { onATileListen }
        pressSpace()
        await expect("and Space alone starts it reading that tile", within: 5) {
            Speaker.shared.speakingId == RequestTile.listenId(videosTile)
        }
        // Starting one stops another. The tile beside it is pressed next, and
        // only that one may say it is speaking.
        let onTheOtherListen = await tabUntil(RequestTile.listenId(tripsTile))
        await expect("Tab reaches the listen control on the tile beside it") { onTheOtherListen }
        pressSpace()
        await expect("starting one stops the other: one voice at a time, and the new one says it is the one", within: 5) {
            Speaker.shared.speakingId == RequestTile.listenId(tripsTile)
        }
        say("one voice at a time: the keyboard moved from one tile's listen control to the next "
            + "and only \(Speaker.shared.speakingId ?? "nothing") says it is speaking")
        // And the screen's own big sentence, which is the control that has always
        // been there: pressing it must stop the tile that was reading.
        let onTheHeadline = await tabUntil("read-aloud")
        await expect("Tab reaches the listen control beside the screen's own sentence") { onTheHeadline }
        pressSpace()
        await expect("and it stops the tile that was reading", within: 5) {
            Speaker.shared.speakingId == "read-aloud"
        }
        // Leaving the screen stops it. The tile's own button is pressed, which
        // takes the explanation's screen in place of this one.
        let backOnATile = await tabUntil(RequestTile.buttonId(videosTile))
        await expect("Tab reaches the tile's own button again") { backOnATile }
        pressSpace()
        await expect("leaving the screen stops it reading", within: 6) {
            flow.homeModel.explaining?.key == "videos" && Speaker.shared.speakingId == nil
        }
        pressEscape()
        await expect("and Not now brings the home screen back") { flow.homeModel.explaining == nil }
        await pause(1.0)
        say("the owner asked for something to be read \(Speaker.shared.timesAsked) time(s); "
            + "every one of them was a Space press in this walk")

        // (v0.9.5) The tab order, measured on the real window rather than argued
        // about. v0.9.4's whole point was that every control can be reached by
        // Tab; a listen control beside every block of words is exactly the change
        // that could turn "three presses to the thing you want" into twenty. So
        // the ring is walked right round, once, and counted.
        // (v0.9.5) From the VERY BEGINNING of the round, not from wherever
        // "Bigger text" happens to sit in it. Tab in this app stops at the end
        // of the list rather than coming round again, and this used to start by
        // tabbing to "Bigger text" and walking to the end — so what it measured
        // was the part of the round AFTER that control, and called it the whole
        // round. It was the whole round only because "Bigger text" happens to
        // be first today, which is exactly the thing a check may not assume
        // about the thing it is checking. The keyboard is let go of first, so
        // the next Tab starts at the first control of all.
        window.makeFirstResponder(nil)
        await pause(0.8)
        key("\t", code: 48)
        await pause(0.5)
        var ring: [String] = []
        var wentNowhere = 0
        for _ in 0..<40 {
            let before = FocusedControl.id
            if let id = before, !ring.contains(id) { ring.append(id) }
            key("\t", code: 48)
            await pause(0.45)
            // Two presses that move nothing mean the end has been reached.
            if FocusedControl.id == before { wentNowhere += 1 } else { wentNowhere = 0 }
            if wentNowhere >= 2 { break }
        }
        say("the keyboard goes round the home screen in this order: \(ring.joined(separator: ", "))")
        // (v0.9.5) What the screen itself says should be on that round, worked
        // out from the very tiles and lines in front of the walk this moment.
        // The ring is required to be exactly this, in this order, so that the
        // screen's own list and the real keyboard cannot drift apart: a control
        // added to one and not the other fails here.
        let shouldBe = HomeScreen.stops(
            shown: HomeScreen.shown(from: flow.homeModel.tiles),
            nextTileWaiting: flow.homeModel.nextTile != nil,
            canChangeAssistant: flow.homeModel.canChangeAssistant,
            wantsChatGPT: flow.homeModel.assistant.wantsChatGPT,
            newerRelease: flow.homeModel.newerRelease != nil && flow.homeModel.newerReleaseLineAllowed,
            // (v0.9.6) The way into the example wiki is the second big button,
            // and it is on this screen whenever the app carries the example.
            showsExample: flow.hasExample)
        say("and the screen's own list of its controls is: \(shouldBe.joined(separator: ", "))")
        // And then the keyboard is let go, exactly as the app lets it go when a
        // control it was on goes away (see `FocusedControl.letGoIfNothingTookIt`),
        // so that the rest of this walk starts afresh at the first control
        // instead of from the end of the list.
        window.makeFirstResponder(nil)
        await pause(1.0)
        // (v0.9.6) Twenty, not nineteen: this version put two more controls on
        // this screen, the way into the example wiki and "Check my wiki". See the
        // same ceiling in `LogicCheck`, which says what the honest options are if
        // twenty turns out to be too many.
        await expect("the keyboard crosses the busiest screen in twenty presses or fewer, listening controls and all") {
            ring.count <= 20 && ring.count >= 8
        }
        await expect("and the keyboard's real round is exactly the round the screen says it has, in that order") {
            ring == shouldBe
        }
        await expect("and every tile's own button and its listen control are both on that round") {
            [tripsTile, videosTile].allSatisfy {
                ring.contains(RequestTile.buttonId($0)) && ring.contains(RequestTile.listenId($0))
            } && ring.contains("read-aloud") && ring.contains("listen-quiet")
        }
        // (v0.9.5) Each listen control STANDS BESIDE the words it reads, on the
        // real window and not only in a list. All three tile speakers used to
        // come one after another before any of the three Add buttons, and the
        // quiet words' speaker was two places away from the quiet words with a
        // control from the opposite corner of the screen in between.
        func besides(_ id: String) -> [String] {
            guard let at = ring.firstIndex(of: id) else { return [] }
            return [at - 1, at + 1].filter { ring.indices.contains($0) }.map { ring[$0] }
        }
        // A control that is not on this screen at all is not a failure of
        // adjacency: the newer-Moblee line only shows when a newer Moblee has
        // been published, and "Prove the guard" only for a wiki that uses
        // ChatGPT. Asking `besides` about an absent control gets an empty list,
        // and an empty list satisfies nothing, so this said FAILED on every
        // walk where no newer release was on record — which is every walk but
        // the one test-app.sh starts with a stand-in for GitHub's answer.
        func standsBeside(_ id: String, oneOf neighbours: [String]) -> Bool {
            guard ring.contains(id) else { return true }
            return besides(id).contains { neighbours.contains($0) }
        }
        await expect("every listen control on the round stands next to the very words it reads") {
            HomeScreen.shown(from: flow.homeModel.tiles).allSatisfy { tile in
                standsBeside(RequestTile.listenId(tile),
                             oneOf: [RequestTile.buttonId(tile), RequestTile.doneId(tile)])
            }
                && standsBeside("listen-quiet", oneOf: ["quiet"])
                && standsBeside("listen-newer-line", oneOf: ["download-newer", "newer-not-now"])
                // (v0.9.6) "Check my wiki" joined this corner, on the line above
                // the one about the assistant, so it is one of the controls that
                // line's listen control may stand beside.
                && standsBeside("listen-assistant-line",
                                oneOf: ["change-assistant", "prove-guard", "check-wiki"])
        }
        await expect("and no tile's listen control stands next to another tile's") {
            ring.filter { $0.hasPrefix("listen-tile-") }
                .allSatisfy { !besides($0).contains { $0.hasPrefix("listen-tile-") } }
        }
        await expect("with the listening controls never more than half of what the keyboard has to step through") {
            ring.filter { $0.hasPrefix("listen-") }.count * 2 <= ring.count
        }
        say("the keyboard is on: \(FocusedControl.id ?? "nothing")")
        let videosButton = RequestTile.buttonId(flow.homeModel.tiles.first { $0.key == "videos" }!)
        let reached = await tabUntil(videosButton)
        say("Tab reached the videos tile's own button: \(reached) (the keyboard is on \(FocusedControl.id ?? "nothing"))")
        await expect("Tab alone reaches a tile's button") { reached }
        pressSpace()
        await expect("and Space alone presses it", within: 5) { flow.homeModel.explaining?.key == "videos" }
        await pause(0.8)
        // Escape is what "Not now" is, wherever "Not now" means not now.
        pressEscape()
        await expect("Escape does what Not now does") { flow.homeModel.explaining == nil }
        await pause(0.8)
        // And it must do nothing at all where there is no "Not now": the
        // ordinary home screen's quiet words are "Open Claude", which Escape
        // must never press.
        let tilesBefore = flow.homeModel.tiles.map(\.state)
        pressEscape()
        await pause(1.0)
        say("Escape where the quiet words are not Not now changed nothing: "
            + "\(flow.homeModel.explaining == nil && flow.homeModel.tiles.map(\.state) == tilesBefore)")
        await expect("Escape presses nothing where there is no Not now") {
            flow.homeModel.explaining == nil && flow.homeModel.tiles.map(\.state) == tilesBefore
        }
        // (v0.9.6) THE EXAMPLE WIKI, ON THE REAL WINDOW, FROM THE KEYBOARD
        // ALONE. Everything about it that a picture file cannot show: that the
        // second big button really opens it, that Tab really reaches a link and
        // Space really follows it — which is the whole reason the links on a
        // page are drawn as buttons under it as well as as words inside it,
        // since an inline link in wrapping text takes no keyboard focus on
        // macOS — that the way back really goes back a page, that the list of
        // pages really opens, and that the way out really puts an owner back on
        // the home screen they came from.
        //
        // Written on 26 September 2026 and NOT SEEN TO PASS: the live-window
        // walk on this Mac starts the app, draws nothing and writes not one
        // byte, and a build from before this version's work hangs the same way.
        // What it checks is checked again without a window in `LogicCheck`,
        // which was run and held; this is here for the first Mac that can run a
        // window again.
        if flow.hasExample {
            window.makeFirstResponder(nil)
            await pause(0.6)
            let onTheWayIn = await tabUntil("second-button")
            say("Tab reached the way into the example wiki: \(onTheWayIn)")
            await expect("Tab alone reaches the way into the example wiki") { onTheWayIn }
            pressSpace()
            await expect("and Space alone opens it, on the page it opens on and not on the catalogue", within: 5) {
                flow.example?.showing == .page(ExamplePages.firstPage)
            }
            await pause(1.0)
            let firstLink = flow.example?.linksOn(ExamplePages.firstPage).first ?? "Bread"
            window.makeFirstResponder(nil)
            await pause(0.6)
            let onALink = await tabUntil(ExampleScreen.linkId(firstLink))
            say("Tab reached the link to \(firstLink): \(onALink)")
            await expect("Tab alone reaches a link on the page") { onALink }
            pressSpace()
            await expect("and Space alone follows it to that page", within: 5) {
                flow.example?.showing == .page(firstLink)
            }
            await pause(1.0)
            window.makeFirstResponder(nil)
            await pause(0.6)
            let onBack = await tabUntil("back")
            await expect("Tab reaches the way back inside the example") { onBack }
            // "Not back through the install" means the install's own step does
            // not move. An owner with a wiki reaches this from the home screen,
            // long past `.welcome`, so the step is compared with itself rather
            // than with the first one (corrected 27 September 2026, the first
            // time this walk ran).
            let stepBeforeBack = flow.step
            pressSpace()
            await pause(1.0)
            say("after back: showing \(String(describing: flow.example?.showing)), step \(flow.step), step before \(stepBeforeBack)")
            await expect("and Space alone goes back to the page before, not back through the install", within: 5) {
                flow.example?.showing == .page(ExamplePages.firstPage) && flow.step == stepBeforeBack
            }
            await pause(1.0)
            window.makeFirstResponder(nil)
            await pause(0.6)
            let onThePages = await tabUntil("quiet")
            await expect("Tab reaches the list of every page") { onThePages }
            pressSpace()
            await expect("and Space alone opens it", within: 5) { flow.example?.showing == .pages }
            await pause(1.0)
            say("nothing spoke inside the example: \(Speaker.shared.speakingId == nil)")
            await expect("nothing spoke inside the example unasked") { Speaker.shared.speakingId == nil }
            await clickBigButton()
            await expect("and the way out puts an owner who has a wiki back on the home screen", within: 5) {
                flow.example == nil && flow.mode == .home
            }
            await pause(1.0)
        } else {
            say("FAILED: the app carries no example wiki, so there was no way in to walk")
        }

        // "Bigger text" is reachable and works by the keyboard too, and the
        // window's least size grows with it. The size is kept between openings,
        // so whatever it was left at, the control itself is pressed until the
        // words are back to normal; then round the three, and back to normal
        // for the rest of the walk. Nothing but the keyboard is used.
        let onTheControl = await tabUntil("bigger-text")
        say("Tab reached Bigger text, at \(TextSize.shared.step.name.lowercased()): \(onTheControl)")
        await expect("Tab reaches Bigger text") { onTheControl }
        var presses = 0
        while TextSize.shared.step != .normal && presses < 4 {
            pressSpace(); await pause(0.9); presses += 1
        }
        await expect("the words can be brought back to normal by the keyboard alone") { TextSize.shared.step == .normal }
        await pause(0.6)
        let wasWide = window.frame.width
        pressSpace()
        await expect("and Space makes the words bigger", within: 4) { TextSize.shared.step == .bigger }
        await pause(1.2)
        say("the window grew with the words: \(Int(wasWide)) -> \(Int(window.frame.width))")
        await expect("the window grows with the words", within: 5) { window.frame.width > wasWide }
        pressSpace(); await pause(0.9)
        pressSpace(); await pause(1.3)
        await expect("a third press puts the words back to normal") { TextSize.shared.step == .normal }
        await pause(1.0)
        say("the window came back down with them: \(Int(window.frame.width))x\(Int(window.frame.height)), "
            + "and it started at \(Int(wasWide)) wide")
        await expect("and the window with them", within: 5) { window.frame.width <= wasWide + 1 }

        // (v0.9.4) The window made bigger, as an owner drags it by its corner:
        // the screens are drawn at the new size, the big button stays in the
        // middle, and the window cannot be dragged smaller than the screens
        // need. The window used to be nailed to 720 by 520 and there was no
        // way to make it, or the words in it, any bigger at all.
        let startedAt = window.frame.size
        window.setContentSize(CGSize(width: startedAt.width + 240, height: startedAt.height + 140))
        await pause(1.5)
        let grew = window.frame.size
        let middle = window.contentView.map { $0.bounds.midX } ?? 0
        // (v0.9.6) The home screen of an owner with a wiki now has two big
        // buttons side by side, the second being the way into the example
        // wiki, and it is the row that is centred, not the first button in it.
        // Measured from the row's outer edges, so two buttons of different
        // widths are still judged fairly. (Corrected 27 September 2026, the
        // first time this walk ran against 0.9.6.)
        func rowMiddle() -> CGFloat? {
            guard let first = DrawnPlaces.frames["main-button"], first.width > 0 else { return nil }
            let last = DrawnPlaces.frames["second-button"].flatMap { $0.width > 0 ? $0 : nil } ?? first
            return (first.minX + last.maxX) / 2
        }
        say("the window was dragged to \(Int(grew.width))x\(Int(grew.height)); the row of big buttons is centred at "
            + "\(rowMiddle().map { Int($0) } ?? -1), the middle is \(Int(middle))")
        await expect("a window made bigger still draws its screens, with the big button in the middle") {
            guard let row = rowMiddle() else { return false }
            return grew.width > startedAt.width && abs(row - middle) < 8 && flow.homeModel.tiles.count > 0
        }

        // (v0.9.4) And now the other order, which nothing had ever tried: the
        // owner sizes the window themselves FIRST, and THEN presses "Bigger
        // text". Every press must leave the size they chose alone — the words
        // may take the window up past it, and must give it back afterwards —
        // and it was the second press that undid it. The app wrote down the
        // size the words had asked for even on the pass that deliberately left
        // an owner-sized window alone, so the next press read the window as one
        // the app had sized itself and took it down to the size the words alone
        // want. A third press took it to 720 by 520. Nothing but the keyboard
        // is used here, and the size is read off the real window.
        let ownersSize = window.frame.size
        say("the owner's own window is \(Int(ownersSize.width))x\(Int(ownersSize.height))")
        func stillTheOwnersSize() -> Bool {
            window.frame.width >= ownersSize.width - 1 && window.frame.height >= ownersSize.height - 1
        }
        let onTheOwnersWindow = await tabUntil("bigger-text")
        await expect("Tab reaches Bigger text on a window the owner has sized") { onTheOwnersWindow }
        pressSpace()
        await expect("one press makes the words bigger", within: 4) { TextSize.shared.step == .bigger }
        await pause(1.3)
        say("after one press the window is \(Int(window.frame.width))x\(Int(window.frame.height))")
        await expect("and a window the owner sized is never made smaller by it") { stillTheOwnersSize() }
        pressSpace()
        await expect("a second press makes them bigger again", within: 4) { TextSize.shared.step == .biggest }
        await pause(1.3)
        say("after the second press the window is \(Int(window.frame.width))x\(Int(window.frame.height))")
        await expect("nor by the second press, which is where the owner's size used to go") { stillTheOwnersSize() }
        pressSpace()
        await expect("a third press puts the words back to normal again", within: 4) { TextSize.shared.step == .normal }
        await pause(1.3)
        say("back at normal words the window is \(Int(window.frame.width))x\(Int(window.frame.height)), "
            + "and the owner left it \(Int(ownersSize.width))x\(Int(ownersSize.height))")
        await expect("and the words coming back down bring the window back to exactly the size the owner left it") {
            abs(window.frame.width - ownersSize.width) < 2 && abs(window.frame.height - ownersSize.height) < 2
        }

        window.setContentSize(CGSize(width: 320, height: 240))
        await pause(1.2)
        say("asked for a window of 320 by 240, got \(Int(window.frame.width))x\(Int(window.frame.height))")
        await expect("and it can never be made smaller than 720 by 520") {
            window.frame.width >= 720 && window.frame.height >= 520
        }
        await pause(0.8)

        // The big button adds the next thing, and it is pressed for real.
        await expect("the big button offers the first thing, trips") { flow.homeModel.nextTile?.key == "trips" }
        await clickBigButton(); say("clicked the big button (Add the first one)")
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
        await clickBigButton(); say("explaining the Terminal window")
        await expect("the click opened the explanation first, and nothing else") { flow.homeModel.explaining?.key == "videos" }
        await pause(1.0)
        // (v0.9.4) The three pictures come one at a time, and nothing is opened
        // until the owner has been through all three. The first two presses of
        // the big button say "Next" and must open no Terminal window; Back
        // returns to the one before, by the keyboard and by the mouse.
        await expect("nothing is handed over on the first picture") {
            flow.homeModel.tiles.first(where: { $0.key == "videos" })?.state == .waiting
        }
        await clickBigButton(); await pause(1.0)    // "Next", to the second picture
        await expect("Next stays on the explanation and hands nothing over") {
            flow.homeModel.explaining?.key == "videos"
                && flow.homeModel.tiles.first(where: { $0.key == "videos" })?.state == .waiting
        }
        await expect("Back appears once there is somewhere to go back to", within: 4) { control("explain-back") != nil }
        if let p = control("explain-back") { click(p) }
        await pause(1.0)
        await expect("Back goes to the picture before, and still hands nothing over") {
            control("explain-back") == nil && flow.homeModel.explaining?.key == "videos"
                && flow.homeModel.tiles.first(where: { $0.key == "videos" })?.state == .waiting
        }
        await clickBigButton(); await pause(0.9)    // Next, to the second
        await clickBigButton(); await pause(0.9)    // Next, to the third
        await expect("still nothing is handed over on the way through the three") {
            flow.homeModel.tiles.first(where: { $0.key == "videos" })?.state == .waiting
        }
        say("walked the three Terminal pictures, forwards and back")
        await clickBigButton()                      // "Open it", on the last of the three
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
        await clickBigButton(); say("explaining the clicks inside Claude")
        await expect("the three cards are the pack's own: where, what by name, how to tell it worked") {
            guard let t = flow.homeModel.explaining, t.key == "google", t.steps.count == 3 else { return false }
            return t.steps[1][1].contains("Gmail") && t.steps[2][1].contains("calendar")
        }
        await pause(1.0)
        await clickBigButton()                      // "Show me"
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
        await clickBigButton(); say("looking at gym-log before adding it")
        await expect("the skill is shown first, the whole of it, and nothing is added yet", within: 10) {
            flow.homeModel.explaining?.key == "gym-log"
                && (flow.homeModel.explaining?.body.contains("Write the sets to the Gym Log page") ?? false)
                && !fm.fileExists(atPath: flow.home.appendingPathComponent(".claude/skills/gym-log").path)
        }
        await pause(1.0)
        await clickBigButton()                      // "Add it"
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
        await clickBigButton()                      // "Repair"
        await expect("pressing Repair brings the guard level", within: 60) {
            !flow.homeModel.needsRepair && (try? Data(contentsOf: installedGuard)) == (try? Data(contentsOf: packGuard))
        }
        let guardLevel = !flow.homeModel.needsRepair
        say("stale guard repaired: \(guardLevel)")

        // (v0.9.4) The live failure of 24 September, and its opposite, against
        // the real scripts. An owner had Moblee's own skills in place from an
        // EARLIER Moblee: not this pack's copies, so the app said a skill was
        // missing; not in the record the skills script keeps, so the script
        // would not replace them. The app offered a repair that could not
        // succeed, every time it opened, for ever.
        //
        // Here the same state is built: one skill holding an earlier Moblee's
        // words, a pack of that earlier Moblee still on the Mac (the app keeps
        // every pack it has settled), and the record stripped of its name.
        let skillName = "galaxy"
        let mineToKeep = flow.home.appendingPathComponent(".claude/skills/\(skillName)", isDirectory: true)
        let earlierPack = flow.home.appendingPathComponent(
            "Library/Application Support/Moblee/pack-0.0.1/skills", isDirectory: true)
        let record = flow.home.appendingPathComponent(".config/moblee/skills-claude")
        let thisMoblees = try? Data(contentsOf: URL(fileURLWithPath: pointsAt + "/skills/\(skillName)/SKILL.md"))
        func forgetInTheRecord() {
            let names = ((try? String(contentsOf: record, encoding: .utf8)) ?? "")
                .split(separator: "\n").map(String.init).filter { $0 != skillName }
            try? (names.joined(separator: "\n") + "\n").write(to: record, atomically: true, encoding: .utf8)
        }
        let olderWords = "---\nname: \(skillName)\ndescription: an earlier Moblee's copy.\n---\n\nOlder words.\n"
        try? fm.createDirectory(at: earlierPack, withIntermediateDirectories: true)
        try? fm.copyItem(at: mineToKeep, to: earlierPack.appendingPathComponent(skillName))
        for place in [mineToKeep, earlierPack.appendingPathComponent(skillName)] {
            try? olderWords.write(to: place.appendingPathComponent("SKILL.md"), atomically: true, encoding: .utf8)
        }
        forgetInTheRecord()
        flow.homeModel.checkSafety()
        await expect("a skill an earlier Moblee left is a repair this app can make, and is never called the owner's") {
            flow.homeModel.needsRepair && flow.homeModel.foreignSkills.isEmpty
        }
        await pause(1.0)
        await clickBigButton()                      // "Repair"
        await expect("and pressing Repair really puts this Moblee's own copy back", within: 60) {
            !flow.homeModel.needsRepair
                && (try? Data(contentsOf: mineToKeep.appendingPathComponent("SKILL.md"))) == thisMoblees
        }
        let earlierPutBack = !flow.homeModel.needsRepair
        say("an earlier Moblee's copy of a skill was recognised and put back: \(earlierPutBack)")

        // The other way: words that match no Moblee pack at all. That is the
        // owner's, or another tool's. No repair may be offered for it, it is
        // named on the screen, and it is left exactly as it is.
        let ownWords = "---\nname: \(skillName)\ndescription: my own skill.\n---\n\nMine, not Moblee's.\n"
        try? ownWords.write(to: mineToKeep.appendingPathComponent("SKILL.md"), atomically: true, encoding: .utf8)
        forgetInTheRecord()
        flow.homeModel.checkSafety()
        await expect("a skill matching no Moblee pack is named, and no repair is offered for it") {
            !flow.homeModel.needsRepair && flow.homeModel.foreignSkills == [skillName]
                && flow.homeModel.showsForeignSkills
        }
        await pause(2.0)
        let ownKept = (try? String(contentsOf: mineToKeep.appendingPathComponent("SKILL.md"), encoding: .utf8)) == ownWords
        say("the owner's own skill was named and left exactly as it was: \(ownKept)")
        // the practice home put back as it was, for the checks that follow
        // (the earlier Moblee's pack is left where it is: nothing is deleted)
        try? thisMoblees?.write(to: mineToKeep.appendingPathComponent("SKILL.md"))
        flow.homeModel.foreignSkillsSetAside = false
        flow.homeModel.checkSafety()
        let skillsSettled = !flow.homeModel.needsRepair && flow.homeModel.foreignSkills.isEmpty
        say("and the skills are settled again afterwards: \(skillsSettled)")

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

        // (v0.9.5) Something dropped on Moblee, on the real window, into the
        // real wiki the install above really made.
        //
        // The drop is handed to `Dropped.arrived`, which is the one door both
        // routes come through: the window's own `onDrop` loads what macOS gave
        // it and calls this, and the Dock icon's `application(_:open:)` calls
        // this. Everything from that door on — the refusals, the copying, the
        // naming, the diary, the receipt drawn on the real window and its
        // button really clicked — is what is walked here. What is NOT walked is
        // macOS's own dragging, which needs a hand on a trackpad; the piece
        // between it and this door (reading a file and some words out of what a
        // drag hands over) is checked in `LogicCheck` against real item
        // providers of the shape macOS really sends.
        let theirs = flow.home.appendingPathComponent("what the owner has", isDirectory: true)
        try? fm.createDirectory(at: theirs, withIntermediateDirectories: true)
        let inbox = Inbox.rawFolder(in: vaultURL)
        let dropMe = theirs.appendingPathComponent("Gym plan.md")
        try? "sets and reps\n".write(to: dropMe, atomically: true, encoding: .utf8)
        let dropMeBytes = try? Data(contentsOf: dropMe)
        func inInbox(_ name: String) -> URL { inbox.appendingPathComponent(name) }

        Dropped.shared.arrived(files: [dropMe], text: nil)
        await expect("a file dropped on Moblee lands in the wiki's inbox, and the receipt is on the real window", within: 15) {
            Dropped.shared.showing?.landed == ["Gym plan.md"]
                && (try? Data(contentsOf: inInbox("Gym plan.md"))) == dropMeBytes
        }
        await pause(1.2)
        await clickBigButton()                      // "Done"
        await expect("and the receipt's own button, really clicked, puts the owner back where they were") {
            Dropped.shared.showing == nil
        }
        await expect("which is the home screen they were on", within: 6) { control("change-assistant") != nil }

        // The Dock icon, through the delegate method macOS really calls.
        let dockFile = theirs.appendingPathComponent("Scan 1.pdf")
        try? "a scan\n".write(to: dockFile, atomically: true, encoding: .utf8)
        // The Dock route, as macOS really works it. `open -a` asks Launch
        // Services to give this file to this app, which is the very thing the
        // Dock does when a file is let go over the icon: the same Apple event,
        // to this same running copy. Nothing here calls Moblee's own code
        // directly, so what is walked is the whole route, macOS's part included.
        let askMacOS = Process()
        askMacOS.executableURL = URL(fileURLWithPath: "/usr/bin/open")
        askMacOS.arguments = ["-a", Bundle.main.bundleURL.path, dockFile.path]
        try? askMacOS.run()
        await expect("a file dropped on the Dock icon lands the same way, with the same receipt", within: 20) {
            Dropped.shared.showing?.landed == ["Scan 1.pdf"]
                && fm.fileExists(atPath: inInbox("Scan 1.pdf").path)
        }
        // And exactly one Moblee window still. A file given to a `WindowGroup`
        // from outside opens a second window by default, and an owner who
        // dropped a PDF on the Dock icon was left with two.
        await pause(1.5)
        await expect("and Moblee is still one window, not two") {
            NSApp.windows.filter { $0.isVisible && $0.contentView != nil }.count == 1
        }
        await pause(1.2)
        await clickBigButton()
        await expect("and that receipt is read the same way") { Dropped.shared.showing == nil }

        // (v0.9.5) FOUR FILES LET GO OVER THE ICON AT ONCE, which is one drop
        // and one Apple event carrying four file URLs. This is the walk that
        // was missing: it only ever sent one file through `open -a`, and one
        // file was the only case that worked. Four dropped together left
        // exactly the first in the inbox and showed the owner a receipt naming
        // that one and saying it was in their wiki — so an owner who dropped
        // four scans was told the drop had worked and stopped looking for the
        // other three. Verified on a built app on 26 September 2026, twice.
        let together = (1...4).map { theirs.appendingPathComponent("Together \($0).pdf") }
        for (at, one) in together.enumerated() {
            try? "scan \(at + 1)\n".write(to: one, atomically: true, encoding: .utf8)
        }
        let askForFour = Process()
        askForFour.executableURL = URL(fileURLWithPath: "/usr/bin/open")
        askForFour.arguments = ["-a", Bundle.main.bundleURL.path] + together.map(\.path)
        try? askForFour.run()
        await expect("four files let go over the Dock icon at once all land, and the receipt says how many", within: 25) {
            Dropped.shared.showing?.landed.sorted()
                == ["Together 1.pdf", "Together 2.pdf", "Together 3.pdf", "Together 4.pdf"]
                && together.allSatisfy { fm.fileExists(atPath: inInbox($0.lastPathComponent).path) }
        }
        await expect("and it is ONE receipt for the whole drop, not one for each file") {
            Dropped.shared.showing?.landed.count == 4
                && Inbox.sentence(for: Dropped.shared.showing ?? Inbox.Landing(), talksTo: "Claude")
                    .hasPrefix("4 things are in your wiki")
        }
        await pause(1.2)
        await clickBigButton()
        await expect("and that receipt is read the same way too") { Dropped.shared.showing == nil }
        // Still one window after four files at once, as after one.
        await expect("and Moblee is still one window after four files at once") {
            NSApp.windows.filter { $0.isVisible && $0.contentView != nil }.count == 1
        }

        // The same name again. The file already in the inbox must not be touched.
        Dropped.shared.arrived(files: [dropMe], text: nil)
        await expect("the same name dropped again gets a number, and the one already there is untouched", within: 15) {
            Dropped.shared.showing?.landed == ["Gym plan 2.md"]
                && (try? Data(contentsOf: inInbox("Gym plan.md"))) == dropMeBytes
                && (try? Data(contentsOf: inInbox("Gym plan 2.md"))) == dropMeBytes
        }
        await pause(1.2); await clickBigButton()
        await expect("and it is read the same way") { Dropped.shared.showing == nil }

        // A folder. Refused out loud, and nothing inside it copied.
        Dropped.shared.arrived(files: [theirs], text: nil)
        await expect("a folder dropped on Moblee is refused out loud, and nothing of it is copied in", within: 15) {
            Dropped.shared.showing?.turnedAway.map(\.why) == [.isAFolder]
                && !fm.fileExists(atPath: inInbox("what the owner has").path)
        }
        await pause(1.2)
        await clickBigButton()                      // "Carry on"
        await expect("and Carry on takes the refusal away") { Dropped.shared.showing == nil }

        // A drop into the middle of an install: the scripts are writing the
        // wiki this moment, so it waits, and the owner is told to.
        flow.install.phase = .running
        Dropped.shared.arrived(files: [dropMe], text: nil)
        await expect("a drop while a wiki is being made is refused, and never half-lands", within: 15) {
            Dropped.shared.showing?.wholeDrop == .busy && !fm.fileExists(atPath: inInbox("Gym plan 3.md").path)
        }
        flow.install.phase = .idle
        await pause(1.2); await clickBigButton()
        await expect("and that refusal is read the same way") { Dropped.shared.showing == nil }

        // Words rather than a file.
        Dropped.shared.arrived(files: [], text: "Remember to ask about the roof.")
        await expect("words dropped on Moblee become a dated note in the inbox that says where they came from", within: 15) {
            guard let made = Dropped.shared.showing?.landed.first, made.hasPrefix("Dropped note ") else { return false }
            let said = (try? String(contentsOf: inInbox(made), encoding: .utf8)) ?? ""
            return said.contains("dropped on the Moblee app") && said.contains("Remember to ask about the roof.")
        }
        await pause(1.2); await clickBigButton()
        await expect("and that receipt is read the same way") { Dropped.shared.showing == nil }

        // (v0.9.5) A picture with no file behind it, which is what an image
        // dragged out of a web page carries. Moblee used to ask macOS for files
        // and words only, so such a drag was never even offered to it: it
        // bounced back and nothing was said, while the app's own words promised
        // an owner could "drag a file, a photo or a piece of text".
        Dropped.shared.arrived(files: [], text: nil,
                               pictures: [Inbox.Picture(bytes: LogicCheck.smallestPNG, ending: "png")])
        await expect("a picture dropped with no file behind it becomes a dated picture in the inbox", within: 15) {
            guard let made = Dropped.shared.showing?.landed.first,
                  made.hasPrefix("Dropped picture "), made.hasSuffix(".png") else { return false }
            return (try? Data(contentsOf: inInbox(made))) == LogicCheck.smallestPNG
        }
        await pause(1.2); await clickBigButton()
        await expect("and that receipt is read the same way as a file's") { Dropped.shared.showing == nil }

        // THE PROMISE, after every one of the above: it copied, and it never
        // moved anything of the owner's and never deleted anything.
        let stillTheirs = ((try? fm.contentsOfDirectory(atPath: theirs.path)) ?? []).sorted()
        let dropsKeptTheOriginals = (try? Data(contentsOf: dropMe)) == dropMeBytes
            && stillTheirs == ["Gym plan.md", "Scan 1.pdf", "Together 1.pdf", "Together 2.pdf",
                               "Together 3.pdf", "Together 4.pdf"]
            && !((try? fm.contentsOfDirectory(atPath: inbox.path)) ?? []).contains { $0.hasPrefix(Inbox.incomingPrefix) }
        say("everything dropped is still exactly where the owner left it: \(dropsKeptTheOriginals)")
        let drops = dropsKeptTheOriginals && Dropped.shared.showing == nil

        // (v0.9.6) THE CHECK-UP THE OWNER RUNS THEMSELVES, on the real window and
        // against the real wiki this walk has just made, with the real check-up
        // out of the pack. The button is the one in the corner and it is really
        // clicked; then the screen is waited on, the report is looked for in the
        // wiki's own raw folder under the name the clinic note gives, and Done is
        // really pressed.
        //
        // Written on 26 September 2026 and NOT SEEN TO PASS: the live walk would
        // not start on this Mac that day (the app made no window and wrote not
        // one byte, on this build and on one from before any of this work). Every
        // decision it makes is read back without a window in `LogicCheck`, where
        // the same code runs the same check-up against a practice wiki; this is
        // here for the first walk that starts.
        var checkUp = false
        if let button = control("check-wiki") {
            // The receipt the walk has just dismissed takes the home screen a
            // moment to slide back from, and a click in that moment lands on a
            // screen still moving. Every other click after a screen changes
            // waits the same way. (27 September 2026: without it, the first
            // click did nothing and a second one a second later worked.)
            await pause(1.2)
            click(button)
            // On a practice wiki this small the check-up can be finished before
            // it is first looked at, so the working sentence is read from the
            // state it is shown in, and a check-up already done counts as begun.
            await expect("pressing Check my wiki opens the check-up, and it says it is working", within: 6) {
                guard flow.mode == .clinic else { return false }
                switch flow.clinic.state {
                case .running, .finished:
                    return Clinic.sentence(for: .running).hasPrefix("Checking your wiki")
                default:
                    return false
                }
            }
            // Long enough for the pack's own check-up on a wiki this size, and
            // well inside the limit the app itself gives it.
            await expect("the check-up finishes and the owner is told what was found", within: 60) {
                if case .finished = flow.clinic.state { return true }
                return false
            }
            if case .finished(let done) = flow.clinic.state {
                let report = flow.homeModel.vault?
                    .appendingPathComponent("raw/" + (done.savedAs ?? "none-at-all"))
                let body = report.flatMap { try? String(contentsOf: $0, encoding: .utf8) } ?? ""
                checkUp = done.savedAs == Clinic.reportName(ownerKey: "tom")
                    && body.contains("do_not_ingest: true") && body.contains("## 2. The owner's answers")
                    && !body.contains(flow.home.path)
                say("the check-up saved: \(done.savedAs ?? "nothing"); the wiki is \(done.card.state)")
                await expect("the report is in the wiki's raw folder, under the clinic note's own name, "
                             + "with nothing of the owner's Mac in it") { checkUp }
            }
            await pause(1.0)
            await clickBigButton()                      // "Done"
            await expect("and Done puts the owner back on the home screen") { flow.mode == .home }
        } else {
            say("FAILED: Check my wiki was not drawn on the home screen")
        }

        let skills = flow.home.appendingPathComponent(".claude/skills", isDirectory: true)
        let tripsThere = fm.fileExists(atPath: skills.appendingPathComponent("trips/SKILL.md").path)
        let gymThere = fm.fileExists(atPath: skills.appendingPathComponent("gym-log/.made-for-you").path)
        let sneakyKept = !fm.fileExists(atPath: skills.appendingPathComponent("sneaky").path)
        let brainSame = (try? Data(contentsOf: skills.appendingPathComponent("brain/SKILL.md"))) == brainBefore
        let noSmuggle = !fm.fileExists(atPath: "/tmp/moblee-pwned")
            && !flow.homeModel.tiles.contains { $0.key.contains("/") || $0.key.contains(";") }
        let ok = tripsState == .done && videosState == .handedOver && tripsThere && googleState == .done && pointerRight && guardLevel && newerLeftAlone && releaseLine && drops && checkUp
            && earlierPutBack && ownKept && skillsSettled
            && skill("gym-log")?.state == .done && gymThere
            && skill("sneaky")?.state == .blocked && sneakyKept
            && skill("brain")?.state == .blocked && brainSame && noSmuggle
        say("trips added: \(tripsThere); gym-log added: \(gymThere); link refused: \(sneakyKept); brain untouched: \(brainSame); nothing smuggled: \(noSmuggle)")
        say(ok ? "every screen opened, the install finished, waiting things were added, and the three bad requests were refused"
               : "the home screen did not behave as expected")
        exit(ok ? 0 : 1)
    }
}
