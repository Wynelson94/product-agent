# Ruby on Rails Scaffolding

## Initial Setup

```bash
# Create Rails app with PostgreSQL
rails new src --database=postgresql --css=tailwind --skip-test --skip-jbuilder

cd src

# Install authentication
bundle add devise
rails generate devise:install
rails generate devise User

# Install admin interface
bundle add activeadmin
rails generate active_admin:install
rails generate active_admin:dashboard
rails db:migrate

# Install background jobs
bundle add sidekiq
bundle add redis

# Install file uploads
bundle add image_processing
rails active_storage:install

# Additional gems
bundle add pagy           # Pagination
bundle add pundit         # Authorization
bundle add friendly_id    # Slugs
```

## Directory Structure

```
src/
├── app/
│   ├── controllers/
│   │   ├── application_controller.rb
│   │   ├── dashboard_controller.rb
│   │   └── api/
│   │       └── v1/
│   ├── models/
│   │   └── user.rb
│   ├── views/
│   │   ├── layouts/
│   │   ├── dashboard/
│   │   └── shared/
│   ├── jobs/
│   ├── mailers/
│   └── admin/
├── config/
│   ├── routes.rb
│   ├── database.yml
│   └── initializers/
├── db/
│   ├── migrate/
│   └── seeds.rb
└── Procfile
```

## Database Setup

```bash
# Create database
rails db:create

# Run migrations
rails db:migrate

# Seed data
rails db:seed
```

## Environment Template

Create `.env.example`:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/app_development
REDIS_URL=redis://localhost:6379/0
SECRET_KEY_BASE=your-secret-key
```

## Procfile (for deployment)

```
web: bundle exec puma -C config/puma.rb
worker: bundle exec sidekiq
release: bundle exec rails db:migrate
```
