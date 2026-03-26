# Swift + SwiftUI App Scaffold

## Project Structure

```
App/
├── Package.swift                          # Root package
├── Sources/
│   ├── App.swift                          # @main App entry point
│   ├── ContentView.swift                  # Root navigation view
│   ├── Info.plist
│   ├── Assets.xcassets/
│   ├── Core/
│   │   └── AppState.swift                 # Global @Observable state
│   ├── Services/
│   │   ├── StorageService.swift           # Local storage implementation
│   │   └── NetworkService.swift           # Network implementation
│   ├── Views/
│   │   ├── Dashboard/
│   │   │   └── DashboardView.swift        # Main dashboard
│   │   ├── Settings/
│   │   │   └── SettingsView.swift         # App settings
│   │   └── Shared/
│   │       ├── LoadingView.swift
│   │       └── ErrorView.swift
│   └── Models/
│       └── AppModels.swift                # Data models
└── Tests/
    ├── CoreTests/
    │   └── AppStateTests.swift
    └── ServiceTests/
        └── StorageServiceTests.swift
```

## Setup Commands

```bash
# 1. Create root directory
mkdir -p App && cd App

# 2. Initialize the Swift package
swift package init --type executable --name App

# 3. Create directory structure
mkdir -p Sources/{Core,Services,Views/{Dashboard,Settings,Shared},Models}
mkdir -p Tests/{CoreTests,ServiceTests}

# 4. Verify compilation
swift build
```

## Root Package.swift

```swift
// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "App",
    platforms: [.iOS(.v17)],
    products: [
        .library(name: "AppCore", targets: ["AppCore"]),
    ],
    targets: [
        .target(
            name: "AppCore",
            path: "Sources"
        ),
        .testTarget(
            name: "AppTests",
            dependencies: ["AppCore"],
            path: "Tests"
        ),
    ]
)
```

## Key Implementation: App Entry Point

```swift
// Sources/App.swift

import SwiftUI

@main
struct MainApp: App {
    @State private var appState = AppState()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(appState)
        }
    }
}
```

## Key Implementation: Content View

```swift
// Sources/ContentView.swift

import SwiftUI

struct ContentView: View {
    @State private var selectedTab = "dashboard"

    var body: some View {
        TabView(selection: $selectedTab) {
            DashboardView()
                .tabItem {
                    Label("Home", systemImage: "house")
                }
                .tag("dashboard")

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
xcodebuild -scheme App -destination 'platform=iOS Simulator,name=iPhone 16' build
```
