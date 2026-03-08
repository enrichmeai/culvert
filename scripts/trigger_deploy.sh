#!/bin/bash
# Trigger deploy workflow with version 1.0.6

echo "Triggering Deploy Generic workflow..."
gh workflow run deploy-generic.yml -f environment=dev -f library_version=1.0.6

echo ""
echo "Waiting 5 seconds for workflow to start..."
sleep 5

echo ""
echo "Recent workflow runs:"
gh run list -L 5

echo ""
echo "To watch the deploy workflow:"
echo "  gh run watch"

