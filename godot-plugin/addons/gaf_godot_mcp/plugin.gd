@tool
extends EditorPlugin
## GAF Godot MCP 插件入口。
## 启用插件时创建 bridge 节点（socket server + 指令队列），禁用时释放。

var _bridge: Node

func _enter_tree() -> void:
	_bridge = preload("res://addons/gaf_godot_mcp/bridge.gd").new()
	_bridge.name = "GAFBridge"
	add_child(_bridge)
	print("[GAF] Godot MCP bridge started on port ", _bridge.port)

func _exit_tree() -> void:
	if _bridge:
		_bridge.queue_free()
		_bridge = null