# Swift + SwiftUI Code Patterns

## Architecture: MVVM

All views follow Model-View-ViewModel:

```
View (SwiftUI) → ViewModel (@Observable) → Service (protocol) → Storage/Network
```

- **Views** are declarative SwiftUI structs — no business logic
- **ViewModels** are `@Observable` classes — own the state and logic
- **Models** are `Codable` structs — pure data
- **Services** are protocols — injected via environment or initializer

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
import SwiftUI  // Includes @Observable macro (iOS 17+)
// IMPORTANT: Use @Observable, NOT ObservableObject + @Published.
// @Published will compile but views won't update — a silent bug.
@Observable
final class ItemListViewModel {
    var items: [Item] = []
    var isLoading = false
    var error: String?
    var showAddSheet = false

    private let storageService: StorageService

    init(storageService: StorageService) {
        self.storageService = storageService
    }
}

// Use @State in views to own view models
struct MyView: View {
    @State private var viewModel = MyViewModel()
    // ...
}

// Use @Environment for dependency injection
struct AppView: View {
    @Environment(AppState.self) var appState
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
        if let data = try await storageService.load(key: storageKey) {
            self.items = try JSONDecoder().decode([Item].self, from: data)
        }
    } catch {
        self.error = error.localizedDescription
    }
}

// Saving data
func save(_ item: Item) async throws {
    let data = try JSONEncoder().encode(item)
    try await storageService.save(data, key: "item-\(item.id)")
}
```

## Error Handling

```swift
// Use typed errors for domain logic
enum AppError: LocalizedError {
    case storageUnavailable
    case networkFailed(String)
    case invalidData

    var errorDescription: String? {
        switch self {
        case .storageUnavailable:
            return "Storage is not available"
        case .networkFailed(let reason):
            return "Network request failed: \(reason)"
        case .invalidData:
            return "The data could not be read"
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

## Accessibility Patterns

Every interactive element must include VoiceOver support:

```swift
// Buttons and tappable elements
Button(action: addItem) {
    Image(systemName: "plus")
}
.accessibilityLabel("Add item")
.accessibilityHint("Creates a new item")

// Data displays
Text(formattedAmount)
    .accessibilityLabel("Budget remaining: \(formattedAmount)")

// Toggle/switch
Toggle("Dark Mode", isOn: $isDarkMode)
    .accessibilityLabel("Dark mode")
    .accessibilityValue(isDarkMode ? "On" : "Off")
```

Support Dynamic Type — never use fixed font sizes:
```swift
// CORRECT
.font(.headline)
.font(.body)

// WRONG — does not scale with Dynamic Type
// .font(.system(size: 16))
```

## Dual-Platform Patterns

Views must adapt to both macOS and iOS:

```swift
// Navigation — use NavigationSplitView on macOS, NavigationStack on iOS
#if os(macOS)
NavigationSplitView {
    SidebarView()
} detail: {
    DetailView()
}
#else
NavigationStack {
    ContentView()
}
#endif

// Platform-specific modifiers
.navigationBarTitleDisplayMode(.inline)  // iOS only
#if os(macOS)
.frame(minWidth: 600, minHeight: 400)
#endif
```

Platform array in Package.swift:
```swift
platforms: [.iOS(.v17), .macOS(.v14)]
```

## Naming Conventions

- **Types**: PascalCase (`ItemListViewModel`, `StorageService`)
- **Properties/Methods**: camelCase (`isLoading`, `loadItems()`)
- **Constants**: camelCase (`let maxItems = 100`)
- **Protocols**: PascalCase with descriptive suffix (`StorageServiceProtocol`)
- **Files**: Match type name (`ItemListViewModel.swift`)
