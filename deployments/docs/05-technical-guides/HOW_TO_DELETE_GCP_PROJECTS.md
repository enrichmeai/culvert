# 🗑️ How to Delete GCP Projects

## Quick Guide to Managing Your GCP Projects

---

## List Your Projects

### Via Console:
```
https://console.cloud.google.com/cloud-resource-manager
```

### Via CLI:
```bash
# List all projects
gcloud projects list

# List only active projects
gcloud projects list --filter="lifecycleState:ACTIVE"

# List deleted projects (within 30-day recovery period)
gcloud projects list --filter="lifecycleState:DELETE_REQUESTED"
```

---

## Delete a Project

### Method 1: Via Console (Easiest) ⭐

1. **Go to Resource Manager:**
   ```
   https://console.cloud.google.com/cloud-resource-manager
   ```

2. **Find the project** you want to delete

3. **Click the 3 dots (⋮)** on the right side of the project row

4. **Select "Delete"**

5. **Confirm deletion:**
   - Type the **project ID** to confirm
   - Click "**Shut down**"

6. **Done!** Project will be deleted after 30 days

---

### Method 2: Via CLI (Faster)

```bash
# Delete a project
gcloud projects delete PROJECT_ID

# Example:
gcloud projects delete my-old-project-123

# Confirm when prompted
Are you sure you want to delete [my-old-project-123]? (Y/n): y
```

---

## Delete Multiple Projects

```bash
# Delete multiple projects at once
for project in project-1 project-2 project-3; do
    gcloud projects delete $project --quiet
done
```

Or with a list:
```bash
# Create a file with project IDs (one per line)
cat > projects_to_delete.txt << EOF
old-project-1
test-project-2
demo-project-3
EOF

# Delete all projects in the file
while read project; do
    echo "Deleting $project..."
    gcloud projects delete $project --quiet
done < projects_to_delete.txt
```

---

## Important Notes

### 30-Day Grace Period ⏰
- Projects are **scheduled for deletion** (not immediate)
- **30-day recovery period** before permanent deletion
- Can **restore** within 30 days if needed
- After 30 days: **permanently deleted** (cannot be recovered)

### What Happens When You Delete:
- ✅ **Billing stops immediately**
- ✅ All resources deleted (VMs, databases, storage, etc.)
- ✅ Service accounts deleted
- ✅ APIs disabled
- ✅ All data removed

### What You Cannot Do:
- ❌ Reuse the same project ID (ever)
- ❌ Recover after 30 days
- ❌ Access project resources during deletion period

---

## Restore a Deleted Project

### Within 30 Days:

**Via Console:**
```
1. Go to: https://console.cloud.google.com/cloud-resource-manager
2. Check "Show deleted projects" checkbox at top
3. Find your project (shows "DELETE_REQUESTED" status)
4. Click the 3 dots (⋮) → "Restore"
5. Project restored and reactivated
```

**Via CLI:**
```bash
# Restore a deleted project
gcloud projects undelete PROJECT_ID

# Example:
gcloud projects undelete my-project-123
```

---

## Check Project Status

```bash
# Check if project is scheduled for deletion
gcloud projects describe PROJECT_ID --format="value(lifecycleState)"

# Possible states:
# - ACTIVE: Project is active
# - DELETE_REQUESTED: Scheduled for deletion (can restore)
# - DELETE_IN_PROGRESS: Being deleted (cannot stop)
```

---

## Clean Up Before Deleting

### Optional: Remove Resources First

If you want to clean up specific resources before deleting the entire project:

```bash
# Set project
gcloud config set project PROJECT_ID

# Delete specific resources
gcloud compute instances list  # List VMs
gcloud compute instances delete INSTANCE_NAME --zone=ZONE

gcloud storage buckets list  # List buckets
gcloud storage rm -r gs://BUCKET_NAME

bq ls  # List BigQuery datasets
bq rm -r -f DATASET_NAME
```

**Note:** Not required - deleting the project deletes everything automatically.

---

## Common Scenarios

### Scenario 1: Delete Old Test Projects

```bash
# List projects with "test" in name
gcloud projects list --filter="name:test"

# Delete them
gcloud projects delete test-project-1 --quiet
gcloud projects delete test-project-2 --quiet
```

### Scenario 2: Delete Projects Created Today

```bash
# List recently created projects
gcloud projects list --format="table(projectId,createTime)" \
    --filter="createTime>=$(date -u +%Y-%m-%d)"

# Delete if needed
gcloud projects delete PROJECT_ID
```

### Scenario 3: Keep Only Specific Projects

```bash
# List all projects except the ones you want to keep
gcloud projects list --format="value(projectId)" \
    | grep -v "production-project" \
    | grep -v "staging-project"

# Delete others (be careful!)
gcloud projects list --format="value(projectId)" \
    | grep -v "production-project" \
    | grep -v "staging-project" \
    | xargs -I {} gcloud projects delete {} --quiet
```

---

## Verify Deletion

```bash
# Check project is scheduled for deletion
gcloud projects describe PROJECT_ID

# Should show:
# lifecycleState: DELETE_REQUESTED
# or error if already gone

# List all deleted projects
gcloud projects list --filter="lifecycleState:DELETE_REQUESTED"
```

---

## Billing After Deletion

### What Happens:
- ✅ **Billing stops immediately** when you delete a project
- ✅ No more charges for that project
- ✅ Can download final invoice before project is gone
- ⚠️ May see charges for resources used before deletion

### Check Final Costs:
```bash
# View billing for deleted project (before it's gone)
gcloud billing projects describe PROJECT_ID
```

Or in console:
```
https://console.cloud.google.com/billing
```

---

## Safety Tips

### Before Deleting:

1. **Backup important data** (if any)
   - Export databases
   - Download storage buckets
   - Save configuration files

2. **Check billing** - understand current costs

3. **Verify project ID** - double check you're deleting the right one

4. **List resources** - see what will be deleted:
   ```bash
   gcloud config set project PROJECT_ID
   gcloud compute instances list
   gcloud storage buckets list
   bq ls
   ```

5. **Remove from scripts/CI/CD** if project is referenced

---

## Quick Reference Commands

```bash
# List all projects
gcloud projects list

# Delete a project
gcloud projects delete PROJECT_ID

# Delete without confirmation prompt
gcloud projects delete PROJECT_ID --quiet

# Check deletion status
gcloud projects describe PROJECT_ID

# List deleted projects (can restore)
gcloud projects list --filter="lifecycleState:DELETE_REQUESTED"

# Restore deleted project
gcloud projects undelete PROJECT_ID

# Get current project
gcloud config get-value project

# Switch to different project
gcloud config set project OTHER_PROJECT_ID
```

---

## Troubleshooting

### Issue: "Permission denied to delete project"

**Solution:** You need **Owner** role on the project:
```bash
# Check your permissions
gcloud projects get-iam-policy PROJECT_ID \
    --flatten="bindings[].members" \
    --filter="bindings.members:user:$(gcloud config get-value account)"

# If not owner, ask project owner to:
gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="user:YOUR_EMAIL@example.com" \
    --role="roles/owner"
```

### Issue: "Project has active billing"

**Solution:** This is fine - billing stops when project is deleted. Or unlink first:
```bash
gcloud beta billing projects unlink PROJECT_ID
```

### Issue: "Project has liens"

**Solution:** Remove liens first:
```bash
# List liens
gcloud alpha resource-manager liens list --project=PROJECT_ID

# Remove lien (need lien ID)
gcloud alpha resource-manager liens delete LIEN_ID
```

### Issue: "Cannot delete - part of organization"

**Solution:** Need organization admin role, or ask your org admin.

---

## Summary

**To delete a project:**

1. **List projects:**
   ```bash
   gcloud projects list
   ```

2. **Delete:**
   ```bash
   gcloud projects delete PROJECT_ID
   ```

3. **Verify:**
   ```bash
   gcloud projects describe PROJECT_ID
   # Should show: lifecycleState: DELETE_REQUESTED
   ```

**To restore (within 30 days):**
```bash
gcloud projects undelete PROJECT_ID
```

---

**Need to delete old projects? Just run:**
```bash
gcloud projects list  # Find the project ID
gcloud projects delete PROJECT_ID
```

**Billing stops immediately. Project deleted after 30 days.** 🗑️

