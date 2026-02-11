# NoCloud BS — App Reference

Source: Taylor's master agent prompt (29-agent architecture for enterprise production-ready build).
This document captures the key details about the real NoCloud BS app so the Product Agent
builds plugins and host features that align with the actual product — not a generic SwiftUI app.

---

## App Identity

**NoCloud BS** is a dual-platform Apple app (macOS + iOS) built around a patented lossless
compression engine. It is NOT a simple file manager — it is a full environment reader, compressor,
and viewer that makes cloud storage unnecessary.

**Core mission**: Replace cloud storage with on-device compressed storage that is invisible to the
user. Files are compressed, stay fully usable while compressed, and remain compressed + usable
when shared with others.

**The compression engine is the HEART of the app. Everything else serves it.**

---

## Core Capabilities

### Lossless Compression Engine

- Reads the user's entire environment — all data, all files, all content types
- Compresses everything with **100% lossless compression** — bit-for-bit identical roundtrip, zero quality loss
- Data stays **fully usable while compressed** — images display, PDFs render, videos play, docs open. The user never sees decompression. Compression is invisible.
- Transparent file access layer intercepts reads and decompresses on-the-fly (<16ms per frame)
- Supports: random access, partial reads, streaming reads
- **SHA-256 verification** on every roundtrip

### Compression Algorithm Strategy

Adaptive selection based on file access frequency ("hotness"):

| Algorithm | Speed | Ratio | Use Case |
|-----------|-------|-------|----------|
| LZ4 | Ultra-fast decompress | Lower | Hot/frequently-accessed files |
| Apple LZFSE | Hardware-accelerated | Good | General use on Apple Silicon |
| zstd | Balanced | Better | Warm files, balanced workloads |
| LZMA | Slower | Best | Cold storage, archival |

**Rules**:
- Already-compressed formats (JPEG, MP4, ZIP) → store as-is or minimal wrapping
- Files <4KB → skip compression (overhead not worth it)
- Target: compress ≥500MB/s, decompress ≥1GB/s on Apple Silicon
- Target: ≥30% average size reduction across all file types
- Target: 64MB memory ceiling for compression operations
- **Target: 100.000% lossless pass rate — zero exceptions**

### File Viewer Engine

The app includes a comprehensive viewer for ALL file types — not just a file manager:

| Category | Formats | Features |
|----------|---------|----------|
| Images | JPEG, PNG, GIF, WebP, HEIC, TIFF, BMP, SVG, RAW, PSD | Pinch-zoom, tile rendering >4096px, EXIF overlay |
| PDF | PDF | Multi-page, thumbnail sidebar, search, text selection |
| Video | All AVPlayer-supported | Custom blackGold/gold controls, PiP, AirPlay, speed control |
| Audio | All AVPlayer-supported | Waveform visualization (gold on black), playback, ID3 metadata |
| Documents | RTF, plain text, Markdown, HTML | Rendered display, sandboxed HTML |
| Spreadsheets | CSV, TSV | Scrollable grid with gold headers |
| Code | 20+ languages | Syntax highlighting, blackGold/gold theme |
| Archives | ZIP, tar, etc. | Browse without extracting, preview individual files |
| 3D | USDZ | SceneKit/RealityKit rendering |

**All viewing works on compressed data seamlessly** — the transparent access layer handles decompression.

Thumbnail pipeline: background generation → disk cache → progressive loading (icon → low-res → full-res).

### Transfer Integrity

Files shared via iMessage, AirDrop, or email arrive **STILL compressed AND immediately usable**
by the recipient **without the NoCloud BS app installed**.

Implementation uses standard container format or format-preserving compression with
UIActivityItemProvider/NSItemProvider and proper UTType registration.

---

## Architecture

### Dual-Platform
- **macOS**: NavigationSplitView-based sidebar navigation, full menu bar, keyboard shortcuts
- **iOS**: NavigationStack + TabBar, swipe actions, pull-to-refresh, share sheet, widgets, Spotlight

### C++/Swift Interop

Performance-critical modules are implemented in C++ with Swift 5.9+ interop:
- Image processing pipeline
- Magic-byte file type detection (100+ types, 10K files/sec)
- Compression algorithms
- Audio DSP
- Text indexing

C++ modules use include/src/modulemap structure. Memory safety via RAII wrappers,
unique_ptr/shared_ptr, documented ownership at boundaries.

### Plugin Architecture

The app uses a plugin system (NCBSPlugin protocol) with:
- PluginRegistry for lifecycle management
- PluginContext for dependency injection (compression, storage, network services)
- Compile-time plugin discovery (explicit registration in App init)
- Each plugin is a self-contained Swift Package

### Offline-First

**Every feature works without internet after download.** This is non-negotiable.
- Cloud sync is additive only — never required
- No spinners, no errors, no degradation offline
- Offline queue for optional networking (persisted to SQLite, processes on connectivity restoration)

---

## Design System

### Color Palette

| Token | Hex | Use |
|-------|-----|-----|
| black | #000000 | Primary background (OLED true black) |
| blackGold | #1A1400 | Cards, sidebar, sheets, modals, nav/tab bars — warm black with gold undertone |
| gold | #CFB53B | Primary accent — buttons, selections, progress, highlights |
| goldLight | #E8D48B | Gold text on dark backgrounds (AA-safe), hover states |
| goldDark | #8B7A2B | Pressed states, borders, dividers |
| teal | #008080 | Secondary accent — links, toggles, secondary buttons |
| tealLight | #40E0D0 | Teal text on dark backgrounds (AA-safe) |
| tealDark | #005F5F | Pressed states, teal borders |
| surfaceTertiary | #2A2210 | Elevated surfaces on blackGold, input fields |
| error | #FF453A | Destructive actions |
| success | #30D158 | Confirmations |
| warning | #FFD60A | Caution states |

### Aesthetic
- Shadows: gold-tinted (gold at 10-30% opacity)
- Loading: gold shimmer animation on blackGold background
- Overall feel: luxury, premium, sleek

### DesignSystem Swift Package
Contains DSColor, DSTypography (Dynamic Type), DSSpacing (4pt grid: 2-64), DSRadius,
DSShadow (gold-tinted), DSAnimation (spring presets). Reusable components: DSButton, DSCard,
DSFileThumbnail, DSSearchBar, DSNavigationBar, DSTabBar, DSLoadingShimmer, DSProgressBar,
DSBadge, DSToast, DSEmptyState, DSErrorState, DSToggle, DSDivider, DSTextField.

---

## Quality Targets

| Metric | Target |
|--------|--------|
| Crash-free rate | ≥ 99.95% |
| Cold launch | < 400ms to interactive |
| Warm launch | < 200ms |
| Scroll performance | 120fps on ProMotion displays |
| Compression transparency | < 16ms overhead per frame |
| Accessibility | WCAG AAA (7:1 contrast ratio) |
| SwiftLint warnings | Zero |
| Force unwraps | Zero in entire codebase |
| Force try | Zero in entire codebase |
| Force cast | Zero in entire codebase |
| Test coverage | 90%+ line coverage |
| Main Thread Checker violations | Zero |
| Memory leaks | Zero (verified via Instruments) |
| Data races | Zero (verified via TSan) |
| Binary size | < 50MB |
| Energy impact | "Low" in Instruments |
| App Store | First-submission approval target |

---

## Golden Rules

These apply to ALL code changes — whether by human or agent:

1. **READ existing codebase FIRST** before any changes
2. **NEVER rename** existing variables, functions, classes, modules, or files
3. **NEVER change** the app's existing vocabulary/terminology
4. **NEVER delete** working code — enhance, optimize, extend only
5. **Follow existing code style** — match what's already there
6. **All changes must be additive and backwards-compatible**
7. **The compression engine is the core** — never break it

---

## Security Requirements

- **Keychain** for all sensitive data (kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly)
- **Biometric auth** via LAContext (Face ID / Touch ID)
- **Encrypted databases** (SQLCipher or NSFileProtectionComplete)
- **ATS enforced**, zero exceptions
- **Public key pinning** for any optional network calls
- **Input validation** on all user input (path traversal prevention, injection prevention)
- **Secure logging** (%{private}@ for sensitive data, strip debug logs in Release)
- **Jailbreak detection** with graceful degradation
- **macOS hardened runtime**
- **Pin all dependency versions**
- **Secure deletion**: remove from filesystem + all caches + DB + search index

---

## Privacy & Compliance

- **PrivacyInfo.xcprivacy** with all required reason APIs
- **ATT**: Only if tracking exists (target: skip entirely for offline-only)
- **Privacy Nutrition Labels**: Target "Data Not Collected"
- **GDPR**: Data export, deletion, consent, bundled privacy policy
- **CCPA**: Opt-out if data sharing exists
- **COPPA**: If applicable

---

## App Store Strategy

- Name (30 chars), subtitle (30), keywords (100), description (4000) — all optimized
- Screenshot strategy: black/gold/teal brand aesthetic for all required device sizes
- App preview video: 15-30s showcasing compression + usability
- Review prep: demo credentials, privacy explanations, export compliance
- SKStoreReviewController at optimal moment
- TestFlight: internal + external test groups

---

## What This Means for Plugin Development

When building NoCloud BS plugins, the Product Agent should know:

1. **Plugins extend a serious production app** — not a toy. Match the quality bar.
2. **Use the host's compression engine** via PluginContext — never implement your own.
3. **Use the host's design system colors** — no custom palettes.
4. **Every plugin feature must work offline** — no network-gated functionality.
5. **Support both macOS and iOS** navigation patterns.
6. **Show compression stats** wherever file sizes are displayed.
7. **Follow the Golden Rules** — all changes additive, never rename/delete host SDK code.
8. **Match quality targets** — zero force unwraps, zero crashes, 90%+ test coverage.
9. **The file viewer is built into the host** — plugins should leverage it, not duplicate it.
10. **Transfer integrity matters** — shared files must remain compressed and usable.

---

## 29-Agent Architecture (Reference)

Taylor's real build system uses 29 specialized agents, showing the enterprise scope:

| # | Agent | Domain |
|---|-------|--------|
| 0 | Orchestrator | Coordination, golden rules enforcement |
| 1 | Software Architect | Clean Architecture, DI, ADRs |
| 2 | Infrastructure & CI/CD | Fastlane, GitHub Actions, SwiftLint |
| 3 | Systems Design | Data flows, caching, offline persistence |
| 4 | Performance | Launch time, scroll, memory, energy |
| 5 | C++/Swift Interop | Native bridges, memory safety |
| 6 | Concurrency & Async | Swift 6, Sendable, actors, TaskGroup |
| 7 | UI/UX Design | HIG compliance, animations, haptics |
| 8 | SwiftUI/UIKit Implementation | State management, view hierarchy |
| 9 | Design System | Tokens, components, component gallery |
| 10 | Accessibility | VoiceOver, Dynamic Type, Reduce Motion |
| 11 | Localization | String Catalogs, RTL, 9 locales |
| 12 | Security | Keychain, biometric, encryption |
| 13 | Privacy & Compliance | PrivacyInfo, GDPR, CCPA |
| 14 | Testing | 90%+ coverage, compression roundtrip tests |
| 15 | Code Quality | SwiftLint strict, zero warnings |
| 16 | Cross-Platform | macOS + iOS, 85%+ code sharing |
| 17 | Apple Frameworks | CloudKit, StoreKit 2, WidgetKit, Spotlight |
| 18 | Networking & API | Optional/additive only, offline queue |
| 19 | App Store Optimization | Listing, screenshots, review prep |
| 20 | Analytics & Observability | os_log, MetricKit, privacy-respecting |
| 21 | Documentation | DocC, ADRs, onboarding guide |
| 22 | File Viewer Engine | All file types, thumbnail pipeline |
| 23 | Data & File Type Handler | UTType + magic bytes, metadata extraction |
| 24 | Git & Version Control | Conventional commits, branch strategy |
| 25 | Error Handling & Resilience | Error hierarchy, graceful degradation |
| 26 | Module Integration | Build verification, dependency direction |
| 27 | Debugging & Diagnostics | Sanitizers, Instruments, debug screen |
| 28 | Compression Engine | THE HEART — lossless, transparent, transfer-safe |
