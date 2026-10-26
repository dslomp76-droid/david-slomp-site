# David Slomp professional website

Source for [davidslomp.ca](https://davidslomp.ca/), a static HTML/CSS/JavaScript site deployed with GitHub Pages.

## Files
- `index.html` — home
- `about.html`
- `research.html`
- `publications.html`
- `engagement.html`
- `mentoring.html`
- `contact.html`
- `downloads/David_Slomp_CV_2026.pdf`
- `css/styles.css`
- `js/site.js`
- `assets/images/` — web-ready photographs and retained source assets

## Site purpose
- Presents a coherent public-facing research profile instead of a CV-only presence.
- Uses first-person voice for the site itself.
- Surfaces key signals quickly: current role, editorial leadership, citation impact, award, research themes, public engagement, and graduate mentoring.
- Keeps navigation simple and deploys cleanly on GitHub Pages.

## Public sources checked for current details (2026-03-24)
The site text was drafted from the supplied CV and EOI, but current public facts were checked against official public sources before building:

- University of Lethbridge directory profile: current title, phone, email, biography, and Co-Editor-in-Chief statement.
- University of Lethbridge faculty profile: public role wording.
- ScienceDirect editorial board page for *Assessing Writing*: confirms “Co Editors-in-Chief”.
- International Literacy Association Albert J. Harris Award page: confirms 2025 award.
- Google Scholar search result: confirms 1,100+ citation scale.

### Role correction (2026-10-26)

David confirmed that he stepped down as Associate Dean at the end of August 2026 and returned to a regular faculty role. His current title is Professor, Faculty of Education, University of Lethbridge. The site and public CV reflect that correction; the Associate Dean service remains historical, from 2022 (the existing CV start year) through August 2026. This direct confirmation supersedes older role wording on institutional profiles.

## Maintenance

- The custom domain is configured through `CNAME`.
- `assets/images/david-slomp-hero-800.jpg` and `david-slomp-hero-1600.jpg` provide responsive, web-optimized hero images.
- `assets/images/David SlompCMYK.jpeg` is not used on the website. It is retained as a print/media source asset.
- Update publication links and the CV as new work is released.
- Validate changed HTML and CSS before publishing.

## Deployment
GitHub Pages publishes the site from the `main` branch. Develop changes on a branch, validate them, and merge through a pull request.

## Notes
- The site intentionally avoids copying external images or university branding assets.
- Citation counts change over time. The weekly metrics process below preserves the last verified snapshot and its date.
- The site keeps the tone measured and public-facing rather than promotional.


## Weekly Google Scholar metrics

The homepage uses a static, dated snapshot from the existing [Google Scholar profile](https://scholar.google.com/citations?hl=en&user=jtLduoQAAAAJ), author ID `jtLduoQAAAAJ`. Its source of truth is `data/scholar-metrics.json`; `scripts/refresh_scholar.py` updates that file and only the marked research-impact section of `index.html` together.

### Initial setup and verification

1. Add a repository Actions secret named **`SERPAPI_API_KEY`** in [GitHub's secret-entry form](https://github.com/dslomp76-droid/david-slomp-site/settings/secrets/actions/new). Enter the key there, never in chat, source files, a URL shared with someone, or logs. This repository does not create a SerpApi account or purchase a plan.
2. Review/approve the refresh job's scoped `contents: write` (save the two generated files) and `pages: write` (request the existing Pages build) permissions. No personal access token, administration permission, OIDC token, Pages source change, or broad repository workflow-permissions setting is needed. Do not weaken protections if an organization/repository policy blocks the job; review the specific denial instead.
3. The first merge automatically attempts an initial refresh while the saved `checked_at` is null. Later ordinary pushes skip the provider request once a verified snapshot exists. You can also open **Actions → Weekly Google Scholar metrics → Run workflow → main**. An initial successful real run is required before calling the automation operational. Tests run without credentials; only the trusted-main refresh step receives the provider key. A missing/invalid key fails safely.
4. Confirm the refresh and public verification steps succeed, then visit [the homepage](https://davidslomp.ca/) and [saved snapshot](https://davidslomp.ca/data/scholar-metrics.json). Both must contain the same genuine `checked_at` timestamp. A commit, queued build, or passing mock test alone is not proof of a live refresh.

Until that first success, the pre-existing September 2026 figures stay explicitly historical: **1,200+ citations, h-index 18, nearly 70% since 2021**. They are not converted to exact current counters, and no i10-index baseline is invented.

### Schedule, validation, and display

- `.github/workflows/scholar-metrics.yml` schedules one fresh SerpApi author request each **Monday at 07:23 UTC**, plus initial setup attempts while no verified snapshot exists and explicitly requested manual runs. No pagination, automatic provider retries, paid signup, or browser-side API calls occur. Provider quota/plan limits still apply.
- The response must be successful and match the configured author ID and name. The script validates nonnegative integer all-time/recent counters, completeness, and a consistent provider-supplied `since_YYYY` label. It rejects errors, partial data, wrong identities, unexpected shapes, and inconsistent counters before publishing. Optional i10-index data is saved only when actually returned; it is not added to the three-card homepage.
- After the first valid response, the third card displays an approximately rounded share calculated from the returned recent/all-time citation counters. Its year comes from the response, not a hard-coded moving window. Zero total citations displays a dash rather than an invented percentage.
- The last successful check is shown in UTC. After more than **14 days**, a small client-side status script labels it overdue without changing the stored figures or check date. With JavaScript disabled, the static last-check date remains visible. Failed requests never reset that date or replace good data with zeroes.
- GitHub schedules are best-effort and can be delayed or dropped under load. Public-repository schedules may be disabled after 60 days without activity. Check the Actions page if the display is overdue, re-enable a disabled workflow if appropriate, and run it manually. A weekly configuration is not a guarantee of execution.

### Publication and failure recovery

The site **continues to publish from `main` using its existing GitHub Pages configuration**. Since commits made by `GITHUB_TOKEN` do not automatically trigger Pages, the refresh job explicitly requests the documented `POST /repos/{owner}/{repo}/pages/builds` endpoint. It then waits up to eight minutes for both the saved JSON and the matching generated homepage to be publicly served.

Only `data/scholar-metrics.json` and `index.html` are committed by the refresh. Non-fast-forward pushes fail rather than overwrite concurrent work. Fetch/validation failures leave the previous snapshot untouched; a publication failure leaves the last deployed page in place. If a valid commit was saved but deployment failed, inspect the Pages run and rerun the workflow on `main` after the cause is resolved. Do not claim new figures are live until the public verification succeeds. Errors intentionally omit provider response bodies, URLs, and key values.

Tests and local consistency checks (Python 3.12+, Node 20+; no dependencies or keys required):

```sh
python -m unittest discover -s tests -v
node --test tests/scholar-status.test.js
python scripts/refresh_scholar.py --check
```

Sources: [SerpApi author endpoint/schema](https://serpapi.com/google-scholar-author-api), [GitHub token behavior](https://docs.github.com/en/actions/concepts/security/github_token), [explicit Pages build endpoint](https://docs.github.com/en/rest/pages/pages#request-a-github-pages-build), and [GitHub schedule limitations](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).
