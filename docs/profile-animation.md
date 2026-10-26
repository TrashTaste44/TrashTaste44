# Profile animation

The README keeps its original ASCII artwork and `whoami`. The lower section is a
generated monochrome GIF: a project showcase, a 30-day contribution graph, and
language bars. A classic pixel snake follows a fixed route along panel borders
and through the left gutter, eats apples, and grows. It is a looping animation,
not an interactive game. The snake is decorative and does not encode activity.
The outer canvas is transparent in both the GIF and PNG so it blends into the
GitHub page. Dark project and graph panels remain opaque. Sprite frames restore
the static canvas between steps so the snake cannot leave trails.

## Automatic updates

`.github/workflows/profile.yml` refreshes the assets daily, when generator code
is pushed to `main`, or through **Actions → Refresh profile animation → Run
workflow**. It fetches stats, runs the renderer, and commits only generated
assets to the default branch when they change. Scheduled workflows run from the
default branch and GitHub may delay scheduled jobs. GitHub can disable schedules
on inactive public repositories after 60 days; they can be re-enabled in Actions.

The workflow uses the built-in `GITHUB_TOKEN`; no personal access token is
required. Actions must be enabled and repository policy must allow this workflow
to write contents. Branch rules that prohibit direct bot commits require a
separate publication arrangement; this workflow does not bypass branch rules.

## Data and privacy

- Contributions use GitHub's daily contribution calendar, for the last 30 UTC
  dates including today. Today's count can change after the daily refresh.
- Counts are what GitHub exposes for the profile. Private contributions can be
  included as anonymous counts if the profile owner enables GitHub's **Private
  contributions** visibility setting. This does not grant access to private code.
- Language percentages sum GitHub language **bytes**, rather than commits or
  time spent, across public, owned, non-fork repositories (including archived
  repositories). The five largest languages are shown, with remaining languages
  grouped as Other. Private repository languages are excluded.
- Only dates, aggregate counts, language names, byte totals, and timestamps are
  saved. No repository names, repository URLs, or credentials are included in
  generated stats. This feature does not change repository visibility on GitHub.
- API or incomplete-data failures stop the refresh and retain the previous
  committed assets. An unavailable count is never replaced with an invented zero.

The first checked-in version can be bootstrapped from GitHub's public contribution
calendar. Its counts are real; it explicitly marks languages as pending until
the first successful API refresh. This bootstrap mode is an explicit local option,
not a silent fallback in the scheduled Action.

## Run locally

Use the existing checkout; no worktree is needed. Requires Python 3.12+, a
monospace TrueType font (Ubuntu package `fonts-dejavu-core`), and Pillow:

```sh
python -m pip install -r scripts/requirements.txt
python -m unittest discover -s tests -v
python scripts/fetch_stats.py --username TrashTaste44
python scripts/render_profile.py
```

The fetcher reads `GITHUB_TOKEN` or `GH_TOKEN` from the process environment. Set
credentials through your normal secure environment tooling, never in source.
The cloud environment needs HTTPS access to `api.github.com`; Actions runners
normally already have this access. To bootstrap contributions without an API token:

```sh
python scripts/fetch_stats.py --username TrashTaste44 --public-calendar-only
python scripts/render_profile.py
```

Pass `--font /path/to/font.ttf` to the renderer on systems without the Ubuntu
font path. Outputs are `assets/profile.gif`, `assets/profile.png` (no animation),
`assets/profile-stats.json`, and `assets/profile-summary.md` (accessible text).
The README links the still and text versions for visitors who prefer no motion.

Edit project copy in `scripts/render_profile.py` and the README's text description
together. The original ASCII header is separate from the generated image.
