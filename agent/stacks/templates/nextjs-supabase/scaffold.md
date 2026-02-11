# Next.js + Supabase Scaffolding

## Initial Setup

```bash
# Create Next.js app
npx create-next-app@latest src --typescript --tailwind --eslint --app --src-dir --import-alias "@/*"

cd src

# Install Supabase
npm install @supabase/supabase-js @supabase/ssr

# Install shadcn/ui
npx shadcn@latest init -y
npx shadcn@latest add button input card form label toast dialog dropdown-menu avatar

# Install additional dependencies
npm install zod@3.23.8 react-hook-form @hookform/resolvers lucide-react
```

## Directory Structure

```
src/
├── app/
│   ├── (auth)/
│   │   ├── login/page.tsx
│   │   ├── signup/page.tsx
│   │   └── layout.tsx
│   ├── (dashboard)/
│   │   ├── dashboard/page.tsx
│   │   ├── settings/page.tsx
│   │   └── layout.tsx
│   ├── api/
│   │   └── [entity]/route.ts
│   ├── layout.tsx
│   ├── page.tsx
│   └── globals.css
├── components/
│   ├── ui/           # shadcn components
│   ├── layout/       # Header, Footer, Sidebar
│   └── features/     # Domain-specific components
├── lib/
│   ├── supabase/
│   │   ├── client.ts
│   │   └── server.ts
│   └── utils.ts
├── types/
│   └── database.ts   # Supabase generated types
└── middleware.ts
```

## Environment Template

Create `.env.local.example`:

```env
NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
```
