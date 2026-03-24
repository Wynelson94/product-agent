# SvelteKit Code Patterns

## Data Loading (Server-Side)

SvelteKit uses `+page.server.ts` files for server-side data loading.

```typescript
// src/routes/dashboard/+page.server.ts
import { error } from '@sveltejs/kit'
import type { PageServerLoad } from './$types'
import { db } from '$lib/server/db'

export const load: PageServerLoad = async ({ locals }) => {
  if (!locals.user) {
    error(401, 'Unauthorized')
  }

  const items = await db.query('SELECT * FROM items WHERE user_id = $1', [locals.user.id])

  return {
    items: items.rows,
  }
}
```

```svelte
<!-- src/routes/dashboard/+page.svelte -->
<script lang="ts">
  import type { PageData } from './$types'

  let { data }: { data: PageData } = $props()
</script>

<div class="max-w-4xl mx-auto p-6">
  <h1 class="text-2xl font-bold mb-4">Dashboard</h1>
  {#each data.items as item}
    <div class="p-3 border-b border-zinc-700">{item.name}</div>
  {/each}
</div>
```

## Form Actions

SvelteKit form actions handle mutations with progressive enhancement.

```typescript
// src/routes/items/+page.server.ts
import { fail } from '@sveltejs/kit'
import type { Actions, PageServerLoad } from './$types'
import { db } from '$lib/server/db'

export const load: PageServerLoad = async ({ locals }) => {
  const items = await db.query('SELECT * FROM items WHERE user_id = $1', [locals.user.id])
  return { items: items.rows }
}

export const actions: Actions = {
  create: async ({ request, locals }) => {
    const formData = await request.formData()
    const name = formData.get('name') as string

    if (!name || name.length < 1) {
      return fail(400, { name, missing: true })
    }

    await db.query('INSERT INTO items (name, user_id) VALUES ($1, $2)', [name, locals.user.id])
    return { success: true }
  },

  delete: async ({ request, locals }) => {
    const formData = await request.formData()
    const id = formData.get('id') as string
    await db.query('DELETE FROM items WHERE id = $1 AND user_id = $2', [id, locals.user.id])
    return { success: true }
  },
}
```

```svelte
<!-- Form with progressive enhancement -->
<script lang="ts">
  import { enhance } from '$app/forms'
  import type { ActionData, PageData } from './$types'

  let { data, form }: { data: PageData; form: ActionData } = $props()
</script>

<form method="POST" action="?/create" use:enhance>
  <input name="name" class="px-3 py-2 bg-zinc-800 border border-zinc-700 rounded text-white"
         placeholder="New item" />
  {#if form?.missing}<p class="text-red-400 text-sm">Name is required</p>{/if}
  <button type="submit" class="px-4 py-2 bg-zinc-700 text-white rounded">Add</button>
</form>

{#each data.items as item}
  <div class="flex items-center justify-between p-3 border-b border-zinc-700">
    <span>{item.name}</span>
    <form method="POST" action="?/delete" use:enhance>
      <input type="hidden" name="id" value={item.id} />
      <button type="submit" class="text-red-400 text-sm">Delete</button>
    </form>
  </div>
{/each}
```

## Server Hooks (Authentication)

```typescript
// src/hooks.server.ts
import type { Handle } from '@sveltejs/kit'

export const handle: Handle = async ({ event, resolve }) => {
  const sessionId = event.cookies.get('session_id')

  if (sessionId) {
    // Look up user from session
    const user = await getUserFromSession(sessionId)
    event.locals.user = user
  }

  // Protect routes
  if (event.url.pathname.startsWith('/dashboard') && !event.locals.user) {
    return new Response(null, {
      status: 302,
      headers: { location: '/login' },
    })
  }

  return resolve(event)
}
```

## API Routes

```typescript
// src/routes/api/items/+server.ts
import { json, error } from '@sveltejs/kit'
import type { RequestHandler } from './$types'
import { db } from '$lib/server/db'

export const GET: RequestHandler = async ({ locals }) => {
  if (!locals.user) error(401, 'Unauthorized')
  const items = await db.query('SELECT * FROM items WHERE user_id = $1', [locals.user.id])
  return json(items.rows)
}

export const POST: RequestHandler = async ({ request, locals }) => {
  if (!locals.user) error(401, 'Unauthorized')
  const { name } = await request.json()
  const result = await db.query(
    'INSERT INTO items (name, user_id) VALUES ($1, $2) RETURNING *',
    [name, locals.user.id]
  )
  return json(result.rows[0], { status: 201 })
}
```

## Layout Pattern

```svelte
<!-- src/routes/+layout.svelte -->
<script lang="ts">
  import '../app.css'
  import type { LayoutData } from './$types'

  let { data, children }: { data: LayoutData; children: any } = $props()
</script>

<div class="min-h-screen bg-zinc-950 text-zinc-100">
  <nav class="border-b border-zinc-800 px-6 py-3">
    <a href="/" class="font-bold">App</a>
    {#if data.user}
      <a href="/dashboard" class="ml-4">Dashboard</a>
      <a href="/settings" class="ml-4">Settings</a>
    {/if}
  </nav>
  <main class="container mx-auto px-4 py-8">
    {@render children()}
  </main>
</div>
```

## Svelte 5 Runes

SvelteKit uses Svelte 5 with runes (`$state`, `$derived`, `$effect`, `$props`):

```svelte
<script lang="ts">
  // Props (replaces export let)
  let { count = 0 }: { count?: number } = $props()

  // Reactive state (replaces let with $:)
  let doubled = $derived(count * 2)

  // Local state
  let name = $state('')

  // Side effects (replaces $:)
  $effect(() => {
    console.log('Count changed:', count)
  })
</script>
```
