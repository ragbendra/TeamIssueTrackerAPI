# Team Issue Tracker API

[![CI](https://github.com/ragbendra/TeamIssueTrackerAPI/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ragbendra/TeamIssueTrackerAPI/actions/workflows/ci.yml)

A Django REST Framework API for tracking work in teams: organizations, projects, tasks and comments. Everything is scoped to an organization. A user only sees and changes things that their membership and role allow.

## At a glance

- **Framework:** Django 6.0.7 and Django REST Framework 3.17.1
- **Database:** PostgreSQL
- **Login:** JSON Web Tokens with `djangorestframework-simplejwt`
- **Filtering:** `django-filter`
- **Local setup:** Docker Compose with PostgreSQL 16 and Django's development server
- **API base path:** `/api/`

The repository has the `core` Django project and the `issues` app. The Docker image uses Python 3.12.

## Data model

| Model | Fields and relationships |
| --- | --- |
| `Organization` | `name`, and an `owner` user. |
| `Membership` | Links a `user` to an `organization` with the role `OWNER`, `ADMIN` or `MEMBER`. `(organization, user)` is unique. |
| `Project` | Belongs to an `organization`. Has `name` and `created_at`. |
| `Task` | Belongs to a `project`. Has `title`, `description`, `status`, `priority`, an optional `assignee`, `created_by` and `created_at`. |
| `Comment` | Belongs to a `task`. Has `author`, `body` and `created_at`. |

Task status is `TODO`, `IN_PROGRESS` or `DONE`. Priority is `LOW`, `MED` or `HIGH`. An assignee has to be a member of the task's organization, or `null`.

Deleting an organization also deletes its memberships, projects, tasks and comments.

## Roles and permissions

Anyone can register. A new user belongs to no organization until they create one, and creating an organization makes them its `OWNER`.

There's no API endpoint for managing members. To give someone the `ADMIN` or `MEMBER` role, a superuser has to do it in the Django admin at `/admin/`. Through the API, the only role you can get is the `OWNER` membership you receive for creating an organization.

| Resource | Read | Create | Update | Delete |
| --- | --- | --- | --- | --- |
| Organization | Organization members | Any logged-in user; the creator becomes `OWNER` | Organization `OWNER` or `ADMIN` | `OWNER` only |
| Project | Organization members | Organization `OWNER` or `ADMIN` | Organization `OWNER` or `ADMIN` | Organization `OWNER` or `ADMIN` |
| Task | Organization members | Any member of the project's organization | Organization `OWNER`/`ADMIN`, the task creator, or the assignee | Same as update |
| Task close action | n/a | n/a | Same as task update | n/a |
| Comment | Organization members | Any member of the task's organization | Not allowed | The comment's author, or organization `OWNER`/`ADMIN` |

A few more rules:

- A plain member, or someone outside the organization, gets `403 Forbidden` when creating a project.
- A project can't be moved to another organization after it's created.
- Objects from another organization are hidden by the queryset, so a detail request for one returns `404 Not Found`.
- An invalid assignee returns `400 Bad Request`.

## API reference

The examples use `http://127.0.0.1:8000`. Protected requests need this header:

```text
Authorization: Bearer <access-token>
```

### Authentication routes

| Method | Route | Auth | What it does |
| --- | --- | --- | --- |
| `POST` | `/api/auth/register/` | None | Registers a user with `username` and `password`. |
| `POST` | `/api/auth/token/` | None | Returns an access token and a refresh token. |
| `POST` | `/api/auth/token/refresh/` | None | Trades a refresh token for a new access token. |

### Resource routes

| Method | Route | Auth | What it does |
| --- | --- | --- | --- |
| `GET`, `POST` | `/api/organizations/` | Required | Lists the organizations you can access, or creates one. List parameters: `page`, `page_size`. |
| `GET`, `PUT`, `PATCH`, `DELETE` | `/api/organizations/{id}/` | Required | Reads, updates or deletes one organization. |
| `GET`, `POST` | `/api/projects/` | Required | Lists accessible projects, or creates one. List parameters: `page`, `page_size`. |
| `GET`, `PUT`, `PATCH`, `DELETE` | `/api/projects/{id}/` | Required | Reads, updates or deletes one project. |
| `GET` | `/api/projects/{id}/tasks/` | Required | Lists every task in one project you can access. Not paginated. |
| `GET`, `POST` | `/api/tasks/` | Required | Lists or creates tasks. |
| `GET`, `PUT`, `PATCH`, `DELETE` | `/api/tasks/{id}/` | Required | Reads, updates or deletes one task. |
| `POST` | `/api/tasks/{id}/close/` | Required | Sets a task's status to `DONE`. |
| `GET`, `POST` | `/api/comments/` | Required | Lists or creates comments. List parameters: `page`, `page_size`. |
| `GET`, `DELETE` | `/api/comments/{id}/` | Required | Reads or deletes one comment. Comments can't be edited. |

### Task list parameters

`GET /api/tasks/` accepts these query parameters:

| Parameter | Values |
| --- | --- |
| `status` | `TODO`, `IN_PROGRESS` or `DONE` |
| `priority` | `LOW`, `MED` or `HIGH` |
| `assignee` | A numeric user ID |
| `ordering` | `created_at`, `-created_at`, `priority` or `-priority` |
| `page` | Page number |
| `page_size` | Defaults to `10`, maximum `100` |

Paginated responses look like this:

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": []
}
```

### Example walkthrough

These requests and responses were captured from a local server run. The IDs and timestamps are from that run and will be different in your database. I've left the tokens out, so use the ones your own token request returns. Where a response repeats the same comments, I've shortened them to `...`.

The examples use a POSIX shell. In PowerShell you can use `curl.exe` or `Invoke-RestMethod`.

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

#### 2. Get tokens

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

Put the access token in `ACCESS_TOKEN` before running the rest:

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

#### 5. Create a task with a first comment

`initial_comment` is write-only. It creates a comment at the same time as the task.

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

#### 6. List tasks with filters and pagination

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
      "comments": [ ... ]
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
  "comments": [ ... ]
}
```

## Authentication

Send the access token in the `Authorization` header:

```text
Authorization: Bearer <access-token>
```

You get an access token from `POST /api/auth/token/`. Send the refresh token to `POST /api/auth/token/refresh/` to get a new access token.

Token lifetimes, read from the Simple JWT settings in my environment:

| Token | Lifetime |
| --- | --- |
| Access | 5 minutes |
| Refresh | 1 day |

## Setup: local development

### What you need

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

and copy the environment template with:

```powershell
Copy-Item .env.example .env
```

For a local PostgreSQL server, set `DATABASE_URL` in `.env` to a local host, for example:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/team_issue_tracker
```

Run the migrations, create an admin user and start the development server:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

The API is then at `http://127.0.0.1:8000/api/` and the admin site at `http://127.0.0.1:8000/admin/`.

## Setup: Docker Compose

Docker Compose gives you PostgreSQL 16 and the Django web container:

```bash
docker compose up --build
```

The web container waits for PostgreSQL to be healthy, runs `python manage.py migrate`, and starts Django's development server on port `8000`.

With Docker Compose the database host has to be the service name `db`:

```env
DATABASE_URL=postgresql://postgres:postgres@db:5432/team_issue_tracker
```

Don't use `localhost` in the web container's database URL. Inside that container, `localhost` is the web container itself.

Useful commands:

```bash
docker compose up -d --build
docker compose logs -f web
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py test
docker compose down
```

This Compose setup is for development. It runs Django's development server, and has no production WSGI/ASGI server, HTTPS, rate limiting or production secret handling.

## Environment variables

| Variable | What it does |
| --- | --- |
| `SECRET_KEY` | Required when `DEBUG=False`; settings raise `ImproperlyConfigured` without it. With `DEBUG=True` it falls back to `django-insecure-development-key-change-me`. |
| `DEBUG` | Defaults to `False`. `1`, `true` and `yes` turn it on. `.env.example` and Docker Compose set it to `True` for development. |
| `DATABASE_URL` | Django's fallback is `postgresql://postgres:postgres@localhost:5432/team_issue_tracker`. Docker Compose's fallback is `postgresql://postgres:postgres@db:5432/team_issue_tracker`. |
| `DJANGO_ALLOWED_HOSTS` | Defaults to `localhost,127.0.0.1,testserver`. |

Keep `.env` out of version control. It's in `.gitignore`; copy `.env.example` as the template for development.

## Running the tests

The tests need PostgreSQL. Django's test runner creates a separate test database and deletes it afterwards.

Locally:

```bash
python manage.py makemigrations --check --dry-run
python manage.py test
python manage.py check --deploy
```

With Docker:

```bash
docker compose exec web python manage.py makemigrations --check --dry-run
docker compose exec web python manage.py test
docker compose exec web python manage.py check --deploy
```

`check --deploy` lists deployment security warnings: HTTPS redirects, HSTS, secure cookies, and the development secret key. You'll see those warnings with this development setup, and they're expected.

### What the tests cover

There are 32 tests in `issues/tests.py`, in five groups:

- **Basic API behaviour (10):** register and log in, the owner membership on a new organization, members viewing but not changing projects, creating a task with an initial comment, who can close a task (creator and assignee yes, an unrelated member no), filtering, and pagination with ordering.
- **Permissions (10):** members can't create projects or patch organizations, admins can patch organizations and manage projects but can't delete an organization, an owner can delete one and its projects go with it, who can delete which comments, and a project can't be moved to another organization.
- **Authentication and isolation (6):** the full JWT workflow, token refresh, `401` with no token or a garbage token, and objects and writes across organizations being rejected.
- **Validation and pagination (5):** assignees outside the organization are rejected on create and update, member and null assignees are accepted, filtering by assignee, the default page size of 10, and the cap of 100.
- **Settings (1):** `DEBUG=False` without a `SECRET_KEY` raises `ImproperlyConfigured`.

## Known limitations

- There's no API for managing members or roles. You need the Django admin for that.
- Anyone can register.
- There's no rate limiting.
- `/api/projects/{id}/tasks/` isn't paginated.
- The Docker setup runs Django's development server.
- Changes to assignees and roles aren't logged.
- The tests only run against PostgreSQL.
- There's no API schema and no Swagger or ReDoc page.

## License

See [LICENSE](LICENSE).
