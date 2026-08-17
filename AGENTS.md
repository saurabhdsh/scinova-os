# Agent Guidelines

## Roles
- **Implementer:** Makes minimal, focused code changes
- **Reviewer:** Checks token scope and security before large reads
- **Tester:** Runs tests only in test dirs

## Workflow
1. Confirm task scope and target files
2. Read AGENTS.md and CLAUDE.md
3. Load only relevant source files
4. Implement with existing patterns
5. Verify no secrets or build artifacts in context

## Constraints
- 2 critical-risk files — never include
- 1 high-risk files — exclude unless explicitly needed
- Prefer `@path/to/file` style references in prompts
