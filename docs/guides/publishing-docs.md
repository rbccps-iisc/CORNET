# Publishing docs on GitHub Pages

The site is built with [MkDocs Material](https://squidfunk.github.io/mkdocs-material/) from the `docs/` tree. The workflow lives in `.github/workflows/pages.yml` on the repository default branch.

## One-time setup (repository admin)

The workflow token cannot create the Pages site. `actions/configure-pages` can try, but only with a personal access token or a GitHub App token, not `GITHUB_TOKEN`. A user with **admin** access on `rbccps-iisc/CORNET` must do this once:

1. Open [Settings → Pages](https://github.com/rbccps-iisc/CORNET/settings/pages).
2. Under **Build and deployment**, set **Source** to **GitHub Actions** (not “Deploy from a branch”).
3. Save.

Until that step is done, the **Docs / deploy** job fails with HTTP 404 from `actions/deploy-pages`. The **Docs / build** job can still succeed.

## After Pages is enabled

- Push changes under `docs/` or `mkdocs.yml`, or
- Re-run the **Docs** workflow from the [Actions tab](https://github.com/rbccps-iisc/CORNET/actions/workflows/pages.yml) (**Run workflow**).

The site is served at <https://rbccps-iisc.github.io/CORNET/>.

## Local preview

```bash
pip install mkdocs-material
mkdocs serve
```

Open the URL printed on the terminal (usually `http://127.0.0.1:8000`).

## Strict build

CI runs `mkdocs build --strict`. Broken internal links fail the build. Regenerate the config schema page after editing `cornet/config/schema.py`:

```bash
make docs
```
