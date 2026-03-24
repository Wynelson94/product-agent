# SvelteKit Build Process

## Steps

1. Scaffold: `npx sv create . --template minimal --types ts --no-add-ons`
2. Add Tailwind: `npx sv add tailwindcss`
3. Install Vercel adapter: `npm install -D @sveltejs/adapter-vercel`
4. Update `svelte.config.js` to use `adapter-vercel`
5. **Install DESIGN.md dependencies**: Read DESIGN.md and `npm install` every library it references
6. **Setup Tests**: `npm install -D vitest @testing-library/svelte jsdom`
7. Create vitest.config.ts
8. Set up database connection in `$lib/server/db.ts`
9. Create `hooks.server.ts` for authentication middleware
10. Create layouts and pages from DESIGN.md
11. Implement form actions for mutations
12. Run `npm run build` to verify

## Test Infrastructure

Create vitest.config.ts:
```typescript
import { defineConfig } from 'vitest/config'
import { sveltekit } from '@sveltejs/kit/vite'

export default defineConfig({
  plugins: [sveltekit()],
  test: {
    include: ['src/**/*.test.{ts,js}'],
    environment: 'jsdom',
  },
})
```

Add to package.json scripts:
```json
{
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest"
  }
}
```
