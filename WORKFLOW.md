# Workflow (Backend)

## Branch model
- `master` — stable baseline only
- `patch/*` — any changes are developed here

## Create patch branch
```bash
git checkout master
git pull origin master
git checkout -b patch/<short-topic>
```

## Work and publish
```bash
git add .
git commit -m "patch: <what changed>"
git push -u origin patch/<short-topic>
```

## Merge rule
- Merge to `master` only via Pull Request after your approval.
- No direct commits to `master`.

## Suggested GitHub branch protection for `master`
- Require a pull request before merging
- Require approvals (at least 1)
- Dismiss stale approvals when new commits are pushed
- Restrict who can push to matching branches
