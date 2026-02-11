# Plugin Host App Domain Patterns

Patterns for building the NoCloud BS host application — the shell that discovers,
loads, and manages Swift Package plugins.

## NoCloud BS Host App Context

### Color System (DesignSystem Package)
The host app uses a DesignSystem Swift Package with DSColor, DSTypography, and DSSpacing tokens.
All UI must use these exact colors:

| Token | Hex | Use |
|-------|-----|-----|
| black | #000000 | Primary background (OLED true black) |
| blackGold | #1A1400 | Cards, sheets, modals, nav bars (warm black with gold undertone) |
| gold | #CFB53B | Primary accent — buttons, selections, progress indicators |
| goldLight | #E8D48B | Gold text on dark backgrounds |
| goldDark | #8B7A2B | Pressed/active states for gold elements |
| teal | #008080 | Secondary accent — links, toggles, secondary buttons |
| tealLight | #40E0D0 | Teal text on dark backgrounds |
| tealDark | #005F5F | Pressed/active states for teal elements |
| error | #FF453A | Destructive actions, validation errors |
| success | #30D158 | Confirmations, positive states |
| warning | #FFD60A | Caution states |

### Performance Targets
- **120fps scroll**: All lists and scroll views must maintain 120fps on ProMotion displays
- **<400ms cold launch**: App must be interactive within 400ms of launch
- **<16ms compression transparency**: Compression/decompression overhead must be invisible to the user
- **Zero main-thread blocking**: All I/O is async. No synchronous file or storage access on main thread.

### Hard Requirements
- **100% Offline-First**: Every feature must work without internet. No feature is gated behind connectivity.
- **Dual-Platform**: macOS uses NavigationSplitView; iOS uses NavigationStack + TabBar. All views must adapt.
- **Accessibility**: WCAG AAA contrast (7:1), VoiceOver labels on all interactive elements, Dynamic Type, Reduce Motion support.
- **Patented Compression**: SHA-256 verified lossless compression. The compression engine is integrated separately — stubs are used in generated code.

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

---

## Real App Context (from Taylor's Master Agent Prompt)

The following sections capture key details about the real NoCloud BS app that go beyond
the basic plugin architecture. When building host features, the agent should be aware of
the full scope of the product.

### Compression Algorithm Strategy

The compression engine uses adaptive algorithm selection based on file access frequency:

| Algorithm | Speed | Ratio | When Used |
|-----------|-------|-------|-----------|
| LZ4 | Ultra-fast decompress | Lower | Hot/frequently-accessed files |
| Apple LZFSE | Hardware-accelerated | Good | General use on Apple Silicon |
| zstd | Balanced | Better | Warm files |
| LZMA | Slower | Best | Cold storage, archival |

Rules:
- Already-compressed formats (JPEG, MP4, ZIP) → store as-is or minimal wrapping
- Files <4KB → skip compression
- Target: ≥500MB/s compress, ≥1GB/s decompress (Apple Silicon)
- Target: ≥30% average size reduction
- Target: 64MB memory ceiling
- **100.000% lossless pass rate — zero exceptions**

### File Viewer Engine

The host app is NOT just a file manager — it includes a comprehensive viewer for ALL file types:
- **Images**: JPEG/PNG/GIF/WebP/HEIC/TIFF/BMP/SVG/RAW/PSD — pinch-zoom, tile rendering >4096px, EXIF overlay
- **PDF**: Multi-page with thumbnail sidebar, search, text selection
- **Video**: Custom blackGold/gold controls, PiP, AirPlay, speed control
- **Audio**: Waveform visualization (gold on black), playback controls, ID3 metadata
- **Documents**: RTF, plain text, Markdown rendered, HTML sandboxed
- **Spreadsheets**: CSV/TSV in scrollable grid with gold headers
- **Code**: Syntax highlighting for 20+ languages with blackGold/gold theme
- **Archives**: Browse without extracting, preview individual files inside
- **3D**: USDZ via SceneKit/RealityKit

All viewing works on compressed data seamlessly through the transparent access layer.
Thumbnail pipeline: background generation → disk cache → progressive loading (icon → low-res → full-res).

### Transfer Integrity

Files shared via iMessage, AirDrop, or email arrive **STILL compressed AND immediately usable**
by recipients **without the NoCloud BS app installed**. Uses UIActivityItemProvider/NSItemProvider
with proper UTType registration.

### C++/Swift Interop Layer

Performance-critical modules are implemented in C++ with Swift 5.9+ interop:
- Image processing pipeline
- Magic-byte file type detection (100+ types, 10K files/sec)
- Compression algorithms (LZ4, zstd, LZMA wrappers)
- Audio DSP
- Text indexing

C++ modules use include/src/modulemap structure. Memory safety enforced via RAII wrappers,
unique_ptr/shared_ptr, with documented ownership at every Swift/C++ boundary.

### Golden Rules

These rules apply to ALL code changes in the NoCloud BS codebase:

1. **READ existing codebase FIRST** before making any changes
2. **NEVER rename** existing variables, functions, classes, modules, or files
3. **NEVER change** the app's existing vocabulary or terminology
4. **NEVER delete** working code — enhance, optimize, extend only
5. **Follow existing code style** — match what's already there
6. **All changes must be additive and backwards-compatible**
7. **The compression engine is the core** — never break it

### Security Requirements

- Keychain for all sensitive data (kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly)
- Biometric auth via LAContext (Face ID / Touch ID)
- Encrypted databases (SQLCipher or NSFileProtectionComplete)
- ATS enforced, zero exceptions
- Public key pinning for optional network calls
- Input validation on all user input (path traversal, injection prevention)
- Secure logging (%{private}@ for sensitive data, strip debug logs in Release)
- Jailbreak detection with graceful degradation
- macOS hardened runtime
- Pin all dependency versions
- Secure deletion: filesystem + caches + DB + search index

### Extended Quality Targets

In addition to the performance targets listed above:

| Metric | Target |
|--------|--------|
| Crash-free rate | ≥ 99.95% |
| SwiftLint warnings | Zero |
| Force unwraps | Zero in entire codebase |
| Force try | Zero in entire codebase |
| Force cast | Zero in entire codebase |
| Test coverage | 90%+ line coverage |
| Memory leaks | Zero (Instruments verified) |
| Data races | Zero (TSan verified) |
| Binary size | < 50MB |
| Energy impact | "Low" in Instruments |
| App Store | First-submission approval target |
