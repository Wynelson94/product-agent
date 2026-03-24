# Astro Test Patterns

## Test Framework

Astro uses Vitest for testing. Since most Astro components render to static HTML,
tests focus on utility functions, content validation, and build output.

## Utility Tests

```typescript
// src/lib/utils.test.ts
import { describe, it, expect } from 'vitest'
import { formatDate, slugify } from './utils'

describe('formatDate', () => {
  it('formats dates correctly', () => {
    const date = new Date('2024-01-15')
    expect(formatDate(date)).toBe('January 15, 2024')
  })
})

describe('slugify', () => {
  it('converts to lowercase slug', () => {
    expect(slugify('Hello World')).toBe('hello-world')
  })

  it('removes special characters', () => {
    expect(slugify("What's New?")).toBe('whats-new')
  })
})
```

## Content Collection Tests

```typescript
// src/content/blog.test.ts
import { describe, it, expect } from 'vitest'
import fs from 'fs'
import path from 'path'

describe('Blog content', () => {
  const blogDir = path.join(process.cwd(), 'src/content/blog')

  it('has at least one post', () => {
    const files = fs.readdirSync(blogDir)
    const mdFiles = files.filter(f => f.endsWith('.md') || f.endsWith('.mdx'))
    expect(mdFiles.length).toBeGreaterThan(0)
  })

  it('all posts have required frontmatter', () => {
    const files = fs.readdirSync(blogDir).filter(f => f.endsWith('.md'))
    for (const file of files) {
      const content = fs.readFileSync(path.join(blogDir, file), 'utf-8')
      expect(content).toContain('title:')
      expect(content).toContain('description:')
      expect(content).toContain('pubDate:')
    }
  })
})
```

## Build Output Tests

```typescript
// tests/build.test.ts
import { describe, it, expect } from 'vitest'
import fs from 'fs'

describe('Build output', () => {
  it('generates index.html', () => {
    expect(fs.existsSync('dist/index.html')).toBe(true)
  })

  it('index.html contains expected content', () => {
    const html = fs.readFileSync('dist/index.html', 'utf-8')
    expect(html).toContain('<!doctype html>')
    expect(html).toContain('<title>')
  })
})
```

## Running Tests

```bash
# Run all tests
npm run test

# Watch mode
npx vitest

# Run specific file
npx vitest run src/lib/utils.test.ts
```
