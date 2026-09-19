// swift-tools-version:5.9
import PackageDescription

// The Moblee installer app. Built with Swift Package Manager and wrapped into
// Moblee.app by scripts/build-app.sh, so the build needs nothing beyond Xcode's
// own tools.
let package = Package(
    name: "Moblee",
    platforms: [.macOS(.v14)],
    targets: [
        .executableTarget(
            name: "Moblee",
            path: "Sources/Moblee"
        )
    ]
)
