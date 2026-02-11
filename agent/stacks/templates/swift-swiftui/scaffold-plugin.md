# Swift Package Plugin Scaffold

## Project Structure

```
NCBS[PluginName]/
├── Package.swift
├── Sources/
│   └── NCBS[PluginName]/
│       ├── [PluginName]Plugin.swift        # NCBSPlugin conformance
│       ├── PluginManifest.swift            # Host discovery entry point
│       ├── Color+NoCloudBS.swift           # Host color palette constants
│       ├── Views/
│       │   ├── MainView.swift              # Plugin's primary view
│       │   ├── SettingsView.swift          # Plugin settings (optional)
│       │   └── Components/                 # Reusable sub-views
│       │       └── ...
│       ├── Models/
│       │   └── ...                         # Plugin-specific data models
│       ├── ViewModels/
│       │   └── MainViewModel.swift         # MVVM view model
│       └── Services/
│           └── ...                         # Plugin-specific services
└── Tests/
    └── NCBS[PluginName]Tests/
        ├── [PluginName]PluginTests.swift    # Plugin lifecycle tests
        ├── ViewModelTests.swift             # ViewModel unit tests
        └── Mocks/
            └── MockPluginContext.swift       # Mock context for testing
```

## Setup Commands

```bash
# 1. Create package
mkdir -p NCBS[PluginName]
cd NCBS[PluginName]
swift package init --type library --name NCBS[PluginName]

# 2. Create directory structure
mkdir -p Sources/NCBS[PluginName]/{Views/Components,Models,ViewModels,Services}
mkdir -p Tests/NCBS[PluginName]Tests/Mocks

# 3. Verify compilation
swift build
```

## Package.swift

```swift
// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "NCBS[PluginName]",
    platforms: [.iOS(.v17)],
    products: [
        .library(name: "NCBS[PluginName]", targets: ["NCBS[PluginName]"]),
    ],
    dependencies: [
        // Try remote first; if it fails, use local path fallback (see below)
        .package(url: "https://github.com/nocloudbs/NCBSPluginSDK.git", from: "1.0.0"),
    ],
    targets: [
        .target(
            name: "NCBS[PluginName]",
            dependencies: ["NCBSPluginSDK"]
        ),
        .testTarget(
            name: "NCBS[PluginName]Tests",
            dependencies: ["NCBS[PluginName]"]
        ),
    ]
)
```

### Local Path Fallback
If `swift build` fails because the remote NCBSPluginSDK cannot be resolved, replace the dependency line:
```swift
// Replace this:
.package(url: "https://github.com/nocloudbs/NCBSPluginSDK.git", from: "1.0.0"),
// With this:
.package(path: "./NCBSPluginSDK"),
```
Then create the local SDK package with all protocol definitions from the Plugin Protocol Reference.

## Plugin Implementation Template

```swift
// Sources/NCBS[PluginName]/[PluginName]Plugin.swift

import SwiftUI
import NCBSPluginSDK

public struct [PluginName]Plugin: NCBSPlugin {
    public static let id = "com.nocloudbs.[plugin-slug]"
    public static let name = "[Plugin Display Name]"
    public static let description = "[One-sentence description]"
    public static let icon = "[sf-symbol-name]"     // e.g. "photo.on.rectangle"
    public static let version = "1.0.0"

    private let context: PluginContext
    @State private var viewModel: MainViewModel

    public init(context: PluginContext) {
        self.context = context
        self._viewModel = State(initialValue: MainViewModel(context: context))
    }

    @MainActor @ViewBuilder
    public var mainView: any View {
        MainView(viewModel: viewModel)
    }

    @MainActor @ViewBuilder
    public var settingsView: (any View)? {
        PluginSettingsView(context: context)
    }

    public func onActivate() async {
        await viewModel.load()
    }

    public func onDeactivate() async {
        await viewModel.save()
    }
}
```

## Plugin Manifest

```swift
// Sources/NCBS[PluginName]/PluginManifest.swift

import NCBSPluginSDK

public struct PluginManifest {
    public static let pluginType: any NCBSPlugin.Type = [PluginName]Plugin.self
}
```

## ViewModel Template (MVVM)

```swift
// Sources/NCBS[PluginName]/ViewModels/MainViewModel.swift

import Foundation
import NCBSPluginSDK

@Observable
final class MainViewModel {
    private let context: PluginContext

    var items: [Item] = []
    var isLoading = false
    var error: String?

    init(context: PluginContext) {
        self.context = context
    }

    func load() async {
        isLoading = true
        defer { isLoading = false }

        do {
            if let data = try await context.storageService.load(key: "items") {
                items = try JSONDecoder().decode([Item].self, from: data)
            }
        } catch {
            self.error = error.localizedDescription
        }
    }

    func save() async {
        do {
            let data = try JSONEncoder().encode(items)
            try await context.storageService.save(data, key: "items")
        } catch {
            self.error = error.localizedDescription
        }
    }

    func addItem(_ item: Item) {
        items.append(item)
    }

    func deleteItem(at offsets: IndexSet) {
        items.remove(atOffsets: offsets)
    }
}
```

## Mock PluginContext for Tests

```swift
// Tests/NCBS[PluginName]Tests/Mocks/MockPluginContext.swift

import Foundation
import NCBSPluginSDK

final class MockPluginContext: PluginContext, @unchecked Sendable {
    let compressionService: CompressionServiceProtocol
    let storageService: StorageServiceProtocol
    let networkService: NetworkServiceProtocol
    let userDefaults: UserDefaults

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
        return true
    }
}

final class MockCompressionService: CompressionServiceProtocol, @unchecked Sendable {
    var compressionRatio: Double = 10.0
    func compress(data: Data) async throws -> Data { data }
    func decompress(data: Data) async throws -> Data { data }
}

final class MockStorageService: StorageServiceProtocol, @unchecked Sendable {
    private var store: [String: Data] = [:]
    var availableSpace: Int64 = 1_000_000_000
    var usedSpace: Int64 = 0

    func save(_ data: Data, key: String) async throws { store[key] = data }
    func load(key: String) async throws -> Data? { store[key] }
    func delete(key: String) async throws { store.removeValue(forKey: key) }
    func listKeys(prefix: String?) async -> [String] {
        guard let prefix else { return Array(store.keys) }
        return store.keys.filter { $0.hasPrefix(prefix) }
    }
}

final class MockNetworkService: NetworkServiceProtocol, @unchecked Sendable {
    func request(_ endpoint: String, method: String, body: Data?) async throws -> Data {
        Data()
    }
}
```

## Build Verification

```bash
# Compile
swift build

# Run tests
swift test

# Verify package resolution works
swift package resolve
```
