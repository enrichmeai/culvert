#!/bin/bash
# Scaffolds a new Orchestration Unit using templates

if [ -z "$1" ]; then
    echo "Usage: $0 <system_id>"
    echo "Example: $0 myapp"
    exit 1
fi

SYSTEM_ID_LOWER=$(echo "$1" | tr '[:upper:]' '[:lower:]')
SYSTEM_ID_UPPER=$(echo "$1" | tr '[:lower:]' '[:upper:]')
TARGET_DIR="deployments_embedded/${SYSTEM_ID_LOWER}-orchestration/dags"

echo "🚀 Scaffolding new orchestration for system: ${SYSTEM_ID_UPPER}"

mkdir -p "${TARGET_DIR}"

for template in templates/dags/template_*.py; do
    filename=$(basename "$template")
    target_filename="${SYSTEM_ID_LOWER}_${filename#template_}"

    echo "  📄 Creating DAG: ${target_filename}..."

    sed "s/<SYSTEM_ID>/${SYSTEM_ID_UPPER}/g; s/<system_id>/${SYSTEM_ID_LOWER}/g" "$template" > "${TARGET_DIR}/${target_filename}"
done

# Scaffold GitHub Workflow
echo "  📄 Creating GitHub Workflow: .github/workflows/deploy-${SYSTEM_ID_LOWER}.yml..."
sed "s/<SYSTEM_ID>/${SYSTEM_ID_UPPER}/g; s/<system_id>/${SYSTEM_ID_LOWER}/g" "templates/cicd/template_deploy_workflow.yml" > ".github/workflows/deploy-${SYSTEM_ID_LOWER}.yml"

echo "✅ Done! Files created in ${TARGET_DIR} and .github/workflows/"
echo "Next steps:"
echo "1. Customize REQUIRED_ENTITIES in ${TARGET_DIR}/${SYSTEM_ID_LOWER}_odp_load_dag.py"
echo "2. Customize dbt selectors in ${TARGET_DIR}/${SYSTEM_ID_LOWER}_fdp_transform_dag.py"
