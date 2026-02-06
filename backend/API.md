# API Documentation

**Base URL**: `/api/v1`

## Authentication (`/auth`)

These endpoints handle user registration, authentication, and password management.

| Method | Endpoint | Description | Request Body | Response |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/login` | Login to get access token (cookie/bearer) | `OAuth2PasswordRequestForm` (username=email, password) | `Token` (access_token, token_type) |
| `POST` | `/logout` | Logout (invalidate token/cookie) | - | 204 No Content |
| `POST` | `/register` | Register a new user | [`UserCreate`](#usercreate) | [`UserRead`](#userread) |
| `POST` | `/request-verify-token` | Request email verification token | `{ "email": "user@example.com" }` | 202 Accepted |
| `POST` | `/verify` | Verify email with token | `{ "token": "..." }` | [`UserRead`](#userread) |
| `POST` | `/forgot-password` | Request password reset | `{ "email": "user@example.com" }` | 202 Accepted |
| `POST` | `/reset-password` | Reset password using token | `{ "token": "...", "password": "new_password" }` | 200 OK |

## Users (`/users`)

Endpoints for managing user profiles and retrieving user data.

| Method | Endpoint | Description | Request Body | Response |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/` | List all users (Cached 60s) | - | List[[`UserRead`](#userread)] |
| `GET` | `/me` | Get current logged-in user profile | - | [`UserRead`](#userread) |
| `PATCH` | `/me` | Update current user profile | [`UserUpdate`](#userupdate) | [`UserRead`](#userread) |
| `GET` | `/{id}` | Get user by ID | - | [`UserRead`](#userread) |
| `PATCH` | `/{id}` | Update user by ID (Admin/Owner) | [`UserUpdate`](#userupdate) | [`UserRead`](#userread) |
| `DELETE` | `/{id}` | Delete user by ID (Admin/Owner) | - | 204 No Content |

## Messages (`/messages`)

Endpoints for retrieving user-specific or system messages.

| Method | Endpoint | Description | Auth Required | Response |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/` | Get standard messages | User | `{ "messages": [...], "user": UserRead }` |
| `GET` | `/secrets` | Get secret messages | Superuser | `{ "messages": [...], "user": UserRead }` |
| `GET` | `/error` | Trigger a test error | - | `{ "ok": true }` or Error |

## Service (`/service`)

System monitoring and utility endpoints.

| Method | Endpoint | Description | Response |
| :--- | :--- | :--- | :--- |
| `GET` | `/stats` | Get request statistics per path | `{ "/path": { "count": int, "statuses": {...} } }` |

---

## Schemas

### UserRead

Structure of the user object returned in responses.

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "email": "user@example.com",
  "is_active": true,
  "is_superuser": false,
  "is_verified": false,
  "role": "user",
  "username": {
    "first_name": "John",
    "last_name": "Doe",
    "middle_name": "Smith"
  }
}
```

### UserCreate

Structure for registering a new user.

```json
{
  "email": "user@example.com",
  "password": "strongpassword",
  "is_active": true,
  "is_superuser": false,
  "is_verified": false,
  "role": "user",
  "username": {
    "first_name": "John",  // Required
    "last_name": "Doe",    // Optional
    "middle_name": "Smith" // Optional
  }
}
```

### UserUpdate

Structure for updating a user. All fields are optional.

```json
{
  "password": "newpassword",
  "email": "newemail@example.com",
  "is_active": true,
  "is_superuser": false,
  "is_verified": false,
  "role": "user",
  "username": {
    "first_name": "John",
    "last_name": "Doe",
    "middle_name": "Smith"
  }
}
```
