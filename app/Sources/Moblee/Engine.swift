import Foundation

/// Runs one of the pack's own programs and hands back its progress lines
/// (the ones that start "@@moblee "). Everything the app adds to the Mac goes
/// through the same scripts a Terminal user runs.
final class EngineTask {
    typealias Event = [String: Any]

    private var process: Process?
    private var buffer = Data()
    private let queue = DispatchQueue(label: "moblee.engine")

    /// The environment every engine run gets: the practice or real home, the
    /// Mac's own tools only, and nothing inherited from whatever started the
    /// app, so every owner's run behaves the same way.
    static func environment(home: URL) -> [String: String] {
        var env: [String: String] = [
            "HOME": home.path,
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "LANG": "en_GB.UTF-8",
        ]
        let inherited = ProcessInfo.processInfo.environment
        for key in ["USER", "LOGNAME", "TMPDIR", "SHELL"] {
            if let v = inherited[key] { env[key] = v }
        }
        return env
    }

    func run(_ executable: String, _ arguments: [String], home: URL,
             onEvent: @escaping @MainActor (Event) -> Void,
             onEnd: @escaping @MainActor (Int32) -> Void) {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: executable)
        p.arguments = arguments
        p.environment = Self.environment(home: home)
        p.standardInput = FileHandle.nullDevice
        let out = Pipe()
        p.standardOutput = out
        p.standardError = out

        out.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard let self, !data.isEmpty else { return }
            self.queue.async {
                for event in self.take(data) {
                    DispatchQueue.main.async { MainActor.assumeIsolated { onEvent(event) } }
                }
            }
        }
        p.terminationHandler = { [weak self] proc in
            out.fileHandleForReading.readabilityHandler = nil
            let rest = out.fileHandleForReading.readDataToEndOfFile()
            let code = proc.terminationStatus
            self?.queue.async {
                let events = (self?.take(rest + Data([0x0A]))) ?? []
                DispatchQueue.main.async {
                    MainActor.assumeIsolated {
                        for e in events { onEvent(e) }
                        onEnd(code)
                    }
                }
            }
        }
        do {
            try p.run()
            process = p
        } catch {
            DispatchQueue.main.async { MainActor.assumeIsolated { onEnd(-1) } }
        }
    }

    private func take(_ data: Data) -> [Event] {
        buffer.append(data)
        var events: [Event] = []
        while let nl = buffer.firstIndex(of: 0x0A) {
            let lineData = buffer.subdata(in: buffer.startIndex..<nl)
            buffer.removeSubrange(buffer.startIndex...nl)
            let marker = "@@moblee "
            guard let line = String(data: lineData, encoding: .utf8), line.hasPrefix(marker),
                  let json = line.dropFirst(marker.count).data(using: .utf8),
                  let obj = try? JSONSerialization.jsonObject(with: json) as? Event else { continue }
            events.append(obj)
        }
        return events
    }

    /// Runs a program to its end in the background and gives back what it
    /// printed. Never blocks the main thread.
    static func output(of executable: String, _ arguments: [String], home: URL,
                       then: @escaping @MainActor (Int32, Data) -> Void) {
        DispatchQueue.global(qos: .userInitiated).async {
            let p = Process()
            p.executableURL = URL(fileURLWithPath: executable)
            p.arguments = arguments
            p.environment = environment(home: home)
            p.standardInput = FileHandle.nullDevice
            let out = Pipe()
            p.standardOutput = out
            p.standardError = Pipe()
            var data = Data()
            var code: Int32 = -1
            do {
                try p.run()
                data = out.fileHandleForReading.readDataToEndOfFile()
                p.waitUntilExit()
                code = p.terminationStatus
            } catch {}
            DispatchQueue.main.async { MainActor.assumeIsolated { then(code, data) } }
        }
    }
}
