# Expo (React Native) + Supabase Scaffolding

## Initial Setup

```bash
# Create Expo app
npx create-expo-app src --template tabs

cd src

# Install Supabase
npx expo install @supabase/supabase-js @react-native-async-storage/async-storage react-native-url-polyfill

# Install navigation
npx expo install @react-navigation/native @react-navigation/native-stack @react-navigation/bottom-tabs
npx expo install react-native-screens react-native-safe-area-context

# Install UI components
npx expo install react-native-paper react-native-vector-icons
npx expo install expo-linear-gradient

# Install utilities
npx expo install expo-secure-store expo-notifications expo-image-picker
npx expo install react-native-reanimated react-native-gesture-handler
```

## Directory Structure

```
src/
├── app/
│   ├── (tabs)/
│   │   ├── index.tsx
│   │   ├── explore.tsx
│   │   └── _layout.tsx
│   ├── (auth)/
│   │   ├── login.tsx
│   │   ├── signup.tsx
│   │   └── _layout.tsx
│   ├── _layout.tsx
│   └── +not-found.tsx
├── components/
│   ├── ui/
│   ├── forms/
│   └── cards/
├── lib/
│   ├── supabase.ts
│   └── auth.tsx
├── hooks/
│   ├── useAuth.ts
│   └── useItems.ts
├── types/
│   └── database.ts
├── constants/
│   └── Colors.ts
└── assets/
```

## Environment Template

Create `.env`:

```env
EXPO_PUBLIC_SUPABASE_URL=your_supabase_url
EXPO_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
```

## App Configuration

### app.json

```json
{
  "expo": {
    "name": "MyApp",
    "slug": "my-app",
    "version": "1.0.0",
    "orientation": "portrait",
    "icon": "./assets/images/icon.png",
    "scheme": "myapp",
    "userInterfaceStyle": "automatic",
    "splash": {
      "image": "./assets/images/splash.png",
      "resizeMode": "contain",
      "backgroundColor": "#ffffff"
    },
    "ios": {
      "supportsTablet": true,
      "bundleIdentifier": "com.yourcompany.myapp"
    },
    "android": {
      "adaptiveIcon": {
        "foregroundImage": "./assets/images/adaptive-icon.png",
        "backgroundColor": "#ffffff"
      },
      "package": "com.yourcompany.myapp"
    },
    "web": {
      "favicon": "./assets/images/favicon.png",
      "bundler": "metro",
      "output": "static"
    },
    "plugins": [
      "expo-router",
      "expo-secure-store"
    ]
  }
}
```

### babel.config.js (REQUIRED for web)

Metro's web bundle is loaded as a regular `<script defer>`, NOT `<script type="module">`.
Dependencies that use `import.meta` (e.g., Zustand v5 ESM middleware) will crash the entire
bundle with `SyntaxError: Cannot use 'import.meta' outside a module`, silently killing React
hydration and making every interactive element on the page unclickable.

```javascript
module.exports = function (api) {
  api.cache(true);
  return {
    presets: ['babel-preset-expo'],
    plugins: [
      // Transform import.meta.env → process.env for web compatibility.
      // Metro outputs non-module scripts where import.meta is not available.
      function () {
        return {
          visitor: {
            MetaProperty(path) {
              const { node } = path;
              if (node.meta.name !== 'import' || node.property.name !== 'meta') return;

              const parent = path.parentPath;
              if (!parent.isMemberExpression()) return;
              if (parent.node.property.name !== 'env') return;

              const grandparent = parent.parentPath;
              if (
                grandparent.isMemberExpression() &&
                grandparent.node.property.name === 'MODE'
              ) {
                grandparent.replaceWithSourceString('process.env.NODE_ENV');
              } else {
                parent.replaceWithSourceString('process.env');
              }
            },
          },
        };
      },
    ],
  };
};
```

### metro.config.js

```javascript
const { getDefaultConfig } = require('expo/metro-config');

const config = getDefaultConfig(__dirname);

module.exports = config;
```

## Development

```bash
# Start development server
npx expo start

# Run on iOS simulator
npx expo run:ios

# Run on Android emulator
npx expo run:android
```
