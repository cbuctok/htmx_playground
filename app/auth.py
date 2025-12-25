"""Authentication system (demo/insecure)."""
from typing import Optional
from dataclasses import dataclass

from itsdangerous import URLSafeSerializer

from app.config import SECRET_KEY
from app.database import get_db_manager


@dataclass
class User:
    """User data class."""
    id: int
    username: str
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role == 'admin'


# Session serializer
serializer = URLSafeSerializer(SECRET_KEY)


def authenticate(username: str, password: str) -> Optional[User]:
    """
    Authenticate a user with plaintext password.

    WARNING: Insecure - demo only!

    Returns:
        User object if authenticated, None otherwise
    """
    db = get_db_manager()

    with db.get_system_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, password, role FROM users WHERE username = ?",
            (username,)
        )
        row = cursor.fetchone()

        if row and row['password'] == password:
            return User(
                id=row['id'],
                username=row['username'],
                role=row['role']
            )

    return None


def create_session(user: User) -> str:
    """Create a session token for a user."""
    return serializer.dumps({
        'user_id': user.id,
        'username': user.username,
        'role': user.role,
    })


def validate_session(token: str) -> Optional[User]:
    """
    Validate a session token and return the user.

    Returns:
        User object if valid, None otherwise
    """
    try:
        data = serializer.loads(token)
        return User(
            id=data['user_id'],
            username=data['username'],
            role=data['role']
        )
    except Exception:
        return None


def get_all_users() -> list[dict]:
    """Get all users."""
    db = get_db_manager()

    with db.get_system_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, role FROM users ORDER BY username")
        return [dict(row) for row in cursor.fetchall()]


def create_user(username: str, password: str, role: str = 'user') -> int:
    """Create a new user."""
    db = get_db_manager()

    with db.get_system_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            (username, password, role)
        )
        conn.commit()
        return cursor.lastrowid


def update_user(user_id: int, username: str = None, password: str = None, role: str = None):
    """Update a user."""
    db = get_db_manager()

    updates = []
    params = []

    if username:
        updates.append("username = ?")
        params.append(username)
    if password:
        updates.append("password = ?")
        params.append(password)
    if role:
        updates.append("role = ?")
        params.append(role)

    if not updates:
        return

    params.append(user_id)

    with db.get_system_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE users SET {', '.join(updates)} WHERE id = ?",
            params
        )
        conn.commit()


def delete_user(user_id: int):
    """Delete a user."""
    db = get_db_manager()

    with db.get_system_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
