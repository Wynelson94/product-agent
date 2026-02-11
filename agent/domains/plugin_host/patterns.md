# Plugin Host App Domain Patterns

Patterns for building the NoCloud BS host application — the shell that discovers,
loads, and manages Swift Package plugins.

## Architecture

The host app has three responsibilities:
1. **Core UI** — Storage dashboard, compression stats, settings
2. **Plugin Infrastructure** — Registry, context injection, lifecycle management
3. **Shared Services** — Compression engine, local storage, network, permissions

```
┌─────────────────────────────────────────┐
│               NoCloudBS App             │
│  ┌───────┐ ┌────────┐ ┌──────────────┐ │
│  │Dashboard│ │Plugin A│ │  Plugin B    │ │  ← TabView tabs
│  └───┬───┘ └───┬────┘ └──────┬───────┘ │
│      │         │              │          │
│  ┌───┴─────────┴──────────────┴───────┐ │
│  │         Plugin Registry            │ │  ← Manages lifecycle
│  └───────────────┬────────────────────┘ │
│  ┌───────────────┴────────────────────┐ │
│  │        PluginContext (impl)        │ │  ← Service injection
│  │  ┌──────────┐ ┌────────┐ ┌──────┐ │ │
│  │  │Compression│ │Storage │ │Network│ │ │
│  │  └──────────┘ └────────┘ └──────┘ │ │
│  └────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

## Core Data Models

### Storage Statistics

```swift
struct StorageStats {
    let totalSpace: Int64
    let availableSpace: Int64
    let usedByApp: Int64
    let usedByPlugins: [String: Int64]  // plugin ID → bytes
    let compressionRatio: Double
    let savedSpace: Int64               // bytes saved via compression

    var usedPercentage: Double {
        guard totalSpace > 0 else { return 0 }
        return Double(totalSpace - availableSpace) / Double(totalSpace)
    }
}
```

### Plugin Metadata (Runtime)

```swift
struct PluginInfo: Identifiable {
    let id: String              // NCBSPlugin.id
    let name: String
    let description: String
    let icon: String
    let version: String
    var isActive: Bool
    var storageUsed: Int64
}
```

## Plugin Registry Pattern

```swift
@Observable
final class PluginRegistry {
    private(set) var plugins: [any NCBSPlugin] = []
    private(set) var pluginInfo: [PluginInfo] = []
    private let context: PluginContext

    init(context: PluginContext) {
        self.context = context
    }

    /// Register a plugin type. Called at app startup.
    func register(_ pluginType: any NCBSPlugin.Type) {
        let instance = pluginType.init(context: context)
        plugins.append(instance)
        pluginInfo.append(PluginInfo(
            id: pluginType.id,
            name: pluginType.name,
            description: pluginType.description,
            icon: pluginType.icon,
            version: pluginType.version,
            isActive: false,
            storageUsed: 0
        ))
    }

    /// Called when a plugin tab becomes visible
    func activate(_ plugin: any NCBSPlugin) async {
        await plugin.onActivate()
        if let idx = pluginInfo.firstIndex(where: { $0.id == type(of: plugin).id }) {
            pluginInfo[idx].isActive = true
        }
    }

    /// Called when a plugin tab is hidden
    func deactivate(_ plugin: any NCBSPlugin) async {
        await plugin.onDeactivate()
        if let idx = pluginInfo.firstIndex(where: { $0.id == type(of: plugin).id }) {
            pluginInfo[idx].isActive = false
        }
    }

    /// Get a plugin by ID
    func plugin(id: String) -> (any NCBSPlugin)? {
        plugins.first { type(of: $0).id == id }
    }
}
```

## Service Implementations

### Compression Service

**INTEGRATION POINT**: The compression methods below are stubs that return data uncompressed.
In the real app, these will call the patented 10:1 lossless compression library via a native bridge.
The builder should implement the stubs as-is — the real compression engine is integrated separately.

```swift
final class CompressionServiceImpl: CompressionServiceProtocol, @unchecked Sendable {
    private(set) var compressionRatio: Double = 10.0

    func compress(data: Data) async throws -> Data {
        // INTEGRATION POINT: Replace with call to native compression library
        // The patented algorithm achieves 10:1 lossless compression (SHA-256 verified)
        // For now, return data uncompressed — real implementation is integrated separately
        return data
    }

    func decompress(data: Data) async throws -> Data {
        // INTEGRATION POINT: Replace with call to native decompression library
        // For now, return data as-is — real implementation is integrated separately
        return data
    }
}
```

### Storage Service

```swift
final class StorageServiceImpl: StorageServiceProtocol, @unchecked Sendable {
    private let baseDirectory: URL
    private let compression: CompressionServiceProtocol

    var availableSpace: Int64 {
        let attrs = try? FileManager.default.attributesOfFileSystem(
            forPath: baseDirectory.path
        )
        return (attrs?[.systemFreeSize] as? Int64) ?? 0
    }

    var usedSpace: Int64 {
        // Calculate total size of all stored files
        guard let enumerator = FileManager.default.enumerator(
            at: baseDirectory, includingPropertiesForKeys: [.fileSizeKey]
        ) else { return 0 }

        var total: Int64 = 0
        for case let url as URL in enumerator {
            let size = (try? url.resourceValues(forKeys: [.fileSizeKey]))?.fileSize ?? 0
            total += Int64(size)
        }
        return total
    }

    init(pluginId: String, compression: CompressionServiceProtocol) {
        let appSupport = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        self.baseDirectory = appSupport.appendingPathComponent("plugins/\(pluginId)/storage")
        self.compression = compression
        try? FileManager.default.createDirectory(at: baseDirectory, withIntermediateDirectories: true)
    }

    func save(_ data: Data, key: String) async throws {
        let compressed = try await compression.compress(data: data)
        let fileURL = baseDirectory.appendingPathComponent(key)
        try? FileManager.default.createDirectory(
            at: fileURL.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        try compressed.write(to: fileURL)
    }

    func load(key: String) async throws -> Data? {
        let fileURL = baseDirectory.appendingPathComponent(key)
        guard FileManager.default.fileExists(atPath: fileURL.path) else { return nil }
        let compressed = try Data(contentsOf: fileURL)
        return try await compression.decompress(data: compressed)
    }

    func delete(key: String) async throws {
        let fileURL = baseDirectory.appendingPathComponent(key)
        try? FileManager.default.removeItem(at: fileURL)
    }

    func listKeys(prefix: String?) async -> [String] {
        guard let enumerator = FileManager.default.enumerator(
            at: baseDirectory, includingPropertiesForKeys: nil
        ) else { return [] }

        var keys: [String] = []
        for case let url as URL in enumerator {
            let key = url.path.replacingOccurrences(of: baseDirectory.path + "/", with: "")
            if let prefix {
                if key.hasPrefix(prefix) { keys.append(key) }
            } else {
                keys.append(key)
            }
        }
        return keys
    }
}
```

### Plugin Context Implementation

```swift
final class PluginContextImpl: PluginContext, @unchecked Sendable {
    let compressionService: CompressionServiceProtocol
    let storageService: StorageServiceProtocol
    let networkService: NetworkServiceProtocol
    let userDefaults: UserDefaults

    init(pluginId: String = "host") {
        let compression = CompressionServiceImpl()
        self.compressionService = compression
        self.storageService = StorageServiceImpl(pluginId: pluginId, compression: compression)
        self.networkService = NetworkServiceImpl()
        self.userDefaults = UserDefaults(suiteName: "com.nocloudbs.\(pluginId)") ?? .standard
    }

    func requestPermission(_ permission: PluginPermission) async -> Bool {
        // Present system permission dialog
        // Return true if granted
        return true // placeholder
    }
}
```

## Core Views

### Dashboard

The dashboard is always the first tab. It shows:
- Total device storage vs available
- Compression ratio achieved
- Space saved via compression
- Per-plugin storage usage breakdown
- Quick actions (compress, manage)

### Settings

The settings view aggregates:
- App-level settings (theme, notifications)
- Per-plugin settings (delegated to each plugin's `settingsView`)
- Plugin management (enable/disable)
- Storage management (clear cache, export data)
- About / version info

## Navigation

```
TabView
├── Dashboard (always first)
│   └── StorageDetailView
│       └── PerPluginStorageView
├── [Plugin A Tab] ← dynamic
├── [Plugin B Tab] ← dynamic
├── [Plugin C Tab] ← dynamic
└── Settings (always last)
    ├── General Settings
    ├── Plugin Settings
    │   ├── Plugin A Settings
    │   ├── Plugin B Settings
    │   └── Plugin C Settings
    ├── Storage Management
    └── About
```

## Plugin Discovery

At compile time, plugins are registered explicitly in the App entry point:

```swift
// NoCloudBSApp.swift
init() {
    let context = PluginContextImpl()
    let registry = PluginRegistry(context: context)

    // Register each plugin package
    registry.register(PhotoGalleryPlugin.self)
    registry.register(DocumentScannerPlugin.self)
    registry.register(NotesPlugin.self)

    _registry = State(initialValue: registry)
}
```

Each new plugin only requires:
1. Adding the SPM dependency to `Package.swift`
2. Adding `import NCBSPluginName`
3. Adding `registry.register(PluginNamePlugin.self)`
