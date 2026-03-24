# AI-Powered Application Patterns

## Architecture Overview

AI-powered apps follow a specific pattern: user input → LLM processing → structured output → UI rendering.
The key is streaming responses for real-time UX and proper error handling for API failures.

## AI SDK Setup (Vercel AI SDK v6)

### Installation

```bash
npm install ai @ai-sdk/react
```

The AI SDK routes through Vercel AI Gateway automatically when using `"provider/model"` strings.
No provider-specific packages needed unless you need provider-specific features.

### Server-Side: API Route

```typescript
// app/api/chat/route.ts
import { streamText, convertToModelMessages, stepCountIs } from 'ai'
import type { UIMessage } from 'ai'

export async function POST(req: Request) {
  const { messages }: { messages: UIMessage[] } = await req.json()
  const modelMessages = await convertToModelMessages(messages)

  const result = streamText({
    model: 'anthropic/claude-sonnet-4.6',  // Routes through AI Gateway
    messages: modelMessages,
    stopWhen: stepCountIs(5),
  })

  return result.toUIMessageStreamResponse()
}
```

### Client-Side: Chat Hook

```typescript
'use client'
import { useChat } from '@ai-sdk/react'

export function ChatInterface() {
  const { messages, sendMessage, status } = useChat()
  const isLoading = status === 'streaming' || status === 'submitted'

  return (
    <div>
      {messages.map((m) => (
        <div key={m.id}>{/* Render with AI Elements */}</div>
      ))}
      <form onSubmit={(e) => {
        e.preventDefault()
        const input = new FormData(e.currentTarget).get('message') as string
        sendMessage({ text: input })
      }}>
        <input name="message" disabled={isLoading} />
      </form>
    </div>
  )
}
```

### Structured Output (Not Chat)

```typescript
import { generateText, Output } from 'ai'
import { z } from 'zod'

const { output } = await generateText({
  model: 'openai/gpt-5.4',
  output: Output.object({
    schema: z.object({
      summary: z.string(),
      sentiment: z.enum(['positive', 'negative', 'neutral']),
      keywords: z.array(z.string()),
    }),
  }),
  prompt: `Analyze: ${userInput}`,
})
```

## Data Model Patterns

### Chat History Storage

```sql
-- Supabase: Store conversation history
create table conversations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  title text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid references conversations(id) on delete cascade,
  role text not null check (role in ('user', 'assistant', 'system')),
  content text not null,
  metadata jsonb default '{}',
  created_at timestamptz default now()
);

-- RLS: Users can only access their own conversations
alter table conversations enable row level security;
create policy "Users own conversations"
  on conversations for all
  using (auth.uid() = user_id);

alter table messages enable row level security;
create policy "Users access own messages"
  on messages for all
  using (
    conversation_id in (
      select id from conversations where user_id = auth.uid()
    )
  );
```

### AI Generation Tracking

```sql
-- Track AI usage for cost monitoring
create table ai_generations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id),
  model text not null,
  prompt_tokens int,
  completion_tokens int,
  total_tokens int,
  cost_usd numeric(10, 6),
  created_at timestamptz default now()
);
```

## Key Patterns

### Always Stream for User-Facing AI
Never use `generateText` for chat UIs — always use `streamText` + `useChat` for real-time feedback.

### Error Handling for AI Calls
AI API calls can fail (rate limits, timeouts, model errors). Always wrap in try/catch:

```typescript
try {
  const result = streamText({ model: 'anthropic/claude-sonnet-4.6', ... })
  return result.toUIMessageStreamResponse()
} catch (error) {
  if (error.message?.includes('rate_limit')) {
    return new Response('Too many requests', { status: 429 })
  }
  return new Response('AI service unavailable', { status: 503 })
}
```

### Token Limits
Set reasonable limits to control costs:
- Chat: `stopWhen: stepCountIs(5)` for multi-step tool calling
- Generation: Use `maxTokens` parameter for output length control

### Environment Variables
AI Gateway uses OIDC tokens provisioned by `vercel env pull`. No manual API keys needed.
For local development, the OIDC token expires after ~24h — re-run `vercel env pull` to refresh.
