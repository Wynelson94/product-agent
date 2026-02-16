# Next.js + Supabase Build Process

## Steps

1. Scaffold: `npx create-next-app@latest . --typescript --tailwind --eslint --app --src-dir --import-alias "@/*"`
2. Install: `npm install @supabase/supabase-js @supabase/ssr`
3. Add shadcn: `npx shadcn@latest init -y && npx shadcn@latest add button input card form label`
4. **Install DESIGN.md dependencies**: Read DESIGN.md and `npm install` every library it references that isn't already installed (e.g., recharts, @react-pdf/renderer, @tanstack/react-table). Do NOT skip this step — missing dependencies cause runtime crashes.
5. **Setup Tests**: `npm install -D vitest @testing-library/react @testing-library/jest-dom happy-dom @vitejs/plugin-react`
6. Create vitest.config.ts and src/test/setup.ts (see Test Infrastructure below)
7. Create Supabase clients (lib/supabase/client.ts, server.ts)
8. Create middleware.ts for auth
9. Create .env.local.example
10. Implement pages from DESIGN.md
11. Implement components
12. Run `npm run build`

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
