# Swift + SwiftUI Code Patterns

## Architecture: MVVM

All plugins and host views follow Model-View-ViewModel:

```
View (SwiftUI) → ViewModel (@Observable) → Service (protocol) → Storage/Network
```

- **Views** are declarative SwiftUI structs — no business logic
- **ViewModels** are `@Observable` classes — own the state and logic
- **Models** are `Codable` structs — pure data
- **Services** are protocols — injected via PluginContext

## SwiftUI View Patterns

### Basic View Structure

```swift
import SwiftUI

struct ItemListView: View {
    @State private var viewModel: ItemListViewModel

    var body: some View {
        NavigationStack {
            Group {
                if viewModel.isLoading {
                    ProgressView("Loading...")
                } else if let error = viewModel.error {
                    ContentUnavailableView("Error", systemImage: "exclamationmark.triangle", description: Text(error))
                } else if viewModel.items.isEmpty {
                    ContentUnavailableView("No Items", systemImage: "tray", description: Text("Add your first item"))
                } else {
                    List {
                        ForEach(viewModel.items) { item in
                            ItemRow(item: item)
                        }
                        .onDelete(perform: viewModel.deleteItems)
                    }
                }
            }
            .navigationTitle("Items")
            .toolbar {
                Button("Add", systemImage: "plus") {
                    viewModel.showAddSheet = true
                }
            }
            .sheet(isPresented: $viewModel.showAddSheet) {
                AddItemView(onSave: viewModel.addItem)
            }
            .task {
                await viewModel.load()
            }
        }
    }
}
```

### State Management

```swift
// Use @Observable for view models (iOS 17+)
@Observable
final class ItemListViewModel {
    var items: [Item] = []
    var isLoading = false
    var error: String?
    var showAddSheet = false

    private let context: PluginContext

    init(context: PluginContext) {
        self.context = context
    }
}

// Use @State in views to own view models
struct MyView: View {
    @State private var viewModel = MyViewModel()
    // ...
}

// Use @Environment for dependency injection from host
struct PluginView: View {
    @Environment(PluginRegistry.self) var registry
    // ...
}
```

### Navigation

```swift
// NavigationStack with typed destinations
struct MainView: View {
    @State private var path = NavigationPath()

    var body: some View {
        NavigationStack(path: $path) {
            List(items) { item in
                NavigationLink(value: item) {
                    ItemRow(item: item)
                }
            }
            .navigationDestination(for: Item.self) { item in
                ItemDetailView(item: item)
            }
        }
    }
}
```

### Forms

```swift
struct AddItemView: View {
    @State private var name = ""
    @State private var description = ""
    @Environment(\.dismiss) private var dismiss
    var onSave: (Item) -> Void

    var body: some View {
        NavigationStack {
            Form {
                Section("Details") {
                    TextField("Name", text: $name)
                    TextField("Description", text: $description)
                }
            }
            .navigationTitle("New Item")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        onSave(Item(name: name, description: description))
                        dismiss()
                    }
                    .disabled(name.isEmpty)
                }
            }
        }
    }
}
```

## Data Models

```swift
// Always Codable for storage, Identifiable for SwiftUI lists
struct Item: Identifiable, Codable, Hashable {
    let id: UUID
    var name: String
    var description: String
    var createdAt: Date
    var data: Data?

    init(id: UUID = UUID(), name: String, description: String, data: Data? = nil) {
        self.id = id
        self.name = name
        self.description = description
        self.createdAt = Date()
        self.data = data
    }
}
```

## Async/Await Patterns

```swift
// Loading data from storage
func load() async {
    isLoading = true
    defer { isLoading = false }

    do {
        if let data = try await context.storageService.load(key: storageKey) {
            self.items = try JSONDecoder().decode([Item].self, from: data)
        }
    } catch {
        self.error = error.localizedDescription
    }
}

// Compressing and saving
func saveWithCompression(_ item: Item) async throws {
    let rawData = try JSONEncoder().encode(item)
    let compressed = try await context.compressionService.compress(data: rawData)
    try await context.storageService.save(compressed, key: "item-\(item.id)")
}

// Loading and decompressing
func loadCompressed(id: UUID) async throws -> Item? {
    guard let compressed = try await context.storageService.load(key: "item-\(id)") else {
        return nil
    }
    let raw = try await context.compressionService.decompress(data: compressed)
    return try JSONDecoder().decode(Item.self, from: raw)
}
```

## Error Handling

```swift
// Use typed errors for domain logic
enum PluginError: LocalizedError {
    case storageUnavailable
    case compressionFailed(String)
    case permissionDenied(PluginPermission)

    var errorDescription: String? {
        switch self {
        case .storageUnavailable:
            return "Storage is not available"
        case .compressionFailed(let reason):
            return "Compression failed: \(reason)"
        case .permissionDenied(let permission):
            return "Permission denied: \(permission.rawValue)"
        }
    }
}

// Handle in views with alerts
struct MyView: View {
    @State private var viewModel: MyViewModel
    @State private var showError = false

    var body: some View {
        ContentView()
            .onChange(of: viewModel.error) { _, newValue in
                showError = newValue != nil
            }
            .alert("Error", isPresented: $showError) {
                Button("OK") { viewModel.error = nil }
            } message: {
                Text(viewModel.error ?? "Unknown error")
            }
    }
}
```

## Naming Conventions

- **Types**: PascalCase (`ItemListViewModel`, `StorageService`)
- **Properties/Methods**: camelCase (`isLoading`, `loadItems()`)
- **Constants**: camelCase (`let maxItems = 100`)
- **Protocols**: PascalCase with descriptive suffix (`CompressionServiceProtocol`)
- **Files**: Match type name (`ItemListViewModel.swift`)
- **Packages**: Prefixed with `NCBS` (`NCBSPhotoGallery`)
- **Plugin IDs**: Reverse DNS (`com.nocloudbs.photo-gallery`)

## Common UI Components

### Storage Gauge

```swift
struct StorageGaugeView: View {
    let used: Int64
    let total: Int64

    private var percentage: Double {
        guard total > 0 else { return 0 }
        return Double(used) / Double(total)
    }

    var body: some View {
        Gauge(value: percentage) {
            Text("Storage")
        } currentValueLabel: {
            Text(ByteCountFormatter.string(fromByteCount: used, countStyle: .file))
        }
        .gaugeStyle(.accessoryCircular)
    }
}
```

### Compression Badge

```swift
struct CompressionBadge: View {
    let ratio: Double

    var body: some View {
        Label("\(ratio, specifier: "%.1f")x", systemImage: "arrow.down.right.and.arrow.up.left")
            .font(.caption)
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(.green.opacity(0.15))
            .foregroundStyle(.green)
            .clipShape(Capsule())
    }
}
```
