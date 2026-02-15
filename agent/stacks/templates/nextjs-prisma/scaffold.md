# Next.js + Prisma Scaffolding

## Initial Setup

```bash
# Create Next.js app
npx create-next-app@latest src --typescript --tailwind --eslint --app --src-dir --import-alias "@/*"

cd src

# Install Prisma (pinned to stable v5 - v7 requires adapter architecture)
npm install prisma@5.22.0 @prisma/client@5.22.0
npx prisma init

# Install Auth.js (NextAuth) — see Dependency Compatibility below
npm install next-auth@latest @auth/prisma-adapter

# Install shadcn/ui
npx shadcn@latest init -y
npx shadcn@latest add button input card form label toast dialog dropdown-menu avatar table data-table

# Install additional dependencies
npm install zod@3.23.8 react-hook-form @hookform/resolvers lucide-react bcryptjs
npm install -D @types/bcryptjs
```

## Dependency Compatibility (CRITICAL)

After installing dependencies, check for peer dependency conflicts:
```bash
npm ls --all 2>&1 | grep "peer dep" || echo "No peer dependency conflicts"
```

If conflicts are found, fix them before proceeding. Common version requirements:

| Next.js Version | next-auth Version | Notes |
|-----------------|-------------------|-------|
| next@16.x | next-auth@5.0.0-beta.30+ | Beta.25 does NOT support Next.js 16 |
| next@15.x | next-auth@5.0.0-beta.25+ | |
| next@14.x | next-auth@5.0.0-beta.20+ | |

**IMPORTANT**: `npx create-next-app@latest` installs the latest Next.js (currently 16.x).
Ensure the next-auth version is compatible with the installed Next.js version.

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
│   │   ├── auth/[...nextauth]/route.ts
│   │   └── [entity]/route.ts
│   ├── layout.tsx
│   ├── page.tsx
│   └── globals.css
├── components/
│   ├── ui/           # shadcn components
│   ├── layout/       # Header, Footer, Sidebar
│   └── features/     # Domain-specific components
├── lib/
│   ├── prisma.ts     # Prisma client singleton
│   ├── auth.ts       # Auth.js config
│   └── utils.ts
├── prisma/
│   ├── schema.prisma
│   └── seed.ts
└── middleware.ts
```

## Environment Template

Create `.env.example`:

```env
# PostgreSQL connection string
# For local PostgreSQL on macOS, use your system username (run `whoami` to find it)
# Example: postgresql://yourusername@localhost:5432/dbname?schema=public
# For remote/Docker PostgreSQL, use: postgresql://user:password@localhost:5432/dbname?schema=public
DATABASE_URL="postgresql://USERNAME@localhost:5432/dbname?schema=public"
NEXTAUTH_SECRET="your-secret-here"
NEXTAUTH_URL="http://localhost:3000"
```

## Prisma Schema Base

```prisma
// prisma/schema.prisma
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model User {
  id            String    @id @default(cuid())
  name          String?
  email         String    @unique
  emailVerified DateTime?
  image         String?
  password      String?
  accounts      Account[]
  sessions      Session[]
  createdAt     DateTime  @default(now())
  updatedAt     DateTime  @updatedAt
}

model Account {
  id                String  @id @default(cuid())
  userId            String
  type              String
  provider          String
  providerAccountId String
  refresh_token     String? @db.Text
  access_token      String? @db.Text
  expires_at        Int?
  token_type        String?
  scope             String?
  id_token          String? @db.Text
  session_state     String?
  user              User    @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@unique([provider, providerAccountId])
}

model Session {
  id           String   @id @default(cuid())
  sessionToken String   @unique
  userId       String
  expires      DateTime
  user         User     @relation(fields: [userId], references: [id], onDelete: Cascade)
}
```

## Database Setup

```bash
# Generate Prisma client
npx prisma generate

# Push schema to database (development)
npx prisma db push

# Or create migration (production)
npx prisma migrate dev --name init

# Seed database (optional)
npx prisma db seed
```
