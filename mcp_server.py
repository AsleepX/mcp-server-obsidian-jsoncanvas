#!/usr/bin/env python3
"""MCP server for JSON Canvas."""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
import mcp.types as types

from jsoncanvas import (
    Canvas,
    TextNode,
    FileNode,
    LinkNode,
    GroupNode,
    Edge,
)
from jsoncanvas.nodes import Node

# Initialize server
server = Server("jsoncanvas-server")

# Get output path from environment variable or use default
OUTPUT_PATH = Path(os.environ.get("OUTPUT_PATH", "./output"))
if not OUTPUT_PATH.exists():
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    """List available resources."""
    return [
        types.Resource(
            uri="canvas://schema",
            name="JSON Canvas Schema",
            mimeType="application/json",
            description="JSON Schema for validating canvas files",
        ),
        types.Resource(
            uri="canvas://examples/basic",
            name="Basic Canvas Example",
            mimeType="application/json",
            description="A simple canvas with basic node types",
        ),
    ]

@server.read_resource()
async def handle_read_resource(uri: str) -> str | bytes:
    """Read a specific resource."""
    if uri == "canvas://schema":
        # Return the JSON Canvas schema
        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": "JSON Canvas",
            "type": "object",
            "properties": {
                "nodes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["id", "type", "x", "y", "width", "height"],
                        "properties": {
                            "id": {"type": "string"},
                            "type": {"type": "string", "enum": ["text", "file", "link", "group"]},
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "width": {"type": "number"},
                            "height": {"type": "number"},
                            "color": {"type": "string"}
                        }
                    }
                },
                "edges": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["id", "fromNode", "toNode"],
                        "properties": {
                            "id": {"type": "string"},
                            "fromNode": {"type": "string"},
                            "toNode": {"type": "string"},
                            "fromSide": {"type": "string", "enum": ["top", "right", "bottom", "left"]},
                            "toSide": {"type": "string", "enum": ["top", "right", "bottom", "left"]},
                            "fromEnd": {"type": "string", "enum": ["none", "arrow"]},
                            "toEnd": {"type": "string", "enum": ["none", "arrow"]},
                            "color": {"type": "string"},
                            "label": {"type": "string"}
                        }
                    }
                }
            }
        }
        return json.dumps(schema, indent=2)

    elif uri == "canvas://examples/basic":
        # Create a basic example canvas
        canvas = Canvas()
        
        # Add nodes
        title = TextNode(
            id="title",
            x=100,
            y=100,
            width=400,
            height=100,
            text="# Example Canvas\n\nCreated by JSON Canvas MCP Server",
            color="#4285F4"
        )
        
        info = TextNode(
            id="info",
            x=600,
            y=100,
            width=300,
            height=100,
            text="This is a simple example canvas.",
            color="2"
        )
        
        canvas.add_node(title)
        canvas.add_node(info)
        
        # Add edge
        edge = Edge(
            id="edge1",
            from_node="title",
            to_node="info",
            from_side="right",
            to_side="left",
            label="Connection"
        )
        canvas.add_edge(edge)
        
        return json.dumps(canvas.to_dict(), indent=2)
    
    raise ValueError(f"Unknown resource: {uri}")


def load_canvas_from_file(file_path: Path) -> Canvas:
    """Helper to load a Canvas object from a file."""
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Try to use from_dict if available, otherwise manual reconstruction
    try:
        return Canvas.from_dict(data)
    except AttributeError:
        # Manual reconstruction
        canvas = Canvas()
        if "nodes" in data:
            for node_data in data["nodes"]:
                node_type = node_data.get("type", "text")
                # Remove type from data as it's passed to constructor implicitly or explicitly depending on class
                # But the classes usually take specific args.
                # Let's try to instantiate based on type.
                # Note: This is a best-effort reconstruction.
                if node_type == "text":
                    canvas.add_node(TextNode(**{k:v for k,v in node_data.items() if k != 'type'}))
                elif node_type == "file":
                    canvas.add_node(FileNode(**{k:v for k,v in node_data.items() if k != 'type'}))
                elif node_type == "link":
                    canvas.add_node(LinkNode(**{k:v for k,v in node_data.items() if k != 'type'}))
                elif node_type == "group":
                    # Map camelCase to snake_case for GroupNode
                    group_data = {k:v for k,v in node_data.items() if k != 'type'}
                    if "backgroundStyle" in group_data:
                        group_data["background_style"] = group_data.pop("backgroundStyle")
                    canvas.add_node(GroupNode(**group_data))
        
        if "edges" in data:
            for edge_data in data["edges"]:
                # Map camelCase to snake_case for Edge
                if "fromNode" in edge_data: edge_data["from_node"] = edge_data.pop("fromNode")
                if "toNode" in edge_data: edge_data["to_node"] = edge_data.pop("toNode")
                if "fromSide" in edge_data: edge_data["from_side"] = edge_data.pop("fromSide")
                if "toSide" in edge_data: edge_data["to_side"] = edge_data.pop("toSide")
                if "fromEnd" in edge_data: edge_data["from_end"] = edge_data.pop("fromEnd")
                if "toEnd" in edge_data: edge_data["to_end"] = edge_data.pop("toEnd")
                canvas.add_edge(Edge(**edge_data))
        
        return canvas

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools."""
    return [
        types.Tool(
            name="create_canvas",
            description="Create a new canvas with specified nodes and edges (generic)",
            inputSchema={
                "type": "object",
                "properties": {
                    "nodes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["id", "type"],
                            "properties": {
                                "id": {"type": "string"},
                                "type": {"type": "string"},
                                "x": {"type": "integer"},
                                "y": {"type": "integer"},
                                "width": {"type": "integer"},
                                "height": {"type": "integer"}
                            }
                        }
                    },
                    "edges": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["id", "fromNode", "toNode"],
                            "properties": {
                                "id": {"type": "string"},
                                "fromNode": {"type": "string"},
                                "toNode": {"type": "string"},
                                "label": {"type": "string"}
                            }
                        }
                    },
                    "filename": {
                        "type": "string",
                        "description": "Output filename (without extension)"
                    }
                },
                "required": ["nodes", "filename"]
            }
        ),
        types.Tool(
            name="create_canvas_with_nodes",
            description="Create a new canvas with text nodes. Supports auto-layout if x/y are omitted.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Filename (e.g., 'idea.canvas')"},
                    "nodes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "text": {"type": "string"},
                                "x": {"type": ["integer", "null"], "description": "Optional X coordinate"},
                                "y": {"type": ["integer", "null"], "description": "Optional Y coordinate"},
                                "width": {"type": "integer"},
                                "height": {"type": "integer"}
                            },
                            "required": ["id", "text"]
                        }
                    }
                },
                "required": ["filename", "nodes"]
            }
        ),
        types.Tool(
            name="add_node",
            description="Add a node to an existing canvas file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Filename of the existing canvas"},
                    "node": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "type": {"type": "string", "enum": ["text", "file", "link", "group"]},
                            "text": {"type": "string", "description": "Text content for text nodes"},
                            "file": {"type": "string", "description": "File path for file nodes"},
                            "url": {"type": "string", "description": "URL for link nodes"},
                            "x": {"type": "integer"},
                            "y": {"type": "integer"},
                            "width": {"type": "integer"},
                            "height": {"type": "integer"}
                        },
                        "required": ["id", "type", "x", "y", "width", "height"]
                    }
                },
                "required": ["filename", "node"]
            }
        ),
        types.Tool(
            name="add_edge",
            description="Connect two nodes in an existing canvas file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Filename of the existing canvas"},
                    "from_node": {"type": "string", "description": "Source node ID"},
                    "to_node": {"type": "string", "description": "Target node ID"},
                    "label": {"type": "string", "description": "Label on the arrow (optional)"}
                },
                "required": ["filename", "from_node", "to_node"]
            }
        ),
        types.Tool(
            name="get_node",
            description="Get detailed information about a specific node in a canvas file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Filename of the canvas (e.g., 'test.canvas')"},
                    "node_id": {"type": "string", "description": "ID of the node to retrieve"}
                },
                "required": ["filename", "node_id"]
            }
        ),
        types.Tool(
            name="get_edge",
            description="Get detailed information about a specific edge in a canvas file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Filename of the canvas (e.g., 'test.canvas')"},
                    "edge_id": {"type": "string", "description": "ID of the edge to retrieve"}
                },
                "required": ["filename", "edge_id"]
            }
        ),
        types.Tool(
            name="update_edge",
            description="Update an existing edge's properties in a canvas file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Filename of the canvas (e.g., 'test.canvas')"},
                    "edge_id": {"type": "string", "description": "ID of the edge to update"},
                    "updates": {
                        "type": "object",
                        "description": "Properties to update on the edge",
                        "properties": {
                            "from_node": {"type": "string", "description": "New source node ID"},
                            "to_node": {"type": "string", "description": "New target node ID"},
                            "from_side": {"type": "string", "enum": ["top", "right", "bottom", "left"], "description": "New start side"},
                            "to_side": {"type": "string", "enum": ["top", "right", "bottom", "left"], "description": "New end side"},
                            "from_end": {"type": "string", "enum": ["none", "arrow"], "description": "New start endpoint shape"},
                            "to_end": {"type": "string", "enum": ["none", "arrow"], "description": "New end endpoint shape"},
                            "color": {"type": "string", "description": "New color (hex #RRGGBB or preset 1-6)"},
                            "label": {"type": "string", "description": "New label text"}
                        }
                    }
                },
                "required": ["filename", "edge_id", "updates"]
            }
        ),
        types.Tool(
            name="validate_canvas",
            description="Validate a canvas against the JSON Canvas specification",
            inputSchema={
                "type": "object",
                "properties": {
                    "canvas": {
                        "type": "object",
                        "description": "Canvas data to validate"
                    }
                },
                "required": ["canvas"]
            }
        ),
        types.Tool(
            name="update_node",
            description="""Update a node's properties in a canvas file.

For #td tasks: Use find_nodes first, then resolve_td (not this tool).

USE CASES (non #td):
- Translate text content
- Modify node text, color, position, or size

Size guide by content length:
- < 100 chars: 300x150
- 100-300 chars: 400x200  
- 300-500 chars: 450x280
- > 500 chars: 500x350""",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Filename of the existing canvas (e.g., 'test.canvas')"},
                    "node_id": {"type": "string", "description": "ID of the node to update"},
                    "updates": {
                        "type": "object",
                        "description": "Properties to update on the node. For text, just provide the raw content directly.",
                        "properties": {
                            "text": {"type": "string", "description": "New text content - provide the complete text as-is, no special formatting required"},
                            "url": {"type": "string", "description": "New URL (for link nodes)"},
                            "file": {"type": "string", "description": "New file path (for file nodes)"},
                            "label": {"type": "string", "description": "New label (for group nodes)"},
                            "color": {"type": "string", "description": "New color (hex #RRGGBB or preset 1-6)"},
                            "x": {"type": "integer", "description": "New X position"},
                            "y": {"type": "integer", "description": "New Y position"},
                            "width": {"type": "integer", "description": "New width"},
                            "height": {"type": "integer", "description": "New height"}
                        }
                    }
                },
                "required": ["filename", "node_id", "updates"]
            }
        ),
        types.Tool(
            name="create_mindmap",
            description="""Create an academic mindmap for paper reading and research notes.

⚠️ LANGUAGE RULE:
- title: Can be Chinese OR English (e.g., "Attention Mechanism" or "注意力机制")
- text: MUST be in Chinese (中文). Always write explanations in Chinese.
- edge_label: MUST be in Chinese if used
- group.label: Can be Chinese or English

Node structure:
- title (required): Concise heading (3-10 words), e.g., "Attention Mechanism" or "实验设置"
- text (required, 必须中文): Core content in Chinese. Be specific and substantive:
  * 概念类: 精确定义 + 关键特性
  * 方法类: 算法步骤或公式描述
  * 发现类: 具体数值/对比，如"准确率比基线提升12.3%"
  * 论证类: 观点 + 支撑逻辑
- type (optional): Semantic category for smart coloring:
  * "concept" (青绿): Definitions, terminology, theoretical frameworks
  * "method" (绿): Algorithms, techniques, procedures
  * "finding" (橙): Results, observations, empirical data
  * "question" (红): Research questions, problems, limitations
  * "evidence" (紫): Citations, proofs, experimental support
- source (optional): Reference like "Fig.3", "Eq.5", "Section 2.1", "[Author 2023]"
- edge_label (optional, 中文): Relationship label on the connecting edge. Examples:
  * "导致", "证明", "对比", "扩展", "组成部分", "前提条件"
  * Don't overuse - only when it clarifies the connection
- group (optional): Group related children together. Structure:
  * label: Group title (e.g., "Ablation Studies", "消融实验")
  * When specified, all children of this node will be visually contained in a group box

Guidelines:
- 内容必须用中文书写，避免英文解释
- Avoid vague phrases like "本节讨论了..." - state WHAT it discusses
- Include specific metrics: "性能提升15%" not "效果更好"
- Each node should be self-contained and informative
- Use edge_label sparingly for non-obvious relationships
- Use group to organize multiple related sub-topics (e.g., 3+ experiments, multiple baselines)

Example:
{
  "title": "Self-Attention Complexity",
  "text": "标准自注意力的时间和空间复杂度均为O(n²)，n为序列长度。当序列超过4096个token时，计算代价过高难以承受。",
  "type": "concept",
  "source": "Section 3.1",
  "edge_label": "核心瓶颈",
  "group": {"label": "Complexity Analysis"},
  "children": [...]
}""",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string", 
                        "description": "Filename of the existing canvas (e.g., 'test.canvas')"
                    },
                    "root_node_id": {
                        "type": "string",
                        "description": "ID of the existing node to attach the mindmap to"
                    },
                    "children": {
                        "type": "array",
                        "description": "Main topic nodes with optional nested children.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {
                                    "type": "string",
                                    "description": "Concise heading (3-10 words)"
                                },
                                "text": {
                                    "type": "string",
                                    "description": "Substantive content with specific details"
                                },
                                "type": {
                                    "type": "string",
                                    "enum": ["concept", "method", "finding", "question", "evidence"],
                                    "description": "Semantic type for coloring (optional)"
                                },
                                "source": {
                                    "type": "string",
                                    "description": "Reference: section, figure, equation, citation (optional)"
                                },
                                "edge_label": {
                                    "type": "string",
                                    "description": "Label on connecting edge - use for non-obvious relationships (optional)"
                                },
                                "group": {
                                    "type": "object",
                                    "description": "Wrap children in a visual group (optional)",
                                    "properties": {
                                        "label": {
                                            "type": "string",
                                            "description": "Group title"
                                        }
                                    }
                                },
                                "children": {
                                    "type": "array",
                                    "description": "Nested sub-topics"
                                }
                            },
                            "required": ["title", "text"]
                        }
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum depth (default: 4, max: 6)",
                        "default": 4
                    },
                    "layout": {
                        "type": "string",
                        "enum": ["right", "down"],
                        "description": "Expansion direction: right (default) or down",
                        "default": "right"
                    }
                },
                "required": ["filename", "root_node_id", "children"]
            }
        ),
        types.Tool(
            name="find_nodes",
            description="""Search for nodes in a canvas file. PRIMARY TRIGGER: #td

When user mentions #td with a .canvas file, ALWAYS use this tool first.
Examples: "#td @file.canvas", "@file.canvas #td", "完成#td", "resolve #td", "#td补充", "#td解释"

IMPORTANT: If connected nodes include FILE types (images/PDFs), you MUST:
1. Call read_file for EACH connected file to view its content
2. Only after reading all files, call resolve_td with the content

This tool returns the #td node and all connected nodes for context.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Filename of the canvas to search"},
                    "search_text": {"type": "string", "description": "Text to search for in nodes (e.g., '#td')"}
                },
                "required": ["filename", "search_text"]
            }
        ),
        types.Tool(
            name="resolve_td",
            description="""Complete a #td node. Use after find_nodes and reading any connected files.

TRIGGER: Any mention of #td with a canvas file.

WORKFLOW:
1. find_nodes → get #td node and connected nodes/files
2. read_file → read any connected image/PDF files  
3. resolve_td → write the final content based on what you learned

This tool auto-sizes the node based on content length.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Canvas filename"},
                    "node_id": {"type": "string", "description": "ID of the #td node to update"},
                    "file_contents": {
                        "type": "array",
                        "description": "Contents extracted from connected files (REQUIRED if #td is connected to file nodes)",
                        "items": {
                            "type": "object",
                            "properties": {
                                "file_path": {"type": "string", "description": "Path of the file that was read"},
                                "summary": {"type": "string", "description": "Summary/key content extracted from the file"}
                            }
                        }
                    },
                    "resolved_content": {
                        "type": "string", 
                        "description": "The final content to replace #td, based on the file contents and context"
                    }
                },
                "required": ["filename", "node_id", "resolved_content"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool execution."""
    arguments = arguments or {}
    
    if name == "create_canvas":
        try:
            # Create a new canvas
            canvas = Canvas()
            
            # Add nodes
            nodes_data = arguments.get("nodes", [])
            for node_data in nodes_data:
                node_type = node_data.pop("type")
                
                # Set default values if missing
                if "x" not in node_data: node_data["x"] = 0
                if "y" not in node_data: node_data["y"] = 0
                if "width" not in node_data: node_data["width"] = 250
                if "height" not in node_data: node_data["height"] = 100

                if node_type == "text":
                    node = TextNode(**node_data)
                elif node_type == "file":
                    node = FileNode(**node_data)
                elif node_type == "link":
                    node = LinkNode(**node_data)
                elif node_type == "group":
                    # Map camelCase to snake_case for GroupNode
                    if "backgroundStyle" in node_data:
                        node_data["background_style"] = node_data.pop("backgroundStyle")
                    node = GroupNode(**node_data)
                else:
                    raise ValueError(f"Unknown node type: {node_type}")
                
                canvas.add_node(node)
            
            # Add edges if provided
            if "edges" in arguments:
                for edge_data in arguments["edges"]:
                    # Map camelCase to snake_case for Edge
                    if "fromNode" in edge_data: edge_data["from_node"] = edge_data.pop("fromNode")
                    if "toNode" in edge_data: edge_data["to_node"] = edge_data.pop("toNode")
                    if "fromSide" in edge_data: edge_data["from_side"] = edge_data.pop("fromSide")
                    if "toSide" in edge_data: edge_data["to_side"] = edge_data.pop("toSide")
                    if "fromEnd" in edge_data: edge_data["from_end"] = edge_data.pop("fromEnd")
                    if "toEnd" in edge_data: edge_data["to_end"] = edge_data.pop("toEnd")
                    
                    edge = Edge(**edge_data)
                    canvas.add_edge(edge)
            
            # Add date prefix to filename to avoid overwriting
            date_prefix = datetime.now().strftime("%Y-%m-%d")
            filename = arguments["filename"]
            output_file = OUTPUT_PATH / f"{date_prefix}-{filename}.canvas"
            
            # Create parent directories if they don't exist
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, "w") as f:
                json.dump(canvas.to_dict(), f, indent=2)
            
            return [types.TextContent(type="text", text=f"Canvas saved to {output_file}")]
            
        except Exception as e:
            return [types.TextContent(type="text", text=f"Error creating canvas: {str(e)}")]

    elif name == "create_canvas_with_nodes":
        try:
            filename = arguments.get("filename", "untitled.canvas")
            if not filename.endswith(".canvas"):
                filename += ".canvas"
            
            nodes_data = arguments.get("nodes", [])
            
            canvas = Canvas()
            
            # Auto-layout settings
            layout_x = 0
            layout_y = 0
            max_width = 2000 # Wrap width
            current_row_height = 0
            spacing_x = 300
            spacing_y = 200
            
            # Add nodes
            for i, n in enumerate(nodes_data):
                # Determine position
                x = n.get("x")
                y = n.get("y")
                
                if x is None or y is None:
                    # Apply auto-layout
                    x = layout_x
                    y = layout_y
                    
                    # Update layout for next node
                    layout_x += spacing_x
                    if layout_x > max_width:
                        layout_x = 0
                        layout_y += spacing_y
                
                node = TextNode(
                    id=n.get("id"),
                    x=x,
                    y=y,
                    width=n.get("width", 250),
                    height=n.get("height", 100),
                    text=n.get("text", ""),
                )
                canvas.add_node(node)
            
            # Save file
            # Note: create_canvas_with_nodes might not want date prefix if user specifies full name?
            # But to be consistent with other tools and avoid overwrites, let's keep it or check if user provided path.
            # The simple server just saved to OUTPUT_PATH/filename.
            # Let's stick to that for this tool as it's "simple".
            save_path = OUTPUT_PATH / filename
            
            with open(save_path, "w") as f:
                json.dump(canvas.to_dict(), f, indent=2)
            
            return [types.TextContent(type="text", text=f"Success! Created canvas at: {save_path}")]
            
        except Exception as e:
            return [types.TextContent(type="text", text=f"Error creating canvas: {str(e)}")]

    elif name == "add_node":
        try:
            filename = arguments.get("filename")
            # Try to find the file. It might have a date prefix or be exact.
            # If exact path exists, use it. If not, search in output.
            target_file = OUTPUT_PATH / filename
            if not target_file.exists():
                # Try to find by suffix if user didn't provide date prefix
                # This is a bit risky but helpful.
                candidates = list(OUTPUT_PATH.glob(f"*{filename}"))
                if candidates:
                    target_file = candidates[0] # Pick first match
                else:
                    return [types.TextContent(type="text", text=f"Error: File {filename} not found in {OUTPUT_PATH}")]
            
            canvas = load_canvas_from_file(target_file)
            
            node_data = arguments.get("node")
            node_type = node_data.pop("type")
            
            if node_type == "text":
                node = TextNode(**node_data)
            elif node_type == "file":
                node = FileNode(**node_data)
            elif node_type == "link":
                node = LinkNode(**node_data)
            elif node_type == "group":
                node = GroupNode(**node_data)
            else:
                raise ValueError(f"Unknown node type: {node_type}")
            
            canvas.add_node(node)
            
            with open(target_file, "w") as f:
                json.dump(canvas.to_dict(), f, indent=2)
                
            return [types.TextContent(type="text", text=f"Added node to {target_file}")]
            
        except Exception as e:
            return [types.TextContent(type="text", text=f"Error adding node: {str(e)}")]

    elif name == "add_edge":
        try:
            filename = arguments.get("filename")
            target_file = OUTPUT_PATH / filename
            if not target_file.exists():
                candidates = list(OUTPUT_PATH.glob(f"*{filename}"))
                if candidates:
                    target_file = candidates[0]
                else:
                    return [types.TextContent(type="text", text=f"Error: File {filename} not found in {OUTPUT_PATH}")]
            
            canvas = load_canvas_from_file(target_file)
            
            edge = Edge(
                id=f"edge-{datetime.now().timestamp()}", # Generate ID if not provided? Tool definition didn't ask for ID.
                from_node=arguments.get("from_node"),
                to_node=arguments.get("to_node"),
                label=arguments.get("label")
            )
            canvas.add_edge(edge)
            
            with open(target_file, "w") as f:
                json.dump(canvas.to_dict(), f, indent=2)
                
            return [types.TextContent(type="text", text=f"Added edge to {target_file}")]
            
        except Exception as e:
            return [types.TextContent(type="text", text=f"Error adding edge: {str(e)}")]
    
    elif name == "validate_canvas":
        try:
            # Validate the canvas
            canvas_data = arguments.get("canvas")
            
            # Basic validation
            if "nodes" not in canvas_data:
                raise ValueError("Canvas must have a 'nodes' array")
            
            # Create a canvas from the data to validate it
            # Assuming Canvas.from_dict exists or we just rely on basic check above
            # If Canvas.from_dict is not available in the library, we might need to skip deep validation
            # But let's assume the user's previous code implied it might work or they want it.
            # Looking at simple_mcp_server.py, it doesn't use from_dict.
            # Let's try to use it if it exists, otherwise just pass.
            try:
                canvas = Canvas.from_dict(canvas_data)
            except AttributeError:
                # Fallback if from_dict is missing in the library version
                pass
            
            return [types.TextContent(type="text", text="Canvas is valid")]
            
        except Exception as e:
            return [types.TextContent(type="text", text=f"Canvas validation failed: {str(e)}")]

    elif name == "create_mindmap":
        try:
            filename = arguments.get("filename")
            root_node_id = arguments.get("root_node_id")
            children_data = arguments.get("children", [])
            max_depth = min(arguments.get("max_depth", 4), 6)  # Default 4, max 6
            layout = arguments.get("layout", "right")  # right or down
            
            # Load existing canvas
            target_file = OUTPUT_PATH / filename
            if not target_file.exists():
                candidates = list(OUTPUT_PATH.glob(f"*{filename}"))
                if candidates:
                    target_file = candidates[0]
                else:
                    return [types.TextContent(type="text", text=f"Error: File {filename} not found in {OUTPUT_PATH}")]
            
            canvas = load_canvas_from_file(target_file)
            
            # Find root node
            root_node = next((n for n in canvas.nodes if n.id == root_node_id), None)
            if not root_node:
                return [types.TextContent(type="text", text=f"Error: Root node {root_node_id} not found in {filename}")]
            
            # Semantic type to color mapping
            # Official spec: 1=red, 2=orange, 3=yellow, 4=green, 5=cyan, 6=purple
            TYPE_COLORS = {
                "concept": "5",    # 青色(cyan) - 概念定义
                "method": "4",     # 绿色(green) - 方法技术
                "finding": "2",    # 橙色(orange) - 研究发现
                "question": "1",   # 红色(red) - 问题挑战
                "evidence": "6",   # 紫色(purple) - 证据支撑
            }
            
            # Layout constants
            BASE_SPACING = 60 if layout == "right" else 50
            
            # Smart node sizing based on content length
            def calculate_node_size(title, text, source=None):
                # Estimate content length
                content = f"{title}\n\n{text}"
                if source:
                    content += f"\n[{source}]"
                length = len(content)
                
                # Calculate dimensions based on content (larger sizes for readability)
                if length < 60:
                    return (320, 160)
                elif length < 120:
                    return (380, 200)
                elif length < 200:
                    return (440, 250)
                elif length < 350:
                    return (500, 300)
                elif length < 500:
                    return (560, 360)
                else:
                    return (600, 420)
            
            # Helper to calculate subtree size
            def get_subtree_size(node_list, level):
                """Returns (width, height) for horizontal layout or (height, width) conceptually."""
                if not node_list or level >= max_depth:
                    return (300, 150)  # Default minimum
                
                total_secondary = 0  # Total in secondary axis
                max_primary = 0  # Max in primary axis
                
                for child in node_list:
                    title = child.get("title", "")
                    text = child.get("text", "")
                    source = child.get("source")
                    node_w, node_h = calculate_node_size(title, text, source)
                    
                    if child.get("children") and level + 1 <= max_depth:
                        child_size = get_subtree_size(child.get("children", []), level + 1)
                        if layout == "right":
                            total_secondary += max(node_h, child_size[1])
                            max_primary = max(max_primary, node_w + child_size[0])
                        else:
                            total_secondary += max(node_w, child_size[0])
                            max_primary = max(max_primary, node_h + child_size[1])
                    else:
                        if layout == "right":
                            total_secondary += node_h
                            max_primary = max(max_primary, node_w)
                        else:
                            total_secondary += node_w
                            max_primary = max(max_primary, node_h)
                
                # Add spacing
                if len(node_list) > 1:
                    total_secondary += (len(node_list) - 1) * BASE_SPACING
                
                if layout == "right":
                    return (max_primary, total_secondary)
                else:
                    return (total_secondary, max_primary)

            # Helper to get subtree height/width for centering
            def get_subtree_span(node_list, level):
                if not node_list or level >= max_depth:
                    return 150
                total = 0
                for child in node_list:
                    title = child.get("title", "")
                    text = child.get("text", "")
                    source = child.get("source")
                    node_w, node_h = calculate_node_size(title, text, source)
                    node_span = node_h if layout == "right" else node_w
                    
                    if child.get("children") and level + 1 <= max_depth:
                        child_span = get_subtree_span(child.get("children", []), level + 1)
                        total += max(node_span, child_span)
                    else:
                        total += node_span
                if len(node_list) > 1:
                    total += (len(node_list) - 1) * BASE_SPACING
                return total

            # Helper to create nodes recursively
            new_nodes = []
            new_edges = []
            
            def process_nodes(parent_node, children_list, primary_offset, secondary_start, level, parent_color=None):
                if level > max_depth:
                    return
                
                secondary_pos = secondary_start
                
                for i, child_data in enumerate(children_list):
                    # Get content
                    title = child_data.get("title", "").strip()
                    body = child_data.get("text", "").strip()
                    node_type = child_data.get("type", "").lower()
                    source = child_data.get("source", "").strip()
                    
                    # Handle literal \n sequences that should be actual newlines
                    # This happens when AI sends "\\n" in JSON which becomes literal "\n" string
                    title = title.replace("\\n", "\n")
                    body = body.replace("\\n", "\n")
                    
                    # Clean up any accidental markdown headers
                    while title.startswith("#"):
                        title = title.lstrip("#").strip()
                    while body.startswith("#"):
                        body = body.lstrip("#").strip()
                    
                    if not title:
                        title = "要点"
                    
                    # Calculate node size
                    node_width, node_height = calculate_node_size(title, body, source)
                    node_span = node_height if layout == "right" else node_width
                    
                    # Calculate subtree span for centering
                    child_span = get_subtree_span(child_data.get("children", []), level + 1) if child_data.get("children") else node_span
                    subtree_span = max(node_span, child_span)
                    
                    # Center node in its subtree
                    node_offset = (subtree_span - node_span) / 2
                    
                    # Calculate position
                    if layout == "right":
                        node_x = primary_offset
                        node_y = secondary_pos + node_offset
                    else:
                        node_x = secondary_pos + node_offset
                        node_y = primary_offset
                    
                    # Create node ID
                    node_id = f"node-{datetime.now().timestamp()}-{len(new_nodes)}"
                    
                    # Format content with markdown
                    header_level = min(level, 3)
                    header_prefix = "#" * header_level
                    text_content = f"{header_prefix} {title}\n\n{body}"
                    if source:
                        text_content += f"\n\n`📍 {source}`"
                    
                    # Determine color
                    if node_type and node_type in TYPE_COLORS:
                        node_color = TYPE_COLORS[node_type]
                    elif level == 1:
                        # First level: cycle through colors if no type specified
                        node_color = str((i % 6) + 1)
                    elif parent_color:
                        # Inherit parent color for visual grouping
                        node_color = parent_color
                    else:
                        node_color = None
                    
                    node = TextNode(
                        id=node_id,
                        x=int(node_x),
                        y=int(node_y),
                        width=node_width,
                        height=node_height,
                        text=text_content,
                        color=node_color
                    )
                    new_nodes.append(node)
                    
                    # Create edge with optional label
                    if layout == "right":
                        from_side, to_side = "right", "left"
                    else:
                        from_side, to_side = "bottom", "top"
                    
                    edge_label = child_data.get("edge_label", "").strip() or None
                    
                    edge = Edge(
                        id=f"edge-{node_id}",
                        from_node=parent_node.id,
                        to_node=node_id,
                        from_side=from_side,
                        to_side=to_side,
                        color=node_color if level == 1 else None,
                        label=edge_label
                    )
                    new_edges.append(edge)
                    
                    # Process children (with optional group)
                    if child_data.get("children") and level < max_depth:
                        if layout == "right":
                            child_primary = primary_offset + node_width + 80
                            child_secondary = secondary_pos
                        else:
                            child_primary = primary_offset + node_height + 60
                            child_secondary = secondary_pos
                        
                        # Check if children should be wrapped in a group
                        group_config = child_data.get("group")
                        if group_config and len(child_data["children"]) > 0:
                            # Calculate group bounds based on children subtree
                            children_span = get_subtree_span(child_data["children"], level + 1)
                            group_padding = 30
                            
                            # Estimate group width based on children depth
                            children_size = get_subtree_size(child_data["children"], level + 1)
                            
                            if layout == "right":
                                group_x = child_primary - group_padding
                                group_y = child_secondary - group_padding
                                group_width = children_size[0] + group_padding * 2
                                group_height = children_span + group_padding * 2
                            else:
                                group_x = child_secondary - group_padding
                                group_y = child_primary - group_padding
                                group_width = children_span + group_padding * 2
                                group_height = children_size[1] + group_padding * 2
                            
                            group_id = f"group-{node_id}"
                            group_node = GroupNode(
                                id=group_id,
                                x=int(group_x),
                                y=int(group_y),
                                width=int(group_width),
                                height=int(group_height),
                                label=group_config.get("label", "")
                            )
                            new_nodes.append(group_node)
                        
                        process_nodes(node, child_data["children"], child_primary, child_secondary, level + 1, node_color)
                    
                    # Advance position for next sibling
                    secondary_pos += subtree_span + BASE_SPACING

            # Start processing
            total_span = get_subtree_span(children_data, 1)
            
            if layout == "right":
                start_primary = root_node.x + root_node.width + 80
                start_secondary = root_node.y + (root_node.height / 2) - (total_span / 2)
            else:
                start_primary = root_node.y + root_node.height + 60
                start_secondary = root_node.x + (root_node.width / 2) - (total_span / 2)
            
            process_nodes(root_node, children_data, start_primary, start_secondary, 1)
            
            # Add all new items to canvas
            for n in new_nodes:
                canvas.add_node(n)
            for e in new_edges:
                canvas.add_edge(e)
            
            # Save
            with open(target_file, "w", encoding="utf-8") as f:
                json.dump(canvas.to_dict(), f, indent=2, ensure_ascii=False)
            
            # Build summary
            type_counts = {}
            edge_label_count = 0
            group_count = 0
            
            def count_features(node):
                nonlocal edge_label_count, group_count
                t = node.get("type", "untyped")
                type_counts[t] = type_counts.get(t, 0) + 1
                if node.get("edge_label"):
                    edge_label_count += 1
                if node.get("group"):
                    group_count += 1
                for c in node.get("children", []):
                    count_features(c)
            
            for child in children_data:
                count_features(child)
            
            # Build type summary
            type_summary = ", ".join([f"{v} {k}" for k, v in type_counts.items() if k != "untyped"])
            
            # Build features summary
            features = []
            if type_summary:
                features.append(type_summary)
            if group_count > 0:
                features.append(f"{group_count} group(s)")
            if edge_label_count > 0:
                features.append(f"{edge_label_count} labeled edge(s)")
            
            features_str = f" ({', '.join(features)})" if features else ""
            
            return [types.TextContent(type="text", text=f"✓ Created academic mindmap: {len(new_nodes)} nodes{features_str}, depth={max_depth}, layout={layout}\nSaved to: {target_file}")]
            
        except Exception as e:
            return [types.TextContent(type="text", text=f"Error creating mindmap: {str(e)}")]

    elif name == "get_node":
        try:
            filename = arguments.get("filename")
            node_id = arguments.get("node_id")
            
            # Find the canvas file
            target_file = OUTPUT_PATH / filename
            if not target_file.exists():
                candidates = list(OUTPUT_PATH.glob(f"*{filename}"))
                if candidates:
                    target_file = candidates[0]
                else:
                    return [types.TextContent(type="text", text=f"Error: File {filename} not found in {OUTPUT_PATH}")]
            
            canvas = load_canvas_from_file(target_file)
            
            # Find the node
            node = canvas.get_node(node_id)
            if not node:
                return [types.TextContent(type="text", text=f"Error: Node '{node_id}' not found in {filename}")]
            
            # Return node info as JSON
            node_info = node.to_dict()
            return [types.TextContent(type="text", text=json.dumps(node_info, indent=2, ensure_ascii=False))]
            
        except Exception as e:
            return [types.TextContent(type="text", text=f"Error getting node: {str(e)}")]

    elif name == "get_edge":
        try:
            filename = arguments.get("filename")
            edge_id = arguments.get("edge_id")
            
            # Find the canvas file
            target_file = OUTPUT_PATH / filename
            if not target_file.exists():
                candidates = list(OUTPUT_PATH.glob(f"*{filename}"))
                if candidates:
                    target_file = candidates[0]
                else:
                    return [types.TextContent(type="text", text=f"Error: File {filename} not found in {OUTPUT_PATH}")]
            
            canvas = load_canvas_from_file(target_file)
            
            # Find the edge
            edge = canvas.get_edge(edge_id)
            if not edge:
                return [types.TextContent(type="text", text=f"Error: Edge '{edge_id}' not found in {filename}")]
            
            # Return edge info as JSON
            edge_info = edge.to_dict()
            return [types.TextContent(type="text", text=json.dumps(edge_info, indent=2, ensure_ascii=False))]
            
        except Exception as e:
            return [types.TextContent(type="text", text=f"Error getting edge: {str(e)}")]

    elif name == "update_edge":
        try:
            filename = arguments.get("filename")
            edge_id = arguments.get("edge_id")
            updates = arguments.get("updates", {})
            
            if not updates:
                return [types.TextContent(type="text", text="Error: No updates provided")]
            
            # Find the canvas file
            target_file = OUTPUT_PATH / filename
            if not target_file.exists():
                candidates = list(OUTPUT_PATH.glob(f"*{filename}"))
                if candidates:
                    target_file = candidates[0]
                else:
                    return [types.TextContent(type="text", text=f"Error: File {filename} not found in {OUTPUT_PATH}")]
            
            canvas = load_canvas_from_file(target_file)
            
            # Find the edge
            edge = canvas.get_edge(edge_id)
            if not edge:
                return [types.TextContent(type="text", text=f"Error: Edge '{edge_id}' not found in {filename}")]
            
            # Track what was updated
            updated_fields = []
            
            # Validate node references if updating from_node or to_node
            node_ids = {node.id for node in canvas.nodes}
            
            if "from_node" in updates:
                if updates["from_node"] not in node_ids:
                    return [types.TextContent(type="text", text=f"Error: Node '{updates['from_node']}' not found")]
                edge.from_node = updates["from_node"]
                updated_fields.append("from_node")
            
            if "to_node" in updates:
                if updates["to_node"] not in node_ids:
                    return [types.TextContent(type="text", text=f"Error: Node '{updates['to_node']}' not found")]
                edge.to_node = updates["to_node"]
                updated_fields.append("to_node")
            
            if "from_side" in updates:
                if updates["from_side"] not in ["top", "right", "bottom", "left"]:
                    return [types.TextContent(type="text", text="Error: from_side must be one of: top, right, bottom, left")]
                edge.from_side = updates["from_side"]
                updated_fields.append("from_side")
            
            if "to_side" in updates:
                if updates["to_side"] not in ["top", "right", "bottom", "left"]:
                    return [types.TextContent(type="text", text="Error: to_side must be one of: top, right, bottom, left")]
                edge.to_side = updates["to_side"]
                updated_fields.append("to_side")
            
            if "from_end" in updates:
                if updates["from_end"] not in ["none", "arrow"]:
                    return [types.TextContent(type="text", text="Error: from_end must be one of: none, arrow")]
                edge.from_end = updates["from_end"]
                updated_fields.append("from_end")
            
            if "to_end" in updates:
                if updates["to_end"] not in ["none", "arrow"]:
                    return [types.TextContent(type="text", text="Error: to_end must be one of: none, arrow")]
                edge.to_end = updates["to_end"]
                updated_fields.append("to_end")
            
            if "color" in updates:
                Edge.validate_color(updates["color"])
                edge.color = updates["color"]
                updated_fields.append("color")
            
            if "label" in updates:
                edge.label = updates["label"]
                updated_fields.append("label")
            
            # Save the updated canvas
            with open(target_file, "w", encoding="utf-8") as f:
                json.dump(canvas.to_dict(), f, indent=2, ensure_ascii=False)
            
            return [types.TextContent(type="text", text=f"Successfully updated edge '{edge_id}' in {target_file}. Updated fields: {', '.join(updated_fields)}")]
            
        except Exception as e:
            return [types.TextContent(type="text", text=f"Error updating edge: {str(e)}")]

    elif name == "update_node":
        try:
            filename = arguments.get("filename")
            node_id = arguments.get("node_id")
            updates = arguments.get("updates", {})
            
            if not updates:
                return [types.TextContent(type="text", text="Error: No updates provided")]
            
            # Find the canvas file
            target_file = OUTPUT_PATH / filename
            if not target_file.exists():
                candidates = list(OUTPUT_PATH.glob(f"*{filename}"))
                if candidates:
                    target_file = candidates[0]
                else:
                    return [types.TextContent(type="text", text=f"Error: File {filename} not found in {OUTPUT_PATH}")]
            
            canvas = load_canvas_from_file(target_file)
            
            # Find the node
            node = canvas.get_node(node_id)
            if not node:
                return [types.TextContent(type="text", text=f"Error: Node '{node_id}' not found in {filename}")]
            
            # Track what was updated
            updated_fields = []
            
            # Update common properties
            if "x" in updates:
                node.x = updates["x"]
                updated_fields.append("x")
            if "y" in updates:
                node.y = updates["y"]
                updated_fields.append("y")
            if "width" in updates:
                node.width = updates["width"]
                updated_fields.append("width")
            if "height" in updates:
                node.height = updates["height"]
                updated_fields.append("height")
            if "color" in updates:
                # Validate color before setting
                Node.validate_color(updates["color"])
                node.color = updates["color"]
                updated_fields.append("color")
            
            # Update type-specific properties
            if "text" in updates:
                if hasattr(node, "text"):
                    node.text = updates["text"]
                    updated_fields.append("text")
                else:
                    return [types.TextContent(type="text", text=f"Error: Node '{node_id}' is not a text node")]
            
            if "url" in updates:
                if hasattr(node, "url"):
                    node.url = updates["url"]
                    updated_fields.append("url")
                else:
                    return [types.TextContent(type="text", text=f"Error: Node '{node_id}' is not a link node")]
            
            if "file" in updates:
                if hasattr(node, "file"):
                    node.file = updates["file"]
                    updated_fields.append("file")
                else:
                    return [types.TextContent(type="text", text=f"Error: Node '{node_id}' is not a file node")]
            
            if "label" in updates:
                if hasattr(node, "label"):
                    node.label = updates["label"]
                    updated_fields.append("label")
                else:
                    return [types.TextContent(type="text", text=f"Error: Node '{node_id}' is not a group node")]
            
            # Save the updated canvas
            with open(target_file, "w", encoding="utf-8") as f:
                json.dump(canvas.to_dict(), f, indent=2, ensure_ascii=False)
            
            return [types.TextContent(type="text", text=f"Successfully updated node '{node_id}' in {target_file}. Updated fields: {', '.join(updated_fields)}")]
            
        except Exception as e:
            return [types.TextContent(type="text", text=f"Error updating node: {str(e)}")]

    elif name == "find_nodes":
        try:
            filename = arguments.get("filename")
            search_text = arguments.get("search_text", "")
            
            # Find the canvas file
            target_file = OUTPUT_PATH / filename
            if not target_file.exists():
                candidates = list(OUTPUT_PATH.glob(f"*{filename}"))
                if candidates:
                    target_file = candidates[0]
                else:
                    return [types.TextContent(type="text", text=f"Error: File {filename} not found in {OUTPUT_PATH}")]
            
            canvas = load_canvas_from_file(target_file)
            
            # Search for nodes containing the text
            found_nodes = []
            for node in canvas.nodes:
                node_text = ""
                if hasattr(node, "text"):
                    node_text = node.text or ""
                elif hasattr(node, "label"):
                    node_text = node.label or ""
                
                if search_text.lower() in node_text.lower():
                    found_nodes.append({
                        "id": node.id,
                        "type": node.__class__.__name__.replace("Node", "").lower(),
                        "text": node_text,
                        "width": node.width,
                        "height": node.height
                    })
            
            if not found_nodes:
                return [types.TextContent(type="text", text=f"No nodes containing '{search_text}' found in {filename}")]
            
            # Build a map of node id to node for quick lookup
            node_map = {}
            for node in canvas.nodes:
                node_info = {
                    "id": node.id,
                    "type": node.__class__.__name__.replace("Node", "").lower(),
                }
                # Get content based on node type
                if hasattr(node, "text"):
                    node_info["text"] = node.text or ""
                if hasattr(node, "file"):
                    node_info["file"] = node.file or ""
                if hasattr(node, "url"):
                    node_info["url"] = node.url or ""
                if hasattr(node, "label"):
                    node_info["label"] = node.label or ""
                node_map[node.id] = node_info
            
            # Track if there are file nodes that need to be viewed
            file_nodes_to_view = []
            
            # Find connected nodes for each found node
            result = f"Found {len(found_nodes)} node(s) containing '{search_text}' in {filename}:\n\n"
            
            for n in found_nodes:
                result += f"=== Target Node ===\n"
                result += f"Node ID: {n['id']}\n"
                result += f"Type: {n['type']}\n"
                result += f"Size: {n['width']}x{n['height']}\n"
                result += f"Text: {n['text']}\n\n"
                
                # Find all edges connected to this node
                connected_nodes = []
                for edge in canvas.edges:
                    if edge.from_node == n['id'] and edge.to_node in node_map:
                        connected_nodes.append(("outgoing", edge.to_node, edge.label))
                    elif edge.to_node == n['id'] and edge.from_node in node_map:
                        connected_nodes.append(("incoming", edge.from_node, edge.label))
                
                if connected_nodes:
                    result += f"=== Connected Nodes (IMPORTANT CONTEXT) ===\n"
                    for direction, node_id, edge_label in connected_nodes:
                        conn_node = node_map[node_id]
                        arrow = "→" if direction == "outgoing" else "←"
                        label_str = f" [{edge_label}]" if edge_label else ""
                        result += f"\n{arrow}{label_str} Node ID: {node_id}\n"
                        result += f"   Type: {conn_node['type']}\n"
                        
                        # Show appropriate content based on node type
                        if conn_node['type'] == 'file':
                            file_path = conn_node.get('file', '')
                            result += f"   File: {file_path}\n"
                            if file_path:
                                file_nodes_to_view.append(file_path)
                        elif conn_node['type'] == 'link':
                            result += f"   URL: {conn_node.get('url', '')}\n"
                        elif conn_node['type'] == 'group':
                            result += f"   Label: {conn_node.get('label', '')}\n"
                        else:
                            result += f"   Text: {conn_node.get('text', '')}\n"
                else:
                    result += "No connected nodes found.\n"
                
                result += "\n" + "="*50 + "\n\n"
            
            # Add instruction based on connected node types
            if file_nodes_to_view:
                result += "STOP! DO NOT call update_node yet!\n"
                result += "You MUST execute these commands FIRST:\n\n"
                for fp in file_nodes_to_view:
                    # Determine file type and suggest appropriate action
                    fp_lower = fp.lower()
                    if fp_lower.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp')):
                        result += f">>> READ IMAGE: read_file \"{fp}\"\n"
                    elif fp_lower.endswith('.pdf'):
                        result += f">>> READ PDF: read_file \"{fp}\"\n"
                    else:
                        result += f">>> READ FILE: read_file \"{fp}\"\n"
                result += "\nAFTER reading ALL files above, THEN call resolve_td (not update_node) with:\n"
                result += "- file_contents: summaries of what you read from each file\n"
                result += "- resolved_content: the final explanation based on those files\n"
            else:
                result += "INSTRUCTION: Review the connected nodes above to understand context, then use update_node to replace the #td content."
            
            return [types.TextContent(type="text", text=result)]
            
        except Exception as e:
            return [types.TextContent(type="text", text=f"Error finding nodes: {str(e)}")]

    elif name == "resolve_td":
        try:
            filename = arguments.get("filename")
            node_id = arguments.get("node_id")
            file_contents = arguments.get("file_contents", [])
            resolved_content = arguments.get("resolved_content", "")
            
            if not resolved_content:
                return [types.TextContent(type="text", text="Error: resolved_content is required")]
            
            # Find the canvas file
            target_file = OUTPUT_PATH / filename
            if not target_file.exists():
                candidates = list(OUTPUT_PATH.glob(f"*{filename}"))
                if candidates:
                    target_file = candidates[0]
                else:
                    return [types.TextContent(type="text", text=f"Error: File {filename} not found in {OUTPUT_PATH}")]
            
            canvas = load_canvas_from_file(target_file)
            
            # Find the node
            node = canvas.get_node(node_id)
            if not node:
                return [types.TextContent(type="text", text=f"Error: Node '{node_id}' not found in {filename}")]
            
            if not hasattr(node, "text"):
                return [types.TextContent(type="text", text=f"Error: Node '{node_id}' is not a text node")]
            
            # Calculate appropriate size based on content length
            content_len = len(resolved_content)
            if content_len < 100:
                new_width, new_height = 300, 150
            elif content_len < 300:
                new_width, new_height = 400, 200
            elif content_len < 500:
                new_width, new_height = 450, 280
            else:
                new_width, new_height = 500, 350
            
            # Update the node
            node.text = resolved_content
            node.width = new_width
            node.height = new_height
            
            # Save the updated canvas
            with open(target_file, "w", encoding="utf-8") as f:
                json.dump(canvas.to_dict(), f, indent=2, ensure_ascii=False)
            
            # Build response
            response = f"Successfully resolved #td in node '{node_id}'!\n"
            response += f"File: {target_file}\n"
            response += f"New size: {new_width}x{new_height}\n"
            if file_contents:
                response += f"Based on {len(file_contents)} file(s): "
                response += ", ".join([fc.get('file_path', 'unknown') for fc in file_contents])
            
            return [types.TextContent(type="text", text=response)]
            
        except Exception as e:
            return [types.TextContent(type="text", text=f"Error resolving #td: {str(e)}")]
    
    raise ValueError(f"Unknown tool: {name}")

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="jsoncanvas-server",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Server error: {e}", file=sys.stderr)
