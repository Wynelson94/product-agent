# Astro Code Patterns

## Astro Components

Astro components (`.astro`) render to HTML at build time with zero client JS by default.

```astro
---
// src/components/Card.astro
// Frontmatter (server-side, runs at build)
interface Props {
  title: string
  description: string
  href?: string
}

const { title, description, href } = Astro.props
---

<article class="p-6 bg-zinc-900 border border-zinc-800 rounded-lg hover:border-zinc-600 transition-colors">
  {href ? (
    <a href={href} class="block">
      <h3 class="text-lg font-semibold text-zinc-100 mb-2">{title}</h3>
      <p class="text-zinc-400">{description}</p>
    </a>
  ) : (
    <>
      <h3 class="text-lg font-semibold text-zinc-100 mb-2">{title}</h3>
      <p class="text-zinc-400">{description}</p>
    </>
  )}
</article>
```

## Layouts

```astro
---
// src/layouts/BaseLayout.astro
interface Props {
  title: string
  description?: string
}

const { title, description = 'Default description' } = Astro.props
---

<!doctype html>
<html lang="en" class="dark">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="description" content={description} />
    <title>{title}</title>
  </head>
  <body class="bg-zinc-950 text-zinc-100 min-h-screen">
    <header class="border-b border-zinc-800 px-6 py-3">
      <nav class="max-w-4xl mx-auto flex items-center gap-6">
        <a href="/" class="font-bold text-lg">Site</a>
        <a href="/about" class="text-zinc-400 hover:text-zinc-100">About</a>
        <a href="/blog" class="text-zinc-400 hover:text-zinc-100">Blog</a>
      </nav>
    </header>
    <main class="max-w-4xl mx-auto px-6 py-12">
      <slot />
    </main>
    <footer class="border-t border-zinc-800 px-6 py-6 text-center text-zinc-500 text-sm">
      &copy; {new Date().getFullYear()} Site Name
    </footer>
  </body>
</html>
```

## Pages

```astro
---
// src/pages/index.astro
import BaseLayout from '../layouts/BaseLayout.astro'
import Card from '../components/Card.astro'
import Hero from '../components/Hero.astro'
---

<BaseLayout title="Home">
  <Hero />
  <section class="grid grid-cols-1 md:grid-cols-3 gap-6 mt-12">
    <Card title="Feature 1" description="Description here" />
    <Card title="Feature 2" description="Description here" />
    <Card title="Feature 3" description="Description here" />
  </section>
</BaseLayout>
```

## Content Collections (Markdown/MDX)

```typescript
// src/content/config.ts
import { defineCollection, z } from 'astro:content'

const blog = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    description: z.string(),
    pubDate: z.coerce.date(),
    heroImage: z.string().optional(),
    tags: z.array(z.string()).default([]),
  }),
})

export const collections = { blog }
```

```astro
---
// src/pages/blog/index.astro
import BaseLayout from '../../layouts/BaseLayout.astro'
import { getCollection } from 'astro:content'

const posts = (await getCollection('blog')).sort(
  (a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf()
)
---

<BaseLayout title="Blog">
  <h1 class="text-3xl font-bold mb-8">Blog</h1>
  <ul class="space-y-6">
    {posts.map((post) => (
      <li>
        <a href={`/blog/${post.slug}`} class="block group">
          <time class="text-zinc-500 text-sm">{post.data.pubDate.toLocaleDateString()}</time>
          <h2 class="text-xl font-semibold group-hover:text-zinc-300">{post.data.title}</h2>
          <p class="text-zinc-400 mt-1">{post.data.description}</p>
        </a>
      </li>
    ))}
  </ul>
</BaseLayout>
```

```astro
---
// src/pages/blog/[slug].astro
import BlogLayout from '../../layouts/BlogLayout.astro'
import { getCollection } from 'astro:content'

export async function getStaticPaths() {
  const posts = await getCollection('blog')
  return posts.map((post) => ({
    params: { slug: post.slug },
    props: post,
  }))
}

const post = Astro.props
const { Content } = await post.render()
---

<BlogLayout title={post.data.title} description={post.data.description}>
  <article class="prose prose-invert max-w-none">
    <Content />
  </article>
</BlogLayout>
```

## Islands Architecture (Interactive Components)

For components that need client-side interactivity, use `client:*` directives:

```astro
---
// In any .astro file — import a framework component
import ContactForm from '../components/interactive/ContactForm' // React/Svelte/Vue
---

<!-- Only hydrate when visible in viewport (saves JS) -->
<ContactForm client:visible />

<!-- Hydrate immediately on page load -->
<ContactForm client:load />

<!-- Hydrate when browser is idle -->
<ContactForm client:idle />
```

> Islands are the exception, not the default. Most content should be
> Astro components (zero JS). Only use `client:*` when you need interactivity.

## API Endpoints (SSR mode only)

```typescript
// src/pages/api/contact.ts
import type { APIRoute } from 'astro'

export const POST: APIRoute = async ({ request }) => {
  const data = await request.formData()
  const name = data.get('name')
  const email = data.get('email')
  const message = data.get('message')

  if (!name || !email || !message) {
    return new Response(JSON.stringify({ error: 'All fields required' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    })
  }

  // Process form submission
  return new Response(JSON.stringify({ success: true }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}
```

## Dynamic Routes

```astro
---
// src/pages/[slug].astro
export async function getStaticPaths() {
  // Return all possible paths at build time
  return [
    { params: { slug: 'about' }, props: { title: 'About Us' } },
    { params: { slug: 'contact' }, props: { title: 'Contact' } },
  ]
}

const { title } = Astro.props
---

<h1>{title}</h1>
```
