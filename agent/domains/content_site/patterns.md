# Content Site Domain Patterns

Patterns for content-heavy websites: nonprofits, portfolios, marketing sites,
event/trip sites, blogs, and landing pages.

## Data Architecture

Content sites are **static-first** — prefer `/src/lib/*-data.ts` files over database tables.
Only use Supabase/database for:
- Contact form submissions
- Newsletter signups
- Donation processing (via Stripe/external)
- User-generated content (comments, reviews)

### Common Data Models

#### Locations / Destinations
```typescript
interface Location {
  slug: string;          // URL-safe identifier
  name: string;          // Display name
  country: string;
  description: string;   // 2-3 sentence overview
  heroImage: string;     // Path or placeholder text
  highlights: string[];  // Key facts / bullet points
  climate?: string;
  currency?: string;
  language?: string;
}
```

#### Trips / Events
```typescript
interface Trip {
  slug: string;
  name: string;
  locationSlug: string;  // Links to Location
  dates: string[];       // ["March 15-28, 2026", "October 5-18, 2026"]
  duration: string;      // "14 days"
  cost: number;          // In USD
  description: string;
  highlights: string[];
  included: string[];    // What's included in the cost
  notIncluded: string[]; // What's not included
  registrationUrl?: string;
}
```

#### Team Members
```typescript
interface TeamMember {
  name: string;
  role: string;
  type: "staff" | "board";
  bio?: string;
  image?: string;
}
```

#### Blog Posts
```typescript
interface BlogPost {
  slug: string;
  title: string;
  excerpt: string;
  content: string;       // Can be markdown
  author: string;
  date: string;          // ISO date
  category: string;
  image?: string;
  tags?: string[];
}
```

#### Products (Store)
```typescript
interface StoreProduct {
  id: string;
  name: string;
  description: string;
  price: number;
  imageText: string;     // For placeholder
  variants?: string[];   // Sizes, colors, etc.
}
```

#### FAQ Items
```typescript
interface FAQItem {
  question: string;
  answer: string;
  category: string;      // For filtering
}
```

#### Press / Media
```typescript
interface PressItem {
  title: string;
  publication: string;
  date: string;
  url?: string;
  excerpt?: string;
  type: "article" | "video" | "podcast" | "mention";
}
```

## Component Patterns

### Layout Components

#### Hero Section
Every page should have a hero section with:
- Gradient background (brand colors)
- H1 heading (white text)
- Subtitle/description (white/90 opacity)
- Optional CTA button(s)

```tsx
<section className="bg-gradient-to-br from-primary to-primary-dark py-16 px-4">
  <div className="max-w-4xl mx-auto text-center text-white">
    <h1 className="text-4xl md:text-5xl font-bold mb-4">{title}</h1>
    <p className="text-xl text-white/90">{subtitle}</p>
  </div>
</section>
```

#### Section Heading
Reusable component for content sections:
```tsx
<SectionHeading title="Our Impact" subtitle="Making a difference worldwide" />
```

#### Card Grid
Standard responsive grid for items:
```tsx
<div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
  {items.map(item => <Card key={item.id} ... />)}
</div>
```

### Feature Components

#### Image Placeholder
Since we don't have real images, use styled placeholders:
```tsx
<ImagePlaceholder text="Nepal Clinic" aspectRatio="video" />
```

#### Stats Counter
Animated counters for impact numbers:
```tsx
<StatsSection stats={[
  { label: "Children Served", value: 135000 },
  { label: "Volunteers", value: 8500 },
]} />
```

#### Accordion (FAQ)
Expandable sections for FAQ:
```tsx
<Accordion items={faqItems.map(f => ({ title: f.question, content: f.answer }))} />
```

#### Filter Buttons
Category filter for blog, FAQ, schedule:
```tsx
<FilterButtons
  categories={["All", "Category A", "Category B"]}
  active={activeCategory}
  onChange={setActiveCategory}
/>
```

## Common Pages

| Page | Route | Key Sections |
|------|-------|-------------|
| Home | `/` | Hero, Impact Stats, Locations Grid, How It Works, Testimonials, Partners, CTA |
| About | `/about` | Hero, Mission, History/Timeline, Team Grid, Values |
| Our Work / Services | `/our-work` | Hero, Process Steps, Impact Data, Photo Gallery |
| Volunteer / Get Involved | `/volunteer` | Hero, Volunteer Tracks, Requirements, CTA |
| Schedule / Events | `/volunteer/schedule` | Hero, Filters (Country, Month), Trip List |
| Location Detail | `/locations/[slug]` | Hero, About Location, Upcoming Trips, Gallery |
| Trip / Event Detail | `/trips/[slug]` | Hero, Details, Dates, Cost, What's Included, Register CTA |
| Donate | `/donate` | Hero, Preset Amounts, Custom Amount, Impact Description, In-Kind |
| Store | `/store` | Hero, Product Grid, Cart Sidebar |
| Blog | `/blog` | Hero, Category Filter, Post Grid |
| Blog Post | `/blog/[slug]` | Hero, Article Content, Author, Related Posts |
| Contact | `/contact` | Hero, Contact Form, Contact Info, Map Placeholder |
| FAQ | `/faq` | Hero, Category Filter, Accordion |
| Press / Media | `/press` | Hero, Press Items List |

## Navigation Patterns

### Header
```
Logo | About Us | Our Work | Volunteer (dropdown?) | Blog | Contact | [Donate Button] | [Register CTA]
```

### Footer
```
Column 1: Organization info + address
Column 2: Quick Links (About, Our Work, Volunteer, Blog)
Column 3: Get Involved (Donate, Register, Store, Contact)
Column 4: Connect (Social links, Newsletter signup)
Bottom: Copyright + Legal links
```

## SEO Patterns

- **Title format**: `Page Name | Organization Name`
- **Home title**: `Organization Name | Tagline`
- **Meta descriptions**: 150-160 chars, include key terms
- **Sitemap**: Generate for all static routes + dynamic routes (locations, trips, blog)
- **robots.txt**: Allow all

## Image Handling

Since Claude Code cannot add real images:
1. Use `ImagePlaceholder` component with descriptive text
2. Store placeholder text in data files (e.g., `imageText: "Volunteers at Nepal clinic"`)
3. Design components to look complete even without real photos
4. Use aspect ratios: `square` (1:1), `video` (16:9), `portrait` (3:4)

## Color Palette Guidance

Content sites typically use:
- **Primary**: Brand color (navy, forest green, etc.)
- **Primary Dark**: Darker variant for gradients
- **Accent**: Action color (green for CTAs, gold for highlights)
- **Surface**: Light background for alternating sections (`#F9FAFB`)
- **Text Primary**: Near-black (`#1A1A2E`)
- **Text Secondary**: Gray (`#6B7280`)

Define all colors in `tailwind.config.ts` for consistency.

## Static Data Strategy

For content sites, store ALL content data in TypeScript files:

```
src/lib/
  trip-data.ts        // All trips with full details
  location-data.ts    // All locations
  blog-data.ts        // All blog posts
  faq-data.ts         // All FAQ items
  team-data.ts        // Staff and board members
  store-data.ts       // Store products
  press-data.ts       // Press/media items
```

Benefits:
- Type-safe with TypeScript interfaces
- No database needed for read-only content
- Fast builds with static generation
- Easy to update (just edit the TS files)
- Works perfectly with Next.js static pages
