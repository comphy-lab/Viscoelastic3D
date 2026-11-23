#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Initialize force_rebuild flag
FORCE_REBUILD=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --force-rebuild)
      FORCE_REBUILD="--force-rebuild"
      shift
      ;;
    *)
      shift
      ;;
  esac
done

# Define the project root relative to the script location
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
PROJECT_ROOT=$(dirname "$(dirname "$SCRIPT_DIR")") # Go two levels up from script dir

# Change to project root to ensure paths work correctly
cd "$PROJECT_ROOT"

# The search index is the committed, reviewed copy. It is updated only by
# .github/workflows/update-search.yml, which imports a pinned comphy-search
# revision through a reviewed pull request. Never fetch it at build time.
for SEARCH_INDEX in "$PROJECT_ROOT/.github/assets/js/search_db.json" "$PROJECT_ROOT/docs/assets/js/search_db.json"; do
    if [ -f "$SEARCH_INDEX" ]; then
        python3 "$PROJECT_ROOT/.github/scripts/validate-search-index.py" "$SEARCH_INDEX"
    fi
done
DOCS_DIR="$PROJECT_ROOT/docs"
PYTHON_SCRIPT="$PROJECT_ROOT/.github/scripts/generate_docs.py"

# Function to display messages
function log_message() {
  echo "$(date +"%Y-%m-%d %H:%M:%S") - $1"
}

# Run the documentation generation script
log_message "Starting documentation generation..."
if [ -n "$FORCE_REBUILD" ]; then
  python3 "$PYTHON_SCRIPT" --force-rebuild
else
  python3 "$PYTHON_SCRIPT"
fi

# Clean HTML files to remove empty anchor tags
log_message "Cleaning HTML files to remove empty anchor tags..."
python3 "$PROJECT_ROOT/.github/scripts/clean_html.py" --dir "$DOCS_DIR" --verbose

if [ $? -ne 0 ]; then
    log_message "Documentation generation failed."
    exit 1
fi

log_message "Documentation generated successfully in $DOCS_DIR"

# Check if docs directory exists
if [ ! -d "$DOCS_DIR" ]; then
    log_message "Error: Docs directory '$DOCS_DIR' not found after generation."
    exit 1
fi
