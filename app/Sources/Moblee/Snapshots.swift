import SwiftUI
import AppKit

/// Two ways of looking at the app without opening a window.
///
/// `--snapshot <folder>` draws every screen, in each of its states, to PNG
/// files, so each can be looked at and read after a change.
///
/// `--rehearse <folder>` (only with `--home <practice folder>`) runs a real
/// install through the same code the window uses, into the practice home
/// folder, then draws the build and hand-off screens as they ended up.
///
/// Animations are drawn in their finished position.
private struct StillPictureKey: EnvironmentKey {
    static let defaultValue = false
}

extension EnvironmentValues {
    var stillPicture: Bool {
        get { self[StillPictureKey.self] }
        set { self[StillPictureKey.self] = newValue }
    }
}

@MainActor
enum Snapshots {
    static func runIfAsked() {
        let args = Practice.args
        if let folder = Flow.value(after: "--snapshot", in: args) {
            drawAll(to: URL(fileURLWithPath: folder, isDirectory: true))
            exit(0)
        }
        if let file = Flow.value(after: "--icon", in: args) {
            drawIcon(to: URL(fileURLWithPath: file))
            exit(0)
        }
        if args.contains("--check-logic") {
            LogicCheck.run()
        }
        if let folder = Flow.value(after: "--rehearse", in: args) {
            rehearse(to: URL(fileURLWithPath: folder, isDirectory: true))
        }
    }

    /// `--dark` draws the screens as they look in dark mode.
    private static let dark = Practice.args.contains("--dark")

    /// (v0.9.4) The made-up name the drawn screens use where a name is needed
    /// in Arabic. "نور" is the Arabic word for "light", and is an ordinary given
    /// name; it is nobody's in particular, and there is no surname or anything
    /// else about a person anywhere in it.
    static let arabicName = "نور"

    private static func draw(_ flow: Flow, _ name: String, to folder: URL) {
        let view = RootView()
            .environmentObject(flow)
            .environmentObject(flow.install)
            .environment(\.stillPicture, true)
            .environment(\.colorScheme, dark ? .dark : .light)
            // (v0.9.4) `--rtl` mirrors the whole run, every screen in it, so
            // that a later version can put both appearances and both directions
            // on one page without a list of screens of its own. The mirroring
            // itself is inside `RootView`, which is the same screens the window
            // draws, so a picture file and the window can never differ.
            // The window's smallest size, at whatever size the words are being
            // drawn: a screen drawn at the biggest size is drawn on the
            // smallest window that size can be shown in. (v0.9.4)
            .frame(width: Theme.leastWidth, height: Theme.leastHeight)
        let renderer = ImageRenderer(content: view)
        renderer.scale = 2
        var drawn: NSImage?
        if let look = NSAppearance(named: dark ? .darkAqua : .aqua) {
            look.performAsCurrentDrawingAppearance { drawn = renderer.nsImage }
        } else {
            drawn = renderer.nsImage
        }
        guard let image = drawn,
              let tiff = image.tiffRepresentation,
              let rep = NSBitmapImageRep(data: tiff),
              let png = rep.representation(using: .png, properties: [:]) else {
            FileHandle.standardError.write("could not draw \(name)\n".data(using: .utf8)!)
            return
        }
        try? png.write(to: folder.appendingPathComponent(name + ".png"))
        print("drew \(name).png")
    }

    /// `--icon <file.png>` draws the app's icon at 1024 points, from the same
    /// symbols and colour the screens use, so the icon never needs an artist
    /// or an image file kept by hand. app/scripts/make-icon.sh turns it into
    /// the .icns the app carries. It is a picture and not a screen, so it is
    /// never mirrored: `--rtl` does not reach it, and must not. (v0.9.4)
    private static func drawIcon(to file: URL) {
        let icon = ZStack {
            RoundedRectangle(cornerRadius: 228, style: .continuous)
                .fill(LinearGradient(colors: [Color(red: 0.26, green: 0.50, blue: 0.96),
                                              Color(red: 0.10, green: 0.27, blue: 0.72)],
                                     startPoint: .top, endPoint: .bottom))
                .frame(width: 824, height: 824)
                .shadow(color: .black.opacity(0.30), radius: 24, y: 12)
            // The icon is a fixed 1024 points and has nothing to do with the
            // size the owner reads at, so these two are not asked of Theme.
            Image(systemName: "books.vertical.fill")
                .font(.system(size: 400, weight: .medium))
                .foregroundStyle(.white)
                .offset(x: -30, y: 40)
            Image(systemName: "sparkles")
                .font(.system(size: 210, weight: .semibold))
                .foregroundStyle(Color(red: 1.0, green: 0.86, blue: 0.42))
                .offset(x: 215, y: -215)
        }
        .frame(width: 1024, height: 1024)
        let renderer = ImageRenderer(content: icon)
        renderer.scale = 1
        guard let image = renderer.nsImage, let tiff = image.tiffRepresentation,
              let rep = NSBitmapImageRep(data: tiff),
              let png = rep.representation(using: .png, properties: [:]) else { return }
        try? png.write(to: file)
        print("drew the icon to \(file.path)")
    }

    private static func scene(_ step: Step, _ configure: (Flow) -> Void = { _ in }) -> Flow {
        let flow = Flow()
        flow.step = step
        configure(flow)
        return flow
    }

    private static func drawAll(to folder: URL) {
        try? FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        // No window and no screen being drawn yet, so waiting here is safe.
        Checkup.knownBeforeDrawing = Checkup.developerToolsInstalled()

        draw(scene(.welcome) { $0.offerMove = true }, "00a-move-to-applications", to: folder)
        // (v0.9.4) The rest of the move screen. None of these had ever been
        // drawn: they are only reached by really moving the app on a real Mac,
        // so the only way to look at their words was to break a move on purpose.
        draw(scene(.welcome) { $0.offerMove = true; $0.moveStart = .askingTheOtherOne },
             "00b-move-asking-the-other-one", to: folder)
        let moveFailures: [(Placement.Failure, String)] = [
            (.copyIncomplete, "00c-move-failed-copy"), (.somethingElseThere, "00d-move-failed-something-else"),
            (.anotherMobleeIsOpen, "00e-move-failed-another-open"), (.otherMobleeIsBusy, "00f-move-failed-other-busy"),
            (.markNotCleared, "00g-move-failed-mark"),
        ]
        for (why, name) in moveFailures {
            draw(scene(.welcome) { $0.offerMove = true; $0.moveStart = .failed; $0.moveWhy = why }, name, to: folder)
        }
        draw(scene(.welcome), "00-welcome", to: folder)
        draw(scene(.checkup), "01-checkup", to: folder)
        // a ChatGPT app that is an older one, with no agent inside it
        Checkup.pretendOlderChatGPT = true
        draw(scene(.checkup) { $0.assistant = .chatgpt }, "01b-checkup-older-chatgpt", to: folder)
        Checkup.pretendOlderChatGPT = false
        draw(scene(.name), "02-name-empty", to: folder)
        draw(scene(.name) { $0.ownerName = "Sam" }, "03-name-typed", to: folder)
        // (v0.9.4) A name the owner typed in Arabic, on the three screens that
        // show it: the box itself, the folder it will be called after, and the
        // hand-off that sends the owner to find that folder. An owner's Mac may
        // be in English while their own name is not, and a name read right to
        // left inside a sentence read left to right is where the quotes and the
        // full stop beside it go to the wrong side. Drawn in both directions,
        // because both happen: an Arabic name on an English Mac, and the same
        // name on a Mac that is itself in Arabic.
        draw(scene(.name) { $0.ownerName = Self.arabicName }, "02b-name-arabic", to: folder)
        draw(scene(.promise) { $0.ownerName = Self.arabicName }, "03g-promise-arabic-name", to: folder)
        draw(scene(.promise) { $0.ownerName = "Sam" }, "03b-promise", to: folder)
        draw(scene(.assistant) { $0.ownerName = "Sam" }, "03c-assistant-unanswered", to: folder)
        draw(scene(.assistant) { $0.ownerName = "Sam"; $0.assistant = .chatgpt }, "03d-assistant-answered", to: folder)
        draw(scene(.promise) { $0.ownerName = "Sam"; $0.assistant = .chatgpt }, "03e-promise-chatgpt", to: folder)
        draw(scene(.promise) { $0.ownerName = "Sam"; $0.assistant = .both }, "03f-promise-both", to: folder)
        draw(scene(.build) { f in
            f.install.phase = .running
            f.install.items[0].state = .done
            f.install.items[1].state = .done
            f.install.items[2].state = .running
        }, "04-build-running", to: folder)
        draw(scene(.build) { f in
            f.install.phase = .finished
            for i in f.install.items.indices { f.install.items[i].state = .done }
        }, "05-build-finished", to: folder)
        draw(scene(.build) { f in
            f.install.phase = .failed(why: "safety-layer")
            for i in 0..<3 { f.install.items[i].state = .done }
            f.install.items[3].state = .failed
        }, "06-build-failed", to: folder)
        draw(scene(.handoff) { f in
            f.ownerName = "Sam"
            f.install.vaultPath = "/Users/sam/Wiki/Sam Wiki"
        }, "07-handoff", to: folder)
        draw(scene(.handoff) { f in
            f.ownerName = "Sam"; f.assistant = .chatgpt
            f.install.vaultPath = "/Users/sam/Wiki/Sam Wiki"
        }, "07b-handoff-chatgpt", to: folder)
        draw(scene(.handoff) { f in
            f.ownerName = "Sam"; f.assistant = .both
            f.install.vaultPath = "/Users/sam/Wiki/Sam Wiki"
        }, "07c-handoff-both", to: folder)
        draw(scene(.handoff) { f in
            f.ownerName = Self.arabicName
            f.install.vaultPath = "/Users/sam/Wiki/\(Self.arabicName) Wiki"
        }, "07d-handoff-arabic-name", to: folder)

        // the Trust screen and the proof, in each of their states
        let trustStages: [(TrustScreen.Stage, String)] = [
            (.openFolder, "06a-trust-open-folder"), (.steps, "06b-trust-steps"), (.offer, "06c-trust-offer"), (.proving, "06d-trust-proving"),
            (.proved, "06e-trust-proved"), (.notRunning, "06f-trust-not-running"), (.cannotTell, "06g-trust-cannot-tell"),
        ]
        for (stage, name) in trustStages {
            draw(scene(.trust) { f in
                f.assistant = .chatgpt; f.trustStart = stage
                f.install.vaultPath = "/Users/sam/Wiki/Sam Wiki"
            }, name, to: folder)
        }

        // the home screen of a Mac that already has a wiki
        let sample: [HomeModel.Tile] = [
            .init(kind: .item, key: "trips", title: "Trip planning",
                  why: "You said you travel most months.", detail: "About 1 min · 1 MB · free",
                  how: .silent, paid: false),
            .init(kind: .item, key: "videos", title: "Watch and summarise videos",
                  why: "You save YouTube videos to watch later.", detail: "About 4 min · 200 MB · free",
                  how: .terminal, paid: false),
            .init(kind: .item, key: "generation", title: "Create new images, video, voices and music",
                  why: "You want a voice for your podcast.", detail: "About 5 min · can cost money",
                  how: .clicks, paid: true),
        ]
        var google = HomeModel.Tile(kind: .item, key: "google", title: "Gmail, Google Calendar and Google Drive",
                                    why: "Your calendar lives in Google.", detail: "About 3 min · free",
                                    how: .clicks, paid: false)
        google.steps = [["Connectors", "The page opens. If it says moved: Customise, then Connectors"],
                        ["Switch on three", "Gmail, Google Calendar, Google Drive. Connect, then sign in"],
                        ["Check it worked", "Ask Claude: what is on my calendar today?"]]
        func homeScene(_ configure: (Flow) -> Void) -> Flow {
            let f = Flow(); f.mode = .home; f.homeModel.loaded = true
            f.homeModel.wikiVersion = "0.8.1"; f.homeModel.packVersion = "0.8.1"
            configure(f); return f
        }
        draw(homeScene { $0.homeModel.tiles = sample }, "08-home-waiting", to: folder)
        draw(homeScene { f in
            var t = sample; t[0].state = .done; t[1].state = .handedOver; t[2].state = .failed
            f.homeModel.tiles = t
        }, "09-home-states", to: folder)
        draw(homeScene { _ in }, "10-home-nothing-waiting", to: folder)
        draw(homeScene { $0.homeModel.tiles = sample; $0.homeModel.assistant = .both }, "08b-home-waiting-both", to: folder)
        draw(homeScene { $0.homeModel.assistant = .chatgpt }, "10b-home-chatgpt", to: folder)
        draw(homeScene { f in f.mode = .update; f.askingAssistant = true }, "15a-update-asks-assistant", to: folder)
        // a wiki that a newer Moblee made: no Change, and no Repair from this app
        draw(homeScene { f in
            f.homeModel.tiles = sample; f.homeModel.assistant = .both
            f.homeModel.wikiVersion = "0.9.1"; f.homeModel.packVersion = "0.9.0"
        }, "08c-home-wiki-newer", to: folder)
        draw(homeScene { f in
            f.homeModel.wikiVersion = "0.9.1"; f.homeModel.packVersion = "0.9.0"
            f.homeModel.safetyOff = true; f.homeModel.needsRepair = true
        }, "12b-home-repair-wiki-newer", to: folder)
        draw(homeScene { $0.homeModel.wikiVersion = "0.7.0" }, "11-home-update", to: folder)
        // a newer Moblee published: one quiet line, bottom left, on the ordinary
        // home screen; and not over an update this app can already make
        draw(homeScene { f in
            f.homeModel.tiles = sample; f.homeModel.newerRelease = "0.9.3"
        }, "08d-home-newer-release", to: folder)
        draw(homeScene { f in
            f.homeModel.wikiVersion = "0.7.0"; f.homeModel.newerRelease = "0.9.3"
        }, "11b-home-update-newer-release-hidden", to: folder)
        draw(homeScene { $0.homeModel.needsRepair = true }, "12-home-repair", to: folder)
        // (v0.9.4) A skill wearing a Moblee name that no Moblee left here: named,
        // with what to do, in place of a Repair that could never succeed.
        draw(homeScene { $0.homeModel.foreignSkills = ["companion"] }, "12c-home-skill-not-moblees", to: folder)
        draw(homeScene { $0.homeModel.tiles = sample; $0.homeModel.explaining = sample[1] }, "13-explain-terminal", to: folder)
        draw(homeScene { $0.homeModel.tiles = sample; $0.homeModel.explaining = sample[2] }, "14-explain-clicks", to: folder)
        draw(homeScene { $0.homeModel.tiles = [google]; $0.homeModel.explaining = google }, "14b-explain-google", to: folder)
        draw(homeScene { f in var g = google; g.state = .handedOver; f.homeModel.tiles = [g] }, "14c-google-handed-over", to: folder)
        var made = HomeModel.Tile(kind: .skill, key: "gym-log", title: "A skill Claude wrote: gym-log",
                                  why: "You asked to log gym sets by saying log gym.",
                                  detail: "Logs the owner's gym sets to the Gym Log page when they say log gym.",
                                  how: .silent, paid: false)
        made.files = ["SKILL.md"]
        var bad = HomeModel.Tile(kind: .skill, key: "brain", title: "A skill Claude wrote: brain",
                                 why: "A better brain.", detail: "", how: .silent, paid: false)
        bad.state = .blocked
        bad.note = "'brain' is the name of one of Moblee's own skills; the draft needs a different name."
        draw(homeScene { $0.homeModel.tiles = [made, bad] }, "16-home-skills", to: folder)
        draw(homeScene { $0.homeModel.tiles = [made]; $0.homeModel.explaining = made }, "17-explain-skill", to: folder)
        draw(homeScene { $0.homeModel.listUnreadable = true }, "18-home-list-unreadable", to: folder)
        draw(homeScene { f in
            f.mode = .update
            f.install.items = InstallRun.updateItems()
            f.install.phase = .running
            for i in 0..<4 { f.install.items[i].state = .done }
            f.install.items[4].state = .running
        }, "15-update-running", to: folder)
        // (v0.9.4) How an update ENDS. Only the running state was ever drawn,
        // so four sentences an owner meets at the end of an update had never
        // been looked at once — the refused-commit one is three lines long.
        func updateScene(_ configure: @escaping (Flow) -> Void) -> Flow {
            homeScene { f in
                f.mode = .update
                f.install.items = InstallRun.updateItems()
                for i in f.install.items.indices { f.install.items[i].state = .done }
                configure(f)
            }
        }
        draw(updateScene { $0.install.phase = .finished }, "15b-update-finished", to: folder)
        draw(updateScene { f in f.install.phase = .finished; f.install.partial = true },
             "15c-update-finished-partial", to: folder)
        draw(updateScene { f in f.install.needsCommit = true; f.install.phase = .needsCommit },
             "15d-update-refused", to: folder)
        draw(updateScene { f in
            f.install.items[4].state = .failed
            f.install.phase = .failed(why: "skills")
        }, "15e-update-failed", to: folder)

        // (v0.9.4) The Terminal explanation, one picture at a time. All three
        // are drawn, because an owner who does not read much meets them one
        // after another and each has to stand on its own.
        draw(homeScene { f in
            f.homeModel.tiles = sample; f.homeModel.explaining = sample[1]
            f.homeModel.explainTerminalStep = 1
        }, "13b-explain-terminal-two", to: folder)
        draw(homeScene { f in
            f.homeModel.tiles = sample; f.homeModel.explaining = sample[1]
            f.homeModel.explainTerminalStep = 2
        }, "13c-explain-terminal-three", to: folder)

        // (v0.9.5) The ring on two of the new listen controls: the one on a
        // tile, which is the smallest control on the busiest screen, and the one
        // at the end of a Trust step, which is the smallest of all. A ring round
        // a 16-point symbol has to be seen in light and in dark, and it has to
        // clear the card's own edge and the words beside it, and no picture file
        // could show either until now.
        FocusedControl.drawnRing = RequestTile.listenId(sample[1])
        draw(homeScene { $0.homeModel.tiles = sample }, "22a-keyboard-ring-listen-tile", to: folder)
        FocusedControl.drawnRing = TrustSteps.listenId(step: 3)
        draw(scene(.trust) { f in
            f.assistant = .chatgpt; f.trustStart = .steps
            f.install.vaultPath = "/Users/sam/Wiki/Sam Wiki"
        }, "22b-keyboard-ring-listen-step", to: folder)

        // (v0.9.4) The ring that says which control the keyboard is on, on the
        // kinds of control that could not be reached by the keyboard at
        // all until now: a tile's own button, the quiet "Not now", and one of
        // the three cards on the question of which assistant. Drawn
        // in light and in dark, because a ring nobody can see is no ring.
        FocusedControl.drawnRing = RequestTile.buttonId(sample[1])
        draw(homeScene { $0.homeModel.tiles = sample }, "20a-keyboard-ring-tile", to: folder)
        FocusedControl.drawnRing = "quiet"
        draw(homeScene { f in
            f.homeModel.tiles = sample; f.homeModel.explaining = sample[1]
        }, "20b-keyboard-ring-not-now", to: folder)
        // The screen nobody can skip: Next is greyed out until one of the three
        // is chosen, so a card the keyboard cannot reach shut an owner who
        // cannot use a mouse out of the install altogether. The ring goes round
        // a whole card, which is a much larger thing than the other two, and is
        // drawn here so it can be looked at.
        FocusedControl.drawnRing = "assistant-claude"
        draw(scene(.assistant) { $0.ownerName = "Sam" }, "20c-keyboard-ring-assistant", to: folder)
        FocusedControl.drawnRing = nil

        // (v0.9.5) Something dropped on Moblee: the receipt, and the two
        // refusals that matter most. The states are only reachable by really
        // dropping a file on a real window, so, like the move screen's, the only
        // way to read their words was to set them here. The made-up names are
        // nobody's: a gym plan and a scan, the same sort of thing the sample
        // tiles above are about.
        func dropScene(_ landing: Inbox.Landing) -> Flow {
            let f = Flow(); f.mode = .home; f.homeModel.loaded = true
            Dropped.shared.showing = landing
            return f
        }
        draw(dropScene(Inbox.Landing(landed: ["Gym plan.pdf"])), "21a-drop-receipt-one", to: folder)
        // Five landed and one turned away, which puts every part of the receipt
        // on one picture: the count in the sentence, the clause about the one
        // that did not go, four names, the line that says how many more there
        // were, and a refused line with its reason.
        draw(dropScene(Inbox.Landing(
            landed: ["Gym plan.pdf", "Scan 1.pdf", "Scan 2.pdf", "Notes.txt", "Recipe.md"],
            turnedAway: [.init(name: "Holiday film.mov", why: .tooBig)])),
             "21b-drop-receipt-several", to: folder)
        draw(dropScene(Inbox.Landing(wholeDrop: .noWikiYet)), "21c-drop-no-wiki", to: folder)
        draw(dropScene(Inbox.Landing(wholeDrop: .isAFolder)), "21d-drop-folder", to: folder)
        Dropped.shared.showing = nil

        // (v0.9.6) The example wiki, being read. Four screens, because those are
        // the four states an owner meets: the page it opens on (`Welcome.md`, not
        // `Index.md`), a content page with links in the middle of its sentences
        // and the row of buttons under it that the keyboard follows them by, the
        // list of every page for a reader who has lost the thread, and a link
        // that leads nowhere — which the shipped example never contains, so the
        // only way to look at its quiet line is to follow one here.
        //
        // The page chosen is `Bread.md`: it is the page the example is really
        // about, and it is the one that carries every piece of markdown at once —
        // two heading levels, a bullet list, bold, italic, inline code and four
        // links. Each is drawn in light and in dark and mirrored, from the same
        // switches as every other screen.
        func exampleScene(_ configure: (ExampleReader) -> Void = { _ in }) -> Flow {
            let flow = Flow()
            flow.mode = .home
            flow.homeModel.loaded = true
            flow.openExample()
            if let reader = flow.example { configure(reader) }
            return flow
        }
        draw(exampleScene(), "23a-example-welcome", to: folder)
        draw(exampleScene { $0.follow("Bread") }, "23b-example-page", to: folder)
        draw(exampleScene { $0.openPages() }, "23c-example-pages", to: folder)
        // A page name the example has none of. The words say "That page is not in
        // the example." and the owner is left exactly where they were.
        draw(exampleScene { $0.follow("Porridge") }, "23d-example-link-missing", to: folder)

        // (v0.9.6) The check-up an owner runs themselves. Its states are only
        // reachable by really running the pack's check-up against a real wiki, so
        // they are set here to be looked at: while it runs, a wiki that looks
        // healthy, a wiki with things to look at, and the two refusals that matter
        // most — no wiki on the Mac at all, and a Moblee that cannot find its own
        // check-up. The findings on the cards are made up and are of the setup
        // only; nothing on them is anybody's.
        func clinicScene(_ state: Clinic.State) -> Flow {
            let f = Flow()
            f.mode = .clinic
            f.homeModel.loaded = true
            f.homeModel.wikiVersion = "0.9.6"; f.homeModel.packVersion = "0.9.6"
            f.clinic.state = state
            return f
        }
        let healthyCard = Clinic.Card(
            lines: ["Moblee health card, 26 September 2026"],
            state: "healthy",
            headline: "This wiki looks healthy. Nothing was found to be wrong.",
            actions: ["Nothing to do. Run the check-up again next month."])
        let poorlyCard = Clinic.Card(
            lines: ["Moblee health card, 26 September 2026"],
            state: "unwell",
            headline: "This wiki needs attention: 4 things to look at. 1 more could not be checked.",
            wrong: [.init(code: "F13", line: "The wiki is in the Desktop folder, which iCloud copies."),
                    .init(code: "F29", line: "macOS stops jobs that run on their own from reading that folder."),
                    .init(code: "F02", line: "The delete guard is an older copy than this Moblee's.")],
            wrongTotal: 4,
            unchecked: [.init(code: "F36", line: "Whether the guard is trusted cannot be seen from here.")],
            uncheckedTotal: 1,
            actions: ["Open the Moblee app: it offers Repair, or the update, when it can help."])
        draw(clinicScene(.running), "24a-clinic-running", to: folder)
        draw(clinicScene(.finished(.init(card: healthyCard,
                                         savedAs: "clinic-report-sam-checkup-2026-09-24.md"))),
             "24b-clinic-healthy", to: folder)
        draw(clinicScene(.finished(.init(card: poorlyCard,
                                         savedAs: "clinic-report-sam-checkup-2026-09-24.md"))),
             "24c-clinic-problems", to: folder)
        draw(clinicScene(.noWiki), "24d-clinic-no-wiki", to: folder)
        draw(clinicScene(.couldNotCheck(.noCheckup, savedAs: "clinic-report-sam-checkup-2026-09-24.md")),
             "24e-clinic-no-checkup", to: folder)
        // And the home screen with a dropped file still copying, where "Check my
        // wiki" is greyed: the one state of that button an owner can actually
        // meet and the only one worth looking at, since a repair takes the whole
        // corner away instead.
        AppDelegate.dropsInFlight += 1
        draw(homeScene { $0.homeModel.tiles = sample }, "24f-home-check-my-wiki-while-busy", to: folder)
        AppDelegate.dropsInFlight -= 1

        // (v0.9.4) And the same screens at the biggest size an owner can set,
        // on the smallest window that size can be shown in. The three hardest
        // are drawn: three cards side by side, one card alone, and the longest
        // sentence in the app. Nothing here touches what the owner has set.
        let started = TextSize.shared.step
        TextSize.shared.drawAt(.biggest)
        draw(homeScene { $0.homeModel.tiles = sample }, "19a-biggest-home-waiting", to: folder)
        draw(homeScene { $0.homeModel.tiles = sample; $0.homeModel.explaining = sample[1] },
             "19b-biggest-explain-terminal", to: folder)
        draw(updateScene { f in f.install.needsCommit = true; f.install.phase = .needsCommit },
             "19c-biggest-update-refused", to: folder)
        // (v0.9.5) And the four screens that carry the most listen controls, at
        // the biggest size an owner can set, because that is where a screen full
        // of small controls comes apart if it is going to. The Trust steps have
        // one at the end of each of five lines on one card; the hand-off has one
        // on each of three cards and one under them; the check-up has one on each
        // of three cards; and the drop receipt has one on a card of names beside
        // a card that is as tall as its own list.
        draw(scene(.trust) { f in
            f.assistant = .chatgpt; f.trustStart = .steps
            f.install.vaultPath = "/Users/sam/Wiki/Sam Wiki"
        }, "19d-biggest-trust-steps", to: folder)
        draw(scene(.handoff) { f in
            f.ownerName = Self.arabicName
            f.install.vaultPath = "/Users/sam/Wiki/\(Self.arabicName) Wiki"
        }, "19e-biggest-handoff", to: folder)
        draw(scene(.checkup), "19f-biggest-checkup", to: folder)
        Dropped.shared.showing = Inbox.Landing(
            landed: ["Gym plan.pdf", "Scan 1.pdf", "Scan 2.pdf", "Notes.txt", "Recipe.md"],
            turnedAway: [.init(name: "Holiday film.mov", why: .tooBig)])
        draw(homeScene { _ in }, "19g-biggest-drop-receipt", to: folder)
        Dropped.shared.showing = nil
        // (v0.9.6) And the example wiki at the biggest size, which is where a
        // screen made of a page of words comes apart if it is going to: the page
        // and the row of link buttons under it, and the list of nine pages, which
        // is the tallest thing the example draws.
        draw(exampleScene { $0.follow("Bread") }, "19h-biggest-example-page", to: folder)
        draw(exampleScene { $0.openPages() }, "19i-biggest-example-pages", to: folder)
        TextSize.shared.drawAt(started)
    }

    private static func rehearse(to folder: URL) {
        let flow = Flow()
        guard flow.isTestMode else {
            print("--rehearse only runs with --home <practice folder>; nothing was done.")
            exit(2)
        }
        guard let pack = flow.bundledPack else {
            print("no pack found inside the app (or at --pack); nothing was done.")
            exit(2)
        }
        try? FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        if flow.trimmedName.isEmpty { flow.ownerName = "Sam" }

        let place = flow.freeLocation()
        flow.assistant = .claude
        flow.install.start(home: flow.home, ownerName: flow.trimmedName,
                           wikiName: place.name, location: place.url, bundledPack: pack,
                           assistant: .claude)

        let deadline = Date().addingTimeInterval(180)
        while flow.install.phase == .running && Date() < deadline {
            RunLoop.main.run(until: Date().addingTimeInterval(0.1))
        }

        flow.step = .build
        draw(flow, "rehearsal-build", to: folder)
        flow.step = .handoff
        draw(flow, "rehearsal-handoff", to: folder)

        for item in flow.install.items { print("step \(item.key): \(item.state)") }
        print("phase: \(flow.install.phase)")
        print("wiki: \(flow.install.vaultPath ?? "none")")
        exit(flow.install.phase == .finished ? 0 : 1)
    }
}
