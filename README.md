# JSON Canvas MCP Server

A Model Context Protocol (MCP) server implementation that provides tools for working with JSON Canvas files according to the [official specification](https://jsoncanvas.org/spec/1.0/). This server enables creating, modifying, and validating infinite canvas data structures, with special features for academic paper reading and research note-taking.

## Overview

The JSON Canvas MCP server provides a complete implementation of the JSON Canvas 1.0 specification, enabling:

- Creation and manipulation of infinite canvas data
- Support for all node types (text, file, link, group)
- Edge connections with styling and labels
- Validation against the specification
- Configurable output paths
- **Academic mindmap generation** for paper reading and research notes
- **#td (todo) task resolution** with connected file context support

## Components

### Resources

The server exposes the following resources:

- `canvas://schema`: JSON Schema for validating canvas files
- `canvas://examples/basic`: Basic canvas example demonstrating different features

### Tools

#### Canvas Creation

- **create_canvas**
  - Create a new canvas with specified nodes and edges (generic)
  - Supports all node types: text, file, link, group
  - Auto-generates date-prefixed filenames

- **create_canvas_with_nodes**
  - Create a new canvas with text nodes
  - Supports auto-layout if x/y coordinates are omitted
  - Simple and fast canvas creation

#### Node Operations

- **add_node**
  - Add a node to an existing canvas file
  - Supports all node types with type-specific properties

- **get_node**
  - Get detailed information about a specific node
  - Returns node properties as JSON

- **update_node**
  - Update a node's properties (text, color, position, size)
  - Auto-sizes based on content length
  - Size guide: <100 chars -> 300x150, 100-300 -> 400x200, 300-500 -> 450x280, >500 -> 500x350

- **find_nodes**
  - Search for nodes containing specific text (e.g., '#td')
  - Returns connected nodes for context
  - Identifies file nodes that need to be read

#### Edge Operations

- **add_edge**
  - Connect two nodes in a canvas
  - Auto-generates edge ID with timestamp

- **get_edge**
  - Get detailed information about a specific edge

- **update_edge**
  - Update edge properties (from/to nodes, sides, ends, color, label)
  - Validates node references before updating

#### Mindmap Generation

- **create_mindmap**
  - Create academic mindmaps for paper reading and research notes
  - Attaches to an existing root node
  - Supports nested children up to 6 levels deep
  - Semantic type coloring:
    - `concept` (cyan): Definitions, terminology
    - `method` (green): Algorithms, techniques
    - `finding` (orange): Results, observations
    - `question` (red): Research questions, problems
    - `evidence` (purple): Citations, proofs
  - Optional features: source references, edge labels, visual grouping
  - Layout options: `right` (horizontal) or `down` (vertical)

#### Task Resolution

- **resolve_td**
  - Complete #td (todo) nodes with context-aware content
  - Reads connected file nodes (images, PDFs) for context
  - Auto-sizes the resolved node based on content length

#### Validation

- **validate_canvas**
  - Validate a canvas against the JSON Canvas specification
  - Returns validation results with any errors

## Usage with Claude Desktop / Gemini CLI

### Python venv (Recommended for Windows)

Add this to your MCP client config (e.g., `claude_desktop_config.json` or Gemini CLI settings):

**Windows:**
```json
{
  "mcpServers": {
    "jsoncanvas": {
      "command": "D:/path/to/mcp-server-obsidian-jsoncanvas/.venv/Scripts/python.exe",
      "args": [
        "-m",
        "mcp_server"
      ],
      "env": {
        "OUTPUT_PATH": "D:/path/to/your/obsidian/vault",
        "PYTHONUTF8": "1"
      }
    }
  }
}
```

**macOS/Linux:**
```json
{
  "mcpServers": {
    "jsoncanvas": {
      "command": "/path/to/mcp-server-obsidian-jsoncanvas/.venv/bin/python",
      "args": [
        "-m",
        "mcp_server"
      ],
      "env": {
        "OUTPUT_PATH": "/path/to/your/obsidian/vault"
      }
    }
  }
}
```

### UV

```json
{
  "mcpServers": {
    "jsoncanvas": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/mcp-server-obsidian-jsoncanvas",
        "run",
        "python",
        "-m",
        "mcp_server"
      ],
      "env": {
        "OUTPUT_PATH": "/path/to/your/obsidian/vault"
      }
    }
  }
}
```

### Docker

```json
{
  "mcpServers": {
    "jsoncanvas": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-v",
        "canvas-data:/data",
        "mcp/jsoncanvas"
      ],
      "env": {
        "OUTPUT_PATH": "/data/output"
      }
    }
  }
}
```

## Configuration

The server can be configured using environment variables:

- `OUTPUT_PATH`: Directory where canvas files will be saved (default: "./output")
- `PYTHONUTF8`: Set to `1` on Windows to ensure proper UTF-8 encoding

## Building

### Docker Build

```bash
docker build -t mcp/jsoncanvas .
```

### Local Build

**Windows (PowerShell):**
```powershell
# Install uv if not already installed
irm https://astral.sh/uv/install.ps1 | iex

# Create virtual environment and install dependencies
uv venv
.venv\Scripts\activate
uv pip install -e .
```

**macOS/Linux:**
```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate
uv pip install -e .
```

## Example Usage

### Creating a Simple Canvas

```python
from jsoncanvas import Canvas, TextNode, Edge

# Create nodes
title = TextNode(
    id="title",
    x=100,
    y=100,
    width=400,
    height=100,
    text="# Hello Canvas\n\nThis is a demonstration.",
    color="#4285F4"
)

info = TextNode(
    id="info",
    x=600,
    y=100,
    width=300,
    height=100,
    text="More information here",
    color="2"  # Using preset color
)

# Create canvas
canvas = Canvas()
canvas.add_node(title)
canvas.add_node(info)

# Connect nodes
edge = Edge(
    id="edge1",
    from_node="title",
    to_node="info",
    from_side="right",
    to_side="left",
    label="Connection"
)
canvas.add_edge(edge)
```

### Creating an Academic Mindmap

Use the `create_mindmap` tool to generate structured research notes:

```json
{
  "filename": "paper-notes.canvas",
  "root_node_id": "paper-title",
  "children": [
    {
      "title": "Self-Attention Complexity",
      "text": "标准自注意力的时间和空间复杂度均为O(n²)，n为序列长度。",
      "type": "concept",
      "source": "Section 3.1",
      "children": [
        {
          "title": "Linear Attention",
          "text": "通过核函数分解将复杂度降至O(n)。",
          "type": "method"
        }
      ]
    }
  ],
  "max_depth": 4,
  "layout": "right"
}
```

### Resolving #td Tasks

1. Use `find_nodes` to locate #td nodes and connected context
2. If connected to file nodes, read those files first
3. Use `resolve_td` to complete the task with appropriate content

## License

This MCP server is licensed under the MIT License. This means you are free to use, modify, and distribute the software, subject to the terms and conditions of the MIT License. For more details, please see the LICENSE file in the project repository.
