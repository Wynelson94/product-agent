# Marketplace Patterns

## Overview
Two-sided platforms connecting buyers and sellers, service providers and clients, or any two parties in a transaction.

## Data Model Essentials

### Two-Sided Users
```sql
-- Buyers and Sellers share auth but have different profiles
create table seller_profiles (
  id uuid primary key references auth.users(id),
  business_name text not null,
  description text,
  verified boolean default false,
  stripe_account_id text,
  rating_avg decimal(3,2) default 0,
  rating_count int default 0,
  created_at timestamptz default now()
);

create table buyer_profiles (
  id uuid primary key references auth.users(id),
  display_name text,
  shipping_address jsonb,
  created_at timestamptz default now()
);
```

### Listings
```sql
create table listings (
  id uuid primary key default gen_random_uuid(),
  seller_id uuid references seller_profiles(id) not null,
  title text not null,
  description text,
  price decimal(10,2) not null,
  currency text default 'USD',
  category_id uuid references categories(id),
  images text[],
  status text default 'draft' check (status in ('draft', 'active', 'sold', 'archived')),
  featured boolean default false,
  views int default 0,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Enable full-text search
create index listings_search_idx on listings using gin(to_tsvector('english', title || ' ' || coalesce(description, '')));
```

### Transactions
```sql
create table transactions (
  id uuid primary key default gen_random_uuid(),
  listing_id uuid references listings(id) not null,
  buyer_id uuid references buyer_profiles(id) not null,
  seller_id uuid references seller_profiles(id) not null,
  amount decimal(10,2) not null,
  platform_fee decimal(10,2) not null,
  seller_payout decimal(10,2) not null,
  status text default 'pending' check (status in ('pending', 'paid', 'shipped', 'delivered', 'completed', 'disputed', 'refunded')),
  stripe_payment_intent_id text,
  created_at timestamptz default now(),
  completed_at timestamptz
);
```

### Reviews
```sql
create table reviews (
  id uuid primary key default gen_random_uuid(),
  transaction_id uuid references transactions(id) not null,
  reviewer_id uuid references auth.users(id) not null,
  reviewee_id uuid references auth.users(id) not null,
  rating int not null check (rating >= 1 and rating <= 5),
  comment text,
  created_at timestamptz default now()
);

-- Update seller rating on new review
create or replace function update_seller_rating()
returns trigger as $$
begin
  update seller_profiles
  set
    rating_avg = (select avg(rating) from reviews where reviewee_id = NEW.reviewee_id),
    rating_count = (select count(*) from reviews where reviewee_id = NEW.reviewee_id)
  where id = NEW.reviewee_id;
  return NEW;
end;
$$ language plpgsql;

create trigger update_rating_trigger
after insert on reviews
for each row execute function update_seller_rating();
```

## Key Features

### 1. Search & Discovery
- Full-text search with ranking
- Category filtering
- Price range filtering
- Location-based (if applicable)
- Sort by: newest, price, rating

### 2. Trust & Safety
- Seller verification badge
- Review system with ratings
- Report/flag functionality
- Escrow payments

### 3. Payment Flow
- Stripe Connect for seller payouts
- Platform fee collection
- Escrow until delivery confirmed
- Refund handling

### 4. Communication
- In-app messaging between buyer/seller
- Notification system (new message, order update)
- Email notifications

## RLS Policies

```sql
-- Sellers can only manage their own listings
create policy "Sellers manage own listings"
  on listings for all
  using (seller_id = auth.uid());

-- Anyone can view active listings
create policy "Public can view active listings"
  on listings for select
  using (status = 'active');

-- Users can only see their own transactions
create policy "Users see own transactions"
  on transactions for select
  using (buyer_id = auth.uid() or seller_id = auth.uid());

-- Reviews are public
create policy "Public can read reviews"
  on reviews for select
  using (true);

-- Only transaction participants can leave reviews
create policy "Transaction participants can review"
  on reviews for insert
  with check (
    exists (
      select 1 from transactions
      where id = transaction_id
      and (buyer_id = auth.uid() or seller_id = auth.uid())
    )
  );
```

## Common Pages

| Route | Purpose | Auth |
|-------|---------|------|
| / | Landing with featured listings | No |
| /browse | Search and filter listings | No |
| /listing/[id] | Listing detail page | No |
| /seller/[id] | Seller profile with reviews | No |
| /dashboard | Buyer/seller dashboard | Yes |
| /dashboard/listings | Manage listings (sellers) | Yes |
| /dashboard/orders | View orders | Yes |
| /dashboard/messages | Inbox | Yes |
| /checkout/[listing_id] | Purchase flow | Yes |

## Platform Fee Calculation

```typescript
const PLATFORM_FEE_PERCENT = 0.10; // 10%

function calculateFees(listingPrice: number) {
  const platformFee = listingPrice * PLATFORM_FEE_PERCENT;
  const sellerPayout = listingPrice - platformFee;

  return {
    total: listingPrice,
    platformFee,
    sellerPayout,
  };
}
```
