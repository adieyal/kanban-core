# Permissions

Use `PermissionPolicy` when your application already has users, roles or an
authorization service.

```python
class ApplicationPermissions:
    def __init__(self, roles):
        self.roles = roles

    def has_permission(self, user_id, context, permission) -> bool:
        role = self.roles.role_for(user_id, context.board_id)
        if role == "owner":
            return True
        if role == "viewer":
            return permission.name == "VIEW_BOARD"
        return role == "member"
```

Inject it at composition:

```python
kanban = KanbanFacade(
    repository,
    uow,
    permission_checker=ApplicationPermissions(roles),
)
```

A permission policy answers: **may this user perform this kind of operation on this
board?** It should not mutate Kanban state or implement workflow semantics.
