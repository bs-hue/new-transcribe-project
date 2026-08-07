# Cookies (Instagram and restricted YouTube videos)

Instagram serves almost nothing to anonymous clients, and some YouTube videos are
age- or region-gated. Both cases are solved the same way: give the downloader a
logged-in browser session via a cookies file.

Without one, those videos fail with a clear
`video_unavailable` / "requires an authenticated session" error rather than
anything mysterious — so if you only ever process public YouTube videos, you can
skip this page entirely.

## Exporting cookies

1. Log in to the platform in a browser profile you are happy to dedicate to this.
2. Install a "Get cookies.txt" style extension that exports **Netscape format**.
3. Export while on the platform's domain and save the file, e.g. `cookies.txt`.

## Wiring it up

```bash
# .env
COOKIES_FILE=/absolute/path/to/cookies.txt
```

With Docker, mount it read-only and point at the container path:

```yaml
# docker-compose.yml, under the api service
volumes:
  - api-data:/data
  - ./cookies.txt:/data/cookies.txt:ro
environment:
  COOKIES_FILE: /data/cookies.txt
```

Restart the API. The file is used for both metadata probing and download.

## Operational notes

- **Treat the file as a credential.** It grants access to the account. It is
  gitignored (`cookies.txt`), and should be mounted read-only and kept off shared
  drives.
- **Use a dedicated account.** Automated access can get an account rate-limited
  or challenged. Do not use a personal or client-facing login.
- **Cookies expire.** Sessions are typically good for weeks. When Instagram jobs
  start failing with login errors across the board, re-export.
- **Respect the platforms' terms.** This tool is for researching publicly posted
  marketing content at human scale. Bulk-scraping private content is neither
  supported nor a good idea.
