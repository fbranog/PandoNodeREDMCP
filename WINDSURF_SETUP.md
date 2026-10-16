# Windsurf MCP Setup Guide

This guide explains how to configure Windsurf to use the **nodered-flow-mcp** server for engineering Node-RED flows.

## Quick Start

```bash
./install-windsurf-mcp.sh
```

The installer will:
- Verify Windsurf is installed
- Check the nodered-mcp project setup
- Create the Windsurf config directory
- Generate the MCP configuration file
- Validate the installation

## What It Does

The installation script configures Windsurf to communicate with the nodered-mcp MCP server, which allows you to:

- **Inspect** Node-RED flows and inspect their structure
- **Learn** node schemas and usage patterns
- **Edit** flows in a local draft before deploying
- **Validate** changes before they reach the server
- **Diff** changes to review what's being deployed
- **Deploy** flows with explicit user approval

## Prerequisites

- **Windsurf** installed ([codeium.com/windsurf](https://codeium.com/windsurf))
- **Linux** (macOS/Windows support can be added)
- **uv** package manager installed
- **Python 3.9+**

### Install Prerequisites

```bash
# Install uv (Rust-based Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Verify installation
uv --version
```

## Setup Instructions

### Step 1: Prepare the Project

```bash
cd /home/frank/Programs/working/nodered_mcp

# Install dependencies
uv sync

# Verify the environment
uv run pytest
```

### Step 2: Configure Node-RED Connection

Edit `.env` file with your Node-RED server details:

```bash
cp .env.example .env
# Edit .env with your server URL and credentials
```

Example `.env`:

```env
NODERED_URL=http://localhost:1880
NODERED_AUTH_TOKEN=your_auth_token_here
NODERED_READ_ONLY=true
```

### Step 3: Run the Installer

```bash
./install-windsurf-mcp.sh
```

Follow the on-screen prompts. The script will create:

- `~/.codeium/windsurf/mcp_config.json` - MCP server configuration

### Step 4: Restart Windsurf

Close and reopen Windsurf to load the new MCP configuration.

## Configuration Details

The installer creates a configuration in `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "nodered-flow-mcp": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/project",
        "nodered-flow-mcp"
      ],
      "env": {
        "NODERED_URL": "http://localhost:1880",
        "NODERED_READ_ONLY": "true"
      }
    }
  }
}
```

### Environment Variables

- **NODERED_URL** - Node-RED server URL (default: `http://localhost:1880`)
- **NODERED_READ_ONLY** - Restrict to read-only mode (default: `true`)
  - `true` - Can inspect flows but cannot deploy
  - `false` - Can deploy changes (requires valid auth token)
- **NODERED_AUTH_TOKEN** - Authentication token for Node-RED API

## Verifying the Installation

After restarting Windsurf, verify the MCP server is available:

```bash
# View the configuration
cat ~/.codeium/windsurf/mcp_config.json

# Test the MCP server directly
cd /path/to/nodered_mcp
uv run nodered-flow-mcp --help
```

## Troubleshooting

### Windsurf doesn't recognize the MCP server

1. Verify the config file exists:
   ```bash
   cat ~/.codeium/windsurf/mcp_config.json
   ```

2. Check JSON syntax:
   ```bash
   python3 -m json.tool ~/.codeium/windsurf/mcp_config.json
   ```

3. Restart Windsurf completely (quit and reopen)

### "Command not found: nodered-flow-mcp"

1. Ensure project dependencies are installed:
   ```bash
   cd /path/to/nodered_mcp
   uv sync
   ```

2. Test the command:
   ```bash
   uv run nodered-flow-mcp --help
   ```

### Connection to Node-RED fails

1. Verify Node-RED is running:
   ```bash
   curl http://localhost:1880/health
   ```

2. Check `.env` configuration:
   ```bash
   cat .env
   ```

3. Verify the URL and auth token are correct

### Permission denied when running installer

Make the script executable:

```bash
chmod +x install-windsurf-mcp.sh
```

## Uninstalling

To remove the MCP configuration:

```bash
rm ~/.codeium/windsurf/mcp_config.json
```

## Advanced Configuration

### Custom Node-RED URL

Edit the MCP config to point to a different Node-RED instance:

```json
{
  "mcpServers": {
    "nodered-flow-mcp": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/project", "nodered-flow-mcp"],
      "env": {
        "NODERED_URL": "https://your-nodered-server.com",
        "NODERED_AUTH_TOKEN": "your_token_here",
        "NODERED_READ_ONLY": "false"
      }
    }
  }
}
```

### Enable Deployments

To allow Windsurf to deploy flows (requires proper authentication):

1. Set `NODERED_READ_ONLY=false` in `.env`
2. Add a valid `NODERED_AUTH_TOKEN` in `.env`
3. Update the MCP config and restart Windsurf

## Support

For issues or questions:

- Check the main [README.md](README.md)
- Review [Node-RED Admin API](https://nodered.org/docs/api/admin)
- Report issues at [GitHub](https://github.com/anomalyco/opencode)

## Safety Model

- **Read-only mode** (default): Safe for exploration, drafts are local-only
- **Deployments**: Require explicit approval token bound to specific draft content
- **Conflict detection**: Uses Admin API v2 with revision checking to prevent overwrites
- **Credentials**: Never read or stored in configuration
- **Rollback**: Pre-deploy snapshots saved for manual recovery

See [README.md](README.md) for complete safety details.
