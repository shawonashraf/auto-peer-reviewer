"""Add the markitdown MCP server to an existing .mcp.json (OSP's installer does not)."""
import json
import sys

path = sys.argv[1]
with open(path) as f:
    cfg = json.load(f)
cfg.setdefault("mcpServers", {})["markitdown"] = {
    "command": "/opt/markitdown/bin/markitdown-mcp",
    "args": [],
}
with open(path, "w") as f:
    json.dump(cfg, f, indent=2)
print(f"markitdown added to {path}: {sorted(cfg['mcpServers'])}")
