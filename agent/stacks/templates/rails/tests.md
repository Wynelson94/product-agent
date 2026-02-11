# Ruby on Rails Test Patterns (Minitest)

## Setup

Add to Gemfile:
```ruby
group :test do
  gem 'minitest-reporters'
  gem 'factory_bot_rails'
  gem 'faker'
  gem 'mocha'
  gem 'webmock'
end
```

Run:
```bash
bundle install
```

## Test Helper (test/test_helper.rb)

```ruby
ENV['RAILS_ENV'] ||= 'test'
require_relative '../config/environment'
require 'rails/test_help'
require 'minitest/reporters'

Minitest::Reporters.use! [Minitest::Reporters::DefaultReporter.new(color: true)]

class ActiveSupport::TestCase
  include FactoryBot::Syntax::Methods

  parallelize(workers: :number_of_processors)
  fixtures :all
end

class ActionDispatch::IntegrationTest
  include Devise::Test::IntegrationHelpers if defined?(Devise)
end
```

## Factory Patterns (test/factories/)

```ruby
# test/factories/users.rb
FactoryBot.define do
  factory :user do
    name { Faker::Name.name }
    email { Faker::Internet.unique.email }
    password { 'password123' }
    password_confirmation { 'password123' }
    confirmed_at { Time.current } if User.column_names.include?('confirmed_at')

    trait :admin do
      admin { true }
    end
  end
end

# test/factories/items.rb
FactoryBot.define do
  factory :item do
    title { Faker::Lorem.sentence(word_count: 3) }
    description { Faker::Lorem.paragraph }
    status { :draft }
    association :user

    trait :published do
      status { :published }
      published_at { Time.current }
    end
  end
end
```

## Model Test Pattern

```ruby
# test/models/item_test.rb
require 'test_helper'

class ItemTest < ActiveSupport::TestCase
  setup do
    @user = create(:user)
    @item = create(:item, user: @user)
  end

  test 'valid item' do
    assert @item.valid?
  end

  test 'invalid without title' do
    @item.title = nil
    assert_not @item.valid?
    assert_includes @item.errors[:title], "can't be blank"
  end

  test 'invalid without user' do
    @item.user = nil
    assert_not @item.valid?
  end

  test 'belongs to user' do
    assert_equal @user, @item.user
    assert_includes @user.items, @item
  end

  test 'scope published returns only published items' do
    published = create(:item, :published, user: @user)
    draft = create(:item, status: :draft, user: @user)

    assert_includes Item.published, published
    assert_not_includes Item.published, draft
  end

  test 'publish! sets published_at' do
    @item.publish!

    assert @item.published?
    assert_not_nil @item.published_at
  end
end
```

## Controller Test Pattern

```ruby
# test/controllers/items_controller_test.rb
require 'test_helper'

class ItemsControllerTest < ActionDispatch::IntegrationTest
  setup do
    @user = create(:user)
    @item = create(:item, user: @user)
    sign_in @user
  end

  test 'should get index' do
    get items_url
    assert_response :success
    assert_select 'h1', /items/i
  end

  test 'should get new' do
    get new_item_url
    assert_response :success
  end

  test 'should create item' do
    assert_difference('Item.count', 1) do
      post items_url, params: { item: { title: 'New Item', description: 'Desc' } }
    end

    assert_redirected_to item_url(Item.last)
    follow_redirect!
    assert_select '.flash', /created/i
  end

  test 'should show item' do
    get item_url(@item)
    assert_response :success
    assert_select 'h1', @item.title
  end

  test 'should update item' do
    patch item_url(@item), params: { item: { title: 'Updated Title' } }
    assert_redirected_to item_url(@item)

    @item.reload
    assert_equal 'Updated Title', @item.title
  end

  test 'should destroy item' do
    assert_difference('Item.count', -1) do
      delete item_url(@item)
    end

    assert_redirected_to items_url
  end

  test 'should not allow access to other users items' do
    other_user = create(:user)
    other_item = create(:item, user: other_user)

    get item_url(other_item)
    assert_response :not_found
  end
end
```

## API Controller Test Pattern

```ruby
# test/controllers/api/v1/items_controller_test.rb
require 'test_helper'

class Api::V1::ItemsControllerTest < ActionDispatch::IntegrationTest
  setup do
    @user = create(:user)
    @item = create(:item, user: @user)
    @headers = { 'Authorization' => "Bearer #{@user.generate_api_token}" }
  end

  test 'GET /api/v1/items returns items as JSON' do
    get api_v1_items_url, headers: @headers
    assert_response :success

    json = JSON.parse(response.body)
    assert_kind_of Array, json
    assert json.any? { |item| item['id'] == @item.id }
  end

  test 'POST /api/v1/items creates item' do
    assert_difference('Item.count', 1) do
      post api_v1_items_url,
           params: { item: { title: 'API Item', description: 'Created via API' } },
           headers: @headers,
           as: :json
    end

    assert_response :created
    json = JSON.parse(response.body)
    assert_equal 'API Item', json['title']
  end

  test 'POST /api/v1/items returns errors for invalid data' do
    post api_v1_items_url,
         params: { item: { title: '' } },
         headers: @headers,
         as: :json

    assert_response :unprocessable_entity
    json = JSON.parse(response.body)
    assert json['errors'].present?
  end

  test 'returns 401 without authentication' do
    get api_v1_items_url
    assert_response :unauthorized
  end
end
```

## Service Object Test Pattern

```ruby
# test/services/item_publisher_test.rb
require 'test_helper'

class ItemPublisherTest < ActiveSupport::TestCase
  setup do
    @item = create(:item, status: :draft)
    @publisher = ItemPublisher.new(@item)
  end

  test 'publishes item successfully' do
    result = @publisher.call

    assert result.success?
    assert @item.reload.published?
    assert_not_nil @item.published_at
  end

  test 'fails if item already published' do
    @item.update!(status: :published, published_at: 1.day.ago)

    result = @publisher.call

    assert result.failure?
    assert_includes result.errors, 'already published'
  end

  test 'sends notification on publish' do
    assert_enqueued_with(job: NotificationJob) do
      @publisher.call
    end
  end
end
```

## Run Tests

```bash
# Run all tests
bundle exec rails test

# Run specific test file
bundle exec rails test test/models/item_test.rb

# Run specific test by line number
bundle exec rails test test/models/item_test.rb:15

# Run with verbose output
bundle exec rails test -v

# Run system tests
bundle exec rails test:system

# Run with coverage (using simplecov)
COVERAGE=true bundle exec rails test
```
