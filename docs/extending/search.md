# Search

Use `CardSearcher` when the default in-memory search is insufficient.

The search port receives detached `SearchContext` / `SearchCard` values and returns
card IDs. It does not receive or mutate domain cards.

```python
class ElasticsearchCardSearcher:
    def __init__(self, client):
        self.client = client

    def search(self, context, **filters) -> tuple[str, ...]:
        # Query your search/read model and return matching card IDs.
        ...
```

Inject it with `searcher=ElasticsearchCardSearcher(es)`.

Search is a read concern. If you maintain an external index, update it from
committed events rather than by mutating Kanban Core state.
