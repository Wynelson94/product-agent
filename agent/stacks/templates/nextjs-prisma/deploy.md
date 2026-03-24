# Next.js + Prisma Deployment (Vercel)

## Pre-Deployment Checklist

1. Build passes locally: `npm run build`
2. Database migrations are up to date
3. Environment variables documented
4. Prisma client generated in build

## Database Setup

### Option 1: Vercel Postgres

```bash
# In Vercel Dashboard, add Vercel Postgres
# Connection string is automatically added as POSTGRES_PRISMA_URL
```

Update `schema.prisma`:

```prisma
datasource db {
  provider  = "postgresql"
  url       = env("POSTGRES_PRISMA_URL")
  directUrl = env("POSTGRES_URL_NON_POOLING")
}
```

### Option 2: Neon (Recommended for Vercel)

```bash
# If NEON_API_KEY is available, provision a database:
# neonctl projects create --name <project-name>
# Then set the connection string on Vercel
```

### Option 3: External PostgreSQL (Supabase, Railway)

Set `DATABASE_URL` in Vercel environment variables.

### CRITICAL: No Placeholder URLs

NEVER set `DATABASE_URL` to a placeholder value like `postgresql://placeholder:placeholder@placeholder.neon.tech/neondb`.
If a real database cannot be provisioned, create `DEPLOY_BLOCKED.md` explaining that manual database setup is required.
A placeholder URL will cause ALL runtime database queries to fail silently.

## Build Configuration

### package.json scripts

```json
{
  "scripts": {
    "postinstall": "prisma generate",
    "build": "prisma generate && next build"
  }
}
```

## Deployment Steps

### 1. Push Database Schema

```bash
# For development/preview
npx prisma db push

# For production (with migrations)
npx prisma migrate deploy
```

### 2. Deploy to Vercel Preview

```bash
npx vercel
```

### 3. Configure Environment Variables

```bash
vercel env add DATABASE_URL
vercel env add NEXTAUTH_SECRET
vercel env add NEXTAUTH_URL
```

Note: `NEXTAUTH_URL` should be your production URL for production deployments.

### 4. Deploy to Production

```bash
npx vercel --prod
```

### 5. Run Production Migrations

After first deployment:

```bash
npx prisma migrate deploy
```

Or use a build hook in `package.json`:

```json
{
  "scripts": {
    "vercel-build": "prisma generate && prisma migrate deploy && next build"
  }
}
```

## Verification

Check these:
- Homepage loads
- Auth flow works (signup, login, logout)
- Database operations succeed
- API routes respond correctly

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
      - run: cd src && npx prisma generate
      - run: cd src && npm run build
      - run: cd src && npm test
```

## Troubleshooting

### "PrismaClient is not initialized"
- Ensure `prisma generate` runs in build
- Check `postinstall` script exists

### Database connection errors
- Verify `DATABASE_URL` is set
- Check connection string format
- Ensure database allows connections from Vercel IPs

### Migration errors
- Run `prisma migrate deploy` manually
- Check migration files are committed

### Auth issues
- Set `NEXTAUTH_URL` to production URL
- Generate new `NEXTAUTH_SECRET` for production
