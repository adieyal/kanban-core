# Events and external integrations

Kanban operations produce events useful for audit trails, notifications, read
models and integrations.

## Reference delivery

`EventBus` is a simple in-process reference adapter:

```python
events = EventBus()
events.subscribe("card.moved", lambda event: print(event.data))
```

## Durable production delivery

If event loss is unacceptable, implement `KanbanUnitOfWork` so the state change and
an outbox record commit in the same database transaction. A separate relay can
publish to Kafka, RabbitMQ, webhooks or another destination.

## Event envelope

Important metadata includes:

- `id` — suitable as an idempotency key;
- `type` — routing key;
- `schema_version` — payload compatibility;
- `correlation_id` — one facade operation and its automation chain;
- `causation_id` — event causality;
- `aggregate_version` — committed board version.
