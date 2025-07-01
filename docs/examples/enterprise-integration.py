#!/usr/bin/env python3
"""
Enterprise Integration Example

This example demonstrates how to integrate the Kanban Core Library with
enterprise systems including:
- LDAP/Active Directory authentication
- Role-based access control (RBAC)
- Audit logging
- Data encryption
- Multi-tenancy support
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass
from enum import Enum
import uuid

from kanban import KanbanFacade, EventBus
from kanban.models import Board, Card, User
from kanban.permissions import PermissionChecker
from kanban.events import Event, EventHandler
from kanban.repositories import RepositoryInterface
from kanban.exceptions import PermissionDeniedError


class Role(Enum):
    """Enterprise roles."""
    SYSTEM_ADMIN = "system_admin"
    ORGANIZATION_ADMIN = "org_admin"
    PROJECT_MANAGER = "project_manager"
    TEAM_MEMBER = "team_member"
    VIEWER = "viewer"
    GUEST = "guest"


@dataclass
class Organization:
    """Organization entity for multi-tenancy."""
    id: str
    name: str
    domain: str
    settings: Dict[str, Any]
    created_at: datetime


@dataclass
class EnterpriseUser:
    """Extended user with enterprise features."""
    id: str
    email: str
    organization_id: str
    department: str
    manager_id: Optional[str]
    roles: List[Role]
    permissions: Set[str]
    active: bool
    last_login: Optional[datetime]


class LDAPAuthenticator:
    """Mock LDAP authentication (replace with real LDAP library)."""
    
    def __init__(self, ldap_server: str, base_dn: str):
        self.ldap_server = ldap_server
        self.base_dn = base_dn
        # In real implementation, initialize LDAP connection
    
    def authenticate(self, username: str, password: str) -> Optional[EnterpriseUser]:
        """Authenticate user against LDAP."""
        # Mock authentication - replace with real LDAP lookup
        if username and password:  # Simplified check
            return EnterpriseUser(
                id=f"ldap_{username}",
                email=f"{username}@enterprise.com",
                organization_id="org_001",
                department="Engineering",
                manager_id="ldap_manager",
                roles=[Role.TEAM_MEMBER],
                permissions=set(),
                active=True,
                last_login=datetime.utcnow()
            )
        return None
    
    def get_user_groups(self, user_id: str) -> List[str]:
        """Get LDAP groups for user."""
        # Mock implementation
        return ["engineering", "project_alpha", "kanban_users"]


class EnterprisePermissionChecker(PermissionChecker):
    """Enterprise permission checker with RBAC."""
    
    def __init__(self, user_repository, role_repository):
        self.user_repo = user_repository
        self.role_repo = role_repository
        
        # Define permission matrix
        self.role_permissions = {
            Role.SYSTEM_ADMIN: {
                "board:*", "card:*", "user:*", "org:*"
            },
            Role.ORGANIZATION_ADMIN: {
                "board:*", "card:*", "user:read", "user:update"
            },
            Role.PROJECT_MANAGER: {
                "board:create", "board:read", "board:update",
                "card:*", "user:read"
            },
            Role.TEAM_MEMBER: {
                "board:read", "card:create", "card:read", 
                "card:update", "user:read"
            },
            Role.VIEWER: {
                "board:read", "card:read", "user:read"
            },
            Role.GUEST: {
                "board:read", "card:read"
            }
        }
    
    def check_permission(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        action: str
    ) -> bool:
        """Check if user has permission for action."""
        user = self.user_repo.get_user(user_id)
        if not user or not user.active:
            return False
        
        # Check direct permissions
        permission = f"{resource_type}:{action}"
        wildcard = f"{resource_type}:*"
        
        # Check user's direct permissions
        if permission in user.permissions or wildcard in user.permissions:
            return True
        
        # Check role-based permissions
        for role in user.roles:
            role_perms = self.role_permissions.get(role, set())
            if permission in role_perms or wildcard in role_perms:
                return True
        
        # Check resource-specific permissions (e.g., board membership)
        if resource_type == "board":
            return self._check_board_permission(user, resource_id, action)
        elif resource_type == "card":
            return self._check_card_permission(user, resource_id, action)
        
        return False
    
    def _check_board_permission(
        self, 
        user: EnterpriseUser, 
        board_id: str, 
        action: str
    ) -> bool:
        """Check board-specific permissions."""
        # Check if user is member of the board
        board_members = self.role_repo.get_board_members(board_id)
        if user.id in board_members:
            member_role = board_members[user.id]
            # Map board roles to permissions
            if member_role == "owner" and action in ["read", "update", "delete"]:
                return True
            elif member_role == "member" and action in ["read", "update"]:
                return True
        
        return False
    
    def _check_card_permission(
        self,
        user: EnterpriseUser,
        card_id: str,
        action: str
    ) -> bool:
        """Check card-specific permissions."""
        # Users can always update cards assigned to them
        card = self.role_repo.get_card(card_id)
        if card and card.assignee == user.id and action == "update":
            return True
        
        # Otherwise, defer to board permissions
        if card:
            return self._check_board_permission(user, card.board_id, action)
        
        return False


class AuditLogger(EventHandler):
    """Comprehensive audit logging for compliance."""
    
    def __init__(self, log_file: str, encryption_key: Optional[bytes] = None):
        self.logger = logging.getLogger("audit")
        handler = logging.FileHandler(log_file)
        handler.setFormatter(
            logging.Formatter('%(asctime)s - %(message)s')
        )
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
        self.encryption_key = encryption_key
    
    def handle(self, event: Event) -> None:
        """Log event with full audit trail."""
        audit_entry = {
            "timestamp": event.timestamp.isoformat(),
            "event_type": event.type,
            "user_id": event.user_id,
            "board_id": event.board_id,
            "session_id": getattr(event, "session_id", None),
            "ip_address": getattr(event, "ip_address", None),
            "user_agent": getattr(event, "user_agent", None),
            "data": self._sanitize_data(event.data)
        }
        
        # Encrypt sensitive data if key provided
        if self.encryption_key:
            audit_entry = self._encrypt_entry(audit_entry)
        
        self.logger.info(json.dumps(audit_entry))
    
    def _sanitize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive information from audit data."""
        sanitized = data.copy()
        
        # Remove sensitive fields
        sensitive_fields = ["password", "token", "api_key", "secret"]
        for field in sensitive_fields:
            if field in sanitized:
                sanitized[field] = "[REDACTED]"
        
        return sanitized
    
    def _encrypt_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt audit entry (simplified - use real encryption in production)."""
        # This is a simplified example - use proper encryption library
        entry_str = json.dumps(entry)
        encrypted = hashlib.sha256(
            entry_str.encode() + self.encryption_key
        ).hexdigest()
        
        return {
            "encrypted": True,
            "data": encrypted,
            "timestamp": entry["timestamp"]
        }


class MultiTenantRepository(RepositoryInterface):
    """Repository with multi-tenancy support."""
    
    def __init__(self, base_repository: RepositoryInterface):
        self.base_repo = base_repository
        self.tenant_context = {}
    
    def set_tenant_context(self, organization_id: str):
        """Set current tenant context."""
        self.tenant_context["current_org"] = organization_id
    
    def _filter_by_tenant(self, items: List[Any], org_field: str = "organization_id") -> List[Any]:
        """Filter items by current tenant."""
        current_org = self.tenant_context.get("current_org")
        if not current_org:
            return items
        
        return [
            item for item in items
            if getattr(item, org_field, None) == current_org
        ]
    
    def create_board(self, board: Board) -> Board:
        # Add organization context
        board.custom_fields["organization_id"] = self.tenant_context.get("current_org")
        return self.base_repo.create_board(board)
    
    def list_boards(self, user_id: str) -> List[Board]:
        boards = self.base_repo.list_boards(user_id)
        # Filter by organization
        return [
            board for board in boards
            if board.custom_fields.get("organization_id") == self.tenant_context.get("current_org")
        ]
    
    # Implement other methods with tenant filtering...


class EnterpriseKanban:
    """Enterprise-ready kanban system."""
    
    def __init__(
        self,
        repository: RepositoryInterface,
        ldap_config: Dict[str, str],
        audit_log_file: str,
        encryption_key: Optional[bytes] = None
    ):
        # Initialize components
        self.ldap = LDAPAuthenticator(
            ldap_config["server"],
            ldap_config["base_dn"]
        )
        
        # Multi-tenant repository
        self.repository = MultiTenantRepository(repository)
        
        # Event bus with audit logging
        self.event_bus = EventBus()
        self.audit_logger = AuditLogger(audit_log_file, encryption_key)
        self.event_bus.subscribe("*", self.audit_logger)
        
        # Permission checker
        self.permission_checker = EnterprisePermissionChecker(
            user_repository=self,  # Simplified - use real user repo
            role_repository=self   # Simplified - use real role repo
        )
        
        # Create facade
        self.kanban = KanbanFacade(
            repository=self.repository,
            event_bus=self.event_bus,
            permission_checker=self.permission_checker
        )
        
        # Session management
        self.sessions: Dict[str, Dict[str, Any]] = {}
    
    def authenticate(self, username: str, password: str) -> Optional[str]:
        """Authenticate user and create session."""
        user = self.ldap.authenticate(username, password)
        if not user:
            return None
        
        # Create session
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            "user": user,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(hours=8),
            "organization_id": user.organization_id
        }
        
        # Set tenant context
        self.repository.set_tenant_context(user.organization_id)
        
        # Log authentication
        self.event_bus.publish(Event(
            type="user.authenticated",
            user_id=user.id,
            board_id=None,
            data={"username": username, "organization": user.organization_id}
        ))
        
        return session_id
    
    def get_user_from_session(self, session_id: str) -> Optional[EnterpriseUser]:
        """Get user from session."""
        session = self.sessions.get(session_id)
        if not session:
            return None
        
        # Check expiration
        if datetime.utcnow() > session["expires_at"]:
            del self.sessions[session_id]
            return None
        
        return session["user"]
    
    # Mock methods for permission checker
    def get_user(self, user_id: str) -> Optional[EnterpriseUser]:
        """Get user by ID (mock implementation)."""
        # In real implementation, fetch from database
        return EnterpriseUser(
            id=user_id,
            email=f"{user_id}@enterprise.com",
            organization_id="org_001",
            department="Engineering",
            manager_id=None,
            roles=[Role.TEAM_MEMBER],
            permissions=set(),
            active=True,
            last_login=datetime.utcnow()
        )
    
    def get_board_members(self, board_id: str) -> Dict[str, str]:
        """Get board members and their roles (mock implementation)."""
        # In real implementation, fetch from database
        return {
            "user1": "owner",
            "user2": "member",
            "user3": "member"
        }
    
    def get_card(self, card_id: str) -> Optional[Card]:
        """Get card by ID (mock implementation)."""
        # In real implementation, fetch from repository
        return None


def demo_enterprise_integration():
    """Demonstrate enterprise features."""
    print("=== Enterprise Integration Demo ===\n")
    
    # Configure enterprise kanban
    from kanban.repositories import InMemoryRepository
    
    ldap_config = {
        "server": "ldap://enterprise.local",
        "base_dn": "dc=enterprise,dc=local"
    }
    
    enterprise_kanban = EnterpriseKanban(
        repository=InMemoryRepository(),
        ldap_config=ldap_config,
        audit_log_file="audit.log",
        encryption_key=b"demo_encryption_key_32_bytes_long"
    )
    
    # Authenticate user
    print("Authenticating user...")
    session_id = enterprise_kanban.authenticate("john.doe", "password123")
    if session_id:
        print(f"Authentication successful. Session: {session_id[:8]}...")
        user = enterprise_kanban.get_user_from_session(session_id)
        print(f"Logged in as: {user.email}")
        print(f"Organization: {user.organization_id}")
        print(f"Roles: {[role.value for role in user.roles]}")
    else:
        print("Authentication failed!")
        return
    
    # Create board with organization context
    print("\nCreating organization board...")
    board = enterprise_kanban.kanban.create_board(
        user.id,
        "Q4 Enterprise Projects"
    )
    print(f"Created board: {board.name}")
    print(f"Organization: {board.custom_fields.get('organization_id')}")
    
    # Add cards with permission checks
    print("\nAdding cards...")
    try:
        card1 = enterprise_kanban.kanban.add_card(
            user.id,
            board.id,
            "To Do",
            "Implement SSO integration",
            description="Add SAML 2.0 support for enterprise SSO",
            labels=["security", "enterprise", "priority:high"]
        )
        print(f"Created: {card1.title}")
        
        card2 = enterprise_kanban.kanban.add_card(
            user.id,
            board.id,
            "To Do",
            "Add compliance reporting",
            description="Generate SOC2 and ISO 27001 compliance reports",
            labels=["compliance", "enterprise"]
        )
        print(f"Created: {card2.title}")
        
    except PermissionDeniedError as e:
        print(f"Permission denied: {e}")
    
    # Demonstrate audit logging
    print("\nChecking audit log...")
    with open("audit.log", "r") as f:
        logs = f.readlines()[-5:]  # Last 5 entries
        print("Recent audit entries:")
        for log in logs:
            entry = json.loads(log.split(" - ", 1)[1])
            print(f"  - {entry['event_type']} by {entry['user_id']}")
    
    # Demonstrate role-based access
    print("\nDemonstrating role-based access...")
    
    # Simulate different user roles
    roles_to_test = [
        (Role.VIEWER, "viewer_user"),
        (Role.TEAM_MEMBER, "member_user"),
        (Role.PROJECT_MANAGER, "pm_user")
    ]
    
    for role, user_id in roles_to_test:
        print(f"\nTesting {role.value} permissions:")
        
        # Mock permission check
        can_create = enterprise_kanban.permission_checker.check_permission(
            user_id, "card", board.id, "create"
        )
        can_read = enterprise_kanban.permission_checker.check_permission(
            user_id, "card", board.id, "read"
        )
        can_delete = enterprise_kanban.permission_checker.check_permission(
            user_id, "board", board.id, "delete"
        )
        
        print(f"  Can create cards: {can_create}")
        print(f"  Can read cards: {can_read}")
        print(f"  Can delete board: {can_delete}")
    
    print("\n\nEnterprise features demonstrated:")
    print("✓ LDAP authentication")
    print("✓ Session management")
    print("✓ Multi-tenancy with organization isolation")
    print("✓ Role-based access control (RBAC)")
    print("✓ Comprehensive audit logging")
    print("✓ Data encryption for audit trails")
    
    print("\nFor production use:")
    print("- Replace mock LDAP with python-ldap or ldap3")
    print("- Use proper encryption (e.g., cryptography library)")
    print("- Implement database-backed repositories")
    print("- Add caching layer (Redis) for sessions")
    print("- Configure log rotation and archival")


if __name__ == "__main__":
    demo_enterprise_integration()