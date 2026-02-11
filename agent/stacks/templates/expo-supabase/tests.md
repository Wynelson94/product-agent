# Expo (React Native) Test Patterns (Jest)

## Setup

```bash
npm install -D jest @testing-library/react-native @testing-library/jest-native jest-expo
```

## package.json scripts

```json
{
  "scripts": {
    "test": "jest",
    "test:watch": "jest --watch",
    "test:coverage": "jest --coverage"
  }
}
```

## jest.config.js

```javascript
module.exports = {
  preset: 'jest-expo',
  setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
  transformIgnorePatterns: [
    'node_modules/(?!((jest-)?react-native|@react-native(-community)?)|expo(nent)?|@expo(nent)?/.*|@expo-google-fonts/.*|react-navigation|@react-navigation/.*|@unimodules/.*|unimodules|sentry-expo|native-base|react-native-svg)'
  ],
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/$1',
  },
  collectCoverageFrom: [
    '**/*.{ts,tsx}',
    '!**/node_modules/**',
    '!**/coverage/**',
    '!**/.expo/**',
  ],
  testPathIgnorePatterns: [
    '/node_modules/',
    '/.expo/',
  ],
};
```

## jest.setup.js

```javascript
import '@testing-library/jest-native/extend-expect';

// Mock AsyncStorage
jest.mock('@react-native-async-storage/async-storage', () =>
  require('@react-native-async-storage/async-storage/jest/async-storage-mock')
);

// Mock Supabase
jest.mock('./lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: jest.fn(() => Promise.resolve({ data: { session: null }, error: null })),
      signInWithPassword: jest.fn(() => Promise.resolve({ data: { user: {} }, error: null })),
      signUp: jest.fn(() => Promise.resolve({ data: { user: {} }, error: null })),
      signOut: jest.fn(() => Promise.resolve({ error: null })),
      onAuthStateChange: jest.fn(() => ({
        data: { subscription: { unsubscribe: jest.fn() } }
      })),
    },
    from: jest.fn(() => ({
      select: jest.fn().mockReturnThis(),
      insert: jest.fn().mockReturnThis(),
      update: jest.fn().mockReturnThis(),
      delete: jest.fn().mockReturnThis(),
      eq: jest.fn().mockReturnThis(),
      order: jest.fn(() => Promise.resolve({ data: [], error: null })),
      single: jest.fn(() => Promise.resolve({ data: null, error: null })),
    })),
  },
}));

// Mock expo-secure-store
jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn(() => Promise.resolve(null)),
  setItemAsync: jest.fn(() => Promise.resolve()),
  deleteItemAsync: jest.fn(() => Promise.resolve()),
}));

// Mock expo-router
jest.mock('expo-router', () => ({
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
    back: jest.fn(),
  }),
  useLocalSearchParams: () => ({}),
  useSegments: () => [],
  Link: 'Link',
}));

// Silence React Native logs in tests
jest.mock('react-native/Libraries/Animated/NativeAnimatedHelper');
```

## Component Test Pattern

```typescript
// __tests__/components/Button.test.tsx
import React from 'react';
import { render, fireEvent, screen } from '@testing-library/react-native';
import { Button } from '@/components/ui/Button';

describe('Button', () => {
  it('renders with title', () => {
    render(<Button title="Press me" onPress={() => {}} />);
    expect(screen.getByText('Press me')).toBeTruthy();
  });

  it('calls onPress when pressed', () => {
    const onPress = jest.fn();
    render(<Button title="Press me" onPress={onPress} />);

    fireEvent.press(screen.getByText('Press me'));
    expect(onPress).toHaveBeenCalledTimes(1);
  });

  it('is disabled when loading', () => {
    const onPress = jest.fn();
    render(<Button title="Press me" onPress={onPress} loading />);

    fireEvent.press(screen.getByText('Press me'));
    expect(onPress).not.toHaveBeenCalled();
  });

  it('shows loading indicator when loading', () => {
    render(<Button title="Press me" onPress={() => {}} loading />);
    expect(screen.getByTestId('loading-indicator')).toBeTruthy();
  });
});
```

## Screen Test Pattern

```typescript
// __tests__/screens/HomeScreen.test.tsx
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react-native';
import HomeScreen from '@/app/(tabs)/index';

// Mock the data fetching
jest.mock('@/hooks/useItems', () => ({
  useItems: () => ({
    items: [
      { id: '1', title: 'Item 1' },
      { id: '2', title: 'Item 2' },
    ],
    isLoading: false,
    error: null,
  }),
}));

describe('HomeScreen', () => {
  it('renders items list', async () => {
    render(<HomeScreen />);

    await waitFor(() => {
      expect(screen.getByText('Item 1')).toBeTruthy();
      expect(screen.getByText('Item 2')).toBeTruthy();
    });
  });
});

describe('HomeScreen loading state', () => {
  beforeEach(() => {
    jest.resetModules();
    jest.mock('@/hooks/useItems', () => ({
      useItems: () => ({
        items: [],
        isLoading: true,
        error: null,
      }),
    }));
  });

  it('shows loading state', () => {
    render(<HomeScreen />);
    expect(screen.getByTestId('loading-indicator')).toBeTruthy();
  });
});
```

## Hook Test Pattern

```typescript
// __tests__/hooks/useAuth.test.tsx
import { renderHook, act, waitFor } from '@testing-library/react-native';
import { useAuth, AuthProvider } from '@/contexts/AuthContext';
import { supabase } from '@/lib/supabase';

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <AuthProvider>{children}</AuthProvider>
);

describe('useAuth', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('starts with no user', () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    expect(result.current.user).toBeNull();
  });

  it('login updates user state', async () => {
    const mockUser = { id: '1', email: 'test@test.com' };
    (supabase.auth.signInWithPassword as jest.Mock).mockResolvedValue({
      data: { user: mockUser, session: {} },
      error: null,
    });

    const { result } = renderHook(() => useAuth(), { wrapper });

    await act(async () => {
      await result.current.signIn('test@test.com', 'password');
    });

    await waitFor(() => {
      expect(result.current.user).toEqual(mockUser);
    });
  });

  it('logout clears user state', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });

    await act(async () => {
      await result.current.signOut();
    });

    expect(result.current.user).toBeNull();
    expect(supabase.auth.signOut).toHaveBeenCalled();
  });
});
```

## Utility Test Pattern

```typescript
// __tests__/utils/format.test.ts
import { formatDate, formatCurrency, truncate } from '@/utils/format';

describe('formatDate', () => {
  it('formats date correctly', () => {
    const date = new Date('2024-01-15T10:30:00Z');
    expect(formatDate(date)).toMatch(/Jan.*15.*2024/);
  });

  it('handles null date', () => {
    expect(formatDate(null)).toBe('');
  });
});

describe('formatCurrency', () => {
  it('formats USD correctly', () => {
    expect(formatCurrency(1234.56)).toBe('$1,234.56');
  });

  it('handles zero', () => {
    expect(formatCurrency(0)).toBe('$0.00');
  });
});

describe('truncate', () => {
  it('truncates long strings', () => {
    const result = truncate('This is a very long string', 10);
    expect(result).toBe('This is a...');
  });

  it('does not truncate short strings', () => {
    expect(truncate('Short', 10)).toBe('Short');
  });
});
```

## Web Bundle Smoke Test (REQUIRED for web deployments)

When deploying to web (Vercel), you MUST verify the web bundle doesn't contain
incompatible code that will silently break React hydration.

### Bundle validation script

Add to `package.json` scripts:
```json
{
  "scripts": {
    "test:web-bundle": "npx expo export --platform web && node scripts/check-web-bundle.js"
  }
}
```

### scripts/check-web-bundle.js

```javascript
const fs = require('fs');
const path = require('path');

const distDir = path.join(__dirname, '..', 'dist', 'bundles');

if (!fs.existsSync(distDir)) {
  console.error('ERROR: dist/bundles not found. Run "npx expo export --platform web" first.');
  process.exit(1);
}

const jsFiles = fs.readdirSync(distDir).filter(f => f.endsWith('.js'));
let hasErrors = false;

for (const file of jsFiles) {
  const content = fs.readFileSync(path.join(distDir, file), 'utf-8');
  // Remove comments before scanning
  const noComments = content.replace(/\/\/.*$/gm, '').replace(/\/\*[\s\S]*?\*\//g, '');

  if (noComments.includes('import.meta')) {
    console.error(`ERROR: ${file} contains "import.meta" — this will crash in the browser.`);
    console.error('  Metro outputs non-module scripts where import.meta is unavailable.');
    console.error('  Fix: Add import.meta → process.env transform to babel.config.js');
    hasErrors = true;
  }
}

if (hasErrors) {
  process.exit(1);
} else {
  console.log('Web bundle check passed — no import.meta found.');
}
```

### When to run

- After the Builder finishes scaffolding and before deployment
- As part of the Tester validation phase
- In the Deployer's pre-deployment checks

## Run Tests

```bash
# Run all tests
npm test

# Run in watch mode
npm run test:watch

# Run with coverage
npm run test:coverage

# Run specific test file
npm test -- __tests__/components/Button.test.tsx

# Run tests matching a pattern
npm test -- --testNamePattern="Button"

# Validate web bundle (for web deployments)
npm run test:web-bundle
```
