# Workflow (Backend)

## Branch model
- `master` — stable baseline only
- `patch/<version>` — any changes are developed here

## Create patch branch
```bash
git checkout master
git pull origin master
git checkout -b patch/0.0.1
```

## Work and publish
```bash
git add .
git commit -m "patch: <what changed>"
git push -u origin patch/0.0.1
```

## Version rule
- Start from `patch/0.0.1`
- Next patch branch increments by 1: `patch/0.0.2`, `patch/0.0.3`, ...

## Merge rule
- Merge to `master` only via Pull Request after your approval.
- No direct commits to `master`.

## Suggested GitHub branch protection for `master`
- Require a pull request before merging
- Require approvals (at least 1)
- Dismiss stale approvals when new commits are pushed
- Restrict who can push to matching branches
