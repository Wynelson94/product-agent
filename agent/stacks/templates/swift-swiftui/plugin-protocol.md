# NCBSPluginSDK — Plugin Protocol Definition

The NCBSPluginSDK defines the standard interface that ALL generated plugins must conform to.
The host app provides concrete implementations of the service protocols via `PluginContext`.

## Plugin Protocol

```swift
// NCBSPluginSDK/Sources/NCBSPluginSDK/NCBSPlugin.swift

import SwiftUI

/// Every plugin module must export exactly one type conforming to this protocol.
public protocol NCBSPlugin {
    /// Unique reverse-DNS identifier, e.g. "com.nocloudbs.photo-gallery"
    static var id: String { get }
    /// Human-readable name shown in the plugin list
    static var name: String { get }
    /// One-sentence description
    static var description: String { get }
    /// SF Symbol name for tab/sidebar icon
    static var icon: String { get }
    /// Semantic version string, e.g. "1.0.0"
    static var version: String { get }

    /// Initialize with the host-provided context
    init(context: PluginContext)

    /// The plugin's primary view (displayed in its tab)
    @MainActor @ViewBuilder
    var mainView: any View { get }

    /// Optional settings view (displayed in Settings > Plugins > [name])
    @MainActor @ViewBuilder
    var settingsView: (any View)? { get }

    /// Called when the user navigates to the plugin tab
    func onActivate() async

    /// Called when the user navigates away from the plugin tab
    func onDeactivate() async
}

/// Default implementations for optional members
public extension NCBSPlugin {
    var settingsView: (any View)? { nil }
    func onActivate() async {}
    func onDeactivate() async {}
}
```

## Plugin Context

```swift
// NCBSPluginSDK/Sources/NCBSPluginSDK/PluginContext.swift

import Foundation

/// Injected by the host app — provides access to shared services.
public protocol PluginContext: Sendable {
    /// 10:1 lossless compression engine
    var compressionService: CompressionServiceProtocol { get }
    /// Local key-value blob storage (compressed by default)
    var storageService: StorageServiceProtocol { get }
    /// Optional network access (requires .network permission)
    var networkService: NetworkServiceProtocol { get }
    /// Scoped UserDefaults for plugin-specific preferences
    var userDefaults: UserDefaults { get }
    /// Request a runtime permission from the user
    func requestPermission(_ permission: PluginPermission) async -> Bool
}
```

## Service Protocols

```swift
// NCBSPluginSDK/Sources/NCBSPluginSDK/Services/CompressionService.swift

import Foundation

public protocol CompressionServiceProtocol: Sendable {
    /// Compress data using the patented 10:1 lossless algorithm (SHA-256 verified)
    func compress(data: Data) async throws -> Data
    /// Decompress previously compressed data
    func decompress(data: Data) async throws -> Data
    /// Current compression ratio achieved
    var compressionRatio: Double { get }
}
```

```swift
// NCBSPluginSDK/Sources/NCBSPluginSDK/Services/StorageService.swift

import Foundation

public protocol StorageServiceProtocol: Sendable {
    /// Save data to local compressed storage
    func save(_ data: Data, key: String) async throws
    /// Load data by key (returns nil if not found)
    func load(key: String) async throws -> Data?
    /// Delete data by key
    func delete(key: String) async throws
    /// List all keys matching an optional prefix
    func listKeys(prefix: String?) async -> [String]
    /// Available device storage in bytes
    var availableSpace: Int64 { get }
    /// Storage used by this plugin in bytes
    var usedSpace: Int64 { get }
}
```

```swift
// NCBSPluginSDK/Sources/NCBSPluginSDK/Services/NetworkService.swift

import Foundation

public protocol NetworkServiceProtocol: Sendable {
    /// Perform an HTTP request (requires .network permission)
    func request(_ endpoint: String, method: String, body: Data?) async throws -> Data
}
```

## Permissions

```swift
// NCBSPluginSDK/Sources/NCBSPluginSDK/PluginPermission.swift

public enum PluginPermission: String, Sendable, CaseIterable {
    case camera
    case photoLibrary
    case notifications
    case fileAccess
    case network
}
```

## Plugin Manifest

Every plugin Swift Package must include a `PluginManifest.swift`:

```swift
// Sources/[PluginName]/PluginManifest.swift

import NCBSPluginSDK

/// The host app discovers plugins through this exported type.
public struct PluginManifest {
    public static let pluginType: any NCBSPlugin.Type = MyPlugin.self
}
```

## Package.swift Template (Plugin)

Two dependency options — try remote first, fall back to local if the GitHub repo doesn't exist yet:

### Option A: Remote (preferred when SDK is published)
```swift
// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "NCBSPhotoGallery",
    platforms: [.iOS(.v17)],
    products: [
        .library(name: "NCBSPhotoGallery", targets: ["NCBSPhotoGallery"]),
    ],
    dependencies: [
        .package(url: "https://github.com/nocloudbs/NCBSPluginSDK.git", from: "1.0.0"),
    ],
    targets: [
        .target(
            name: "NCBSPhotoGallery",
            dependencies: ["NCBSPluginSDK"]
        ),
        .testTarget(
            name: "NCBSPhotoGalleryTests",
            dependencies: ["NCBSPhotoGallery"]
        ),
    ]
)
```

### Option B: Local path (fallback — use when SDK repo doesn't exist)
```swift
// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "NCBSPhotoGallery",
    platforms: [.iOS(.v17)],
    products: [
        .library(name: "NCBSPhotoGallery", targets: ["NCBSPhotoGallery"]),
    ],
    dependencies: [
        .package(path: "./NCBSPluginSDK"),  // Local SDK package
    ],
    targets: [
        .target(
            name: "NCBSPhotoGallery",
            dependencies: ["NCBSPluginSDK"]
        ),
        .testTarget(
            name: "NCBSPhotoGalleryTests",
            dependencies: ["NCBSPhotoGallery"]
        ),
    ]
)
```
When using Option B, create the NCBSPluginSDK directory with all protocol definitions from this document.
