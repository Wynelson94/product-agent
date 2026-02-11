# Multi-Tenant SaaS Patterns

## Overview
Software-as-a-Service applications with organization-based isolation, subscription billing, and team collaboration.

## Data Model Essentials

### Organizations (Tenants)
```sql
create table organizations (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  slug text unique not null,
  logo_url text,
  plan text default 'free' check (plan in ('free', 'starter', 'pro', 'enterprise')),
  stripe_customer_id text,
  stripe_subscription_id text,
  trial_ends_at timestamptz,
  settings jsonb default '{}',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Generate slug from name
create or replace function generate_org_slug()
returns trigger as $$
begin
  NEW.slug := lower(regexp_replace(NEW.name, '[^a-zA-Z0-9]+', '-', 'g'));
  return NEW;
end;
$$ language plpgsql;

create trigger org_slug_trigger
before insert on organizations
for each row execute function generate_org_slug();
```

### Organization Membership
```sql
create table organization_members (
  organization_id uuid references organizations(id) on delete cascade,
  user_id uuid references auth.users(id) on delete cascade,
  role text default 'member' check (role in ('owner', 'admin', 'member', 'viewer')),
  invited_by uuid references auth.users(id),
  invited_at timestamptz,
  joined_at timestamptz default now(),
  primary key (organization_id, user_id)
);

-- Track user's current organization
alter table auth.users add column current_organization_id uuid references organizations(id);
```

### Invitations
```sql
create table invitations (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid references organizations(id) on delete cascade,
  email text not null,
  role text default 'member',
  token text unique not null default gen_random_uuid()::text,
  invited_by uuid references auth.users(id),
  expires_at timestamptz default (now() + interval '7 days'),
  accepted_at timestamptz,
  created_at timestamptz default now()
);
```

### Tenant-Scoped Data
```sql
-- Example: Projects belong to an organization
create table projects (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid references organizations(id) on delete cascade not null,
  name text not null,
  description text,
  status text default 'active',
  created_by uuid references auth.users(id),
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Index for efficient tenant queries
create index projects_org_idx on projects(organization_id);
```

## Tenant Isolation Patterns

### RLS with Organization Scope
```sql
-- Helper function to get user's organizations
create or replace function user_organizations()
returns setof uuid as $$
  select organization_id from organization_members where user_id = auth.uid()
$$ language sql security definer;

-- Helper to get current organization
create or replace function current_organization()
returns uuid as $$
  select current_organization_id from auth.users where id = auth.uid()
$$ language sql security definer;

-- Projects: Users see only their org's projects
create policy "Org members can view projects"
  on projects for select
  using (organization_id in (select user_organizations()));

create policy "Admins can manage projects"
  on projects for all
  using (
    organization_id in (
      select organization_id from organization_members
      where user_id = auth.uid()
      and role in ('owner', 'admin')
    )
  );
```

### Organization Context Middleware
```typescript
// middleware.ts - Set organization context
import { createServerClient } from '@supabase/ssr'
import { NextResponse, type NextRequest } from 'next/server'

export async function middleware(request: NextRequest) {
  const response = NextResponse.next()
  const supabase = createServerClient(/* ... */)

  const { data: { user } } = await supabase.auth.getUser()

  if (user) {
    // Get org from subdomain or path
    const hostname = request.headers.get('host') || ''
    const subdomain = hostname.split('.')[0]

    // Verify user has access to this org
    const { data: membership } = await supabase
      .from('organization_members')
      .select('organization_id')
      .eq('user_id', user.id)
      .eq('organization:slug', subdomain)
      .single()

    if (!membership && subdomain !== 'app') {
      return NextResponse.redirect(new URL('/select-org', request.url))
    }
  }

  return response
}
```

## Subscription & Billing

### Plan Limits
```typescript
const PLAN_LIMITS = {
  free: {
    members: 3,
    projects: 5,
    storage_mb: 100,
  },
  starter: {
    members: 10,
    projects: 25,
    storage_mb: 1000,
  },
  pro: {
    members: 50,
    projects: -1, // unlimited
    storage_mb: 10000,
  },
  enterprise: {
    members: -1,
    projects: -1,
    storage_mb: -1,
  },
};

function checkLimit(org: Organization, resource: string, current: number): boolean {
  const limit = PLAN_LIMITS[org.plan][resource];
  return limit === -1 || current < limit;
}
```

### Usage Tracking
```sql
create table usage_records (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid references organizations(id) not null,
  metric text not null, -- 'api_calls', 'storage_bytes', 'members'
  value bigint not null,
  period_start date not null,
  period_end date not null,
  created_at timestamptz default now()
);

-- Aggregate usage by period
create index usage_org_period_idx on usage_records(organization_id, metric, period_start);
```

## Key Features

### 1. Organization Management
- Create organization
- Invite members by email
- Role-based permissions (owner, admin, member, viewer)
- Organization settings

### 2. Subscription Management
- Plan selection
- Upgrade/downgrade
- Usage-based billing
- Invoice history

### 3. Team Collaboration
- Shared workspace
- Activity feed
- Comments/mentions
- Real-time updates

### 4. Admin Dashboard
- User management
- Usage analytics
- Audit logs

## Common Pages

| Route | Purpose | Auth |
|-------|---------|------|
| / | Marketing landing | No |
| /login, /signup | Auth | No |
| /select-org | Organization picker | Yes |
| /[org]/dashboard | Main workspace | Yes |
| /[org]/settings | Org settings | Yes (admin) |
| /[org]/members | Team management | Yes (admin) |
| /[org]/billing | Subscription | Yes (owner) |
| /[org]/[resource] | Resource pages | Yes |

## Audit Logging
```sql
create table audit_logs (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid references organizations(id),
  user_id uuid references auth.users(id),
  action text not null, -- 'create', 'update', 'delete', 'invite', etc.
  resource_type text not null,
  resource_id uuid,
  changes jsonb,
  ip_address inet,
  user_agent text,
  created_at timestamptz default now()
);

create index audit_org_idx on audit_logs(organization_id, created_at desc);
```
