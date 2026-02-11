# Plugin Module Domain Patterns

Patterns for building individual Swift Package plugins that integrate with the
NoCloud BS host app via the NCBSPlugin protocol.

## Host App Context — NoCloud BS

Plugins snap into **NoCloud BS**, a dual-platform (macOS + iOS) app built around a
**patented lossless compression engine**. The app is NOT a simple file manager — it
reads the user's entire environment, compresses everything losslessly (bit-for-bit
identical roundtrip), and keeps data fully usable while compressed. It also includes
a comprehensive file viewer engine for all file types (images, PDFs, video, audio,
documents, spreadsheets, code, archives, 3D models) that works seamlessly on
compressed data. Files shared via iMessage/AirDrop/email arrive still compressed AND
usable by recipients without the app installed.

**The compression engine is the HEART of the app. Plugins extend it — they never replace it.**

Key requirements for all plugins:

### Color System
Plugins MUST use the host's color palette, not custom colors:
| Token | Hex | Use |
|-------|-----|-----|
| black | #000000 | Primary background (OLED true black) |
| blackGold | #1A1400 | Cards, sheets, modals, nav bars (warm black with gold undertone) |
| gold | #CFB53B | Primary accent — buttons, selections, progress |
| goldLight | #E8D48B | Gold text on dark backgrounds |
| teal | #008080 | Secondary accent — links, toggles, secondary buttons |
| tealLight | #40E0D0 | Teal text on dark backgrounds |
| error | #FF453A | Destructive actions, validation errors |
| success | #30D158 | Confirmations, positive states |
| warning | #FFD60A | Caution states |

Until plugins can import the host's DesignSystem package, define these as
local Color extensions in the plugin (see `Color+NoCloudBS.swift`).

### Hard Requirements
- **100% Offline-First**: Every feature must work without internet. No spinners waiting on network, no error states for "no connection", no degraded experience offline.
- **Dual-Platform**: Views must adapt to macOS (NavigationSplitView) and iOS (NavigationStack + TabBar).
- **Accessibility**: VoiceOver labels on all interactive elements, Dynamic Type support, WCAG AAA contrast (7:1 ratio).
- **Performance**: Never block the main thread. Async load/save. Smooth 120fps scroll.

## Plugin Anatomy

Every plugin is a self-contained Swift Package with:

```
NCBSMyPlugin/
├── Package.swift           # SPM manifest
├── Sources/NCBSMyPlugin/
│   ├── MyPlugin.swift          # NCBSPlugin conformance (entry point)
│   ├── PluginManifest.swift    # Host discovery hook
│   ├── Views/                  # SwiftUI views
│   ├── Models/                 # Data models (Codable structs)
│   ├── ViewModels/             # @Observable view models
│   └── Services/               # Plugin-specific logic
└── Tests/NCBSMyPluginTests/
    ├── MyPluginTests.swift     # Lifecycle tests
    ├── ViewModelTests.swift    # ViewModel unit tests
    └── Mocks/
        └── MockPluginContext.swift
```

## Common Plugin Types

### File Manager Plugin
- Browse compressed local files
- Upload/import from Photos or Files app
- Folder organization
- File preview with decompression
- Share sheet integration
- **Key services**: storageService, compressionService
- **Permissions**: fileAccess, photoLibrary
- **Icon**: "folder.fill"

### Photo Gallery Plugin
- Albums with compressed photo storage
- Grid/list view of photos
- Full-screen viewer with zoom
- Import from camera or photo library
- Compression stats per album
- **Key services**: storageService, compressionService
- **Permissions**: camera, photoLibrary
- **Icon**: "photo.on.rectangle"

### Document Scanner Plugin
- Camera-based document scanning
- OCR text extraction (Vision framework)
- PDF generation from scans
- Compressed document storage
- Full-text search across scans
- **Key services**: storageService, compressionService
- **Permissions**: camera
- **Icon**: "doc.text.viewfinder"

### Notes Plugin
- Rich text notes with markdown
- Note organization (folders, tags)
- Compressed note storage
- Search across all notes
- **Key services**: storageService
- **Permissions**: none
- **Icon**: "note.text"

### Backup Manager Plugin
- Select data to back up
- Compressed local backups with timestamps
- Restore from backup
- Backup scheduling
- Storage usage per backup
- **Key services**: storageService, compressionService
- **Permissions**: fileAccess
- **Icon**: "arrow.clockwise.circle"

### Analytics Dashboard Plugin
- Compression statistics over time
- Storage usage trends
- Per-file compression ratios
- Charts and visualizations
- **Key services**: storageService
- **Permissions**: none
- **Icon**: "chart.bar.fill"

## Data Model Patterns

### Always Use Codable Structs

```swift
struct Photo: Identifiable, Codable, Hashable {
    let id: UUID
    var name: String
    var albumId: UUID
    var createdAt: Date
    var sizeOriginal: Int64
    var sizeCompressed: Int64
    var metadata: PhotoMetadata?

    var compressionRatio: Double {
        guard sizeCompressed > 0 else { return 0 }
        return Double(sizeOriginal) / Double(sizeCompressed)
    }
}

struct PhotoMetadata: Codable, Hashable {
    var width: Int
    var height: Int
    var format: String
    var location: String?
}
```

### Storage Key Convention

Plugins should namespace their storage keys:

```swift
// Good: namespaced keys
"albums"                     // list of albums
"albums/\(albumId)/photos"   // photos in an album
"photos/\(photoId)/data"     // photo binary data
"settings"                   // plugin settings

// The StorageService automatically scopes to the plugin's directory
```

## ViewModel Patterns

### Standard Load/Save Cycle

```swift
@Observable
final class AlbumListViewModel {
    var albums: [Album] = []
    var isLoading = false
    var error: String?
    var selectedAlbum: Album?

    private let context: PluginContext
    private let storageKey = "albums"

    init(context: PluginContext) {
        self.context = context
    }

    func load() async {
        isLoading = true
        defer { isLoading = false }
        do {
            if let data = try await context.storageService.load(key: storageKey) {
                albums = try JSONDecoder().decode([Album].self, from: data)
            }
        } catch {
            self.error = error.localizedDescription
        }
    }

    func save() async {
        do {
            let data = try JSONEncoder().encode(albums)
            try await context.storageService.save(data, key: storageKey)
        } catch {
            self.error = error.localizedDescription
        }
    }

    func createAlbum(name: String) async {
        let album = Album(name: name)
        albums.append(album)
        await save()
    }

    func deleteAlbum(_ album: Album) async {
        albums.removeAll { $0.id == album.id }
        // Also delete album contents
        let photoKeys = await context.storageService.listKeys(prefix: "albums/\(album.id)/")
        for key in photoKeys {
            try? await context.storageService.delete(key: key)
        }
        await save()
    }
}
```

### Handling Permissions

```swift
func importFromPhotos() async {
    guard await context.requestPermission(.photoLibrary) else {
        error = "Photo library access is required to import photos"
        return
    }
    // Proceed with PHPicker
}
```

### Compression Workflow

```swift
func savePhoto(imageData: Data, name: String, album: Album) async throws {
    let sizeOriginal = Int64(imageData.count)

    // Compress using the host's engine
    let compressed = try await context.compressionService.compress(data: imageData)
    let sizeCompressed = Int64(compressed.count)

    // Store compressed data
    let photoId = UUID()
    try await context.storageService.save(compressed, key: "albums/\(album.id)/photos/\(photoId)/data")

    // Update metadata
    let photo = Photo(
        id: photoId,
        name: name,
        albumId: album.id,
        createdAt: Date(),
        sizeOriginal: sizeOriginal,
        sizeCompressed: sizeCompressed
    )
    // ... save photo metadata to album's photo list
}
```

## View Patterns

### List with Empty State

```swift
struct AlbumListView: View {
    @State private var viewModel: AlbumListViewModel

    var body: some View {
        Group {
            if viewModel.isLoading {
                ProgressView()
            } else if viewModel.albums.isEmpty {
                ContentUnavailableView(
                    "No Albums",
                    systemImage: "photo.on.rectangle.angled",
                    description: Text("Create your first album to start organizing photos")
                )
            } else {
                List(viewModel.albums) { album in
                    NavigationLink(value: album) {
                        AlbumRow(album: album)
                    }
                }
            }
        }
        .task { await viewModel.load() }
    }
}
```

### Compression Stats Badge

Show compression stats wherever file sizes are displayed:

```swift
struct FileSizeView: View {
    let original: Int64
    let compressed: Int64

    var ratio: Double {
        guard compressed > 0 else { return 0 }
        return Double(original) / Double(compressed)
    }

    var body: some View {
        HStack(spacing: 4) {
            Text(ByteCountFormatter.string(fromByteCount: compressed, countStyle: .file))
                .foregroundStyle(.secondary)
            if ratio > 1 {
                Text("\(ratio, specifier: "%.1f")x")
                    .font(.caption2)
                    .padding(.horizontal, 4)
                    .padding(.vertical, 2)
                    .background(.green.opacity(0.15))
                    .foregroundStyle(.green)
                    .clipShape(Capsule())
            }
        }
    }
}
```

## Testing Patterns

### Mock PluginContext

Always provide a mock context that the tests can inspect.
Use dependency injection so tests can substitute custom mock services:

```swift
final class MockPluginContext: PluginContext, @unchecked Sendable {
    let compressionService: CompressionServiceProtocol
    let storageService: StorageServiceProtocol
    let networkService: NetworkServiceProtocol
    let userDefaults: UserDefaults
    var permissionRequests: [PluginPermission] = []

    init(
        compression: CompressionServiceProtocol = MockCompressionService(),
        storage: StorageServiceProtocol = MockStorageService(),
        network: NetworkServiceProtocol = MockNetworkService(),
        defaults: UserDefaults = UserDefaults(suiteName: "test.\(UUID().uuidString)")!
    ) {
        self.compressionService = compression
        self.storageService = storage
        self.networkService = network
        self.userDefaults = defaults
    }

    func requestPermission(_ permission: PluginPermission) async -> Bool {
        permissionRequests.append(permission)
        return true
    }
}
```

### Test the Full Round-Trip

```swift
func testSaveAndLoadAlbum() async throws {
    let vm = AlbumListViewModel(context: MockPluginContext())
    await vm.createAlbum(name: "Vacation")
    XCTAssertEqual(vm.albums.count, 1)

    // Simulate relaunch
    let vm2 = AlbumListViewModel(context: vm.context)
    await vm2.load()
    XCTAssertEqual(vm2.albums.count, 1)
    XCTAssertEqual(vm2.albums.first?.name, "Vacation")
}
```

---

## Real App Context (from Taylor's Master Agent Prompt)

### Golden Rules for Plugins

These rules apply to all code in the NoCloud BS ecosystem — including plugins:

1. **NEVER rename** anything from the host SDK (NCBSPlugin, PluginContext, service protocols)
2. **NEVER delete** working code — enhance, optimize, extend only
3. **All changes must be additive and backwards-compatible**
4. **Follow existing code style** — match what's already in the plugin
5. **The compression engine is the core** — plugins use it via PluginContext, never implement their own

### Quality Bar

Plugin code must match the host app's quality standards:

| Metric | Target |
|--------|--------|
| Crash-free rate | ≥ 99.95% |
| Force unwraps | Zero |
| Force try | Zero |
| Force cast | Zero |
| SwiftLint warnings | Zero |
| Test coverage | 90%+ line coverage |
| Main Thread Checker | Zero violations |
| Memory leaks | Zero |

### Offline-First Enforcement

This is the defining difference between NoCloud BS plugins and generic SwiftUI code:

- **No feature may be gated behind network connectivity** — not even partially
- **No spinners for "connecting"** — there is nothing to connect to
- **No error states for "no connection"** — offline IS the normal state
- **Cloud sync is additive only** — it enhances but is never required
- **Every feature must work on airplane mode** — test this explicitly
- Networking (if any) uses an offline queue: persisted to SQLite, processes on connectivity restoration, survives app termination

### What the Host Already Provides

Plugins should leverage the host app's capabilities rather than duplicating them:

- **Compression**: Use `context.compressionService` — the host has LZ4/zstd/LZMA/LZFSE with adaptive selection
- **File viewing**: The host has a comprehensive viewer for all file types — don't rebuild viewers
- **File type detection**: The host uses UTType + C++ magic-byte detection (100+ types, 10K files/sec)
- **Storage**: Use `context.storageService` — automatically scoped, compressed, managed
- **Thumbnail pipeline**: The host generates thumbnails (background → disk cache → progressive loading)
- **Transfer/sharing**: The host handles compressed file sharing via UIActivityItemProvider
- **Design system**: The host provides DSColor, DSTypography, DSSpacing tokens — use them
