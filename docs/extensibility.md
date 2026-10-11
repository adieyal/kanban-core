# Extending Kanban Core

Extend the module by supplying an implementation of a constructor-injected port.
Do not import internal models or services and do not create alternate command paths
around `KanbanFacade`.

## Choose the extension point by problem

| I need to... | Use |
| --- | --- |
| store boards in PostgreSQL, Django ORM, etc. | `KanbanRepository` + `KanbanUnitOfWork` |
| integrate application authorization | `PermissionPolicy` |
| enforce organization-specific workflow rules | `WorkflowPolicy` |
| use Elasticsearch or another search engine | `CardSearcher` |
| react to events with automated Kanban actions | `AutomationRunner` (see guide) |
| deliver committed events durably | `KanbanUnitOfWork` / event infrastructure |
| make tests reproducible | injected `Clock` and `IDFactory` |

All extension contracts are available from `kanban.spi`.

## Boundary rule

If an extension needs to mutate a `Board` or `Card` directly, it is probably
crossing the business-module boundary. Extensions receive immutable records,
contexts or facts and return decisions/actions through their contract.

## Guides

- [Persistence and atomic commits](extending/persistence.md)
- [Permissions](extending/permissions.md)
- [Workflow policies](extending/workflow-policy.md)
- [Search](extending/search.md)
- [Automation](extending/automation.md)
- [Card attributes for domain policies](extending/card-attributes.md)
- [Card timestamps and column age limits](extending/card-age.md)
- [External blocking and shared WIP limits](extending/blocking-and-wip.md)
- [Scheduled automation ticks](extending/scheduled-automation.md)
- [Events and external integrations](extending/events.md)
- [Clock and ID generation](extending/deterministic-dependencies.md)
