# Expo + Supabase Code Patterns

## Supabase Client Setup

### lib/supabase.ts

```typescript
import 'react-native-url-polyfill/auto'
import AsyncStorage from '@react-native-async-storage/async-storage'
import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.EXPO_PUBLIC_SUPABASE_URL!
const supabaseAnonKey = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY!

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    storage: AsyncStorage,
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: false,
  },
})
```

## Authentication Context

### lib/auth.tsx

```typescript
import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { Session, User } from '@supabase/supabase-js'
import { supabase } from './supabase'

type AuthContextType = {
  session: Session | null
  user: User | null
  loading: boolean
  signIn: (email: string, password: string) => Promise<void>
  signUp: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Get initial session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      setUser(session?.user ?? null)
      setLoading(false)
    })

    // Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setSession(session)
        setUser(session?.user ?? null)
      }
    )

    return () => subscription.unsubscribe()
  }, [])

  const signIn = async (email: string, password: string) => {
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) throw error
  }

  const signUp = async (email: string, password: string) => {
    const { error } = await supabase.auth.signUp({ email, password })
    if (error) throw error
  }

  const signOut = async () => {
    const { error } = await supabase.auth.signOut()
    if (error) throw error
  }

  return (
    <AuthContext.Provider value={{ session, user, loading, signIn, signUp, signOut }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
```

## Root Layout with Auth

### app/_layout.tsx

```typescript
import { useEffect } from 'react'
import { Stack, useRouter, useSegments } from 'expo-router'
import { AuthProvider, useAuth } from '@/lib/auth'

function RootLayoutNav() {
  const { session, loading } = useAuth()
  const segments = useSegments()
  const router = useRouter()

  useEffect(() => {
    if (loading) return

    const inAuthGroup = segments[0] === '(auth)'

    if (!session && !inAuthGroup) {
      router.replace('/login')
    } else if (session && inAuthGroup) {
      router.replace('/')
    }
  }, [session, loading, segments])

  return (
    <Stack>
      <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
      <Stack.Screen name="(auth)" options={{ headerShown: false }} />
    </Stack>
  )
}

export default function RootLayout() {
  return (
    <AuthProvider>
      <RootLayoutNav />
    </AuthProvider>
  )
}
```

## Login Screen

### app/(auth)/login.tsx

```typescript
import { useState } from 'react'
import { View, StyleSheet, Alert } from 'react-native'
import { TextInput, Button, Text } from 'react-native-paper'
import { Link } from 'expo-router'
import { useAuth } from '@/lib/auth'

export default function LoginScreen() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const { signIn } = useAuth()

  const handleLogin = async () => {
    setLoading(true)
    try {
      await signIn(email, password)
    } catch (error: any) {
      Alert.alert('Error', error.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <View style={styles.container}>
      <Text variant="headlineMedium" style={styles.title}>
        Welcome Back
      </Text>

      <TextInput
        label="Email"
        value={email}
        onChangeText={setEmail}
        autoCapitalize="none"
        keyboardType="email-address"
        style={styles.input}
      />

      <TextInput
        label="Password"
        value={password}
        onChangeText={setPassword}
        secureTextEntry
        style={styles.input}
      />

      <Button
        mode="contained"
        onPress={handleLogin}
        loading={loading}
        disabled={loading}
        style={styles.button}
      >
        Sign In
      </Button>

      <Link href="/signup" asChild>
        <Button mode="text">Don't have an account? Sign Up</Button>
      </Link>
    </View>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 20,
    justifyContent: 'center',
  },
  title: {
    textAlign: 'center',
    marginBottom: 30,
  },
  input: {
    marginBottom: 15,
  },
  button: {
    marginVertical: 10,
  },
})
```

## Data Fetching Hook

### hooks/useItems.ts

```typescript
import { useState, useEffect, useCallback } from 'react'
import { supabase } from '@/lib/supabase'
import { useAuth } from '@/lib/auth'

type Item = {
  id: string
  title: string
  description: string
  created_at: string
}

export function useItems() {
  const [items, setItems] = useState<Item[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { user } = useAuth()

  const fetchItems = useCallback(async () => {
    if (!user) return

    setLoading(true)
    const { data, error } = await supabase
      .from('items')
      .select('*')
      .eq('user_id', user.id)
      .order('created_at', { ascending: false })

    if (error) {
      setError(error.message)
    } else {
      setItems(data || [])
    }
    setLoading(false)
  }, [user])

  useEffect(() => {
    fetchItems()
  }, [fetchItems])

  const addItem = async (title: string, description: string) => {
    if (!user) return

    const { data, error } = await supabase
      .from('items')
      .insert({ title, description, user_id: user.id })
      .select()
      .single()

    if (error) throw error

    setItems((prev) => [data, ...prev])
    return data
  }

  const deleteItem = async (id: string) => {
    const { error } = await supabase.from('items').delete().eq('id', id)

    if (error) throw error

    setItems((prev) => prev.filter((item) => item.id !== id))
  }

  return { items, loading, error, addItem, deleteItem, refresh: fetchItems }
}
```

## Real-time Subscriptions

```typescript
import { useEffect } from 'react'
import { supabase } from '@/lib/supabase'

export function useRealtimeItems(onInsert: (item: any) => void) {
  useEffect(() => {
    const channel = supabase
      .channel('items')
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'items' },
        (payload) => {
          onInsert(payload.new)
        }
      )
      .subscribe()

    return () => {
      supabase.removeChannel(channel)
    }
  }, [onInsert])
}
```

## List Screen with Pull to Refresh

### app/(tabs)/index.tsx

```typescript
import { FlatList, RefreshControl, StyleSheet } from 'react-native'
import { FAB, Card, Text } from 'react-native-paper'
import { useRouter } from 'expo-router'
import { useItems } from '@/hooks/useItems'

export default function HomeScreen() {
  const { items, loading, refresh } = useItems()
  const router = useRouter()

  return (
    <>
      <FlatList
        data={items}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <Card style={styles.card}>
            <Card.Title title={item.title} />
            <Card.Content>
              <Text>{item.description}</Text>
            </Card.Content>
          </Card>
        )}
        refreshControl={
          <RefreshControl refreshing={loading} onRefresh={refresh} />
        }
        contentContainerStyle={styles.list}
      />

      <FAB
        icon="plus"
        style={styles.fab}
        onPress={() => router.push('/new-item')}
      />
    </>
  )
}

const styles = StyleSheet.create({
  list: {
    padding: 16,
  },
  card: {
    marginBottom: 12,
  },
  fab: {
    position: 'absolute',
    right: 16,
    bottom: 16,
  },
})
```

## Push Notifications

```typescript
import * as Notifications from 'expo-notifications'
import * as Device from 'expo-device'
import { supabase } from '@/lib/supabase'

export async function registerForPushNotifications() {
  if (!Device.isDevice) {
    return null
  }

  const { status: existingStatus } = await Notifications.getPermissionsAsync()
  let finalStatus = existingStatus

  if (existingStatus !== 'granted') {
    const { status } = await Notifications.requestPermissionsAsync()
    finalStatus = status
  }

  if (finalStatus !== 'granted') {
    return null
  }

  const token = (await Notifications.getExpoPushTokenAsync()).data

  // Save token to database
  await supabase.from('push_tokens').upsert({
    user_id: (await supabase.auth.getUser()).data.user?.id,
    token,
  })

  return token
}
```

## Web Compatibility (Expo Web)

When deploying Expo apps to the web (e.g., Vercel via `npx expo export --platform web`),
Metro bundles the app as a regular `<script defer>` — NOT `<script type="module">`.
This creates compatibility issues with ESM-only features.

### Known Issues

1. **`import.meta.env` in dependencies** — Libraries like Zustand v5 use `import.meta.env.MODE`
   in their ESM middleware. This crashes the entire JS bundle with
   `SyntaxError: Cannot use 'import.meta' outside a module`. React never hydrates, making
   the page look correct but completely non-interactive.

2. **Node.js-only APIs** — Some dependencies may use Node.js APIs (`fs`, `path`, `crypto`)
   that don't exist in the browser. These will throw at runtime.

### Required: babel.config.js

Every Expo project targeting web MUST include a `babel.config.js` with the `import.meta` → `process.env`
transform. See the scaffold template for the exact implementation.

### Required: metro.config.js

Always create a `metro.config.js` even if starting with defaults. This makes it easy to add
web-specific resolver configuration later.

### Validation

After building, always verify the web bundle:
```bash
npx expo export --platform web
# Check for import.meta in the output (excluding comments)
grep -r "import\.meta" dist/bundles/ --include="*.js" | grep -v "\/\/" | grep -v "\*"
```

If `import.meta` appears in non-comment code, the babel transform is not working correctly.
