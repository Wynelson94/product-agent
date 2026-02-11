# Design - {{PRODUCT_NAME}}

## Data Model

### users
Extends Supabase auth.users. Additional fields if needed:

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | From auth.users |
| created_at | timestamp | Auto-set |

### {{MAIN_ENTITY}}

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| user_id | uuid | Foreign key to auth.users |
| name | text | {{DESCRIPTION}} |
| created_at | timestamp | Auto-set |
| updated_at | timestamp | Auto-set |

## Pages

| Route | Purpose | Auth Required |
|-------|---------|---------------|
| / | Landing page | No |
| /login | Sign in | No |
| /signup | Create account | No |
| /dashboard | Main app view | Yes |
| /settings | User settings | Yes |

## Components

### Layout
- Header (logo, nav, user menu)
- Footer (links, copyright)

### Features
- {{ENTITY}}Form - Create/edit {{entity}}
- {{ENTITY}}List - Display all {{entities}}
- {{ENTITY}}Card - Single {{entity}} display

### Shared
- Button, Input, Card (from shadcn/ui)
- LoadingSpinner
- EmptyState

## Auth Flow

1. User signs up with email/password via Supabase Auth
2. Email confirmation (optional)
3. On login, redirect to /dashboard
4. Protected routes check session in middleware
5. Logout clears session, redirects to /

## API Routes

| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/{{entity}} | GET | List user's {{entities}} |
| /api/{{entity}} | POST | Create new {{entity}} |
| /api/{{entity}}/[id] | GET | Get single {{entity}} |
| /api/{{entity}}/[id] | PUT | Update {{entity}} |
| /api/{{entity}}/[id] | DELETE | Delete {{entity}} |

## Database Schema (SQL)

```sql
-- Create {{main_entity}} table
create table {{main_entity}} (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade not null,
  name text not null,
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now()
);

-- Enable RLS
alter table {{main_entity}} enable row level security;

-- RLS Policies
create policy "Users can view own {{main_entity}}"
  on {{main_entity}} for select
  using (auth.uid() = user_id);

create policy "Users can create own {{main_entity}}"
  on {{main_entity}} for insert
  with check (auth.uid() = user_id);

create policy "Users can update own {{main_entity}}"
  on {{main_entity}} for update
  using (auth.uid() = user_id);

create policy "Users can delete own {{main_entity}}"
  on {{main_entity}} for delete
  using (auth.uid() = user_id);

-- Updated at trigger
create or replace function update_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger {{main_entity}}_updated_at
  before update on {{main_entity}}
  for each row execute function update_updated_at();
```
