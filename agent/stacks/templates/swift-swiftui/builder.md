# Swift + SwiftUI Build Process

## Standard Swift/SwiftUI App

1. **Create the Swift package**: `swift package init --type executable --name AppName`
2. Update Package.swift: add `platforms: [.iOS(.v17), .macOS(.v14)]`
3. Run `swift build` to verify initial setup
4. Create directory structure: `Sources/{Core,Services,Views,Models}`
5. Create `Tests/` directory for XCTest targets
6. Implement models as `Codable`, `Identifiable` structs
7. Implement view models using `@Observable` macro
   **CRITICAL**: All ViewModels MUST use the `@Observable` macro, NOT `ObservableObject`/`@Published`.
   Views use `@State` for owned ViewModels and plain property references — no `@ObservedObject` or `@StateObject`.
8. Implement SwiftUI views per DESIGN.md
9. Implement services (storage, network, etc.) as protocols with concrete implementations
10. Create mock services for tests
11. Run `swift build` to verify final compilation
12. Run `swift test` to verify all tests pass

## Build Verification

```bash
# Verify package resolves
swift package resolve

# Compile
swift build

# Run tests
swift test

# If using Xcode project:
xcodebuild -scheme AppName -destination 'platform=iOS Simulator,name=iPhone 16' build
xcodebuild test -scheme AppName -destination 'platform=iOS Simulator,name=iPhone 16'
```
