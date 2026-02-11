"""Feature templates for design enhancement.

These templates provide Prisma models, API routes, and component definitions
for common Monday.com-style features that can be added to existing designs.
"""

BOARD_VIEWS_TEMPLATE = """
## Board Views Enhancement

Add multiple view types for tasks and projects, similar to Monday.com.

### Data Models

```prisma
model TaskDependency {
  id           String         @id @default(cuid())
  taskId       String
  dependsOnId  String
  type         DependencyType @default(FINISH_TO_START)
  lagDays      Int            @default(0)
  createdAt    DateTime       @default(now())

  task         Task           @relation("TaskDependencies", fields: [taskId], references: [id], onDelete: Cascade)
  dependsOn    Task           @relation("DependentTasks", fields: [dependsOnId], references: [id], onDelete: Cascade)

  @@unique([taskId, dependsOnId])
  @@index([taskId])
  @@index([dependsOnId])
}

model UserViewPreference {
  id             String   @id @default(cuid())
  userId         String
  projectId      String
  preferredView  ViewType @default(KANBAN)
  viewConfig     Json?    // Stores column widths, sort order, filters, etc.
  updatedAt      DateTime @updatedAt

  user           User     @relation(fields: [userId], references: [id], onDelete: Cascade)
  project        Project  @relation(fields: [projectId], references: [id], onDelete: Cascade)

  @@unique([userId, projectId])
  @@index([userId])
  @@index([projectId])
}

enum ViewType {
  KANBAN     // Column-based drag-drop (existing)
  TIMELINE   // Gantt chart with dependencies
  CALENDAR   // Calendar grid by due date
  TABLE      // Spreadsheet-style inline editing
}

enum DependencyType {
  FINISH_TO_START   // Task B starts when Task A finishes (most common)
  START_TO_START    // Task B starts when Task A starts
  FINISH_TO_FINISH  // Task B finishes when Task A finishes
  START_TO_FINISH   // Task B finishes when Task A starts (rare)
}
```

### API Routes

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/projects/:id/tasks/timeline | Get tasks with dependencies for timeline view |
| POST | /api/tasks/:id/dependencies | Add a dependency to a task |
| DELETE | /api/tasks/:id/dependencies/:depId | Remove a dependency |
| PUT | /api/projects/:id/view-preference | Save user's view preference |
| GET | /api/projects/:id/view-preference | Get user's view preference |

### Components

```
Views/
├── ViewSwitcher.tsx           # Toggle between view types
├── TimelineView/
│   ├── TimelineView.tsx       # Main Gantt chart container
│   ├── TimelineHeader.tsx     # Date range header
│   ├── TimelineRow.tsx        # Single task row with bar
│   ├── DependencyLine.tsx     # Arrow connecting dependent tasks
│   └── TimelineControls.tsx   # Zoom, scroll, date range
├── CalendarView/
│   ├── CalendarView.tsx       # Main calendar container
│   ├── CalendarGrid.tsx       # Month/week/day grid
│   ├── CalendarTask.tsx       # Task card in calendar
│   └── CalendarControls.tsx   # Month/week/day toggle, navigation
├── TableView/
│   ├── TableView.tsx          # Main table container
│   ├── TableHeader.tsx        # Sortable column headers
│   ├── TableRow.tsx           # Editable task row
│   ├── TableCell.tsx          # Inline editable cell
│   └── TableFilters.tsx       # Column filters
└── DependencyEditor.tsx       # Modal to manage task dependencies
```

### User Flows

1. **Switch View**: User clicks ViewSwitcher → selects new view → preference saved → view renders
2. **Add Dependency**: User clicks dependency icon → DependencyEditor opens → user selects dependent task → dependency created
3. **Timeline Drag**: User drags task bar → dates update → connected dependencies adjust
"""

DASHBOARDS_TEMPLATE = """
## Dashboards Enhancement

Add customizable dashboard system with widgets and charts.

### Data Models

```prisma
model Dashboard {
  id             String   @id @default(cuid())
  name           String
  description    String?
  organizationId String
  createdById    String
  isDefault      Boolean  @default(false)
  layout         Json?    // Grid layout configuration
  createdAt      DateTime @default(now())
  updatedAt      DateTime @updatedAt

  organization   Organization @relation(fields: [organizationId], references: [id], onDelete: Cascade)
  createdBy      User         @relation(fields: [createdById], references: [id])
  widgets        Widget[]

  @@index([organizationId])
  @@index([createdById])
}

model Widget {
  id          String     @id @default(cuid())
  dashboardId String
  type        WidgetType
  title       String
  config      Json?      // Widget-specific configuration
  x           Int        @default(0)  // Grid position X
  y           Int        @default(0)  // Grid position Y
  width       Int        @default(2)  // Grid width (1-4)
  height      Int        @default(2)  // Grid height (1-4)
  createdAt   DateTime   @default(now())
  updatedAt   DateTime   @updatedAt

  dashboard   Dashboard  @relation(fields: [dashboardId], references: [id], onDelete: Cascade)

  @@index([dashboardId])
}

enum WidgetType {
  TASKS_BY_STATUS      // Pie/donut chart
  TASKS_BY_ASSIGNEE    // Bar chart
  TASKS_BY_PRIORITY    // Bar chart
  OVERDUE_TASKS        // List with count badge
  VELOCITY_CHART       // Line chart over time
  BURNDOWN_CHART       // Line chart for sprints
  ACTIVITY_FEED        // Recent activity stream
  MY_TASKS             // Personal task list
  PROJECT_PROGRESS     // Progress bars per project
  METRIC_CARD          // Single number with label
}
```

### API Routes

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/dashboards | List dashboards for organization |
| POST | /api/dashboards | Create new dashboard |
| GET | /api/dashboards/:id | Get dashboard with widgets |
| PUT | /api/dashboards/:id | Update dashboard (name, layout) |
| DELETE | /api/dashboards/:id | Delete dashboard |
| POST | /api/dashboards/:id/widgets | Add widget to dashboard |
| PUT | /api/dashboards/:id/widgets/:widgetId | Update widget |
| DELETE | /api/dashboards/:id/widgets/:widgetId | Remove widget |
| GET | /api/dashboards/:id/data | Get aggregated data for all widgets |

### Components

```
Dashboards/
├── DashboardList.tsx          # List of dashboards
├── DashboardView.tsx          # Main dashboard container
├── DashboardGrid.tsx          # Drag-and-drop grid layout
├── DashboardHeader.tsx        # Name, edit mode toggle
├── WidgetContainer.tsx        # Widget wrapper with resize/drag
├── WidgetLibrary.tsx          # Widget picker modal
├── widgets/
│   ├── PieChartWidget.tsx     # For status/priority distribution
│   ├── BarChartWidget.tsx     # For assignee/category breakdown
│   ├── LineChartWidget.tsx    # For velocity/burndown
│   ├── ListWidget.tsx         # For overdue/my tasks
│   ├── ActivityWidget.tsx     # Activity feed
│   ├── MetricWidget.tsx       # Single number display
│   └── ProgressWidget.tsx     # Progress bars
└── charts/
    ├── PieChart.tsx           # Reusable pie chart
    ├── BarChart.tsx           # Reusable bar chart
    └── LineChart.tsx          # Reusable line chart
```

### User Flows

1. **Create Dashboard**: User clicks "New Dashboard" → enters name → empty grid appears → user adds widgets
2. **Add Widget**: User clicks "Add Widget" → WidgetLibrary opens → user selects type → widget appears in grid
3. **Customize Widget**: User clicks widget settings → config modal opens → user selects data source, filters
4. **Rearrange**: User drags widget → grid reflows → layout auto-saved
"""

AUTOMATIONS_TEMPLATE = """
## Automations Enhancement

Add workflow automation system with triggers, conditions, and actions.

### Data Models

```prisma
model Automation {
  id             String            @id @default(cuid())
  name           String
  description    String?
  organizationId String
  projectId      String?           // Optional: scope to specific project
  trigger        AutomationTrigger
  conditions     Json?             // Array of condition objects
  actions        Json              // Array of action objects
  enabled        Boolean           @default(true)
  runCount       Int               @default(0)
  lastRunAt      DateTime?
  createdById    String
  createdAt      DateTime          @default(now())
  updatedAt      DateTime          @updatedAt

  organization   Organization      @relation(fields: [organizationId], references: [id], onDelete: Cascade)
  project        Project?          @relation(fields: [projectId], references: [id], onDelete: Cascade)
  createdBy      User              @relation(fields: [createdById], references: [id])
  logs           AutomationLog[]

  @@index([organizationId])
  @@index([projectId])
  @@index([trigger])
  @@index([enabled])
}

model AutomationLog {
  id           String           @id @default(cuid())
  automationId String
  triggeredAt  DateTime         @default(now())
  status       AutomationStatus
  entityType   String           // "task", "project", etc.
  entityId     String
  triggerData  Json?            // Data that triggered the automation
  actionsTaken Json?            // Record of actions performed
  error        String?          // Error message if failed
  duration     Int?             // Execution time in ms

  automation   Automation       @relation(fields: [automationId], references: [id], onDelete: Cascade)

  @@index([automationId])
  @@index([triggeredAt])
  @@index([status])
}

enum AutomationTrigger {
  TASK_CREATED
  TASK_UPDATED
  STATUS_CHANGED
  ASSIGNEE_CHANGED
  PRIORITY_CHANGED
  DUE_DATE_APPROACHING   // Configurable days before
  DUE_DATE_PASSED
  TASK_COMPLETED
  COMMENT_ADDED
  PROJECT_CREATED
  MEMBER_ADDED
}

enum AutomationStatus {
  SUCCESS
  FAILED
  SKIPPED      // Conditions not met
  PARTIAL      // Some actions succeeded
}
```

### Condition Schema

```json
{
  "conditions": [
    {
      "field": "status",
      "operator": "equals",
      "value": "IN_PROGRESS"
    },
    {
      "field": "priority",
      "operator": "in",
      "value": ["HIGH", "URGENT"]
    },
    {
      "field": "dueDate",
      "operator": "within_days",
      "value": 3
    }
  ],
  "logic": "AND"  // "AND" or "OR"
}
```

### Action Schema

```json
{
  "actions": [
    {
      "type": "change_status",
      "config": { "newStatus": "IN_REVIEW" }
    },
    {
      "type": "assign_to",
      "config": { "userId": "user_id" | "CREATOR" | "MANAGER" }
    },
    {
      "type": "notify_user",
      "config": { "userId": "user_id", "message": "Task needs attention" }
    },
    {
      "type": "add_comment",
      "config": { "content": "Automatically moved to review" }
    },
    {
      "type": "set_priority",
      "config": { "priority": "URGENT" }
    },
    {
      "type": "create_task",
      "config": { "title": "Follow up on {{task.title}}", "assigneeId": "..." }
    }
  ]
}
```

### API Routes

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/automations | List automations for organization |
| POST | /api/automations | Create new automation |
| GET | /api/automations/:id | Get automation details |
| PUT | /api/automations/:id | Update automation |
| DELETE | /api/automations/:id | Delete automation |
| POST | /api/automations/:id/toggle | Enable/disable automation |
| POST | /api/automations/:id/test | Test run automation on sample data |
| GET | /api/automations/:id/logs | Get execution logs |
| POST | /api/internal/automations/trigger | Internal: process automation triggers |

### Components

```
Automations/
├── AutomationList.tsx         # List of automations with enable toggles
├── AutomationBuilder.tsx      # Main automation editor
├── AutomationCard.tsx         # Summary card for list view
├── TriggerSelector.tsx        # Dropdown to select trigger type
├── ConditionBuilder.tsx       # Add/remove conditions
├── ConditionRow.tsx           # Single condition (field, operator, value)
├── ActionBuilder.tsx          # Add/remove actions
├── ActionRow.tsx              # Single action configuration
├── ActionConfigurator.tsx     # Action-specific config forms
├── AutomationLogs.tsx         # Execution history table
├── AutomationLogDetail.tsx    # Single log entry detail
└── AutomationPreview.tsx      # Preview automation flow visually
```

### User Flows

1. **Create Automation**: User clicks "New Automation" → selects trigger → adds conditions (optional) → adds actions → saves
2. **Test Automation**: User clicks "Test" → selects sample entity → automation runs in preview mode → results shown
3. **View Logs**: User clicks automation → logs tab → sees recent executions with status
4. **Debug Failed**: User clicks failed log → sees error details and trigger data
"""


FEATURE_TEMPLATES = {
    "board-views": BOARD_VIEWS_TEMPLATE,
    "dashboards": DASHBOARDS_TEMPLATE,
    "automations": AUTOMATIONS_TEMPLATE,
}


def get_feature_template(feature: str) -> str:
    """Get the template for a specific feature.

    Args:
        feature: Feature name (board-views, dashboards, automations)

    Returns:
        Template string or empty string if not found
    """
    return FEATURE_TEMPLATES.get(feature, "")


def get_all_feature_templates() -> dict[str, str]:
    """Get all available feature templates.

    Returns:
        Dictionary mapping feature names to their templates
    """
    return dict(FEATURE_TEMPLATES)
