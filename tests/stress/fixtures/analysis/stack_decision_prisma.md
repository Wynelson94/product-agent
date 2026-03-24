---
stack_id: nextjs-prisma
product_type: multi_tenant
deployment_target: vercel
---
# Stack Decision

## Product Analysis
- **Type**: multi_tenant (organization-scoped SaaS with RBAC)
- **Complexity**: high
- **Key Features**: multi-tenancy, RBAC (owner/admin/member/viewer), Stripe subscription billing, tiered pricing plans, org-scoped RLS isolation, project management, time tracking, invoicing, client billing, activity audit logs

## Deployment Configuration (v5.0)
- **Deployment Target**: vercel
- **Deployment Type**: serverless
- **Database Type**: postgresql
- **Database Provider**: neon (via Vercel Marketplace)

## Compatibility Check
- **SQLite Allowed**: No — serverless Vercel deployment prohibits file-based databases
- **File Storage Allowed**: No — use Vercel Blob for file assets (invoice PDFs, attachments)
- **Compatibility Status**: COMPATIBLE

## Selected Stack
- **Stack ID**: nextjs-prisma
- **Build Mode**: standard
- **Rationale**: This product has a complex relational data model — organizations, members with roles, projects, time entries, invoices, line items, subscription plans, and audit log events — all requiring well-defined foreign keys, transactions, and multi-tenant row isolation. Prisma provides type-safe schema migrations, a rich relation API, and the ability to enforce org-scoping at the query layer with RLS acting as a safety net in PostgreSQL. Neon's serverless PostgreSQL (via Vercel Marketplace) pairs naturally with Vercel's serverless runtime, supports row-level security for org-scoped isolation, and offers connection pooling essential for high-concurrency time-tracking dashboards. Next.js App Router Server Actions handle mutations (time entries, invoice creation) with built-in CSRF protection and edge-close data access, while Stripe's webhook Route Handler pattern integrates cleanly alongside them.

## Stack-Specific Considerations

### Multi-Tenancy & RLS
- Every Prisma query **must** include an `orgId` filter. Use a `tenantPrisma(orgId)` factory that wraps the base client and injects the filter — never expose a bare `prisma` client to route handlers.
- Enable PostgreSQL row-level security on all tenant tables (`projects`, `time_entries`, `invoices`, `audit_logs`) using a `SET app.current_org_id` session variable pattern with Neon's connection pooler to propagate tenant context to RLS policies.
- RLS is a safety net — enforce org scoping in the application layer first (service/repository layer), then let RLS catch any leaks at the DB layer.

### RBAC (owner / admin / member / viewer)
- Store roles in a `memberships` table: `{ orgId, userId, role, createdAt }`. Resolve the caller's role in a shared `auth()` helper in `proxy.ts` and attach `{ userId, orgId, role }` to the request context.
- Use a centralized `can(role, action)` capability matrix (e.g., `can('member', 'create:time_entry')`) evaluated in Server Actions before any DB mutation — keeps authorization logic testable and in one place.
- Permission hierarchy: `owner > admin > member > viewer`. Owners can manage billing and delete the org; viewers are read-only across all resources.

### Stripe Subscription Billing & Tiered Plans
- Use Stripe Billing with Products + Prices for plan tiers (e.g., Starter / Pro / Enterprise). Store `stripeCustomerId`, `stripeSubscriptionId`, `stripePriceId`, and `planTier` on the `organizations` table.
- Handle Stripe webhooks in a dedicated Next.js Route Handler (`/api/webhooks/stripe`) — not a Server Action — to support raw body signature verification via `stripe.webhooks.constructEvent()`.
- Gate features by `planTier` with a `requirePlan(orgId, minTier)` guard on the server and a `usePlan()` hook on the client. On plan downgrade, enforce limits (e.g., max 3 active projects on Starter) at the mutation layer.
- Bill per seat for member counts — listen to `customer.subscription.updated` webhook to sync seat counts.

### Activity Audit Logs
- Write audit events asynchronously using Next.js `after()` (post-response) to avoid adding latency to user-facing mutations.
- Schema: `{ id, orgId, actorId, actorRole, action, resourceType, resourceId, metadata (JSON), ipAddress, createdAt }`. Index on `(orgId, createdAt DESC)` for paginated queries.
- Retain audit logs per plan tier (e.g., 30 days on Starter, 1 year on Enterprise). Run a nightly Vercel Cron job to prune expired entries.

### Time Tracking
- Time entries reference both a `projectId` and a `userId`, with `startedAt` / `stoppedAt` timestamps plus an optional manual `durationMinutes` override.
- Enforce that an org member can only have one active timer (no `stoppedAt`) at a time — add a partial unique index: `UNIQUE (userId) WHERE stopped_at IS NULL`.
- Aggregate billable hours per project / per client via PostgreSQL `SUM(duration)` with `GROUP BY` for invoice generation.

### Invoicing & Client Billing
- Normalize into `clients → invoices → invoice_line_items`. Line items reference either a time entry range (auto-generated) or a manual description + unit price.
- Generate PDF invoices using `@react-pdf/renderer` in a Vercel Function and store the output in **Vercel Blob**, linking the blob URL back to the invoice record.
- Invoice status workflow: `DRAFT → SENT → PAID → OVERDUE → VOID` — model as a Prisma enum with allowed transitions enforced at the service layer.

### Data Model (Core Entities)
```
Organization → Memberships (role) → Users
Organization → SubscriptionPlan (Stripe)
Organization → Clients
Organization → Projects → TimeEntries → Users
             → Projects → Tasks (optional)
Clients → Invoices → InvoiceLineItems (→ TimeEntries)
Organization → AuditLogs
```

### Auth
- Use **Clerk** (Vercel Marketplace) for authentication — it handles email/social login, JWT issuance, and organization membership out of the box. Map Clerk `orgId` → internal `organizations.id` on first org creation via a `clerk:organization.created` webhook.
- Protect all routes with `clerkMiddleware()` in `proxy.ts`. Store `orgId` and `role` in Clerk's custom session metadata so they are available on every request without an extra DB lookup.
- Handle the org-less state: after sign-in, if the user has no org, redirect to an org creation/join page — never loop back to the dashboard.

### Performance
- Use **Prisma Accelerate** or Neon's built-in connection pooling (pgBouncer) to prevent connection exhaustion under serverless concurrency — critical for time-tracking dashboards that fire many parallel queries.
- Cache org membership + role lookups in **Vercel Runtime Cache** with a 30-second TTL so role checks don't hit the DB on every Server Component render.
- Use `@neondatabase/serverless` (HTTP driver) for edge-adjacent queries where connection overhead matters.

### Required Environment Variables
| Variable | Source |
|---|---|
| `DATABASE_URL` | Neon (auto-provisioned via Vercel Marketplace) |
| `DIRECT_URL` | Neon direct connection (for Prisma migrations) |
| `STRIPE_SECRET_KEY` | Stripe dashboard |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret |
| `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` | Stripe dashboard |
| `CLERK_SECRET_KEY` | Clerk (auto-provisioned via Vercel Marketplace) |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Clerk (auto-provisioned via Vercel Marketplace) |
| `BLOB_READ_WRITE_TOKEN` | Vercel Blob (for invoice PDF storage) |
