---
stack_id: nextjs-supabase
product_type: saas
deployment_target: vercel
---
# Stack Decision

## Product Analysis
- **Type**: saas
- **Complexity**: low-medium
- **Key Features**: auth, dashboard, CRUD

## Deployment Configuration (v5.0)
- **Deployment Target**: vercel
- **Deployment Type**: serverless
- **Database Type**: postgresql
- **Database Provider**: supabase

## Selected Stack
- **Stack ID**: nextjs-supabase
- **Build Mode**: standard
- **Rationale**: Simple SaaS application with standard auth and CRUD operations. Supabase provides auth, realtime, and RLS out of the box.
