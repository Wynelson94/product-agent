# Swift + SwiftUI Host App Scaffold

## Project Structure

```
NoCloudBS/
├── Package.swift                          # Root package (workspace)
├── NoCloudBSApp/
│   ├── NoCloudBSApp.swift                 # @main App entry point
│   ├── ContentView.swift                  # Root TabView with plugin tabs
│   ├── Info.plist
│   └── Assets.xcassets/
├── Sources/
│   ├── Core/
│   │   ├── PluginRegistry.swift           # Discovers and manages plugins
│   │   ├── PluginHost.swift               # Wraps plugin views with lifecycle
│   │   └── AppState.swift                 # Global @Observable state
│   ├── Services/
│   │   ├── CompressionService.swift       # Concrete compression implementation
│   │   ├── StorageService.swift           # Concrete local storage implementation
│   │   ├── NetworkService.swift           # Concrete network implementation
│   │   └── PluginContextImpl.swift        # Concrete PluginContext for injection
│   ├── Views/
│   │   ├── Dashboard/
│   │   │   ├── DashboardView.swift        # Storage stats, compression ratio
│   │   │   └── StorageGaugeView.swift     # Visual storage indicator
│   │   ├── Settings/
│   │   │   ├── SettingsView.swift         # App + plugin settings
│   │   │   └── PluginSettingsView.swift   # Per-plugin settings wrapper
│   │   └── Shared/
│   │       ├── LoadingView.swift
│   │       └── ErrorView.swift
│   └── Models/
│       └── StorageStats.swift             # Device storage model
├── NCBSPluginSDK/                         # Plugin SDK package (local)
│   ├── Package.swift
│   └── Sources/NCBSPluginSDK/
│       ├── NCBSPlugin.swift               # Plugin protocol
│       ├── PluginContext.swift             # Context protocol
│       ├── PluginPermission.swift          # Permission enum
│       └── Services/
│           ├── CompressionService.swift    # Protocol only
│           ├── StorageService.swift        # Protocol only
│           └── NetworkService.swift        # Protocol only
└── Tests/
    ├── CoreTests/
    │   ├── PluginRegistryTests.swift
    │   └── AppStateTests.swift
    └── ServiceTests/
        ├── CompressionServiceTests.swift
        └── StorageServiceTests.swift
```

## Setup Commands

```bash
# 1. Create root directory
mkdir -p NoCloudBS && cd NoCloudBS

# 2. Initialize the plugin SDK package first
mkdir -p NCBSPluginSDK
cd NCBSPluginSDK
swift package init --type library --name NCBSPluginSDK
cd ..

# 3. Initialize the main app package
swift package init --type executable --name NoCloudBSApp

# 4. Create directory structure
mkdir -p Sources/{Core,Services,Views/{Dashboard,Settings,Shared},Models}
mkdir -p Tests/{CoreTests,ServiceTests}

# 5. Verify compilation
swift build
```

## Root Package.swift

```swift
// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "NoCloudBS",
    platforms: [.iOS(.v17)],
    products: [
        .library(name: "NoCloudBSCore", targets: ["NoCloudBSCore"]),
    ],
    dependencies: [
        .package(path: "./NCBSPluginSDK"),
        // Plugin packages are added here as they are built:
        // .package(path: "../plugins/NCBSPhotoGallery"),
    ],
    targets: [
        .target(
            name: "NoCloudBSCore",
            dependencies: ["NCBSPluginSDK"],
            path: "Sources"
        ),
        .testTarget(
            name: "NoCloudBSTests",
            dependencies: ["NoCloudBSCore"],
            path: "Tests"
        ),
    ]
)
```

## Key Implementation: Plugin Registry

```swift
// Sources/Core/PluginRegistry.swift

import SwiftUI
import NCBSPluginSDK

@Observable
final class PluginRegistry {
    private(set) var plugins: [any NCBSPlugin] = []
    private let context: PluginContext

    init(context: PluginContext) {
        self.context = context
    }

    func register(_ pluginType: any NCBSPlugin.Type) {
        let instance = pluginType.init(context: context)
        plugins.append(instance)
    }

    func activate(_ plugin: any NCBSPlugin) async {
        await plugin.onActivate()
    }

    func deactivate(_ plugin: any NCBSPlugin) async {
        await plugin.onDeactivate()
    }
}
```

## Key Implementation: App Entry Point

```swift
// NoCloudBSApp/NoCloudBSApp.swift

import SwiftUI

@main
struct NoCloudBSApp: App {
    @State private var registry: PluginRegistry
    @State private var appState = AppState()

    init() {
        let context = PluginContextImpl()
        _registry = State(initialValue: PluginRegistry(context: context))
        // Register built-in plugins here:
        // registry.register(PhotoGalleryPlugin.self)
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(registry)
                .environment(appState)
        }
    }
}
```

## Key Implementation: Dynamic Tab View

```swift
// NoCloudBSApp/ContentView.swift

import SwiftUI

struct ContentView: View {
    @Environment(PluginRegistry.self) var registry
    @State private var selectedTab = "dashboard"

    var body: some View {
        TabView(selection: $selectedTab) {
            // Core dashboard tab (always present)
            DashboardView()
                .tabItem {
                    Label("Storage", systemImage: "internaldrive")
                }
                .tag("dashboard")

            // Dynamic plugin tabs
            ForEach(registry.plugins, id: \.Self.id) { plugin in
                AnyView(plugin.mainView)
                    .tabItem {
                        Label(type(of: plugin).name, systemImage: type(of: plugin).icon)
                    }
                    .tag(type(of: plugin).id)
            }

            // Settings tab (always last)
            SettingsView()
                .tabItem {
                    Label("Settings", systemImage: "gear")
                }
                .tag("settings")
        }
    }
}
```

## Build Verification

```bash
# Verify the project compiles
swift build

# Run tests
swift test

# If using Xcode project:
xcodebuild -scheme NoCloudBS -destination 'platform=iOS Simulator,name=iPhone 16' build
```
