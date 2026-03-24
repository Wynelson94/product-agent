# Ruby on Rails Code Patterns

## Authentication (Devise)

### User Model

```ruby
# app/models/user.rb
class User < ApplicationRecord
  # NOTE: :confirmable requires email delivery config (letter_opener for dev,
  # SendGrid/Mailgun for production). Only add :confirmable if email is set up.
  devise :database_authenticatable, :registerable,
         :recoverable, :rememberable, :validatable,
         :trackable

  has_many :items, dependent: :destroy

  validates :name, presence: true
end
```

### Controller Authentication

```ruby
# app/controllers/application_controller.rb
class ApplicationController < ActionController::Base
  before_action :authenticate_user!

  protected

  def after_sign_in_path_for(resource)
    dashboard_path
  end
end
```

## Controllers

### RESTful Controller

```ruby
# app/controllers/items_controller.rb
class ItemsController < ApplicationController
  before_action :set_item, only: [:show, :edit, :update, :destroy]

  def index
    @items = current_user.items.order(created_at: :desc)
    @pagy, @items = pagy(@items)
  end

  def show
  end

  def new
    @item = current_user.items.build
  end

  def create
    @item = current_user.items.build(item_params)

    if @item.save
      redirect_to @item, notice: 'Item created successfully.'
    else
      render :new, status: :unprocessable_entity
    end
  end

  def edit
  end

  def update
    if @item.update(item_params)
      redirect_to @item, notice: 'Item updated successfully.'
    else
      render :edit, status: :unprocessable_entity
    end
  end

  def destroy
    @item.destroy
    redirect_to items_path, notice: 'Item deleted.'
  end

  private

  def set_item
    @item = current_user.items.find(params[:id])
  end

  def item_params
    params.require(:item).permit(:title, :description, :status)
  end
end
```

### API Controller

```ruby
# app/controllers/api/v1/items_controller.rb
module Api
  module V1
    class ItemsController < ApplicationController
      skip_before_action :verify_authenticity_token
      before_action :authenticate_api_user!

      def index
        items = current_user.items.order(created_at: :desc)
        render json: items
      end

      def create
        item = current_user.items.build(item_params)

        if item.save
          render json: item, status: :created
        else
          render json: { errors: item.errors }, status: :unprocessable_entity
        end
      end

      private

      def authenticate_api_user!
        token = request.headers['Authorization']&.split(' ')&.last
        @current_user = User.find_by(api_token: token)

        render json: { error: 'Unauthorized' }, status: :unauthorized unless @current_user
      end

      def item_params
        params.require(:item).permit(:title, :description)
      end
    end
  end
end
```

## Models

### Model with Validations and Callbacks

```ruby
# app/models/item.rb
class Item < ApplicationRecord
  belongs_to :user
  belongs_to :category, optional: true
  has_many :comments, dependent: :destroy
  has_one_attached :image

  validates :title, presence: true, length: { maximum: 100 }
  validates :description, length: { maximum: 1000 }

  enum status: { draft: 0, published: 1, archived: 2 }

  scope :recent, -> { order(created_at: :desc) }
  scope :published, -> { where(status: :published) }

  before_save :set_slug

  private

  def set_slug
    self.slug = title.parameterize if title_changed?
  end
end
```

### Multi-Tenant Model

```ruby
# app/models/concerns/multi_tenant.rb
module MultiTenant
  extend ActiveSupport::Concern

  included do
    belongs_to :organization
    default_scope { where(organization_id: Current.organization&.id) }
  end
end

# app/models/item.rb
class Item < ApplicationRecord
  include MultiTenant
  # ...
end
```

## Background Jobs

```ruby
# app/jobs/send_notification_job.rb
class SendNotificationJob < ApplicationJob
  queue_as :default

  def perform(user_id, message)
    user = User.find(user_id)
    NotificationMailer.notify(user, message).deliver_now
  end
end

# Usage
SendNotificationJob.perform_later(user.id, "Your item was sold!")
```

## Mailers

```ruby
# app/mailers/notification_mailer.rb
class NotificationMailer < ApplicationMailer
  def notify(user, message)
    @user = user
    @message = message

    mail(to: @user.email, subject: 'Notification')
  end
end
```

## Routes

```ruby
# config/routes.rb
Rails.application.routes.draw do
  devise_for :users

  root 'home#index'

  resources :dashboard, only: [:index]
  resources :items

  namespace :api do
    namespace :v1 do
      resources :items, only: [:index, :create, :show, :update, :destroy]
    end
  end

  # Admin
  ActiveAdmin.routes(self)

  # Sidekiq dashboard (authenticated)
  authenticate :user, ->(u) { u.admin? } do
    mount Sidekiq::Web => '/sidekiq'
  end
end
```

## Views (Hotwire/Turbo)

### Turbo Frame

```erb
<!-- app/views/items/index.html.erb -->
<%= turbo_frame_tag "items" do %>
  <% @items.each do |item| %>
    <%= render item %>
  <% end %>
<% end %>

<!-- app/views/items/_item.html.erb -->
<%= turbo_frame_tag dom_id(item) do %>
  <div class="item-card">
    <h3><%= item.title %></h3>
    <%= link_to "Edit", edit_item_path(item) %>
  </div>
<% end %>
```

### Turbo Stream

```ruby
# app/controllers/items_controller.rb
def create
  @item = current_user.items.build(item_params)

  respond_to do |format|
    if @item.save
      format.turbo_stream
      format.html { redirect_to @item }
    else
      format.html { render :new, status: :unprocessable_entity }
    end
  end
end
```

```erb
<!-- app/views/items/create.turbo_stream.erb -->
<%= turbo_stream.prepend "items", @item %>
<%= turbo_stream.update "item_form", partial: "items/form", locals: { item: Item.new } %>
```

## Authorization (Pundit)

```ruby
# app/policies/item_policy.rb
class ItemPolicy < ApplicationPolicy
  def show?
    record.user == user || record.published?
  end

  def update?
    record.user == user
  end

  def destroy?
    record.user == user
  end

  class Scope < Scope
    def resolve
      if user.admin?
        scope.all
      else
        scope.where(user: user)
      end
    end
  end
end

# Usage in controller
def show
  @item = Item.find(params[:id])
  authorize @item
end
```
