# Next.js + Prisma Build Process

## Steps

1. Scaffold: `npx create-next-app@latest . --yes --typescript --tailwind --eslint --app --src-dir --import-alias "@/*" --turbopack --use-npm`
2. Install: `npm install prisma @prisma/client next-auth@latest @auth/prisma-adapter`
3. **Validate peer dependencies**: Run `npm ls --all 2>&1 | grep "peer dep"` — if any conflicts, fix versions before continuing
4. Run: `npx prisma init`
5. **Setup Tests**: `npm install -D vitest @testing-library/react @testing-library/jest-dom happy-dom @vitejs/plugin-react`
6. Create vitest.config.ts and src/test/setup.ts (see Test Infrastructure below)
7. Create Prisma schema from DESIGN.md
8. Set up Auth.js configuration using the `useActionState` + server action pattern (see Code Patterns Reference)
9. Implement pages and components — use native `<select>` for form dropdowns, NOT Radix Select
10. Run `npm run build`

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
