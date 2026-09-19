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
        let args = CommandLine.arguments
        if let folder = Flow.value(after: "--snapshot", in: args) {
            drawAll(to: URL(fileURLWithPath: folder, isDirectory: true))
            exit(0)
        }
        if let folder = Flow.value(after: "--rehearse", in: args) {
            rehearse(to: URL(fileURLWithPath: folder, isDirectory: true))
        }
    }

    private static func draw(_ flow: Flow, _ name: String, to folder: URL) {
        let view = RootView()
            .environmentObject(flow)
            .environmentObject(flow.install)
            .environment(\.stillPicture, true)
            .frame(width: 720, height: 520)
        let renderer = ImageRenderer(content: view)
        renderer.scale = 2
        guard let image = renderer.nsImage,
              let tiff = image.tiffRepresentation,
              let rep = NSBitmapImageRep(data: tiff),
              let png = rep.representation(using: .png, properties: [:]) else {
            FileHandle.standardError.write("could not draw \(name)\n".data(using: .utf8)!)
            return
        }
        try? png.write(to: folder.appendingPathComponent(name + ".png"))
        print("drew \(name).png")
    }

    private static func scene(_ step: Step, _ configure: (Flow) -> Void = { _ in }) -> Flow {
        let flow = Flow()
        flow.step = step
        configure(flow)
        return flow
    }

    private static func drawAll(to folder: URL) {
        try? FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)

        draw(scene(.welcome), "00-welcome", to: folder)
        draw(scene(.checkup), "01-checkup", to: folder)
        draw(scene(.name), "02-name-empty", to: folder)
        draw(scene(.name) { $0.ownerName = "Sam" }, "03-name-typed", to: folder)
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
