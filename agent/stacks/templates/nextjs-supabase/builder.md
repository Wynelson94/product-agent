# Next.js + Supabase Build Process

## Steps

1. Scaffold: `npx create-next-app@latest . --typescript --tailwind --eslint --app --src-dir --import-alias "@/*"`
2. Install: `npm install @supabase/supabase-js @supabase/ssr`
3. Add shadcn: `npx shadcn@latest init -y && npx shadcn@latest add button input card form label`
4. **Setup Tests**: `npm install -D vitest @testing-library/react @testing-library/jest-dom happy-dom @vitejs/plugin-react`
5. Create vitest.config.ts and src/test/setup.ts (see Test Infrastructure below)
6. Create Supabase clients (lib/supabase/client.ts, server.ts)
7. Create middleware.ts for auth
8. Create .env.local.example
9. Implement pages from DESIGN.md
10. Implement components
11. Run `npm run build`

## Test Infrastructure

Create vitest.config.ts:
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

Create src/test/setup.ts:
```typescript
import '@testing-library/jest-dom'
```

Add to package.json scripts:
```json
{
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest",
    "test:coverage": "vitest run --coverage"
  }
}
```
