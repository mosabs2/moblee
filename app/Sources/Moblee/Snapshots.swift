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
        if let folder = Flow.value(after: "--rehearse", in: args) {
            rehearse(to: URL(fileURLWithPath: folder, isDirectory: true))
        }
    }

    /// `--dark` draws the screens as they look in dark mode.
    private static let dark = Practice.args.contains("--dark")

    private static func draw(_ flow: Flow, _ name: String, to folder: URL) {
        let view = RootView()
            .environmentObject(flow)
            .environmentObject(flow.install)
            .environment(\.stillPicture, true)
            .environment(\.colorScheme, dark ? .dark : .light)
            .frame(width: 720, height: 520)
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
    /// the .icns the app carries.
    private static func drawIcon(to file: URL) {
        let icon = ZStack {
            RoundedRectangle(cornerRadius: 228, style: .continuous)
                .fill(LinearGradient(colors: [Color(red: 0.26, green: 0.50, blue: 0.96),
                                              Color(red: 0.10, green: 0.27, blue: 0.72)],
                                     startPoint: .top, endPoint: .bottom))
                .frame(width: 824, height: 824)
                .shadow(color: .black.opacity(0.30), radius: 24, y: 12)
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
        draw(scene(.welcome), "00-welcome", to: folder)
        draw(scene(.checkup), "01-checkup", to: folder)
        draw(scene(.name), "02-name-empty", to: folder)
        draw(scene(.name) { $0.ownerName = "Sam" }, "03-name-typed", to: folder)
        draw(scene(.promise) { $0.ownerName = "Sam" }, "03b-promise", to: folder)
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

        // the home screen of a Mac that already has a wiki
        let sample: [HomeModel.Tile] = [
            .init(kind: .item, key: "trips", title: "Trip planning",
                  why: "You said you travel most months.", detail: "About 1 min · 1 MB · free",
                  how: .silent, paid: false),
            .init(kind: .item, key: "videos", title: "Watch and summarise videos",
                  why: "You save YouTube videos to watch later.", detail: "About 4 min · 200 MB · free",
                  how: .terminal, paid: false),
            .init(kind: .item, key: "generation", title: "Create new images, video, voices and music",
                  why: "You want a voice for your podcast.", detail: "About 5 min · 0 MB · can cost money",
                  how: .clicks, paid: true),
        ]
        var google = HomeModel.Tile(kind: .item, key: "google", title: "Gmail, Google Calendar and Google Drive",
                                    why: "Your calendar lives in Google.", detail: "About 3 min · 0 MB · free",
                                    how: .clicks, paid: false)
        google.steps = [["Connectors", "The page opens. If not: in Claude, Settings, then Connectors"],
                        ["Switch on three", "Gmail, Google Calendar, Google Drive. Connect, then sign in"],
                        ["Check it worked", "Ask Claude: what is on my calendar today?"]]
        func homeScene(_ configure: (Flow) -> Void) -> Flow {
            let f = Flow(); f.mode = .home; f.homeModel.loaded = true
            f.homeModel.wikiVersion = "0.8.0"; f.homeModel.packVersion = "0.8.0"
            configure(f); return f
        }
        draw(homeScene { $0.homeModel.tiles = sample }, "08-home-waiting", to: folder)
        draw(homeScene { f in
            var t = sample; t[0].state = .done; t[1].state = .handedOver; t[2].state = .failed
            f.homeModel.tiles = t
        }, "09-home-states", to: folder)
        draw(homeScene { _ in }, "10-home-nothing-waiting", to: folder)
        draw(homeScene { $0.homeModel.wikiVersion = "0.7.0" }, "11-home-update", to: folder)
        draw(homeScene { $0.homeModel.needsRepair = true }, "12-home-repair", to: folder)
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
        flow.install.start(home: flow.home, ownerName: flow.trimmedName,
                           wikiName: place.name, location: place.url, bundledPack: pack)

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
