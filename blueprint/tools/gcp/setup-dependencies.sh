#!/bin/bash
# Setup Script - Install all dependencies for LOA pipeline

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║           📦 INSTALLING LOA DEPENDENCIES                     ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

cd /path/to/project

echo "📋 Step 1: Upgrading pip..."
pip3 install --upgrade pip --quiet

echo ""
echo "📦 Step 2: Installing LOA dependencies..."
echo "   (This may take 2-3 minutes...)"
echo ""

pip3 install -r requirements-ci.txt --quiet

echo ""
echo "✅ Step 3: Verifying installation..."
echo ""

# Test Apache Beam
if python3 -c "import apache_beam" 2>/dev/null; then
    VERSION=$(python3 -c "import apache_beam; print(apache_beam.__version__)")
    echo "   ✓ Apache Beam $VERSION"
else
    echo "   ✗ Apache Beam - FAILED"
fi

# Test Google Cloud BigQuery
if python3 -c "import google.cloud.bigquery" 2>/dev/null; then
    echo "   ✓ Google Cloud BigQuery"
else
    echo "   ✗ Google Cloud BigQuery - FAILED"
fi

# Test LOA modules
if python3 -c "import sys; sys.path.insert(0, '.'); from loa_common.validation import validate_application_record" 2>/dev/null; then
    echo "   ✓ LOA Common Modules"
else
    echo "   ✗ LOA Common Modules - FAILED"
fi

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║                  ✅ SETUP COMPLETE!                           ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo "🚀 Ready to trigger the pipeline:"
echo "   ./trigger-pipeline-now.sh"
echo ""

