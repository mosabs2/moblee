import SwiftUI
import AppKit

/// `--snapshot <folder>` draws every screen to a PNG file and quits without
/// opening a window, so each screen can be looked at and read after a change.
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
        guard let i = args.firstIndex(of: "--snapshot"), i + 1 < args.count else { return }
        let folder = URL(fileURLWithPath: args[i + 1], isDirectory: true)
        try? FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)

        for step in Step.allCases {
            let flow = Flow()
            flow.step = step
            let view = RootView()
                .environmentObject(flow)
                .environment(\.stillPicture, true)
                .frame(width: 720, height: 520)
            let renderer = ImageRenderer(content: view)
            renderer.scale = 2
            guard let image = renderer.nsImage,
                  let tiff = image.tiffRepresentation,
                  let rep = NSBitmapImageRep(data: tiff),
                  let png = rep.representation(using: .png, properties: [:]) else {
                FileHandle.standardError.write("could not draw \(step)\n".data(using: .utf8)!)
                continue
            }
            let name = String(format: "%02d-%@.png", step.rawValue, String(describing: step))
            try? png.write(to: folder.appendingPathComponent(name))
            print("drew \(name)")
        }
        exit(0)
    }
}
