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

## Auth.js Configuration

### lib/auth.ts

```typescript
import { NextAuthOptions } from 'next-auth'
import { PrismaAdapter } from '@auth/prisma-adapter'
import CredentialsProvider from 'next-auth/providers/credentials'
import bcrypt from 'bcryptjs'
import { prisma } from './prisma'

export const authOptions: NextAuthOptions = {
  adapter: PrismaAdapter(prisma),
  providers: [
    CredentialsProvider({
      name: 'credentials',
      credentials: {
        email: { label: 'Email', type: 'email' },
        password: { label: 'Password', type: 'password' },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) {
          return null
        }

        const user = await prisma.user.findUnique({
          where: { email: credentials.email },
        })

        if (!user || !user.password) {
          return null
        }

        const isValid = await bcrypt.compare(credentials.password, user.password)

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
}
```

### API Route (app/api/auth/[...nextauth]/route.ts)

```typescript
import NextAuth from 'next-auth'
import { authOptions } from '@/lib/auth'

const handler = NextAuth(authOptions)

export { handler as GET, handler as POST }
```

## Middleware

### middleware.ts

```typescript
import { withAuth } from 'next-auth/middleware'

export default withAuth({
  pages: {
    signIn: '/login',
  },
})

export const config = {
  matcher: ['/dashboard/:path*', '/settings/:path*'],
}
```

## Server Actions

### Signup Action

```typescript
'use server'

import { prisma } from '@/lib/prisma'
import bcrypt from 'bcryptjs'
import { redirect } from 'next/navigation'

export async function signup(formData: FormData) {
  const email = formData.get('email') as string
  const password = formData.get('password') as string
  const name = formData.get('name') as string

  const existingUser = await prisma.user.findUnique({
    where: { email },
  })

  if (existingUser) {
    return { error: 'Email already in use' }
  }

  const hashedPassword = await bcrypt.hash(password, 12)

  await prisma.user.create({
    data: {
      email,
      password: hashedPassword,
      name,
    },
  })

  redirect('/login?message=Account created successfully')
}
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
