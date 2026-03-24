---
verdict: NEEDS_REVISION
issues_count: 1
---
# Design Review — Pass 2

> **Pass 1 summary**: Three issues were raised (settings redirect dead-end, cron routes absent from §5/§12, MEMBER/invoice role ambiguity). All three have been correctly resolved in this revision. Pass 2 review follows.

## Status: NEEDS_REVISION

## Checklist Results

- **Data Model**: FAIL — All PKs, FKs, cascades, and indexes are correct. `SECURITY DEFINER current_org_id()` correctly eliminates RLS circular dependencies. Partial unique index on active timers is correct. Invoice sequencing via `SELECT FOR UPDATE` is well-designed. **One gap**: `invoice_sequences` is a tenant table but is omitted from RLS enablement (see Issue #1).
- **Pages/Routes**: PASS — All routes have auth requirements and minimum roles. Role-aware `/settings` redirect (Issue #1 from Pass 1) is correctly resolved. Cron routes now appear in §5 and §12 (Issue #2 from Pass 1). `/invoices` min role = ADMIN is consistent with the capability matrix (Issue #3 from Pass 1). Loading, error, and empty states are defined for every async page.
- **Components**: PASS — Clear layout / feature / shared separation. No circular dependencies. All referenced components are defined with file paths.
- **Security**: PASS — Clerk auth flow is complete including the org-less edge case. Stripe raw-body signature verification documented. `CRON_SECRET` verification on cron handlers. RBAC capability matrix is explicit. MEMBER ownership assertion for `update:time_entry` is documented (§10 note + `time-actions.ts` spec in §12).
- **Completeness**: PASS — Exceptional depth: Prisma schema, RLS migration SQL, RBAC matrix, capability enforcement in proxy + actions, Stripe webhook event handlers, Clerk webhook sync, cron handler specs, form validation rules, env var table, and `vercel.ts` cron config are all fully specified.

---

## Issues Found

### Issue 1 — `invoice_sequences` tenant table missing RLS (BLOCKING)

**Location**: §1 Additional Database Migrations — RLS enablement block

The design explicitly states: *"Enable RLS on all tenant tables"* and lists 8 tables. The `invoice_sequences` model is a 9th tenant table — it has `orgId String @id`, one row per organization, and stores a mutable integer counter — but it is absent from the `ALTER TABLE … ENABLE ROW LEVEL SECURITY` block and has no isolation policy.

**Impact without this fix:**
- A cross-org read can enumerate all organizations' invoice sequence counters.
- A cross-org write (e.g., `UPDATE invoice_sequences SET last_seq = 0 WHERE org_id = <other_org>`) resets another org's counter, causing duplicate invoice numbers (`INV-2026-0001` collision), which breaks the uniqueness guarantee and could cause the `@@unique([orgId, number])` constraint to reject legitimate invoice creation.

The risk is low when the application layer always uses `tenantPrisma(orgId)`, but the design's own stated invariant is not met, and any future raw-SQL migration or DB admin error would expose the gap.

---

## Required Changes

### Fix 1 — Add RLS to `invoice_sequences`

In `prisma/migrations/YYYYMMDD_partial_unique_timer/migration.sql`, append the following immediately after `ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;`:

```sql
-- invoice_sequences: per-org counter, must be tenant-isolated.
-- org_id IS the primary key (maps from Prisma orgId via snake_case convention).
ALTER TABLE invoice_sequences ENABLE ROW LEVEL SECURITY;

CREATE POLICY "invoice_sequence_isolation" ON invoice_sequences
  FOR ALL USING  (org_id = current_org_id())
  WITH CHECK     (org_id = current_org_id());
```

No structural schema change is required — `org_id` is already the primary key of `invoice_sequences`.

---

## Recommendations (non-blocking)

### Rec 1 — `tenantPrisma` `set_config` may not persist across pooled connections

**Location**: §11 `tenantPrisma` Factory

`set_config('app.current_org_id', orgId, true)` uses `is_local = true`, which means the setting is **local to the current transaction**. Because `$executeRaw` and the subsequent Prisma data queries each run as separate implicit auto-commit transactions, the session variable may not carry over to those queries in Neon's pgBouncer transaction-pooling mode. Additionally, the factory returns the shared `globalPrisma` instance, so two concurrent requests calling `set_config` with different `orgId` values could interleave.

The app-layer `orgId` filter on every query (the primary enforcement) remains correct regardless. But the RLS safety net would silently receive an empty `current_org_id()` and block all rows rather than catching cross-org leaks.

**Recommended implementation pattern** (Build phase):
```typescript
// Wrap set_config + queries in a single $transaction so set_config is
// local to the same DB transaction as all subsequent queries
export async function withTenant<T>(
  orgId: string,
  fn: (tx: PrismaTransactionClient) => Promise<T>
): Promise<T> {
  return globalPrisma.$transaction(async (tx) => {
    await tx.$executeRaw`SELECT set_config('app.current_org_id', ${orgId}, true)`;
    return fn(tx);
  });
}
```

### Rec 2 — Clarify `/*/edit` route guard pattern to prevent MEMBER lockout

**Location**: §4 Protected Route Handling (`proxy.ts`)

The proxy pseudocode lists:
```
/clients/new, /projects/new, /*/edit  → require ADMIN
/time, /time/*                         → require MEMBER
```

The wildcard `/*/edit` matches `/time/[id]/edit`. If evaluated before `/time/*`, it locks MEMBERs out of editing their own time entries — the opposite of the intended behavior in the routes table (§2: `/time/[id]/edit` min role = MEMBER).

**Recommended fix**: Replace the wildcard with explicit patterns:
```
/clients/new, /clients/[id]/edit, /projects/new, /projects/[id]/edit  → require ADMIN
/invoices/[id]/edit                                                     → require ADMIN
/time, /time/*                                                          → require MEMBER
```

### Rec 3 — Document VIEWER `view:time_entry` vs MEMBER-only `/time` page

**Location**: §2 Routes table + §10 RBAC Capability Matrix

The CAPABILITIES matrix grants `view:time_entry` to VIEWER, yet `/time` and `/time/*` routes require MEMBER. VIEWERs therefore see time data only through `/projects/[id]` (the project detail page). This is a coherent design choice — the `/time` list is a time-management tool for workers, not a read-only reporting surface — but the inconsistency between the capability name and the route guard is undocumented and may confuse implementers. A one-line note in §2 or §10 would prevent misinterpretation.

### Rec 4 — Add `error.tsx` companions for settings sub-pages

**Location**: §12 Key File Structure

`loading.tsx` exists for all four settings sub-pages, but no `error.tsx` companions are defined. The root `app/error.tsx` catches everything, but per-route error boundaries allow contextual inline-alert rendering within the settings layout shell rather than a full-page error. Low-effort addition using the inline-alert pattern already established in §6.
