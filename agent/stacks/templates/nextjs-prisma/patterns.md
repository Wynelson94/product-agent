# Next.js + Prisma Code Patterns

## Prisma Client Singleton

### lib/prisma.ts

```typescript
import { PrismaClient } from '@prisma/client'

const globalForPrisma = globalThis as unknown as {
  prisma: PrismaClient | undefined
}

export const prisma = globalForPrisma.prisma ?? new PrismaClient()

if (process.env.NODE_ENV !== 'production') globalForPrisma.prisma = prisma
```

## Auth.js Configuration (Auth.js v5 / NextAuth v5)

### lib/auth.ts

```typescript
import NextAuth from 'next-auth'
import { PrismaAdapter } from '@auth/prisma-adapter'
import Credentials from 'next-auth/providers/credentials'
import bcrypt from 'bcryptjs'
import { prisma } from './prisma'

export const { handlers, auth, signIn, signOut } = NextAuth({
  adapter: PrismaAdapter(prisma),
  providers: [
    Credentials({
      credentials: {
        email: { label: 'Email', type: 'email' },
        password: { label: 'Password', type: 'password' },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) {
          return null
        }

        const user = await prisma.user.findUnique({
          where: { email: credentials.email as string },
        })

        if (!user || !user.passwordHash) {
          return null
        }

        const isValid = await bcrypt.compare(
          credentials.password as string,
          user.passwordHash
        )

        if (!isValid) {
          return null
        }

        return {
          id: user.id,
          email: user.email,
          name: user.name,
        }
      },
    }),
  ],
  session: {
    strategy: 'jwt',
  },
  pages: {
    signIn: '/login',
  },
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.id = user.id
      }
      return token
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.id = token.id as string
      }
      return session
    },
  },
})
```

### API Route (app/api/auth/[...nextauth]/route.ts)

```typescript
import { handlers } from '@/lib/auth'

export const { GET, POST } = handlers
```

## Middleware

### middleware.ts

```typescript
export { auth as middleware } from '@/lib/auth'

export const config = {
  matcher: ['/dashboard/:path*', '/settings/:path*'],
}
```

## Auth Forms (CRITICAL — useActionState Pattern)

ALWAYS use server actions with `useActionState` for auth forms.
NEVER use `signIn()` from `next-auth/react` on the client side — it depends on
a CSRF token fetch that fails on Next.js 16+, breaking hydration and making
all forms non-interactive.

### Login Server Action (app/login/actions.ts)

```typescript
'use server'

import { signIn } from '@/lib/auth'
import { AuthError } from 'next-auth'
import { redirect } from 'next/navigation'

export async function loginAction(
  prevState: { error?: string } | null,
  formData: FormData
) {
  const email = formData.get('email') as string
  const password = formData.get('password') as string

  if (!email || !password) {
    return { error: 'Email and password are required.' }
  }

  try {
    await signIn('credentials', { email, password, redirect: false })
  } catch (e) {
    if (e instanceof AuthError) {
      return { error: 'Invalid email or password.' }
    }
    throw e
  }

  redirect('/dashboard')
}
```

### Login Page (app/login/page.tsx)

```tsx
'use client'

import { useActionState } from 'react'
import { loginAction } from './actions'

export default function LoginPage() {
  const [state, formAction, pending] = useActionState(loginAction, null)

  return (
    <form action={formAction}>
      {state?.error && <div className="text-destructive">{state.error}</div>}
      <input name="email" type="email" required />
      <input name="password" type="password" required />
      <button type="submit" disabled={pending}>
        {pending ? 'Signing in...' : 'Sign in'}
      </button>
    </form>
  )
}
```

### Signup Server Action (app/signup/actions.ts)

```typescript
'use server'

import { prisma } from '@/lib/prisma'
import bcrypt from 'bcryptjs'
import { signIn } from '@/lib/auth'
import { AuthError } from 'next-auth'
import { redirect } from 'next/navigation'

export async function signUpAction(
  prevState: { error?: string } | null,
  formData: FormData
) {
  const name = formData.get('name') as string
  const email = formData.get('email') as string
  const password = formData.get('password') as string

  if (!name) return { error: 'Name is required.' }
  if (!email) return { error: 'Email is required.' }
  if (!password || password.length < 8) {
    return { error: 'Password must be at least 8 characters.' }
  }

  try {
    const existingUser = await prisma.user.findUnique({ where: { email } })
    if (existingUser) {
      return { error: 'An account with this email already exists.' }
    }

    const passwordHash = await bcrypt.hash(password, 12)
    await prisma.user.create({ data: { name, email, passwordHash } })

    await signIn('credentials', { email, password, redirect: false })
  } catch (e) {
    if (e instanceof AuthError) {
      redirect('/login')
    }
    throw e
  }

  redirect('/dashboard')
}
```

### Signup Page (app/signup/page.tsx)

```tsx
'use client'

import { useActionState } from 'react'
import { signUpAction } from './actions'

export default function SignUpPage() {
  const [state, formAction, pending] = useActionState(signUpAction, null)

  return (
    <form action={formAction}>
      {state?.error && <div className="text-destructive">{state.error}</div>}
      <input name="name" type="text" required />
      <input name="email" type="email" required />
      <input name="password" type="password" required />
      <button type="submit" disabled={pending}>
        {pending ? 'Creating account...' : 'Sign up'}
      </button>
    </form>
  )
}
```

## Form Dropdowns

ALWAYS use native `<select>` elements in forms instead of Radix UI Select components.
Radix Select requires JavaScript hydration to function. If hydration fails (which can
happen with auth provider issues), native `<select>` still works as a standard HTML element.

```tsx
<select name="categoryId" required defaultValue="">
  <option value="" disabled>Select a category</option>
  {categories.map((cat) => (
    <option key={cat.id} value={cat.id}>{cat.name}</option>
  ))}
</select>
```

## Data Fetching

### Server Component with Relations

```typescript
import { prisma } from '@/lib/prisma'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'

export default async function DashboardPage() {
  const session = await getServerSession(authOptions)

  if (!session?.user?.id) {
    return null
  }

  const items = await prisma.item.findMany({
    where: { userId: session.user.id },
    include: {
      category: true,
      tags: true,
    },
    orderBy: { createdAt: 'desc' },
  })

  return (
    <div>
      {items.map((item) => (
        <ItemCard key={item.id} item={item} />
      ))}
    </div>
  )
}
```

## API Routes with Prisma

### CRUD Route (app/api/items/route.ts)

```typescript
import { prisma } from '@/lib/prisma'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { NextResponse } from 'next/server'

export async function GET() {
  const session = await getServerSession(authOptions)

  if (!session?.user?.id) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const items = await prisma.item.findMany({
    where: { userId: session.user.id },
    orderBy: { createdAt: 'desc' },
  })

  return NextResponse.json(items)
}

export async function POST(request: Request) {
  const session = await getServerSession(authOptions)

  if (!session?.user?.id) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const body = await request.json()

  const item = await prisma.item.create({
    data: {
      ...body,
      userId: session.user.id,
    },
  })

  return NextResponse.json(item, { status: 201 })
}
```

## Complex Queries

### Marketplace Pattern (Listings with Seller)

```typescript
// Get listings with seller info and average rating
const listings = await prisma.listing.findMany({
  where: {
    status: 'active',
    price: { gte: minPrice, lte: maxPrice },
  },
  include: {
    seller: {
      select: {
        id: true,
        name: true,
        image: true,
      },
    },
    _count: {
      select: { reviews: true },
    },
  },
  orderBy: { createdAt: 'desc' },
  take: 20,
  skip: page * 20,
})

// Aggregate seller rating
const sellerStats = await prisma.review.aggregate({
  where: { sellerId: sellerId },
  _avg: { rating: true },
  _count: true,
})
```

### Multi-Tenant Pattern

```typescript
// All queries scoped to organization
const items = await prisma.item.findMany({
  where: {
    organizationId: session.user.organizationId,
  },
})

// Middleware to enforce tenant isolation
prisma.$use(async (params, next) => {
  if (params.model === 'Item' && params.action === 'findMany') {
    params.args.where = {
      ...params.args.where,
      organizationId: getCurrentOrganizationId(),
    }
  }
  return next(params)
})
```

## Error Boundary

Create a global error boundary in `src/app/error.tsx`:

```tsx
'use client'

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <div className="flex min-h-[400px] flex-col items-center justify-center gap-4">
      <h2 className="text-xl font-semibold">Something went wrong</h2>
      <p className="text-muted-foreground">{error.message}</p>
      <button onClick={reset} className="rounded bg-primary px-4 py-2 text-primary-foreground">
        Try again
      </button>
    </div>
  )
}
```

## Loading States (Suspense)

Create `src/app/loading.tsx` for route-level loading:

```tsx
export default function Loading() {
  return (
    <div className="flex min-h-[400px] items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
    </div>
  )
}
```

Use Suspense for component-level loading:

```tsx
import { Suspense } from 'react'

export default function DashboardPage() {
  return (
    <Suspense fallback={<ItemsSkeleton />}>
      <ItemsList />
    </Suspense>
  )
}
```

## Empty States

Always handle empty data:

```tsx
function ItemsList({ items }: { items: Item[] }) {
  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <p className="text-lg font-medium">No items yet</p>
        <p className="text-muted-foreground">Create your first item to get started.</p>
      </div>
    )
  }

  return items.map((item) => <ItemCard key={item.id} item={item} />)
}
```

## Form Validation (Zod)

Use Zod schemas for server-side form validation:

```typescript
import { z } from 'zod'

const ItemSchema = z.object({
  title: z.string().min(1, 'Title is required').max(100),
  description: z.string().max(1000).optional(),
  email: z.string().email('Invalid email address'),
})

export async function createItem(
  prevState: { error?: string } | null,
  formData: FormData
) {
  const parsed = ItemSchema.safeParse({
    title: formData.get('title'),
    description: formData.get('description'),
    email: formData.get('email'),
  })

  if (!parsed.success) {
    return { error: parsed.error.issues[0].message }
  }

  // Use parsed.data (typed and validated)
}
```

## Transactions

```typescript
// Transfer with transaction
const transfer = await prisma.$transaction(async (tx) => {
  // Deduct from sender
  const sender = await tx.account.update({
    where: { id: senderId },
    data: { balance: { decrement: amount } },
  })

  if (sender.balance < 0) {
    throw new Error('Insufficient funds')
  }

  // Add to receiver
  await tx.account.update({
    where: { id: receiverId },
    data: { balance: { increment: amount } },
  })

  // Record transaction
  return tx.transaction.create({
    data: { senderId, receiverId, amount },
  })
})
```
