#!/bin/bash

# Windsurf MCP Configuration Installer
# Installs nodered-mcp server configuration for Windsurf

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
WINDSURF_CONFIG_DIR="${HOME}/.codeium/windsurf"
MCP_CONFIG_FILE="${WINDSURF_CONFIG_DIR}/mcp_config.json"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Windsurf MCP Configuration Installer   ║${NC}"
echo -e "${BLUE}║        for nodered-flow-mcp              ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# Step 1: Verify Windsurf is installed
echo -e "${YELLOW}[1/5]${NC} Checking Windsurf installation..."
if ! command -v windsurf &> /dev/null && [ ! -d "${WINDSURF_CONFIG_DIR}" ]; then
    echo -e "${RED}✗ Windsurf does not appear to be installed${NC}"
    echo "  Install Windsurf from: https://codeium.com/windsurf"
    exit 1
fi
echo -e "${GREEN}✓ Windsurf found${NC}"
echo ""

# Step 2: Verify project setup
echo -e "${YELLOW}[2/5]${NC} Verifying nodered-mcp project..."
if [ ! -f "${PROJECT_DIR}/pyproject.toml" ]; then
    echo -e "${RED}✗ Project directory is not valid${NC}"
    echo "  Expected: ${PROJECT_DIR}"
    exit 1
fi

if [ ! -d "${PROJECT_DIR}/.venv" ] && [ ! -f "${PROJECT_DIR}/uv.lock" ]; then
    echo -e "${YELLOW}⚠ Project dependencies not installed${NC}"
    echo "  Run: cd ${PROJECT_DIR} && uv sync"
    read -p "  Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi
echo -e "${GREEN}✓ Project verified at ${PROJECT_DIR}${NC}"
echo ""

# Step 3: Create Windsurf config directory
echo -e "${YELLOW}[3/5]${NC} Setting up Windsurf config directory..."
mkdir -p "${WINDSURF_CONFIG_DIR}"
echo -e "${GREEN}✓ Config directory ready: ${WINDSURF_CONFIG_DIR}${NC}"
echo ""

# Step 4: Create or update MCP configuration
echo -e "${YELLOW}[4/5]${NC} Creating MCP configuration..."

# Create the MCP config JSON
MCP_CONFIG=$(cat <<EOF
{
  "mcpServers": {
    "nodered-flow-mcp": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "${PROJECT_DIR}",
        "nodered-flow-mcp"
      ],
      "env": {
        "NODERED_URL": "http://localhost:1880",
        "NODERED_READ_ONLY": "true"
      }
    }
  }
}
EOF
)

if [ -f "${MCP_CONFIG_FILE}" ]; then
    echo -e "${YELLOW}⚠ Existing mcp_config.json found${NC}"
    read -p "  Replace with new configuration? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}✓ Skipped${NC}"
    else
        echo "${MCP_CONFIG}" > "${MCP_CONFIG_FILE}"
        echo -e "${GREEN}✓ Configuration updated${NC}"
    fi
else
    echo "${MCP_CONFIG}" > "${MCP_CONFIG_FILE}"
    echo -e "${GREEN}✓ Configuration created${NC}"
fi
echo ""

# Step 5: Verify installation
echo -e "${YELLOW}[5/5]${NC} Verifying installation..."

if [ ! -f "${MCP_CONFIG_FILE}" ]; then
    echo -e "${RED}✗ Failed to create MCP config file${NC}"
    exit 1
fi

# Try to parse JSON
if ! python3 -m json.tool "${MCP_CONFIG_FILE}" > /dev/null 2>&1; then
    echo -e "${RED}✗ Invalid JSON in configuration${NC}"
    exit 1
fi

# Test if we can run the command
echo "  Testing nodered-mcp command..."
if cd "${PROJECT_DIR}" && uv run nodered-flow-mcp --help > /dev/null 2>&1; then
    echo -e "${GREEN}✓ nodered-mcp command is functional${NC}"
else
    echo -e "${YELLOW}⚠ Could not verify nodered-mcp command${NC}"
    echo "  This may be due to missing dependencies. Run: cd ${PROJECT_DIR} && uv sync"
fi

echo ""
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         Installation Complete!         ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo ""
echo "Configuration file: ${MCP_CONFIG_FILE}"
echo ""
echo "Next steps:"
echo "  1. Edit environment variables in mcp_config.json if needed:"
echo "     - NODERED_URL: Node-RED server URL (default: http://localhost:1880)"
echo "     - NODERED_READ_ONLY: Set to 'false' to enable deployments"
echo "  2. Restart Windsurf to load the new MCP configuration"
echo "  3. The 'nodered-flow-mcp' server will be available in Windsurf"
echo ""
echo "View configuration:"
echo "  cat ${MCP_CONFIG_FILE}"
echo ""
