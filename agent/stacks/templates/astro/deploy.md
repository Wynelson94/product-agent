# Astro Deployment (Vercel)

## Pre-Deployment Checklist

1. Build passes: `npm run build`
2. Preview works: `npm run preview`
3. All pages render correctly
4. Content collections have valid frontmatter
5. If SSR: Vercel adapter installed and configured

## Static Deployment (Default)

For fully static sites (`output: 'static'`), Vercel auto-detects Astro:

```bash
# Deploy preview
npx vercel

# Deploy production
npx vercel --prod
```

No adapter needed — Vercel builds and serves static files automatically.

## SSR Deployment

For server-rendered pages (`output: 'server'` or `output: 'hybrid'`):

1. Install adapter: `npx astro add vercel --yes`
2. Update astro.config.mjs:

```javascript
import vercel from '@astrojs/vercel'

export default defineConfig({
  output: 'server',  // or 'hybrid' for mixed static + SSR
  adapter: vercel(),
})
```

3. Deploy:

```bash
npx vercel --prod
```

## Hybrid Rendering

Use `hybrid` output to make most pages static while allowing specific pages to be server-rendered:

```javascript
// astro.config.mjs
export default defineConfig({
  output: 'hybrid',
  adapter: vercel(),
})
```

Then opt pages into SSR:

```astro
---
// This page will be server-rendered
export const prerender = false
---
```

## Environment Variables

```bash
# Only needed for SSR features
vercel env add PUBLIC_SITE_URL
```

## Verify Deployment

- All pages load (check each route)
- Images and assets load from /public
- Blog posts render markdown correctly
- Contact form submits (if API routes exist)
- No console errors

## Troubleshooting

### Build fails with "getStaticPaths() required"
- Dynamic routes (`[slug].astro`) need `getStaticPaths()` in static mode
- Switch to SSR if paths are determined at runtime

### 404 on routes after deployment
- Verify all pages are in `src/pages/`
- Check dynamic route params match content

### Images not loading
- Static images go in `public/` (served as-is)
- Optimized images use Astro's `<Image />` component from `astro:assets`
