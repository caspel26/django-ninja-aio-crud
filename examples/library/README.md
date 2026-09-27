# Library example

A small Django app showing the v3 serializer facade, relations, bulk operations,
permissions, JWT and cookie authentication, custom actions, hooks, Admin, and MCP.
Every viewset is mounted twice: `/api/sync/` and `/api/async/`.

## Run locally

From the repository root, with Python 3.10–3.14:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[mcp]'
cd examples/library
python manage.py migrate
python manage.py seed_library
python manage.py library_report
python manage.py runserver
```

Use a fresh database for `seed_library`. The command creates `librarian` and `reader` with generated passwords printed
once in the terminal, plus authors, tags, three books, and a loan.
One bulk-create item intentionally duplicates an ISBN to demonstrate partial
success: expect one saved item and one failed item.

Open <http://127.0.0.1:8000/api/docs>. Public author reads work without a token:

```sh
curl http://127.0.0.1:8000/api/sync/authors
curl http://127.0.0.1:8000/api/async/authors
```

Log in to get an access token; the response also sets the `access_token` cookie:

```sh
curl -X POST http://127.0.0.1:8000/api/sync/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"librarian","password":"YOUR_GENERATED_LIBRARIAN_PASSWORD"}'
```

Copy `access_token` from that response:

```sh
curl http://127.0.0.1:8000/api/async/books \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN'
```

Readers can browse the catalogue and borrow for themselves. Librarians can
change books and tags and see all loans. Cookie writes also need Django's CSRF
token; bearer requests avoid cookie authentication's CSRF check.

To use Django Admin, run `python manage.py createsuperuser` and open
<http://127.0.0.1:8000/admin/>.

## Tests and background jobs

```sh
python -W error::DeprecationWarning -W error::RuntimeWarning -W error::UserWarning manage.py test library
python manage.py shell -c 'from asgiref.sync import async_to_sync; from library.tasks import send_due_reminders; print(async_to_sync(send_due_reminders)())'
```

The parity suite compares status, body, database state, and query counts for the
same requests in both modes. PostgreSQL sequence state is restored between the
two test scenarios because sequence allocations survive transaction rollback.

Set `LIBRARY_SQLITE_PATH=/tmp/library-demo.sqlite3` to use a separate SQLite file.
For PostgreSQL, install `.[postgres]` from the repository root, create an empty
database, and set `LIBRARY_DATABASE_BACKEND=postgresql` plus `PGDATABASE`, `PGUSER`,
`PGPASSWORD`, `PGHOST`, and `PGPORT` before running the same commands.

## MCP over stdio

After seeding the database:

```sh
LIBRARY_MCP_USERNAME=reader python -m library.mcp_server
```

The server attaches that user's `Member` to each tool request. MCP calls invoke
view handlers directly, so HTTP JWT authentication does not run; viewset
permission hooks enforce the selected member's role and loan ownership. Set
`LIBRARY_MCP_USERNAME=librarian` when the client should be allowed to write to the
catalogue. The stdio client receives the selected user's permissions.

The server defaults to the seeded `reader` account. It fails at startup if that
active member does not exist. Nothing is deployed by these commands.
