"""Level 2: Build phase integration tests — real SDK calls.

Runs the Builder agent with perfect prior artifacts and validates the
produced source code has the expected structure.

WARNING: Build tests take 5-15 minutes each and use Claude Pro subscription.
Run selectively: python3 -m pytest tests/stress/test_phase_build.py::TestBuildPhaseSimple -v -m stress

Run all: python3 -m pytest tests/stress/test_phase_build.py -v -m stress
"""

import re
import pytest
from pathlib import Path

from agent.state import Phase
from agent.phases import run_phase
from agent.validators import validate_phase_output

from .conftest import make_state, make_progress, populate_project


pytestmark = pytest.mark.stress


class TestBuildPhaseSimple:
    """Build a simple todo app — should complete in one attempt (~3-5 min)."""

    async def test_produces_source_code(self, simple_project):
        """Builder should create src/ directory with .tsx files."""
        populate_project(simple_project, {
            "STACK_DECISION.md": "analysis/stack_decision_supabase.md",
        })
        # Create a minimal design for a todo app
        (simple_project / "DESIGN.md").write_text("""---
stack_id: nextjs-supabase
tables: 2
routes: 4
---
# DESIGN.md — Todo App

## Data Model (Supabase)

```sql
create table todos (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  title text not null,
  completed boolean default false,
  created_at timestamptz default now()
);

alter table todos enable row level security;
create policy "Users own todos" on todos for all using (auth.uid() = user_id);
```

## Routes

| Route | Page | Auth |
|-------|------|------|
| / | Landing page | No |
| /login | Login form | No |
| /signup | Signup form | No |
| /dashboard | Todo list with add/complete/delete | Yes |

## Components
- TodoList — displays todos with checkboxes
- TodoForm — input + submit button
- AuthForm — login/signup form

## Auth
- Supabase Auth with email/password
- middleware.ts protects /dashboard
""")

        state = make_state(
            idea="Build a simple todo app with user authentication",
            stack_id="nextjs-supabase",
            phase=Phase.REVIEW,
        )

        call, validation = await run_phase(
            Phase.BUILD, state, simple_project, make_progress(),
            timeout_override=900,  # 15 min for simple app
        )

        assert call.success, f"Build failed: {call.error}"

        # Verify source code exists
        build_val = validate_phase_output(Phase.BUILD, simple_project)
        assert build_val.passed, f"Build validation failed: {build_val.messages}"

        # Verify key files
        assert (simple_project / "package.json").exists(), "Missing package.json"

        # Verify at least some .tsx files were created
        tsx_files = list(simple_project.rglob("*.tsx"))
        assert len(tsx_files) >= 3, f"Expected 3+ .tsx files, found {len(tsx_files)}"


class TestBuildPhaseComplex:
    """Build the stress test SaaS — may take 15-25 min with scaffold split."""

    async def test_produces_prisma_schema(self, project_with_review):
        """Builder should create prisma/schema.prisma with models from DESIGN.md."""
        state = make_state(
            idea="Build a multi-tenant SaaS for professional services teams",
            stack_id="nextjs-prisma",
            phase=Phase.REVIEW,
        )

        call, validation = await run_phase(
            Phase.BUILD, state, project_with_review, make_progress(),
            timeout_override=1500,  # 25 min for complex app
        )

        assert call.success, f"Build failed: {call.error}"

        # Verify Prisma schema
        schema_path = project_with_review / "prisma" / "schema.prisma"
        if schema_path.exists():
            content = schema_path.read_text()
            model_count = len(re.findall(r'^model\s+\w+', content, re.MULTILINE))
            assert model_count >= 5, f"Expected 5+ Prisma models, found {model_count}"

        # Verify source files
        tsx_files = list(project_with_review.rglob("*.tsx"))
        assert len(tsx_files) >= 10, f"Expected 10+ .tsx files, found {len(tsx_files)}"
