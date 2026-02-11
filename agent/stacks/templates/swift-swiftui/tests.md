# Swift + SwiftUI Test Patterns (XCTest)

## Test Infrastructure

Swift packages include XCTest support out of the box. Tests live in the `Tests/` directory.

### Running Tests

```bash
# Run all tests
swift test

# Run a specific test class
swift test --filter ItemViewModelTests

# Run with verbose output
swift test --verbose
```

## Test Categories

### 1. ViewModel Unit Tests

```swift
// Tests/NCBS[PluginName]Tests/ViewModelTests.swift

import XCTest
@testable import NCBS[PluginName]

final class MainViewModelTests: XCTestCase {
    var viewModel: MainViewModel!
    var mockContext: MockPluginContext!

    override func setUp() {
        super.setUp()
        mockContext = MockPluginContext()
        viewModel = MainViewModel(context: mockContext)
    }

    override func tearDown() {
        viewModel = nil
        mockContext = nil
        super.tearDown()
    }

    func testInitialState() {
        XCTAssertTrue(viewModel.items.isEmpty)
        XCTAssertFalse(viewModel.isLoading)
        XCTAssertNil(viewModel.error)
    }

    func testLoadItems() async {
        // Arrange: seed mock storage
        let items = [Item(name: "Test", description: "A test item")]
        let data = try! JSONEncoder().encode(items)
        try! await mockContext.storageService.save(data, key: "items")

        // Act
        await viewModel.load()

        // Assert
        XCTAssertEqual(viewModel.items.count, 1)
        XCTAssertEqual(viewModel.items.first?.name, "Test")
        XCTAssertFalse(viewModel.isLoading)
    }

    func testAddItem() {
        let item = Item(name: "New", description: "New item")
        viewModel.addItem(item)

        XCTAssertEqual(viewModel.items.count, 1)
        XCTAssertEqual(viewModel.items.first?.name, "New")
    }

    func testDeleteItem() {
        viewModel.addItem(Item(name: "A", description: ""))
        viewModel.addItem(Item(name: "B", description: ""))

        viewModel.deleteItem(at: IndexSet(integer: 0))

        XCTAssertEqual(viewModel.items.count, 1)
        XCTAssertEqual(viewModel.items.first?.name, "B")
    }

    func testSaveItems() async {
        viewModel.addItem(Item(name: "Saved", description: "Saved item"))
        await viewModel.save()

        let stored = try! await mockContext.storageService.load(key: "items")
        XCTAssertNotNil(stored)

        let decoded = try! JSONDecoder().decode([Item].self, from: stored!)
        XCTAssertEqual(decoded.count, 1)
        XCTAssertEqual(decoded.first?.name, "Saved")
    }
}
```

### 2. Plugin Lifecycle Tests

```swift
// Tests/NCBS[PluginName]Tests/PluginTests.swift

import XCTest
@testable import NCBS[PluginName]

final class PluginTests: XCTestCase {
    var plugin: [PluginName]Plugin!
    var mockContext: MockPluginContext!

    override func setUp() {
        super.setUp()
        mockContext = MockPluginContext()
        plugin = [PluginName]Plugin(context: mockContext)
    }

    func testPluginMetadata() {
        XCTAssertFalse([PluginName]Plugin.id.isEmpty)
        XCTAssertFalse([PluginName]Plugin.name.isEmpty)
        XCTAssertFalse([PluginName]Plugin.icon.isEmpty)
        XCTAssertFalse([PluginName]Plugin.version.isEmpty)
    }

    func testPluginIDFormat() {
        // Should be reverse DNS
        XCTAssertTrue([PluginName]Plugin.id.hasPrefix("com.nocloudbs."))
    }

    func testPluginActivation() async {
        // Should not throw
        await plugin.onActivate()
    }

    func testPluginDeactivation() async {
        await plugin.onActivate()
        await plugin.onDeactivate()
    }

    func testPluginManifest() {
        // PluginManifest should export the correct type
        XCTAssertTrue(PluginManifest.pluginType == [PluginName]Plugin.self)
    }
}
```

### 3. Model Tests

```swift
// Tests/NCBS[PluginName]Tests/ModelTests.swift

import XCTest
@testable import NCBS[PluginName]

final class ItemModelTests: XCTestCase {
    func testItemCreation() {
        let item = Item(name: "Test", description: "A test")
        XCTAssertEqual(item.name, "Test")
        XCTAssertEqual(item.description, "A test")
        XCTAssertNotNil(item.id)
    }

    func testItemCodable() throws {
        let item = Item(name: "Encode", description: "Test encoding")
        let data = try JSONEncoder().encode(item)
        let decoded = try JSONDecoder().decode(Item.self, from: data)

        XCTAssertEqual(item.id, decoded.id)
        XCTAssertEqual(item.name, decoded.name)
    }

    func testItemHashable() {
        let item1 = Item(name: "A", description: "")
        let item2 = Item(name: "B", description: "")
        let set: Set<Item> = [item1, item2, item1]
        XCTAssertEqual(set.count, 2)
    }
}
```

### 4. Service Integration Tests

```swift
// Tests/NCBS[PluginName]Tests/ServiceTests.swift

import XCTest
@testable import NCBS[PluginName]

final class StorageIntegrationTests: XCTestCase {
    var mockStorage: MockStorageService!

    override func setUp() {
        super.setUp()
        mockStorage = MockStorageService()
    }

    func testSaveAndLoad() async throws {
        let data = "Hello".data(using: .utf8)!
        try await mockStorage.save(data, key: "test")

        let loaded = try await mockStorage.load(key: "test")
        XCTAssertEqual(loaded, data)
    }

    func testDelete() async throws {
        let data = Data([1, 2, 3])
        try await mockStorage.save(data, key: "delete-me")
        try await mockStorage.delete(key: "delete-me")

        let loaded = try await mockStorage.load(key: "delete-me")
        XCTAssertNil(loaded)
    }

    func testListKeys() async throws {
        try await mockStorage.save(Data(), key: "photos/a")
        try await mockStorage.save(Data(), key: "photos/b")
        try await mockStorage.save(Data(), key: "docs/c")

        let photoKeys = await mockStorage.listKeys(prefix: "photos/")
        XCTAssertEqual(photoKeys.count, 2)

        let allKeys = await mockStorage.listKeys(prefix: nil)
        XCTAssertEqual(allKeys.count, 3)
    }
}
```

## Minimum Test Requirements

### Plugin Mode (--mode plugin)
- **3 ViewModel tests**: initial state, load, add/delete operations
- **2 Plugin lifecycle tests**: metadata validation, activate/deactivate
- **2 Model tests**: creation, Codable round-trip
- **1 Service test**: storage save/load integration
- **Total minimum: 8 tests**

### Host Mode (--mode host)
- **4 ViewModel tests**: for core views (dashboard, settings)
- **3 Plugin registry tests**: register, activate, deactivate
- **3 Service tests**: compression, storage, network
- **3 Model tests**: storage stats, plugin metadata
- **2 Integration tests**: plugin loading, context injection
- **Total minimum: 15 tests**
