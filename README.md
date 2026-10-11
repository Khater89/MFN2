# Medical Nation

A responsive medical marketplace MVP for **Jordan**, using **JOD** (three decimal places) and **Asia/Amman** appointment times. Built with Django 5.2 LTS, server-rendered HTML, accessible CSS, and a persistent SQLite database. SQLite shares records across authenticated users on this server; it is not browser-local storage.

## Run locally

Requires Python 3.12+ with venv support.

```bash
./scripts/setup.sh --demo
./scripts/start.sh
```

The development server listens on port 8000. Register a patient, doctor, nurse, or pharmacy through the UI. For an administrator, run the following in your own terminal and follow the secure prompts:

```bash
.venv/bin/python manage.py createsuperuser
```

There are **no default passwords**. Sample provider accounts have unusable passwords; demo listings are clearly labeled and offer no real clinical services. Do not use real patient information in this development app. To start with an empty marketplace, omit `--demo` on a fresh database. `seed_demo` adds sample providers, products, and the next seven days of appointments without replacing existing records, stock, or commission settings.

## Railway

See [Railway deployment instructions](docs/railway.md). The repository now includes Gunicorn, WhiteNoise, and a cloud startup command that migrates the database, collects static assets, and binds to Railway’s `PORT`. Configure a secure `DJANGO_SECRET_KEY` and persistent volume in Railway before using the public service.

## Implemented

- Search and category/city filters, empty states, licensed profile surfaces.
- Password-hashed session authentication, CSRF protection, server-enforced roles and record ownership. Users cannot self-register as administrators.
- Private license upload (PDF/JPEG/PNG, 5 MB maximum, extension and file signature checks); files are served as downloads only to their owner or an administrator. Edits return a provider to pending review.
- Admin approvals/rejections with notes; unapproved providers cannot accept marketplace requests or publish offerings.
- Provider services, future appointment availability, reserved-slot protection, overlapping-appointment prevention, and request acceptance/fulfillment.
- Patient saved addresses and checkout defaults; exact, case-insensitive city service-area matching.
- Pharmacy catalog creation/editing/deactivation, live stock, single-pharmacy multi-item baskets, and atomic stock reservations.
- Persistent unpaid booking/order records, immutable price snapshots, signed 15-minute checkout quotes, status history, and cancellation of pending requests with stock/slot release.
- Admin-defined commission rate and currency, snapshotted on new records. The proposed supported rule is a percentage deducted from merchant gross, with no patient surcharge. An administrator must explicitly confirm this rule; no default rate is invented. Accrued commission stays zero until a verified payment implementation exists.
- Durable in-app notifications and activity logs. Issue submission and admin resolution records do not execute financial actions.
- Responsive sidebar/workspace layout, keyboard focus, field labels, reduced motion support, and no external font or image dependencies.

## Payments and launch limitations

**This is a runnable development MVP, not a launch-ready healthcare or payments service.** A submitted request is unpaid and is not a confirmed paid booking. There is no payment gateway, no card collection, no successful-payment simulation, and no payout execution. The payment endpoint deliberately returns HTTP 503 with a clear explanation. Payment and payout dashboard states remain unavailable.

To finish the financial slice, supply the gateway, approved commission formula/rate, merchant split/payout model, cancellation/refund/rescheduling rules, and gateway credentials through secure environment settings. Implement gateway checkout and signed, idempotent webhook verification before recording successful payments, commission, or payouts. Do not manually change payment statuses to make the UI appear complete.

Consultations currently mean **appointment requests**, not messaging, audio, or video. Pharmacy orders collect a delivery address; there is no courier integration or dispatch claim. Notifications are in-app only; email/SMS delivery requires an actual service and verified responses. The catalog is limited to generic non-prescription sample products; prescription handling is not implemented. Verification is an admin-recorded review, not an automated check against a Jordan licensing authority. Ratings are deliberately absent rather than fabricated. Currency defaults to JOD, but the admin/provider forms allow explicit codes; checkout rejects mixed-currency baskets.

## Configuration

`.env.example` lists environment variable names without secrets. The application reads exported process variables; it does not automatically load `.env` files. Set variables in cloud environment settings or export them in your terminal. `DJANGO_DEBUG=0` requires a unique `DJANGO_SECRET_KEY`. Configure `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` for the real host. Neither credentials nor private uploaded files belong in version control or source archives.

`DATABASE_PATH` can select a persistent SQLite path. Back up the database and `private-media/` together. Data has no automatic expiration in this MVP; retention, deletion, audit access, backups, and restoration policies require agreement before accepting patient information. For multiple production instances, migrate to a shared database such as PostgreSQL and revalidate locking/concurrency.

For production, use a supported WSGI server (e.g. Gunicorn), HTTPS/reverse proxy, static asset collection, and persistent protected storage. Run `manage.py collectstatic` and serve the output separately. The supplied `runserver` script is for development only. Production additionally needs throttling, security/clinical review, upload scanning, observability, payment reconciliation, verified Jordan licensing operations, refund procedures, and privacy/retention policies. The demo command must never be run against a live marketplace.

## Checks and artifacts

```bash
.venv/bin/python manage.py test
.venv/bin/python scripts/concurrency_check.py
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
```

See [acceptance cases](docs/acceptance.md) and [decisions](docs/decisions.md). Test and validation outcomes are recorded in [validation](docs/validation.md).

The source ZIP contains source, migrations, static assets, scripts, pinned dependencies, and these instructions. It excludes local databases, virtual environments, uploads, secret values, and test accounts. There is no standalone build ZIP: this application needs its Python server and database. Frontend assets are local; installation requires PyPI. Live external payments, messaging, and courier services are not integrated. Setup alone is not deployment or environment publication.
