# Swift + SwiftUI Build Process

## Plugin Mode (--mode plugin)

1. **FIRST: Create NCBSPluginSDK as a local package** using the EXACT definitions in the Plugin Protocol Reference. Do NOT simplify or create your own version.
2. Verify it compiles: `cd NCBSPluginSDK && swift build && cd ..`
3. Scaffold plugin: `swift package init --type library --name [PluginName]Plugin`
4. Update Package.swift: add `.package(path: "./NCBSPluginSDK")` dependency and `platforms: [.iOS(.v17), .macOS(.v14)]`
5. Run `swift build` to verify dependency resolves
6. Implement `[PluginName]Plugin.swift` conforming to `NCBSPlugin` protocol with `init(context: PluginContext)` (NOT `init()`)
7. Implement `PluginManifest.swift` — see the Plugin PluginManifest Pattern section below
8. Create `Sources/[PluginName]Plugin/Color+NoCloudBS.swift` with the host color constants:
   black (#000000), blackGold (#1A1400), gold (#CFB53B), goldLight (#E8D48B),
   teal (#008080), tealLight (#40E0D0). Use these in ALL views — no custom colors.
9. Implement views, models, and view models per DESIGN.md
   **CRITICAL**: All ViewModels MUST use the `@Observable` macro, NOT `ObservableObject`/`@Published`.
   Views use `@State` for owned ViewModels and plain property references — no `@ObservedObject` or `@StateObject`.
10. Create `MockPluginContext.swift` for tests (must conform to `PluginContext` protocol)
11. Run `swift build` to verify final compilation

## Host Mode (--mode host)

1. **FIRST: Create NCBSPluginSDK as a local package** — this MUST exist before the host app can build
2. `mkdir -p NCBSPluginSDK && cd NCBSPluginSDK && swift package init --type library`
3. Implement ALL protocol definitions in SDK: NCBSPlugin, PluginContext, CompressionServiceProtocol, StorageServiceProtocol, NetworkServiceProtocol, PluginPermission
4. Run `swift build` in NCBSPluginSDK to verify SDK compiles
5. Create main app package with local path dependency: `.package(path: "../NCBSPluginSDK")`
6. Create app structure: `Sources/{Core,Services,Views,Models}`
7. Implement `PluginRegistry.swift`, `PluginContextImpl.swift`
8. Implement service concretions: CompressionService, StorageService, NetworkService
9. Create SwiftUI App entry point with TabView and plugin registration
10. Implement DashboardView (storage stats) and SettingsView
11. Run `swift build` to verify compilation

## NCBSPluginSDK Definition (MANDATORY — create this FIRST, before the plugin)

**Do NOT simplify, rename, or redesign these protocols.** Copy them exactly.
**Do NOT define `PluginManifest` inside the SDK** — that name is reserved for the plugin-side discovery file.

See the Plugin Protocol Reference for the exact protocol definitions that must be implemented.

## Plugin PluginManifest Pattern (REQUIRED — in the PLUGIN, not in the SDK)

The plugin (not the SDK) must include `PluginManifest.swift` for host discovery:
```swift
import NCBSPluginSDK
public struct PluginManifest {
    public static let pluginType: any NCBSPlugin.Type = MyPlugin.self
}
```
Replace `MyPlugin` with the actual plugin struct name.
Do NOT use `typealias PluginEntry`. Do NOT put `PluginManifest` in the SDK package.
