# Prompt Templates

## Scoped feature (Docker · Node · React · Express)
```
Implement [FEATURE] in [MODULE_PATH] only.
Read: [FILE_LIST]
Do not scan node_modules, dist, or logs.
Match existing patterns in the module.
```

## Bug fix
```
Fix [BUG] in [FILE].
Relevant log excerpt (paste max 50 lines below):
---
[paste]
---
Do not read full log directories.
```

## Refactor
```
Refactor [COMPONENT] in [PATH].
Phase 1: analysis of [FILE] only.
Phase 2: implementation after confirmation.
```

## Test generation
```
Add tests for [UNIT] in [TEST_PATH].
Mirror patterns from [EXISTING_TEST].
```
