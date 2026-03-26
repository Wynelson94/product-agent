# Swift + SwiftUI Deployment

## Build Verification

```bash
# 1. Verify package resolves
swift package resolve

# 2. Compile
swift build

# 3. Run tests
swift test
```

## Archive for TestFlight

```bash
# 1. Archive
xcodebuild archive \
    -scheme AppName \
    -destination 'generic/platform=iOS' \
    -archivePath ./build/AppName.xcarchive

# 2. Export for App Store / TestFlight
xcodebuild -exportArchive \
    -archivePath ./build/AppName.xcarchive \
    -exportOptionsPlist ExportOptions.plist \
    -exportPath ./build/export

# 3. Upload to App Store Connect
xcrun altool --upload-app \
    -f ./build/export/AppName.ipa \
    -t ios \
    --apiKey $APP_STORE_API_KEY \
    --apiIssuer $APP_STORE_ISSUER_ID
```

## ExportOptions.plist

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

## Swift Package Distribution (Library)

For Swift packages distributed via SPM (not App Store apps):

```bash
# Tag for SPM version resolution
git init
git add .
git commit -m "Initial release"
git tag 1.0.0
```

Consumers add the package to their `Package.swift`:

```swift
dependencies: [
    .package(url: "https://github.com/user/PackageName.git", from: "1.0.0"),
]
```

## Pre-Deployment Checks

- [ ] `swift build` succeeds with no errors
- [ ] `swift test` passes all tests
- [ ] No compiler warnings
- [ ] `Package.swift` has correct platform requirement (`.iOS(.v17)`)
- [ ] Info.plist has required privacy descriptions (if applicable)
- [ ] App icons and launch screen configured (if App Store deployment)
