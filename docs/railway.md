# Railway deployment

The crash `gunicorn: command not found` was caused by Gunicorn being absent from the pinned requirements. Gunicorn is now installed during the Railway build. WhiteNoise serves collected CSS/JS through WSGI; Django's development static handler is not used.

The checked-in `railway.json` selects `bash scripts/start-cloud.sh`. If you have a custom Start Command in Railway's UI, set it to that exact command. The script validates settings, applies migrations, collects static files, and executes Gunicorn on `0.0.0.0:$PORT` (8080 fallback). One worker is intentional for this SQLite-backed MVP.

Before redeploying:

1. In the service's **Variables**, add `DJANGO_SECRET_KEY` with a securely generated random value of at least 50 characters. Do not send it in chat or commit it. You can generate a value in your own local terminal using `python -c "import secrets; print(secrets.token_urlsafe(64))"`.
2. Keep `DJANGO_DEBUG=0`. The cloud startup script defaults to this value and requires a valid secret. Do not enable debug on the public service.
3. Add a Railway persistent Volume mounted at `/data` before storing accounts, bookings, or documents. Railway's injected `RAILWAY_VOLUME_MOUNT_PATH` selects the database and private-media locations. Without a volume, data inside the container can disappear during redeployments. Only run one replica with SQLite. Moving an existing database to a volume requires a deliberate backup/restore; the app does not copy it automatically.
4. Under **Settings → Source**, use `Khater89/MFN2`, branch `main`, root directory unset. Redeploy after the requirements change so dependencies are rebuilt; restarting the previous image will not install Gunicorn.
5. Under **Settings → Networking**, generate a public domain on the port printed by Gunicorn in Deploy Logs. Normally Railway's `PORT` is 8080. Verify it rather than assuming the number. The app includes the injected `RAILWAY_PUBLIC_DOMAIN` in its host/origin allowlists. If this variable is absent or you use a custom domain, set `DJANGO_ALLOWED_HOSTS` to the exact hostname and `DJANGO_CSRF_TRUSTED_ORIGINS` to its `https://` URL.

The script trusts the HTTPS headers from Railway's managed proxy. Do not use that default behind an untrusted proxy. For a different deployment topology, configure proxy trust explicitly.

Register users in the UI. Create an admin through Railway's authenticated shell with `python manage.py createsuperuser`. No admin account is created automatically. To intentionally add demo listings to an otherwise empty development service, use `python manage.py seed_demo` in that shell. No payment integration, funds collection, real medical credential validation, or production clinical readiness is claimed by this deployment.
