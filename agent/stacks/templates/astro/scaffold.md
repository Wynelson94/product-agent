# Astro Scaffolding

## Initial Setup

```bash
# Create Astro app (--yes skips interactive prompts)
npm create astro@latest src -- --template basics --yes --no-git --no-install

cd src

# Install dependencies
npm install

# Add Tailwind CSS integration
npx astro add tailwind --yes

# Add Vercel adapter for SSR (if needed)
npx astro add vercel --yes

# Install UI utilities
npm install lucide-astro
```

## Directory Structure

```
src/
├── src/
│   ├── pages/
│   │   ├── index.astro          # Homepage (/)
│   │   ├── about.astro          # About page (/about)
│   │   ├── blog/
│   │   │   ├── index.astro      # Blog listing (/blog)
│   │   │   └── [slug].astro     # Blog post (/blog/:slug)
│   │   ├── 404.astro            # 404 page
│   │   └── api/
│   │       └── contact.ts       # API endpoint
│   ├── layouts/
│   │   ├── BaseLayout.astro     # Root layout with <html>, <head>
│   │   └── BlogLayout.astro     # Blog post layout with metadata
│   ├── components/
│   │   ├── Header.astro
│   │   ├── Footer.astro
│   │   ├── Hero.astro
│   │   ├── Card.astro
│   │   └── interactive/         # Client-side islands (React/Svelte/Vue)
│   ├── content/
│   │   ├── config.ts            # Content collection schemas
│   │   └── blog/
│   │       ├── first-post.md
│   │       └── second-post.md
│   └── styles/
│       └── global.css
├── public/
│   ├── favicon.svg
│   └── images/
├── astro.config.mjs
├── tailwind.config.mjs
├── tsconfig.json
└── package.json
```

## Astro Config

```javascript
// astro.config.mjs
import { defineConfig } from 'astro/config'
import tailwind from '@astrojs/tailwind'
import vercel from '@astrojs/vercel'

export default defineConfig({
  integrations: [tailwind()],
  // Use 'static' for fully static sites, 'server' for SSR
  output: 'static',
  // Add adapter for SSR or hybrid rendering
  // adapter: vercel(),
})
```

> Set `output: 'server'` and uncomment `adapter: vercel()` if any page needs
> server-side rendering. For fully static sites, keep `output: 'static'`.

## Environment Template

Create `.env.example`:

```env
# Only needed if using SSR features
# PUBLIC_ prefix makes vars available in client-side code
PUBLIC_SITE_URL=https://example.com
```
