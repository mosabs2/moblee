// swift-tools-version:5.9
import PackageDescription

// The Moblee installer app. Built with Swift Package Manager and wrapped into
// Moblee.app by scripts/build-app.sh, so the build needs nothing beyond Xcode's
// own tools.
//
// (v0.15.0) Sparkle, pinned to one exact version, is the app's updater: it
// downloads a new Moblee, checks it is signed with the maintainer's update key,
// replaces the app wherever it lives and opens the new one. build-app.sh copies
// Sparkle.framework into Contents/Frameworks, which the rpath below points at.
let package = Package(
    name: "Moblee",
    platforms: [.macOS(.v14)],
    dependencies: [
        .package(url: "https://github.com/sparkle-project/Sparkle", exact: "2.10.0")
    ],
    targets: [
        .executableTarget(
            name: "Moblee",
            dependencies: [.product(name: "Sparkle", package: "Sparkle")],
            path: "Sources/Moblee",
            linkerSettings: [
                .unsafeFlags(["-Xlinker", "-rpath", "-Xlinker", "@executable_path/../Frameworks"])
            ]
        )
    ]
)
