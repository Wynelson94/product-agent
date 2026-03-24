# SvelteKit Scaffolding

## Initial Setup

```bash
# Create SvelteKit app
npx sv create src --template minimal --types ts --no-add-ons

cd src

# Install Tailwind CSS
npx sv add tailwindcss

# Install additional dependencies
npm install zod lucide-svelte
npm install -D @sveltejs/adapter-vercel
```

## Directory Structure

```
src/
├── src/
│   ├── routes/
│   │   ├── +layout.svelte       # Root layout
│   │   ├── +layout.server.ts    # Root layout data loader
│   │   ├── +page.svelte         # Homepage
│   │   ├── +error.svelte        # Error page
│   │   ├── (auth)/
│   │   │   ├── login/+page.svelte
│   │   │   └── signup/+page.svelte
│   │   ├── (app)/
│   │   │   ├── dashboard/+page.svelte
│   │   │   ├── dashboard/+page.server.ts
│   │   │   └── settings/+page.svelte
│   │   └── api/
│   │       └── [entity]/+server.ts
│   ├── lib/
│   │   ├── components/
│   │   │   └── ui/
│   │   ├── server/
│   │   │   ├── db.ts
│   │   │   └── auth.ts
│   │   └── utils.ts
│   ├── app.html
│   ├── app.css
│   └── hooks.server.ts          # Server hooks (auth middleware)
├── static/
├── svelte.config.js
├── vite.config.ts
├── tailwind.config.ts
└── package.json
```

## Svelte Config (Vercel adapter)

```javascript
// svelte.config.js
import adapter from '@sveltejs/adapter-vercel';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter(),
  },
};

export default config;
```

## Environment Template

Create `.env.example`:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/app_dev
AUTH_SECRET=your-secret-here
```

> SvelteKit uses `$env/static/private` and `$env/dynamic/private` for env vars.
> Prefix with `PUBLIC_` for client-accessible variables.
