#!/usr/bin/env bash
# Scaffold a new service from _service-template/ after init.py has run.
# Run from the project root. See README "Adding a new service" for the manual
# CI-matrix step at the end.
set -euo pipefail

if [ $# -ne 1 ]; then
    echo "Usage: $0 <service-name>"
    echo "Example: $0 wiki-store"
    exit 1
fi

NEW_NAME="$1"
NEW_MODULE="${NEW_NAME//-/_}"

# Name validation: lowercase kebab-case, must start with a letter, end with letter/digit.
if ! [[ "$NEW_NAME" =~ ^[a-z][a-z0-9-]*[a-z0-9]$ ]]; then
    echo "Error: service name must be lowercase kebab-case (e.g. 'wiki-store')."
    exit 1
fi

if [ ! -d "_service-template" ]; then
    echo "Error: _service-template/ not found. Run this from the project root."
    exit 1
fi

if [ -d "services/$NEW_NAME" ]; then
    echo "Error: services/$NEW_NAME already exists."
    exit 1
fi

# Post-init, _service-template carries the first service's values (init.py
# substituted them). Extract those so we can rewrite to the new name.
OLD_NAME=$(grep '^name = ' _service-template/pyproject.toml | head -1 | sed 's/name = "//; s/".*//')
OLD_MODULE="${OLD_NAME//-/_}"

if [ -z "$OLD_NAME" ]; then
    echo "Error: could not read first service name from _service-template/pyproject.toml."
    echo "Has init.py been run yet?"
    exit 1
fi
if [[ "$OLD_NAME" == *"{{"* ]]; then
    echo "Error: _service-template/ still has placeholders. Run init.py first."
    exit 1
fi

mkdir -p services
cp -r _service-template "services/$NEW_NAME"

# The package directory in _service-template is literally named `service_module`
# (init.py only renames it inside the copied service, not in _service-template).
if [ -d "services/$NEW_NAME/src/service_module" ]; then
    mv "services/$NEW_NAME/src/service_module" "services/$NEW_NAME/src/$NEW_MODULE"
fi

# Substitute names in service files. -i.bak works on both BSD (macOS) and GNU sed.
find "services/$NEW_NAME" -type f \( -name "*.toml" -o -name "*.py" -o -name ".envrc" \) \
    -exec sed -i.bak "s/$OLD_NAME/$NEW_NAME/g; s/$OLD_MODULE/$NEW_MODULE/g" {} \;
find "services/$NEW_NAME" -name "*.bak" -delete

echo ""
echo "Created services/$NEW_NAME (module: $NEW_MODULE)"
echo ""
echo "Next steps:"
echo "  1. Add '$NEW_NAME' to the matrix in .github/workflows/ci.yml"
echo "  2. cd services/$NEW_NAME && direnv allow ."
echo "  3. uv sync --group dev"
