# Expo + Supabase Build Process

## Steps

1. Scaffold: `npx create-expo-app . --template tabs`
2. Install Supabase and navigation dependencies
3. **Setup Tests**: `npm install -D jest @testing-library/react-native @testing-library/jest-native jest-expo`
4. Create jest.config.js and jest.setup.js
5. **CRITICAL**: Create `babel.config.js` with `import.meta.env` → `process.env` transform (see scaffold template). Without this, the web bundle will silently fail — pages render but no click handlers work.
6. Create `metro.config.js` using `expo/metro-config` defaults
7. If targeting web: Add `"web": { "bundler": "metro", "output": "static" }` to app.json
8. Set up auth context
9. Implement screens from DESIGN.md
10. Run `npx expo start` to verify compilation
11. If targeting web: Run `npx expo export --platform web` and scan the output bundle for `import.meta` to verify the babel transform is working
