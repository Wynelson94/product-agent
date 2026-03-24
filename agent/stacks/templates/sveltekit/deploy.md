# SvelteKit Deployment (Vercel)

## Pre-Deployment Checklist

1. Build passes: `npm run build`
2. Tests pass: `npm run test`
3. `svelte.config.js` uses `@sveltejs/adapter-vercel`
4. Environment variables documented in `.env.example`

## Vercel Adapter

Ensure svelte.config.js uses the Vercel adapter:

```javascript
import adapter from '@sveltejs/adapter-vercel';

const config = {
  kit: {
    adapter: adapter({
      runtime: 'nodejs22.x',
    }),
  },
};
```

## Deployment Steps

### 1. Verify Build

```bash
npm run build
```

### 2. Deploy to Preview

```bash
npx vercel
```

### 3. Configure Environment Variables

```bash
vercel env add DATABASE_URL
vercel env add AUTH_SECRET
```

### 4. Deploy to Production

```bash
npx vercel --prod
```

### 5. Verify

- Homepage loads
- Auth flow works
- Form actions submit correctly
- API routes respond

## Edge Functions

SvelteKit routes can run at the edge:

```typescript
// src/routes/api/fast/+server.ts
export const config = {
  runtime: 'edge',
}

export const GET = async () => {
  return new Response('Hello from the edge!')
}
```

## GitHub Actions CI/CD (Optional)

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: npm
          cache-dependency-path: src/package-lock.json
      - run: cd src && npm ci
      - run: cd src && npm run build
      - run: cd src && npm test
```

## Troubleshooting

### Build fails with adapter error
- Verify `@sveltejs/adapter-vercel` is installed as devDependency
- Check svelte.config.js imports it correctly

### Environment variables not available
- Server-side: use `$env/static/private` or `$env/dynamic/private`
- Client-side: prefix with `PUBLIC_` and use `$env/static/public`
- Never import from `$env/static/private` in client code

### Form actions not working
- Ensure `use:enhance` is on the form for progressive enhancement
- Check the action name matches `?/actionName`
