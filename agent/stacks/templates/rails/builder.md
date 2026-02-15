# Ruby on Rails Build Process

## Steps

1. Scaffold: `rails new . --database=postgresql --css=tailwind`
2. Add gems: devise, activeadmin, sidekiq
3. **Setup Tests**: Add to Gemfile test group: minitest-reporters, factory_bot_rails, faker
4. Generate models from DESIGN.md
5. Create controllers and views
6. Set up routes
7. Run `rails test` to verify setup
