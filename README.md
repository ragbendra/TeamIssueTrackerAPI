# Team Issue Tracker API

[![CI](https://github.com/ragbendra/TeamIssueTrackerAPI/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ragbendra/TeamIssueTrackerAPI/actions/workflows/ci.yml)

Team Issue Tracker API is a Django REST Framework application for managing organizations, projects, tasks, and comments. Data access is organization-scoped: users can see and modify resources only when their membership and role allow it.

## At a glance

- **Framework:** Django 6.0.7 and Django REST Framework 3.17.1
- **Database:** PostgreSQL
- **Authentication:** JSON Web Tokens with `djangorestframework-simplejwt`
- **Filtering:** `django-filter`
- **Local orchestration:** Docker Compose with PostgreSQL 16 and Django's development server
- **API base path:** `/api/`

The repository contains the `core` Django project and the `issues` application. The Docker image uses Python 3.12.

## Data model

| Model | Key fields and relationships |
| --- | --- |
| `Organization` | `name`; has an `owner` user. |
| `Membership` | Connects a `user` to an `organization` with role `OWNER`, `ADMIN`, or `MEMBER`; `(organization, user)` is unique. |
| `Project` | Belongs to an `organization`; has `name` and `created_at`. |
| `Task` | Belongs to a `project`; has `title`, `description`, `status`, `priority`, optional `assignee`, `created_by`, and `created_at`. |
| `Comment` | Belongs to a `task`; has `author`, `body`, and `created_at`. |

Task statuses are `TODO`, `IN_PROGRESS`, and `DONE`. Task priorities are `LOW`, `MED`, and `HIGH`. An assignee must be a member of the task's organization, or `null`.

Deleting an organization cascades through its memberships, projects, tasks, and comments.

## Roles and permissions

Registration is open. A newly registered user has no organization until they create one. Creating an organization automatically creates an `OWNER` membership for its creator.

The API does not provide a membership-management endpoint. A superuser assigns `ADMIN` and `MEMBER` roles through Django admin at `/admin/`; the API-created owner membership is the initial role available through the API workflow.

| Resource | Read | Create | Update | Delete |
| --- | --- | --- | --- | --- |
| Organization | Organization members | Any authenticated user; creator becomes `OWNER` | Organization `OWNER` or `ADMIN` | `OWNER` only |
| Project | Organization members | Organization `OWNER` or `ADMIN` | Organization `OWNER` or `ADMIN` | Organization `OWNER` or `ADMIN` |
| Task | Organization members | Any member of the project organization | Organization `OWNER`/`ADMIN`, task creator, or assignee | Same as update |
| Task close action | Not applicable | Not applicable | Same as task update | Not applicable |
| Comment | Organization members | Any member of the task organization | Not allowed | Comment author or organization `OWNER`/`ADMIN` |

Additional authorization rules:

- A plain member and a non-member receive `403 Forbidden` when creating a project.
- A project's organization is immutable after creation.
- Cross-organization detail requests are hidden by the queryset and return `404 Not Found`.
- Invalid assignees return `400 Bad Request`.

## API reference

The examples use `http://127.0.0.1:8000`. Protected requests require:

```text
Authorization: Bearer <access-token>
```

### Authentication routes

| Method | Route | Authentication | Purpose |
| --- | --- | --- | --- |
| `POST` | `/api/auth/register/` | Open | Register a user with `username` and `password`. |
| `POST` | `/api/auth/token/` | Open | Obtain an access token and refresh token. |
| `POST` | `/api/auth/token/refresh/` | Open | Exchange a refresh token for a new access token. |

### Resource routes

| Method | Route | Authentication | Purpose |
| --- | --- | --- | --- |
| `GET`, `POST` | `/api/organizations/` | Required | List accessible organizations or create one. List parameters: `page`, `page_size`. |
| `GET`, `PUT`, `PATCH`, `DELETE` | `/api/organizations/{id}/` | Required | Read, update, or delete one organization. |
| `GET`, `POST` | `/api/projects/` | Required | List accessible projects or create one. List parameters: `page`, `page_size`. |
| `GET`, `PUT`, `PATCH`, `DELETE` | `/api/projects/{id}/` | Required | Read, update, or delete one project. |
| `GET` | `/api/projects/{id}/tasks/` | Required | List all tasks for one accessible project. This response is not paginated. |
| `GET`, `POST` | `/api/tasks/` | Required | List or create tasks. |
| `GET`, `PUT`, `PATCH`, `DELETE` | `/api/tasks/{id}/` | Required | Read, update, or delete one task. |
| `POST` | `/api/tasks/{id}/close/` | Required | Set a task's status to `DONE`. |
| `GET`, `POST` | `/api/comments/` | Required | List or create comments. List parameters: `page`, `page_size`. |
| `GET`, `DELETE` | `/api/comments/{id}/` | Required | Read or delete one comment. Comment update methods are not enabled. |

### Task list parameters

`GET /api/tasks/` supports the following query parameters:

| Parameter | Values or behavior |
| --- | --- |
| `status` | `TODO`, `IN_PROGRESS`, or `DONE` |
| `priority` | `LOW`, `MED`, or `HIGH` |
| `assignee` | Numeric user ID |
| `ordering` | `created_at`, `-created_at`, `priority`, or `-priority` |
| `page` | Page number |
| `page_size` | Defaults to `10`; maximum is `100` |

Paginated responses use the standard envelope:

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": []
}
```

### Example workflow

The following request and response shapes were captured from a local server run. Sample IDs and timestamps are illustrative values from that run and will differ in another database. Token values are intentionally omitted from the documentation; use the values returned by your own token request.

The examples use a POSIX shell. In PowerShell, `curl.exe` can be used, or the same requests can be sent with `Invoke-RestMethod`.

#### 1. Register

```bash
curl -X POST http://127.0.0.1:8000/api/auth/register/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"readme-user-3","password":"readme-password-123"}'
```

```json
{
  "id": 1,
  "username": "readme-user-3"
}
```

#### 2. Obtain tokens

```bash
curl -X POST http://127.0.0.1:8000/api/auth/token/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"readme-user-3","password":"readme-password-123"}'
```

```json
{
  "refresh": "<refresh-token>",
  "access": "<access-token>"
}
```

Set `ACCESS_TOKEN` to the returned access-token value before running the protected examples:

```bash
export ACCESS_TOKEN='<access-token>'
```

#### 3. Create an organization

```bash
curl -X POST http://127.0.0.1:8000/api/organizations/ \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"name":"README Demo Org"}'
```

```json
{
  "id": 1,
  "name": "README Demo Org",
  "owner": "readme-user-3"
}
```

#### 4. Create a project

```bash
curl -X POST http://127.0.0.1:8000/api/projects/ \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"organization":1,"name":"README Demo Project"}'
```

```json
{
  "id": 1,
  "organization": 1,
  "name": "README Demo Project",
  "created_at": "2026-10-18T06:01:36.875463Z"
}
```

#### 5. Create a task with an initial comment

`initial_comment` is write-only input that creates a comment together with the task.

```bash
curl -X POST http://127.0.0.1:8000/api/tasks/ \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"project":1,"title":"README Demo Task","priority":"HIGH","initial_comment":"Created from the curl example."}'
```

```json
{
  "id": 1,
  "project": 1,
  "title": "README Demo Task",
  "description": "",
  "status": "TODO",
  "priority": "HIGH",
  "assignee": null,
  "assignee_detail": null,
  "created_by": {
    "id": 1,
    "username": "readme-user-3"
  },
  "created_at": "2026-10-18T06:01:44.088762Z",
  "comments": [
    {
      "id": 1,
      "task": 1,
      "author": {
        "id": 1,
        "username": "readme-user-3"
      },
      "body": "Created from the curl example.",
      "created_at": "2026-10-18T06:01:44.113921Z"
    }
  ]
}
```

#### 6. List filtered and paginated tasks

```bash
curl "http://127.0.0.1:8000/api/tasks/?status=TODO&priority=HIGH&page_size=10" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "project": 1,
      "title": "README Demo Task",
      "description": "",
      "status": "TODO",
      "priority": "HIGH",
      "assignee": null,
      "assignee_detail": null,
      "created_by": {
        "id": 1,
        "username": "readme-user-3"
      },
      "created_at": "2026-10-18T06:01:44.088762Z",
      "comments": [
        {
          "id": 1,
          "task": 1,
          "author": {
            "id": 1,
            "username": "readme-user-3"
          },
          "body": "Created from the curl example.",
          "created_at": "2026-10-18T06:01:44.113921Z"
        }
      ]
    }
  ]
}
```

#### 7. Add a comment

```bash
curl -X POST http://127.0.0.1:8000/api/comments/ \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"task":1,"body":"Added after task creation."}'
```

```json
{
  "id": 2,
  "task": 1,
  "author": {
    "id": 1,
    "username": "readme-user-3"
  },
  "body": "Added after task creation.",
  "created_at": "2026-10-18T06:01:59.124317Z"
}
```

#### 8. Close the task

```bash
curl -X POST http://127.0.0.1:8000/api/tasks/1/close/ \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

```json
{
  "id": 1,
  "project": 1,
  "title": "README Demo Task",
  "description": "",
  "status": "DONE",
  "priority": "HIGH",
  "assignee": null,
  "assignee_detail": null,
  "created_by": {
    "id": 1,
    "username": "readme-user-3"
  },
  "created_at": "2026-10-18T06:01:44.088762Z",
  "comments": [
    {
      "id": 1,
      "task": 1,
      "author": {
        "id": 1,
        "username": "readme-user-3"
      },
      "body": "Created from the curl example.",
      "created_at": "2026-10-18T06:01:44.113921Z"
    },
    {
      "id": 2,
      "task": 1,
      "author": {
        "id": 1,
        "username": "readme-user-3"
      },
      "body": "Added after task creation.",
      "created_at": "2026-10-18T06:01:59.124317Z"
    }
  ]
}
```

## Authentication

Send the access token in the `Authorization` header:

```text
Authorization: Bearer <access-token>
```

Access tokens are obtained from `POST /api/auth/token/`. Refresh tokens are sent to `POST /api/auth/token/refresh/` to obtain a new access token.

The configured Simple JWT lifetimes were read from `rest_framework_simplejwt.settings.api_settings` in this environment:

| Token | Lifetime |
| --- | --- |
| Access | `0:05:00` (5 minutes) |
| Refresh | `1 day, 0:00:00` (1 day) |

## Setup: local development

### Requirements

- Python 3.12
- PostgreSQL
- `pip`

### Install and configure

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

On Windows PowerShell, activate the environment with:

```powershell
.\.venv\Scripts\Activate.ps1
```

Copy the environment template in PowerShell with:

```powershell
Copy-Item .env.example .env
```

For a local PostgreSQL server, set `DATABASE_URL` in `.env` to a local host, for example:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/team_issue_tracker
```

Apply migrations, create an admin user, and start the development server:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

The API is then available at `http://127.0.0.1:8000/api/` and the admin site at `http://127.0.0.1:8000/admin/`.

## Setup: Docker Compose

Docker Compose provides PostgreSQL 16 and the Django web container:

```bash
docker compose up --build
```

The web container waits for PostgreSQL to become healthy, runs `python manage.py migrate`, and starts Django's development server on port `8000`.

When using Docker Compose, the database hostname must be the Compose service name `db`:

```env
DATABASE_URL=postgresql://postgres:postgres@db:5432/team_issue_tracker
```

Do not use `localhost` for the web container's database URL. Inside the web container, `localhost` refers to the web container itself.

Useful commands:

```bash
docker compose up -d --build
docker compose logs -f web
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py test
docker compose down
```

This Compose configuration is for development. It runs Django's development server and does not configure a production WSGI/ASGI server, HTTPS, rate limiting, or production secret management.

## Environment variables

| Variable | Behavior and default |
| --- | --- |
| `SECRET_KEY` | Required when `DEBUG=False`; settings raise `ImproperlyConfigured` if it is missing. With `DEBUG=True`, the development fallback is `django-insecure-development-key-change-me`. |
| `DEBUG` | Defaults to `False`. Values `1`, `true`, and `yes` enable debug mode. `.env.example` and Docker Compose use `True` for development. |
| `DATABASE_URL` | Django fallback: `postgresql://postgres:postgres@localhost:5432/team_issue_tracker`. Docker Compose fallback: `postgresql://postgres:postgres@db:5432/team_issue_tracker`. |
| `DJANGO_ALLOWED_HOSTS` | Defaults to `localhost,127.0.0.1,testserver`. |

Keep `.env` out of version control. `.env` is ignored by `.gitignore`; use `.env.example` as the development template.

## Running the tests

The test suite uses PostgreSQL. The Django test runner creates and destroys a separate test database.

Local commands:

```bash
python manage.py makemigrations --check --dry-run
python manage.py test
python manage.py check --deploy
```

Docker commands:

```bash
docker compose exec web python manage.py makemigrations --check --dry-run
docker compose exec web python manage.py test
docker compose exec web python manage.py check --deploy
```

`check --deploy` reports deployment-security warnings for settings such as HTTPS redirects, HSTS, secure cookies, and the development secret-key configuration. Those warnings are expected for this development setup.

### Test inventory

The following inventory is generated from `issues/tests.py`.

| Test class | Test methods |
| --- | --- |
| `IssueTrackerAPITests` | `test_register_and_login`; `test_organization_creation_adds_owner_membership`; `test_member_can_view_project`; `test_member_cannot_modify_project`; `test_task_creation_with_initial_comment`; `test_task_creator_can_close_task`; `test_unrelated_member_cannot_close_task`; `test_assignee_can_close_task`; `test_tasks_can_be_filtered`; `test_tasks_are_paginated_and_orderable` |
| `PermissionAPITests` | `test_member_cannot_create_project`; `test_member_cannot_patch_organization`; `test_admin_can_patch_organization`; `test_admin_cannot_delete_organization`; `test_owner_can_delete_organization_and_projects_are_gone`; `test_member_cannot_delete_another_users_comment`; `test_comment_author_can_delete_own_comment`; `test_admin_can_delete_anyones_comment`; `test_admin_can_create_update_delete_projects`; `test_project_organization_change_is_rejected` |
| `AuthenticationAndIsolationAPITests` | `test_jwt_end_to_end_workflow`; `test_token_refresh_returns_new_access_token`; `test_request_without_token_returns_401`; `test_request_with_garbage_token_returns_401`; `test_cross_organization_objects_are_isolated`; `test_cross_organization_task_and_comment_writes_are_rejected` |
| `ValidationAndPaginationAPITests` | `test_assignee_outside_organization_rejected_on_create_and_update`; `test_member_assignee_and_null_assignee_are_accepted`; `test_tasks_filter_by_assignee`; `test_tasks_default_page_size_is_ten`; `test_tasks_page_size_is_capped_at_one_hundred` |
| `SettingsTests` | `test_debug_false_without_secret_key_raises_improperly_configured` |

## Known limitations

- There is no API endpoint for managing members or roles; Django admin is required.
- `/api/projects/{id}/tasks/` is not paginated.
- The Docker setup uses Django's development server.
- Registration is open.
- There is no rate limiting.
- Assignee and role changes are not audited.
- Tests run against PostgreSQL only.
- The project does not include an API schema or interactive Swagger/ReDoc endpoint.

## License

This project is distributed under the license in [LICENSE](LICENSE).
