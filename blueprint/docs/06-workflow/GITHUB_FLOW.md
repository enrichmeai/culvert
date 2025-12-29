# 🚀 GitHub Flow & CI/CD - LOA Blueprint

**Version:** 1.0  
**Last Updated:** December 21, 2025  
**Status:** Production Ready

---

## 📋 Table of Contents

1. [Quick Start](#quick-start)
2. [GitHub Flow Process](#github-flow-process)
3. [Branch Strategy](#branch-strategy)
4. [Pull Request Workflow](#pull-request-workflow)
5. [CI/CD Pipelines](#cicd-pipelines)
6. [Deployment Process](#deployment-process)
7. [Rollback Procedures](#rollback-procedures)
8. [Best Practices](#best-practices)

---

## 🚀 Quick Start

### Your First Contribution

```bash
# 1. Create feature branch
git checkout -b feature/my-component

# 2. Make changes
# (edit files, create components)

# 3. Commit with clear message
git commit -m "feat(epic7c): add github workflow automation"

# 4. Push to GitHub
git push origin feature/my-component

# 5. Create Pull Request on GitHub
# - Fill in PR template
# - Link to issue (if applicable)
# - Request reviewers

# 6. CI/CD runs automatically
# - Tests run
# - Coverage checked
# - Linting performed

# 7. Address review feedback
# (make changes, push again)

# 8. Merge when ready
# (GitHub auto-closes PR and deletes branch)

# 9. Main branch deploys automatically
# - Terraform applies changes
# - Services deployed
# - Documentation updated
```

---

## 📊 GitHub Flow Process

### Branches

**Main Branch (`main`)**
- ✅ Always production-ready
- ✅ All tests passing
- ✅ All reviews approved
- ✅ Auto-deploys to GCP
- 🔒 Protected (requires PR reviews)

**Develop Branch (`develop`)**
- ✅ Integration branch for features
- ✅ Pre-release testing
- ✅ All tests must pass
- 🔒 Protected (requires PR reviews)

**Feature Branches**
- 📝 Named: `feature/descriptive-name`
- 📝 Created from: `develop`
- 📝 Merged back to: `develop` → `main`
- 📝 Short-lived (delete after merge)

**Hotfix Branches**
- 🔥 Named: `hotfix/critical-issue`
- 🔥 Created from: `main`
- 🔥 Merged back to: `main` (then `develop`)
- 🔥 For critical production issues

---

## 🌿 Branch Strategy

### Creating a Feature Branch

```bash
# Update develop branch
git checkout develop
git pull origin develop

# Create feature branch
git checkout -b feature/add-new-epic-component

# Naming conventions:
# feature/    - New features or components
# fix/        - Bug fixes
# refactor/   - Code refactoring
# docs/       - Documentation changes
# test/       - Test additions/improvements
# ci/         - CI/CD pipeline changes

# Example branch names:
# feature/epic7d-architecture-docs
# fix/dataflow-job-timeout
# refactor/simplify-validation-logic
# docs/update-deployment-guide
# test/add-chaos-engineering-tests
```

### Keeping Branch Up to Date

```bash
# If develop has new commits
git fetch origin
git rebase origin/develop

# Or use merge (alternative)
git merge origin/develop

# Push changes
git push origin feature/my-component
```

---

## 🔄 Pull Request Workflow

### Creating a Pull Request

**Step 1: Push your branch**
```bash
git push origin feature/my-component
```

**Step 2: Fill PR Template**

Template:
```markdown
## Description
Brief description of changes

## Type of Change
- [ ] New feature
- [ ] Bug fix
- [ ] Documentation
- [ ] Performance improvement

## Related Issue
Closes #123

## Testing Done
- [ ] Unit tests added
- [ ] Integration tests pass
- [ ] Manual testing completed

## Screenshots (if applicable)
Add screenshots of UI changes

## Checklist
- [ ] My code follows style guidelines
- [ ] I have updated documentation
- [ ] Tests added/updated
- [ ] No breaking changes
```

**Step 3: Assign Reviewers**
- Assign 2+ team members
- Add labels (epic, priority, etc.)
- Link to issues

### PR Review Process

**Reviewer Responsibilities:**
- ✅ Check code quality
- ✅ Verify tests pass
- ✅ Ensure documentation updated
- ✅ Ask questions if unclear
- ✅ Approve when satisfied

**Approval Requirements:**
- ✅ 2 approvals needed
- ✅ All tests passing
- ✅ Coverage > 80%
- ✅ No conflicts with main

**CI Checks (Automated):**
- ✅ Tests must pass
- ✅ Coverage must not decrease
- ✅ Linting must pass
- ✅ Docker builds must succeed
- ✅ Security scans must pass

### Addressing Feedback

```bash
# Make requested changes
# (edit files)

# Commit changes
git commit -m "Address review feedback: clarify validation logic"

# Push again (CI reruns automatically)
git push origin feature/my-component

# Conversation continues in PR
```

### Merging the PR

**Merge Strategy:**
- Squash commits for clean history
- Rebase & merge for linear history
- Create merge commit for complex PRs

```bash
# GitHub handles merge (web UI)
# Click "Merge pull request" button
# Choose merge strategy
# GitHub auto-deletes feature branch
```

---

## 🤖 CI/CD Pipelines

### Test Workflow (test.yml)

**Triggers:**
- On every push to main/develop
- On every pull request

**What it does:**
1. **Unit Tests** (5 min)
   - Python 3.8, 3.9, 3.10
   - All unit tests pass
   - Coverage > 80%

2. **Integration Tests** (10 min)
   - Full pipeline tests
   - Mock services (GCS, BQ, Pub/Sub)
   - End-to-end validation

3. **Local Tests** (5 min)
   - Docker Compose services
   - Real emulator testing
   - Complete workflow

4. **Security Scans** (5 min)
   - Bandit for security issues
   - Safety for vulnerabilities
   - Code quality checks

5. **Quality Checks** (5 min)
   - Pylint for code quality
   - MyPy for type checking
   - Black for formatting

6. **Docker Builds** (10 min)
   - Build validation API image
   - Build data-quality API image
   - Verify images work

**Output:**
- ✅ Test reports
- ✅ Coverage reports
- ✅ Security reports
- ✅ Build artifacts

### Deploy Workflow (deploy.yml)

**Triggers:**
- Only on merge to main
- Only if tests passed

**What it does:**
1. **Plan Phase** (5 min)
   - Terraform plan
   - Shows what will change
   - Can review changes

2. **Apply Phase** (15 min)
   - Terraform apply
   - Creates/updates resources
   - GCS buckets, BigQuery, IAM

3. **Cloud Functions** (5 min)
   - Deploy file validation function
   - Deploy data quality function
   - Set environment variables

4. **dbt** (15 min)
   - Parse dbt models
   - Run transformations
   - Run tests
   - Generate documentation

5. **Documentation** (5 min)
   - Build mkdocs site
   - Deploy to GitHub Pages
   - Available at: https://yourusername.github.io/legacy-migration-reference

**Total Deployment Time:** ~45 minutes

---

## 🚀 Deployment Process

### Automatic Deployment

```
Feature Branch Created
    ↓
Tests Run (test.yml)
    ↓
PR Created
    ↓
Code Review
    ↓
Approved & Merged to Main
    ↓
Deploy Workflow Runs (deploy.yml)
    ├─ Terraform Plan
    ├─ Terraform Apply
    ├─ Deploy Cloud Functions
    ├─ Run dbt
    └─ Update Documentation
    ↓
✅ Live on GCP
```

### Manual Deployment (if needed)

```bash
# Only use if auto-deployment failed

# Get latest code
git clone https://github.com/yourusername/legacy-migration-reference.git
cd legacy-migration-reference

# Authenticate with GCP
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Deploy infrastructure
cd infrastructure/terraform
terraform init
terraform plan -var-file="env/prod.tfvars"
terraform apply

# Deploy dbt
cd ../../blueprint/transformations/dbt
dbt run --target prod
dbt test --target prod

# Deploy functions
gcloud functions deploy loa-file-validation \
  --runtime python310 \
  --trigger-topic file-uploaded \
  --entry-point validate_file
```

### Monitoring Deployment

**During Deployment:**
```bash
# Watch workflow progress
# GitHub Actions tab → Deploy workflow
# See real-time logs

# Or via gcloud
gcloud functions describe loa-file-validation
gcloud dataflow jobs list
```

**After Deployment:**
```bash
# Verify resources created
terraform output deployment_summary

# Test endpoints
curl https://loa-validation-api.cloudfunctions.net/health

# Check BigQuery datasets
bq ls

# Verify dbt models
dbt docs serve
```

---

## 🔄 Rollback Procedures

### If Deployment Fails

```bash
# Option 1: Revert commit
git revert <commit-hash>
git push origin main
# CI/CD will re-run with reverted code

# Option 2: Rollback Terraform
cd infrastructure/terraform
terraform plan -destroy -var-file="env/prod.tfvars"
terraform apply -destroy

# Option 3: Redeploy previous version
git checkout <previous-commit>
git push origin main --force-with-lease
# ⚠️ Use with caution! Only if necessary
```

### If Issues Found Post-Deployment

**Step 1: Create hotfix branch**
```bash
git checkout main
git pull origin main
git checkout -b hotfix/critical-issue
```

**Step 2: Fix the issue**
```bash
# Make changes
git commit -m "fix: critical production issue"
git push origin hotfix/critical-issue
```

**Step 3: Create PR and merge**
```bash
# Create PR from hotfix to main
# Get reviews
# Merge to main
# Auto-deploy happens
```

**Step 4: Sync develop**
```bash
git checkout develop
git pull origin main
git push origin develop
```

---

## ✅ Best Practices

### ✅ DO

1. **Small, focused PRs**
   - One feature per PR
   - Easy to review
   - Quick to merge

2. **Clear commit messages**
   ```bash
   git commit -m "feat(epic7d): add architecture documentation"
   # Type: feat, fix, refactor, docs, test, ci
   # Scope: which epic/component
   # Message: what changed
   ```

3. **Test before pushing**
   ```bash
   pytest blueprint/components/tests/ -v
   # Run tests locally first
   ```

4. **Update documentation**
   - Update README
   - Update architecture docs
   - Add API documentation
   - Update deployment guide

5. **Follow naming conventions**
   - Branch: `feature/descriptive-name`
   - Commits: `type(scope): message`
   - PRs: Clear title and description

6. **Keep branch updated**
   ```bash
   git fetch origin
   git rebase origin/develop
   ```

7. **Request reviews**
   - Assign multiple reviewers
   - Add labels
   - Link to issues

### ❌ DON'T

1. **Don't force push to main**
   - Never `git push --force` on main
   - Use `--force-with-lease` only in emergencies

2. **Don't merge without tests**
   - All tests must pass
   - Coverage must be maintained
   - Security scans must pass

3. **Don't skip review**
   - Always get 2 approvals
   - Address all feedback
   - Don't merge your own PRs

4. **Don't make huge PRs**
   - Keep PRs < 400 lines
   - Split large changes
   - Submit multiple small PRs

5. **Don't deploy to prod manually**
   - Always use CI/CD
   - Automate everything
   - Only emergency hotfixes manually

6. **Don't ignore tests**
   - Write tests for new code
   - Update tests with changes
   - Maintain > 80% coverage

7. **Don't commit secrets**
   - Use GitHub Secrets
   - Use environment variables
   - Use Cloud Secret Manager

---

## 📊 CI/CD Status & Checks

### Status Badges

```markdown
![Tests](https://github.com/yourusername/legacy-migration-reference/workflows/Test/badge.svg)
![Deployment](https://github.com/yourusername/legacy-migration-reference/workflows/Deploy/badge.svg)
[![codecov](https://codecov.io/gh/yourusername/legacy-migration-reference/branch/main/graph/badge.svg)](https://codecov.io/gh/yourusername/legacy-migration-reference)
```

### Viewing Status

**In Pull Request:**
- See test results below PR description
- See coverage change
- See lint results
- See security scan results

**GitHub Actions Tab:**
- Click workflow to see details
- Click job to see logs
- Click step to see output
- Download artifacts if needed

**Slack Integration:**
- Get notified on deploy start
- Get notified on deploy success
- Get notified on deploy failure

---

## 🎯 Troubleshooting

### Test Failures

**Problem:** Tests failing in CI but pass locally

**Solution:**
```bash
# Check Python version
python --version  # Should be 3.8, 3.9, or 3.10

# Check dependencies
pip install -r requirements-dev.txt

# Run same tests as CI
pytest blueprint/components/tests/ -v --cov

# Compare environment variables
# CI might have different env vars
```

### Deployment Failure

**Problem:** Terraform apply failed

**Solution:**
```bash
# Check the error message in GitHub Actions
# Click workflow → deploy → apply

# Common issues:
# 1. Missing credentials: Check GCP_SA_KEY secret
# 2. Resource quota: Check GCP quotas
# 3. Invalid configuration: Check tfvars file
# 4. Network issues: Check firewall rules

# Rerun deployment
# Click "Re-run failed jobs" in GitHub Actions
```

### Coverage Decrease

**Problem:** PR blocked due to coverage decrease

**Solution:**
- Add tests for new code
- Ensure coverage doesn't drop
- Run coverage report locally

```bash
pytest blueprint/components/tests/ \
  --cov=blueprint/components \
  --cov-report=html
open htmlcov/index.html
```

---

## 📚 Useful Commands

```bash
# Branch management
git branch -a                    # List all branches
git checkout -b feature/name     # Create feature branch
git branch -d feature/name       # Delete local branch
git push origin --delete feature/name  # Delete remote branch

# Commit management
git log --oneline               # View commit history
git diff origin/main            # Show changes vs main
git rebase -i HEAD~3            # Squash last 3 commits

# Sync with remote
git fetch origin                 # Get latest from remote
git pull origin develop          # Get latest and merge
git push origin feature/name     # Push your branch

# Clean up
git branch -d merged-branch      # Delete merged branch locally
git remote prune origin          # Clean deleted remote branches
```

---

## ✅ Deployment Checklist

Before merging to main:
- [ ] All tests passing
- [ ] Coverage > 80%
- [ ] 2+ reviews approved
- [ ] Documentation updated
- [ ] No conflicts with main
- [ ] Commit messages clear
- [ ] No secrets in code

After deployment:
- [ ] Verify GCP resources created
- [ ] Test API endpoints
- [ ] Check Cloud Functions working
- [ ] Verify BigQuery datasets
- [ ] dbt models running
- [ ] Documentation deployed
- [ ] Slack notification received

---

## 🔗 Resources

- [GitHub Flow Guide](https://guides.github.com/introduction/flow/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Terraform Best Practices](https://www.terraform.io/docs/cloud/guides/recommended-practices)
- [dbt Best Practices](https://docs.getdbt.com/guides/best-practices)

---

**Status:** ✅ Ready to Use!

Your CI/CD pipeline is fully automated and ready for production! 🚀

