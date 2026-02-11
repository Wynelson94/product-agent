# Internal Tool Patterns

## Overview
Admin dashboards, back-office tools, data management interfaces, and employee-facing applications.

## Data Model Essentials

### Users with Roles
```sql
create table employees (
  id uuid primary key references auth.users(id),
  email text unique not null,
  full_name text not null,
  department text,
  role text default 'user' check (role in ('super_admin', 'admin', 'manager', 'user', 'viewer')),
  avatar_url text,
  is_active boolean default true,
  last_login_at timestamptz,
  created_at timestamptz default now()
);

-- Role hierarchy for permission checks
create or replace function has_role(required_role text)
returns boolean as $$
declare
  user_role text;
  role_hierarchy text[] := array['viewer', 'user', 'manager', 'admin', 'super_admin'];
begin
  select role into user_role from employees where id = auth.uid();
  return array_position(role_hierarchy, user_role) >= array_position(role_hierarchy, required_role);
end;
$$ language plpgsql security definer;
```

### Entity Management (Generic CRUD)
```sql
-- Example: Customers table for CRM-style tool
create table customers (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  email text,
  phone text,
  company text,
  status text default 'active' check (status in ('active', 'inactive', 'lead', 'churned')),
  tags text[],
  metadata jsonb default '{}',
  assigned_to uuid references employees(id),
  created_by uuid references employees(id),
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Full-text search
create index customers_search_idx on customers
using gin(to_tsvector('english', name || ' ' || coalesce(email, '') || ' ' || coalesce(company, '')));

-- Filter indexes
create index customers_status_idx on customers(status);
create index customers_assigned_idx on customers(assigned_to);
```

### Activity/Audit Log
```sql
create table activity_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references employees(id),
  action text not null,
  entity_type text not null,
  entity_id uuid,
  old_values jsonb,
  new_values jsonb,
  ip_address inet,
  created_at timestamptz default now()
);

-- Trigger for automatic logging
create or replace function log_changes()
returns trigger as $$
begin
  insert into activity_logs (user_id, action, entity_type, entity_id, old_values, new_values)
  values (
    auth.uid(),
    TG_OP,
    TG_TABLE_NAME,
    coalesce(NEW.id, OLD.id),
    case when TG_OP = 'DELETE' then to_jsonb(OLD) else null end,
    case when TG_OP != 'DELETE' then to_jsonb(NEW) else null end
  );
  return coalesce(NEW, OLD);
end;
$$ language plpgsql security definer;
```

### Settings/Configuration
```sql
create table app_settings (
  key text primary key,
  value jsonb not null,
  description text,
  updated_by uuid references employees(id),
  updated_at timestamptz default now()
);

-- Insert default settings
insert into app_settings (key, value, description) values
  ('notifications_enabled', 'true', 'Enable email notifications'),
  ('default_page_size', '25', 'Default items per page'),
  ('maintenance_mode', 'false', 'Enable maintenance mode');
```

## Key Features

### 1. Data Tables
- Sortable columns
- Filterable (status, date range, assigned to)
- Searchable
- Bulk actions (delete, update status, export)
- Pagination

### 2. CRUD Operations
- Create with validation
- Edit inline or in modal
- Soft delete with confirmation
- Duplicate entry

### 3. Data Export
- CSV export
- Excel export
- PDF reports
- Scheduled exports

### 4. Dashboard Analytics
- Key metrics cards
- Charts (line, bar, pie)
- Date range selection
- Comparison periods

### 5. Role-Based Access
- Page-level permissions
- Action-level permissions
- Data filtering by role

## RLS Policies

```sql
-- Viewers can only read
create policy "Viewers can read"
  on customers for select
  using (has_role('viewer'));

-- Users can read and create
create policy "Users can create"
  on customers for insert
  with check (has_role('user'));

-- Managers can update assigned records or all if admin
create policy "Managers can update"
  on customers for update
  using (
    has_role('admin') or
    (has_role('manager') and assigned_to = auth.uid())
  );

-- Only admins can delete
create policy "Admins can delete"
  on customers for delete
  using (has_role('admin'));
```

## Component Patterns

### Data Table Component
```typescript
interface DataTableProps<T> {
  data: T[];
  columns: ColumnDef<T>[];
  searchable?: boolean;
  filterable?: boolean;
  exportable?: boolean;
  selectable?: boolean;
  onRowClick?: (row: T) => void;
  onBulkAction?: (action: string, rows: T[]) => void;
}
```

### Filter Panel
```typescript
interface FilterConfig {
  field: string;
  label: string;
  type: 'select' | 'date' | 'daterange' | 'search' | 'multiselect';
  options?: { label: string; value: string }[];
}
```

### Stat Card
```typescript
interface StatCardProps {
  title: string;
  value: number | string;
  change?: number; // percentage change
  trend?: 'up' | 'down' | 'neutral';
  icon?: React.ReactNode;
}
```

## Common Pages

| Route | Purpose | Required Role |
|-------|---------|---------------|
| /login | Authentication | - |
| /dashboard | Overview + stats | viewer |
| /customers | Customer list | viewer |
| /customers/[id] | Customer detail | viewer |
| /customers/new | Create customer | user |
| /reports | Analytics | manager |
| /settings | App settings | admin |
| /users | User management | admin |
| /audit-log | Activity history | admin |

## Export Function
```typescript
async function exportToCSV(data: any[], filename: string) {
  const headers = Object.keys(data[0]);
  const csvContent = [
    headers.join(','),
    ...data.map(row =>
      headers.map(h => JSON.stringify(row[h] ?? '')).join(',')
    )
  ].join('\n');

  const blob = new Blob([csvContent], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${filename}_${new Date().toISOString().split('T')[0]}.csv`;
  a.click();
}
```

## Dashboard Metrics Query
```sql
-- Example: Get key metrics for dashboard
with metrics as (
  select
    count(*) filter (where created_at > now() - interval '30 days') as new_customers_30d,
    count(*) filter (where created_at > now() - interval '7 days') as new_customers_7d,
    count(*) filter (where status = 'active') as active_customers,
    count(*) as total_customers
  from customers
)
select
  new_customers_30d,
  new_customers_7d,
  active_customers,
  total_customers,
  round(100.0 * active_customers / nullif(total_customers, 0), 1) as active_rate
from metrics;
```
