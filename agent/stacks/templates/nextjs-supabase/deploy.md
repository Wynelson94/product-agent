# Next.js + Supabase Deployment (Vercel)

## Pre-Deployment Checklist

1. Build passes locally: `npm run build`
2. All environment variables documented in `.env.local.example`
3. Supabase project created and configured
4. RLS policies applied to all tables

## Deployment Steps

### 1. Verify Build

```bash
npm run build
```

Must complete without errors.

### 2. Deploy to Vercel Preview

```bash
npx vercel
```

Follow prompts to link project. This creates a preview deployment.

### 3. Configure Environment Variables

In Vercel Dashboard or CLI:

```bash
vercel env add NEXT_PUBLIC_SUPABASE_URL
vercel env add NEXT_PUBLIC_SUPABASE_ANON_KEY
```

### 4. Deploy to Production

```bash
npx vercel --prod
```

### 5. Verify Deployment

Check these endpoints:
- Homepage loads: `curl -I https://[url]`
- Auth pages accessible: `/login`, `/signup`
- API responds: `/api/health` or any API route

## Supabase Configuration

### URL Configuration in Supabase Dashboard

1. Go to Authentication > URL Configuration
2. Add your Vercel URL to:
   - Site URL: `https://your-app.vercel.app`
   - Redirect URLs: `https://your-app.vercel.app/**`

### Required for Email Auth

If using email confirmation, ensure redirect URLs are configured.

## Observability (Recommended)

Add Vercel Analytics and Speed Insights for production monitoring:

```bash
npm install @vercel/analytics @vercel/speed-insights
```

```typescript
// app/layout.tsx — add inside <body>
import { Analytics } from '@vercel/analytics/react'
import { SpeedInsights } from '@vercel/speed-insights/next'

// Inside the layout JSX:
<body>
  {children}
  <Analytics />
  <SpeedInsights />
</body>
```

These are automatically enabled on Vercel deployments with zero config.

## GitHub Actions CI/CD (Optional)

Generate `.github/workflows/ci.yml` for automated testing on pull requests:

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

> Vercel auto-deploys on push to main (production) and on PRs (preview).
> This workflow adds CI test gating — PRs must pass tests before merge.

## Troubleshooting

### "Failed to fetch" errors
- Check CORS settings in Supabase
- Verify environment variables are set in Vercel

### Auth redirect issues
- Ensure Site URL is set correctly in Supabase
- Check redirect URLs include your domain

### RLS blocking requests
- Verify policies are correctly defined
- Check user is authenticated before protected operations
