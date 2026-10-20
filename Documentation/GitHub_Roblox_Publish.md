# GitHub → Roblox publish (GarfGames)

This template already ships the publish kit:

- `.github/workflows/publish.yml` — runs on push to `release`, not `main`
- `tool/publish.sh` — lint, `rojo build`, Open Cloud upload
- `tool/publish.env` — this game’s universe / place ids (not secret)

Hand this file to an agent (or follow it) in a **private** GarfGames game created from this template.

## The API key

**GarfGames is on the GitHub Free plan, where organization secrets are not
available to private repositories.** The org secret `ROBLOX_API_KEY` exists, but
a private game repo cannot read it — CI fails with `secrets.ROBLOX_API_KEY is
not set` and an empty value. So every private game carries its **own repo-level
secret** of the same name:

```bash
gh secret set ROBLOX_API_KEY --repo GarfGames/<game>
```

Same key as the org secret; it just has to live on the repo until the org moves
to Team/Enterprise. Only then — or for a public repo — does the org secret
reach the workflow on its own. CI reads `${{ secrets.ROBLOX_API_KEY }}` either
way. Public repos and forks never get it.
([GitHub docs: organization secrets require Team or Enterprise for private
repos](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets))

## Per game

### 1. Repo secret

```bash
gh secret set ROBLOX_API_KEY --repo GarfGames/<game>
```

Paste the shared Open Cloud key at the prompt. Skip only if this repo is public
and meant to inherit the org secret. Verify with `gh secret list --repo
GarfGames/<game>`.

### 2. Open Cloud allowlist

At [create.roblox.com/dashboard/credentials](https://create.roblox.com/dashboard/credentials), the shared key needs **universe-places:write** on **this** experience. If CI 403s, this universe is not on the key yet.

### 3. Fill `tool/publish.env`

Creator Dashboard URL:

`.../dashboard/creations/experiences/<UNIVERSE_ID>/places/<PLACE_ID>/configure`

```bash
UNIVERSE_ID=0          # replace
PLACE_ID=0             # replace
PLACE_FILE=build/my-game.rbxl
# PLACE_NAME=my-game   # optional macOS Keychain account
```

Ids are public; the API key is not. Leave zeros until the experience exists — `publish.sh` will refuse to upload.

### 4. `release` branch

```bash
git checkout main
git pull
git checkout -b release        # skip if it already exists
git push -u origin release
```

That branch is the production snapshot. Further `main` pushes do **not** go live.

### 5. First ship (this is the deploy)

```bash
git checkout release
git merge --ff-only main       # or open a PR targeting release
git push origin release
```

That push publishes **live** to players. Manual run: Actions → **Publish to Roblox** → Published (live) or Saved (history only).

Local (optional): `tool/publish.sh`, `tool/publish.sh --saved`, or `tool/publish.sh --build-only`. Key from `$ROBLOX_API_KEY`, macOS Keychain `roblox-open-cloud`, or gitignored `.env.publish`.

## Don’t

- Trigger publish on `main` (agents commit there).
- Commit `.env.publish` or any API key, including in `tool/publish.env`.
- Assume the org secret covers a private repo — on the Free plan it does not.
- Publish while `UNIVERSE_ID` is still `0`.

## If it fails

| Symptom | Likely cause |
| --- | --- |
| `secrets.ROBLOX_API_KEY is not set` | No repo secret on this private repo — run `gh secret set ROBLOX_API_KEY --repo GarfGames/<game>`. On the Free plan the org secret does not reach private repos. Also fires on a fork PR, which never gets secrets. |
| HTTP 401 / 403 | Key missing **universe-places:write** for this universe, or IP allowlist. |
| HTTP 404 | Wrong ids in `tool/publish.env`. |
| Push to `release` does nothing | Workflow file on **that** branch still says `branches: [main]`. Merge main into release. |
