# Swift + SwiftUI Deployment

## Plugin Mode (--mode plugin)

Plugins are distributed as Swift Packages via git. No App Store deployment needed.

### Build Verification

```bash
# 1. Verify package resolves
swift package resolve

# 2. Compile
swift build

# 3. Run tests
swift test

# 4. Verify the package can be consumed
# Create a temporary consumer to test import
mkdir -p /tmp/test-consumer
cat > /tmp/test-consumer/Package.swift << 'EOF'
// swift-tools-version: 5.9
import PackageDescription
let package = Package(
    name: "TestConsumer",
    platforms: [.iOS(.v17)],
    dependencies: [
        .package(path: "PLUGIN_PATH_HERE"),
    ],
    targets: [
        .executableTarget(name: "TestConsumer", dependencies: ["PLUGIN_NAME_HERE"]),
    ]
)
EOF
```

### Version Tagging

```bash
# Tag for SPM version resolution
git init
git add .
git commit -m "Initial plugin release"
git tag 1.0.0
```

### Integration with Host App

Add the plugin to the host app's `Package.swift`:

```swift
dependencies: [
    .package(path: "../plugins/NCBS[PluginName]"),
    // Or from git:
    // .package(url: "https://github.com/nocloudbs/NCBS[PluginName].git", from: "1.0.0"),
]
```

Then register in the host:

```swift
registry.register([PluginName]Plugin.self)
```

## Host Mode (--mode host)

### Build

```bash
# 1. Resolve all package dependencies
swift package resolve

# 2. Build for iOS Simulator
xcodebuild -scheme NoCloudBS \
    -destination 'platform=iOS Simulator,name=iPhone 16' \
    build

# 3. Run tests on simulator
xcodebuild test \
    -scheme NoCloudBS \
    -destination 'platform=iOS Simulator,name=iPhone 16'
```

### Archive for TestFlight

```bash
# 1. Archive
xcodebuild archive \
    -scheme NoCloudBS \
    -destination 'generic/platform=iOS' \
    -archivePath ./build/NoCloudBS.xcarchive

# 2. Export for App Store / TestFlight
xcodebuild -exportArchive \
    -archivePath ./build/NoCloudBS.xcarchive \
    -exportOptionsPlist ExportOptions.plist \
    -exportPath ./build/export

# 3. Upload to App Store Connect
xcrun altool --upload-app \
    -f ./build/export/NoCloudBS.ipa \
    -t ios \
    --apiKey $APP_STORE_API_KEY \
    --apiIssuer $APP_STORE_ISSUER_ID
```

### ExportOptions.plist

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>method</key>
    <string>app-store</string>
    <key>teamID</key>
    <string>APPLE_TEAM_ID</string>
    <key>uploadBitcode</key>
    <false/>
    <key>uploadSymbols</key>
    <true/>
</dict>
</plist>
```

## Pre-Deployment Checks

### For Both Modes
- [ ] `swift build` succeeds with no errors
- [ ] `swift test` passes all tests
- [ ] No compiler warnings

### Plugin-Specific
- [ ] `Package.swift` has correct platform requirement (`.iOS(.v17)`)
- [ ] NCBSPluginSDK dependency is declared
- [ ] `PluginManifest.swift` exports the plugin type
- [ ] Plugin ID follows reverse-DNS format

### Host-Specific
- [ ] All registered plugins compile
- [ ] Plugin SDK package is included as local dependency
- [ ] Info.plist has required privacy descriptions
- [ ] App icons and launch screen configured
