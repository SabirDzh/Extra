# Project Documentation

This document provides an overview of the file structure and purpose of each module in the FastAPI Users Intro project.

## Root Directory

### Application Entry Points
- **`main.py`**: The main entry point for the FastAPI application during development. It initializes the app using `create_app`, includes API and View routers, and runs the server using `uvicorn` if executed directly.
- **`run_main.py`**: Entry point for running the application in a production-like environment using a custom `Gunicorn` application wrapper.
- **`create_fastapi_app.py`**: Contains the `create_app` factory function. It handles:
  - FastAPI app initialization.
  - Lifespan events (Redis/Cache startup and shutdown).
  - Middleware registration.
  - Exception handlers registration.
  - SQLAdmin integration.
- **`alembic.ini`**: Configuration file for Alembic database migrations.
- **`.env.template`**: Template file listing required environment variables for the application.

## Core Module (`core/`)

The `core` directory contains the foundational elements of the application.

### Configuration
- **`core/config.py`**: Defines the application settings using `pydantic-settings`. It loads variables from `.env` files and structures them into categories like `RunConfig`, `GunicornConfig`, `DatabaseConfig`, `ApiPrefix`, etc.

### Models (`core/models/`)
- **`core/models/base.py`**: Defines the `Base` class for SQLAlchemy models with automatic table naming conventions (CamelCase to snake_case).
- **`core/models/db_helper.py`**: Manages the asynchronous database engine and session creation (`DatabaseHelper`).
- **`core/models/user.py`**: Defines the `User` model, inheriting from `SQLAlchemyBaseUserTable` and `IdIntPkMixin`. It maps to the `users` table.
- **`core/models/access_token.py`**: Defines the `AccessToken` model for database-backed session tokens.
- **`core/models/mixins/id_int_pk.py`**: A mixin that adds an integer primary key `id` to models.

### Authentication (`core/authentication/`)
- **`core/authentication/fastapi_users.py`**: Initializes the `FastAPIUsers` instance with the user manager and authentication backend. Exports `current_active_user` and `current_active_superuser` dependencies.
- **`core/authentication/user_manager.py`**: Customizes the `UserManager` logic (likely for registration, verification workflows).
- **`core/authentication/transport.py`**: Configures authentication transports (e.g., Cookies, Bearer tokens).

### Schemas (`core/schemas/`)
- **`core/schemas/user.py`**: Pydantic models for User serialization and deserialization (`UserRead`, `UserCreate`, `UserUpdate`).

### Types (`core/types/`)
- **`core/types/user_id.py`**: Defines the type alias for User IDs (e.g., `int`).

### Gunicorn (`core/gunicorn/`)
- **`core/gunicorn/application.py`**: Custom Gunicorn application class to run the FastAPI app programmatically.
- **`core/gunicorn/app_options.py`**: Helper to configure Gunicorn options.
- **`core/gunicorn/logger.py`**: Logging configuration for Gunicorn.

## API Module (`api/`)

Contains the route definitions and API-specific logic.

### API v1 (`api/api_v1/`)
- **`api/api_v1/users.py`**: User management endpoints. Includes a cached list of users and mounts `fastapi_users` router for user updates.
- **`api/api_v1/auth.py`**: Authentication endpoints (Login, Logout, Register, Verify, Reset Password).
- **`api/api_v1/messages.py`**: Example endpoints demonstrating protected routes for authenticated users and superusers.
- **`api/api_v1/service.py`**: Service-related endpoints (if any).

### Dependencies (`api/dependencies/`)
- **`api/dependencies/authentication/`**:
  - **`backend.py`**: Configures the `AuthenticationBackend` combining transport and strategy.
  - **`strategy.py`**: Defines the strategy (e.g., Database strategy for access tokens).
  - **`users.py`**: Dependency to get the user database adapter.
  - **`user_manager.py`**: Dependency to get the `UserManager` instance.

### Webhooks (`api/webhooks/`)
- **`api/webhooks/user.py`**: Handlers for user-related webhooks.

## Views Module (`views/` & `templates/`)

Handles server-side rendered pages using Jinja2.

- **`views/home.py`**: Renders the home page (`home.html`).
- **`views/verification.py`**: Renders the email verification page (`verification.html`).
- **`jinja_templates.py`**: Initializes the `Jinja2Templates` instance pointing to the `templates` directory.
- **`templates/`**: HTML files for the views and emails.

## Admin Module (`admin/`)

Integrates `sqladmin` for a dashboard interface.

- **`admin/user.py`**: Defines `UserAdmin` model view, customizing column display and password hashing on change.
- **`admin/access_token.py`**: Admin view for Access Tokens.
- **`admin/converter.py`**: Helpers for admin data conversion.

## Actions (`actions/`)

Scripts for administrative tasks.

- **`actions/create_superuser.py`**: An async script to create a superuser directly in the database using the `UserManager`.

## Mailing (`mailing/`)

- **`mailing/send_email.py`**: Utilities for sending emails via SMTP (using `aiosmtplib`).
- **`mailing/send_verification_email.py`**: Logic to send account verification emails.

## Middlewares (`middlewares/`)

- **`middlewares/requests_count_middleware.py`**: A middleware to count requests and track response status codes by path.
- **`middlewares/middlewares.py`**: function to register all middlewares to the app.

## Utils (`utils/`)

General utility functions.

- **`utils/case_converter.py`**: Functions like `camel_case_to_snake_case` used for DB table naming.

## Alembic (`alembic/`)

Database migration scripts.

- **`alembic/env.py`**: Configures the Alembic environment, connecting it to the app's metadata and database URL.
- **`alembic/versions/`**: Contains the individual migration scripts (e.g., creating users and access tokens tables).
