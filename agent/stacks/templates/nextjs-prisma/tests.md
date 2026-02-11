# Next.js + Prisma Test Patterns

## Setup

```bash
npm install -D vitest @testing-library/react @testing-library/jest-dom happy-dom @vitejs/plugin-react
```

## vitest.config.ts

```typescript
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'happy-dom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    globals: true,
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
```

## Test Setup (src/test/setup.ts)

```typescript
import '@testing-library/jest-dom'
import { vi } from 'vitest'

// Mock Prisma client
vi.mock('@/lib/prisma', () => ({
  default: {
    user: {
      findUnique: vi.fn(),
      findMany: vi.fn(),
      create: vi.fn(),
      update: vi.fn(),
      delete: vi.fn(),
    },
    item: {
      findUnique: vi.fn(),
      findMany: vi.fn(),
      create: vi.fn(),
      update: vi.fn(),
      delete: vi.fn(),
    },
    $transaction: vi.fn((fn) => fn({
      user: { findUnique: vi.fn(), create: vi.fn() },
      item: { findUnique: vi.fn(), create: vi.fn() },
    })),
    $disconnect: vi.fn(),
  },
}))

// Mock NextAuth
vi.mock('next-auth', () => ({
  getServerSession: vi.fn(() => Promise.resolve({
    user: { id: '1', email: 'test@test.com', name: 'Test User' }
  })),
}))

// Mock next/navigation
vi.mock('next/navigation', () => ({
  redirect: vi.fn(),
  useRouter: vi.fn(() => ({
    push: vi.fn(),
    replace: vi.fn(),
    refresh: vi.fn(),
  })),
  usePathname: vi.fn(() => '/'),
}))
```

## Unit Test Pattern

```typescript
// src/lib/__tests__/utils.test.ts
import { describe, it, expect } from 'vitest'
import { cn, formatDate, validateEmail } from '../utils'

describe('utils', () => {
  describe('cn', () => {
    it('merges class names', () => {
      expect(cn('foo', 'bar')).toBe('foo bar')
    })
  })

  describe('formatDate', () => {
    it('formats date correctly', () => {
      const date = new Date('2024-01-15')
      expect(formatDate(date)).toMatch(/Jan.*15.*2024/)
    })
  })

  describe('validateEmail', () => {
    it('returns true for valid email', () => {
      expect(validateEmail('test@example.com')).toBe(true)
    })

    it('returns false for invalid email', () => {
      expect(validateEmail('invalid')).toBe(false)
    })
  })
})
```

## Service/Data Layer Test Pattern

```typescript
// src/services/__tests__/item.service.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import prisma from '@/lib/prisma'
import { createItem, getItems, updateItem, deleteItem } from '../item.service'

describe('ItemService', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('createItem', () => {
    it('creates item with correct data', async () => {
      const mockItem = { id: '1', title: 'Test', userId: 'user1', createdAt: new Date() }
      vi.mocked(prisma.item.create).mockResolvedValue(mockItem)

      const result = await createItem({ title: 'Test', userId: 'user1' })

      expect(prisma.item.create).toHaveBeenCalledWith({
        data: { title: 'Test', userId: 'user1' }
      })
      expect(result).toEqual(mockItem)
    })
  })

  describe('getItems', () => {
    it('returns items for user', async () => {
      const mockItems = [{ id: '1', title: 'Test', userId: 'user1' }]
      vi.mocked(prisma.item.findMany).mockResolvedValue(mockItems)

      const result = await getItems('user1')

      expect(prisma.item.findMany).toHaveBeenCalledWith({
        where: { userId: 'user1' },
        orderBy: { createdAt: 'desc' }
      })
      expect(result).toEqual(mockItems)
    })
  })

  describe('deleteItem', () => {
    it('deletes item by id', async () => {
      vi.mocked(prisma.item.delete).mockResolvedValue({ id: '1' } as any)

      await deleteItem('1')

      expect(prisma.item.delete).toHaveBeenCalledWith({
        where: { id: '1' }
      })
    })
  })
})
```

## Component Test Pattern

```typescript
// src/components/__tests__/ItemList.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ItemList } from '@/components/ItemList'

describe('ItemList', () => {
  it('renders items', () => {
    const items = [
      { id: '1', title: 'Item 1' },
      { id: '2', title: 'Item 2' },
    ]

    render(<ItemList items={items} />)

    expect(screen.getByText('Item 1')).toBeInTheDocument()
    expect(screen.getByText('Item 2')).toBeInTheDocument()
  })

  it('shows empty state when no items', () => {
    render(<ItemList items={[]} />)
    expect(screen.getByText(/no items/i)).toBeInTheDocument()
  })
})
```

## API Route Test Pattern

```typescript
// src/app/api/items/__tests__/route.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { GET, POST, DELETE } from '../route'
import { NextRequest } from 'next/server'
import prisma from '@/lib/prisma'

describe('/api/items', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('GET', () => {
    it('returns items', async () => {
      vi.mocked(prisma.item.findMany).mockResolvedValue([
        { id: '1', title: 'Test Item', userId: '1', createdAt: new Date(), updatedAt: new Date() }
      ])

      const response = await GET()
      const data = await response.json()

      expect(response.status).toBe(200)
      expect(data).toHaveLength(1)
      expect(data[0].title).toBe('Test Item')
    })
  })

  describe('POST', () => {
    it('creates item', async () => {
      vi.mocked(prisma.item.create).mockResolvedValue({
        id: '1', title: 'New Item', userId: '1', createdAt: new Date(), updatedAt: new Date()
      })

      const request = new NextRequest('http://localhost/api/items', {
        method: 'POST',
        body: JSON.stringify({ title: 'New Item' })
      })

      const response = await POST(request)
      expect(response.status).toBe(201)
    })

    it('returns 400 for missing title', async () => {
      const request = new NextRequest('http://localhost/api/items', {
        method: 'POST',
        body: JSON.stringify({})
      })

      const response = await POST(request)
      expect(response.status).toBe(400)
    })
  })
})
```

## Run Tests

```bash
# Run all tests
npm test

# Run with coverage
npm run test:coverage

# Watch mode
npm run test:watch

# Run specific file
npm test -- src/services/__tests__/item.service.test.ts
```
