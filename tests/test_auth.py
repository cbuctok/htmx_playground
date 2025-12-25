"""Tests for the auth module."""
import pytest

from app.auth import (
    User,
    authenticate,
    create_session,
    validate_session,
    get_all_users,
    create_user,
    update_user,
    delete_user,
)


class TestUser:
    """Tests for User dataclass."""

    def test_user_creation(self):
        """Should create User with all fields."""
        user = User(id=1, username="testuser", role="user")
        assert user.id == 1
        assert user.username == "testuser"
        assert user.role == "user"

    def test_is_admin_property_for_admin(self):
        """is_admin should be True for admin role."""
        user = User(id=1, username="admin", role="admin")
        assert user.is_admin is True

    def test_is_admin_property_for_user(self):
        """is_admin should be False for user role."""
        user = User(id=1, username="user", role="user")
        assert user.is_admin is False


class TestAuthenticate:
    """Tests for authenticate function."""

    def test_authenticate_valid_credentials(self, initialized_system_db):
        """Should authenticate with valid credentials."""
        user = authenticate("admin", "password")

        assert user is not None
        assert user.username == "admin"
        assert user.role == "admin"

    def test_authenticate_wrong_password(self, initialized_system_db):
        """Should return None for wrong password."""
        user = authenticate("admin", "wrongpassword")
        assert user is None

    def test_authenticate_unknown_user(self, initialized_system_db):
        """Should return None for unknown user."""
        user = authenticate("unknown", "password")
        assert user is None

    def test_authenticate_returns_user_object(self, initialized_system_db):
        """Should return User object on success."""
        user = authenticate("user1", "password")

        assert isinstance(user, User)
        assert user.id is not None
        assert user.username == "user1"
        assert user.role == "user"


class TestCreateSession:
    """Tests for create_session function."""

    def test_creates_session_token(self, initialized_system_db):
        """Should create a session token."""
        user = User(id=1, username="testuser", role="user")
        token = create_session(user)

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_session_contains_user_info(self, initialized_system_db):
        """Session token should be validatable."""
        user = User(id=1, username="testuser", role="admin")
        token = create_session(user)

        validated_user = validate_session(token)
        assert validated_user is not None
        assert validated_user.username == "testuser"
        assert validated_user.role == "admin"


class TestValidateSession:
    """Tests for validate_session function."""

    def test_validates_valid_token(self, initialized_system_db):
        """Should validate valid token."""
        user = User(id=1, username="testuser", role="user")
        token = create_session(user)

        validated = validate_session(token)
        assert validated is not None
        assert validated.id == user.id
        assert validated.username == user.username
        assert validated.role == user.role

    def test_returns_none_for_invalid_token(self, initialized_system_db):
        """Should return None for invalid token."""
        validated = validate_session("invalid-token")
        assert validated is None

    def test_returns_none_for_empty_token(self, initialized_system_db):
        """Should return None for empty token."""
        validated = validate_session("")
        assert validated is None

    def test_returns_none_for_tampered_token(self, initialized_system_db):
        """Should return None for tampered token."""
        user = User(id=1, username="testuser", role="user")
        token = create_session(user)

        # Tamper with token
        tampered = token + "x"
        validated = validate_session(tampered)
        assert validated is None


class TestGetAllUsers:
    """Tests for get_all_users function."""

    def test_returns_all_users(self, initialized_system_db):
        """Should return all users."""
        users = get_all_users()

        assert len(users) >= 2
        usernames = [u['username'] for u in users]
        assert 'admin' in usernames
        assert 'user1' in usernames

    def test_returns_dict_list(self, initialized_system_db):
        """Should return list of dicts."""
        users = get_all_users()

        assert isinstance(users, list)
        for user in users:
            assert isinstance(user, dict)
            assert 'id' in user
            assert 'username' in user
            assert 'role' in user

    def test_excludes_password(self, initialized_system_db):
        """Should not include password in response."""
        users = get_all_users()

        for user in users:
            assert 'password' not in user

    def test_returns_sorted_by_username(self, initialized_system_db):
        """Should return users sorted by username."""
        users = get_all_users()
        usernames = [u['username'] for u in users]
        assert usernames == sorted(usernames)


class TestCreateUser:
    """Tests for create_user function."""

    def test_creates_user(self, initialized_system_db):
        """Should create a new user."""
        user_id = create_user("newuser", "newpass", "user")

        assert user_id is not None
        assert user_id > 0

    def test_user_can_authenticate(self, initialized_system_db):
        """Created user should be able to authenticate."""
        create_user("newuser", "newpass", "user")

        user = authenticate("newuser", "newpass")
        assert user is not None
        assert user.username == "newuser"

    def test_default_role_is_user(self, initialized_system_db):
        """Default role should be 'user'."""
        create_user("newuser2", "newpass")

        user = authenticate("newuser2", "newpass")
        assert user.role == "user"

    def test_can_create_admin(self, initialized_system_db):
        """Should be able to create admin user."""
        create_user("newadmin", "adminpass", "admin")

        user = authenticate("newadmin", "adminpass")
        assert user.role == "admin"
        assert user.is_admin is True

    def test_duplicate_username_raises_error(self, initialized_system_db):
        """Should raise error for duplicate username."""
        create_user("duplicate", "pass1")

        with pytest.raises(Exception):  # sqlite3.IntegrityError
            create_user("duplicate", "pass2")


class TestUpdateUser:
    """Tests for update_user function."""

    def test_update_username(self, initialized_system_db):
        """Should update username."""
        user_id = create_user("oldname", "pass", "user")

        update_user(user_id, username="newname")

        # Old username should not work
        assert authenticate("oldname", "pass") is None
        # New username should work
        user = authenticate("newname", "pass")
        assert user is not None

    def test_update_password(self, initialized_system_db):
        """Should update password."""
        user_id = create_user("passtest", "oldpass", "user")

        update_user(user_id, password="newpass")

        # Old password should not work
        assert authenticate("passtest", "oldpass") is None
        # New password should work
        user = authenticate("passtest", "newpass")
        assert user is not None

    def test_update_role(self, initialized_system_db):
        """Should update role."""
        user_id = create_user("roletest", "pass", "user")

        update_user(user_id, role="admin")

        user = authenticate("roletest", "pass")
        assert user.role == "admin"

    def test_update_multiple_fields(self, initialized_system_db):
        """Should update multiple fields at once."""
        user_id = create_user("multitest", "oldpass", "user")

        update_user(user_id, username="multi2", password="newpass", role="admin")

        user = authenticate("multi2", "newpass")
        assert user is not None
        assert user.role == "admin"

    def test_update_with_no_fields_does_nothing(self, initialized_system_db):
        """Update with no fields should not raise error."""
        user_id = create_user("nochange", "pass", "user")

        update_user(user_id)  # No fields to update

        user = authenticate("nochange", "pass")
        assert user is not None


class TestDeleteUser:
    """Tests for delete_user function."""

    def test_deletes_user(self, initialized_system_db):
        """Should delete user."""
        user_id = create_user("todelete", "pass", "user")

        delete_user(user_id)

        user = authenticate("todelete", "pass")
        assert user is None

    def test_delete_removes_from_list(self, initialized_system_db):
        """Deleted user should not appear in list."""
        user_id = create_user("todelete2", "pass", "user")

        delete_user(user_id)

        users = get_all_users()
        usernames = [u['username'] for u in users]
        assert "todelete2" not in usernames

    def test_delete_nonexistent_user_does_not_raise(self, initialized_system_db):
        """Deleting nonexistent user should not raise error."""
        delete_user(99999)  # Should not raise
