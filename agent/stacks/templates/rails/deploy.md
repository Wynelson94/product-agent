# Ruby on Rails Deployment (Railway)

## Pre-Deployment Checklist

1. Tests pass: `rails test`
2. Assets compile: `rails assets:precompile`
3. Database migrations ready
4. Environment variables documented
5. Procfile configured

## Railway Deployment

### 1. Install Railway CLI

```bash
npm install -g @railway/cli
railway login
```

### 2. Initialize Project

```bash
railway init
```

### 3. Add PostgreSQL

```bash
railway add
# Select PostgreSQL
```

### 4. Configure Environment Variables

```bash
railway variables set SECRET_KEY_BASE=$(rails secret)
railway variables set RAILS_ENV=production
railway variables set RAILS_SERVE_STATIC_FILES=true
```

### 5. Deploy

```bash
railway up
```

### 6. Run Migrations

```bash
railway run rails db:migrate
```

## Procfile

```
web: bundle exec puma -C config/puma.rb
worker: bundle exec sidekiq
release: bundle exec rails db:migrate
```

## Production Configuration

### config/environments/production.rb

```ruby
Rails.application.configure do
  config.force_ssl = true
  config.assume_ssl = true

  config.public_file_server.enabled = ENV['RAILS_SERVE_STATIC_FILES'].present?

  config.active_storage.service = :amazon # or :cloudinary

  config.action_mailer.delivery_method = :smtp
  config.action_mailer.smtp_settings = {
    address: ENV['SMTP_ADDRESS'],
    port: ENV['SMTP_PORT'],
    user_name: ENV['SMTP_USERNAME'],
    password: ENV['SMTP_PASSWORD'],
    authentication: 'plain',
    enable_starttls_auto: true
  }
end
```

### config/puma.rb

```ruby
workers ENV.fetch("WEB_CONCURRENCY") { 2 }
threads_count = ENV.fetch("RAILS_MAX_THREADS") { 5 }
threads threads_count, threads_count

preload_app!

port ENV.fetch("PORT") { 3000 }
environment ENV.fetch("RAILS_ENV") { "development" }

on_worker_boot do
  ActiveRecord::Base.establish_connection if defined?(ActiveRecord)
end
```

## Alternative: Fly.io Deployment

### 1. Install Fly CLI

```bash
curl -L https://fly.io/install.sh | sh
fly auth login
```

### 2. Launch App

```bash
fly launch
```

### 3. Add PostgreSQL

```bash
fly postgres create
fly postgres attach --app your-app-name
```

### 4. Deploy

```bash
fly deploy
```

### 5. Run Migrations

```bash
fly ssh console -C "rails db:migrate"
```

## Verification

Check these endpoints:
- Homepage loads
- User can sign up and log in
- CRUD operations work
- Background jobs process (check Sidekiq dashboard)
- Emails send (check logs)

## Troubleshooting

### Asset compilation errors
- Ensure `rails assets:precompile` runs in build
- Check for missing JavaScript dependencies

### Database connection errors
- Verify `DATABASE_URL` is set
- Check PostgreSQL addon is provisioned

### Sidekiq not processing
- Ensure Redis addon is added
- Check `REDIS_URL` is set
- Verify worker process is running

### Missing environment variables
- List all required vars in `.env.example`
- Set each in Railway/Fly dashboard
