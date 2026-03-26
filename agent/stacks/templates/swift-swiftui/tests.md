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
// Tests/AppTests/ViewModelTests.swift

import XCTest
@testable import AppCore

final class MainViewModelTests: XCTestCase {
    var viewModel: MainViewModel!
    var mockStorage: MockStorageService!

    override func setUp() {
        super.setUp()
        mockStorage = MockStorageService()
        viewModel = MainViewModel(storageService: mockStorage)
    }

    override func tearDown() {
        viewModel = nil
        mockStorage = nil
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
        try! await mockStorage.save(data, key: "items")

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

        let stored = try! await mockStorage.load(key: "items")
        XCTAssertNotNil(stored)

        let decoded = try! JSONDecoder().decode([Item].self, from: stored!)
        XCTAssertEqual(decoded.count, 1)
        XCTAssertEqual(decoded.first?.name, "Saved")
    }
}
```

### 2. Model Tests

```swift
// Tests/AppTests/ModelTests.swift

import XCTest
@testable import AppCore

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

### 3. Service Integration Tests

```swift
// Tests/AppTests/ServiceTests.swift

import XCTest
@testable import AppCore

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

### Swift/SwiftUI Apps
- **3 ViewModel tests**: initial state, load, add/delete operations
- **2 Model tests**: creation, Codable round-trip
- **1 Service test**: storage save/load integration
- **Total minimum: 6 tests**

### Async Testing

```swift
func testAsyncLoad() async {
    await viewModel.load()
    XCTAssertFalse(viewModel.isLoading)
    XCTAssertEqual(viewModel.items.count, expectedCount)
}

func testAsyncThrows() async throws {
    mockStorage.shouldFail = true
    await viewModel.load()
    XCTAssertNotNil(viewModel.error)
}
```

## Mock Patterns

```swift
// Mock storage service for testing
final class MockStorageService: StorageServiceProtocol {
    var store: [String: Data] = [:]
    var shouldFail = false

    func save(_ data: Data, key: String) async throws {
        if shouldFail { throw AppError.storageUnavailable }
        store[key] = data
    }

    func load(key: String) async throws -> Data? {
        if shouldFail { throw AppError.storageUnavailable }
        return store[key]
    }

    func delete(key: String) async throws {
        store.removeValue(forKey: key)
    }

    func listKeys(prefix: String?) async -> [String] {
        if let prefix {
            return store.keys.filter { $0.hasPrefix(prefix) }
        }
        return Array(store.keys)
    }
}
```
