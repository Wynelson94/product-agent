# SvelteKit Test Patterns

## Test Framework

SvelteKit uses Vitest with `@testing-library/svelte`.

## Component Tests

```typescript
// src/lib/components/ui/Button.test.ts
import { render, screen, fireEvent } from '@testing-library/svelte'
import { describe, it, expect, vi } from 'vitest'
import Button from './Button.svelte'

describe('Button', () => {
  it('renders with text', () => {
    render(Button, { props: { children: 'Click me' } })
    expect(screen.getByText('Click me')).toBeTruthy()
  })

  it('calls onclick when clicked', async () => {
    const onclick = vi.fn()
    render(Button, { props: { onclick } })
    await fireEvent.click(screen.getByRole('button'))
    expect(onclick).toHaveBeenCalled()
  })

  it('is disabled when disabled prop is true', () => {
    render(Button, { props: { disabled: true, children: 'Disabled' } })
    expect(screen.getByRole('button')).toBeDisabled()
  })
})
```

## API Route Tests

```typescript
// src/routes/api/items/server.test.ts
import { describe, it, expect, vi } from 'vitest'

describe('GET /api/items', () => {
  it('returns 401 when unauthenticated', async () => {
    const response = await fetch('/api/items')
    expect(response.status).toBe(401)
  })
})
```

## Form Action Tests

```typescript
// src/routes/items/page.test.ts
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/svelte'
import Page from './+page.svelte'

describe('Items page', () => {
  it('renders item list', () => {
    render(Page, {
      props: {
        data: {
          items: [
            { id: '1', name: 'Item 1' },
            { id: '2', name: 'Item 2' },
          ],
        },
      },
    })
    expect(screen.getByText('Item 1')).toBeTruthy()
    expect(screen.getByText('Item 2')).toBeTruthy()
  })

  it('shows empty state when no items', () => {
    render(Page, { props: { data: { items: [] } } })
    expect(screen.getByText(/no items/i)).toBeTruthy()
  })
})
```

## Running Tests

```bash
# Run all tests
npm run test

# Watch mode
npm run test:watch

# Run specific file
npx vitest run src/lib/components/ui/Button.test.ts
```
