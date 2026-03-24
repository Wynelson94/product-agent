# Astro Build Process

## Steps

1. Scaffold: `npm create astro@latest . -- --template basics --yes --no-git --no-install && npm install`
2. Add Tailwind: `npx astro add tailwind --yes`
3. If SSR needed: `npx astro add vercel --yes` and set `output: 'server'` in astro.config.mjs
4. **Install DESIGN.md dependencies**: Read DESIGN.md and `npm install` every library it references
5. Create BaseLayout.astro in src/layouts/
6. Create pages from DESIGN.md in src/pages/
7. Create components in src/components/
8. If blog/content: Create content collections in src/content/ with config.ts schema
9. If interactive islands needed: Create framework components and use `client:visible`
10. Run `npm run build` to verify static generation
11. Preview: `npm run preview`

## Test Infrastructure

Astro projects use Vitest:

```bash
npm install -D vitest
```

Add to package.json:
```json
{
  "scripts": {
    "test": "vitest run"
  }
}
```

Test component rendering with Astro's container API or test utilities/logic separately.
