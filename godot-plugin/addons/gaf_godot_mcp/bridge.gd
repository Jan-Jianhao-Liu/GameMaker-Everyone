@tool
extends Node
## socket 桥：用 TCPServer 监听，_process 每帧非阻塞轮询。
## 所有编辑器操作在 _process_queue（主线程）执行，线程安全。
## 端口读 GODOT_MCP_PORT 环境变量，默认 19877（避 Godot 知名插件 9877 冲突）。

var port: int = 19877
var _server: TCPServer
var _client: StreamPeerTCP
var _buffer: String
var _cmd_queue: Array
var _executor: Node

func _ready() -> void:
	if OS.has_environment("GODOT_MCP_PORT"):
		port = int(OS.get_environment("GODOT_MCP_PORT"))
	_server = TCPServer.new()
	var err = _server.listen(port)
	if err != OK:
		push_warning("[GAF] 端口 %d 监听失败: %d" % [port, err])
		return
	_cmd_queue = []
	_buffer = ""
	_executor = preload("res://addons/gaf_godot_mcp/command_executor.gd").new()
	add_child(_executor)
	set_process(true)
	print("[GAF] listening on ", port)

func _process(_delta: float) -> void:
	_poll_server()
	_process_queue()

func _poll_server() -> void:
	if _client == null or not _client.is_connected_to_host():
		if _server.is_connection_available():
			_client = _server.take_connection()
	if _client and _client.is_connected_to_host():
		_client.poll()
		var available := _client.get_available_bytes()
		if available > 0:
			_buffer += _client.get_utf8_string(available)
			_split_commands()

func _split_commands() -> void:
	while _buffer.find("\n") >= 0:
		var idx := _buffer.find("\n")
		var line := _buffer.substr(0, idx)
		_buffer = _buffer.substr(idx + 1)
		_parse_command(line)

func _parse_command(line: String) -> void:
	if line.strip_edges() == "":
		return
	var json := JSON.new()
	if json.parse(line) != OK:
		_send_response({"req_id": "?", "status": "error", "error": "JSON 解析失败"})
		return
	_cmd_queue.append(json.data)

func _process_queue() -> void:
	while _cmd_queue.size() > 0:
		var msg: Dictionary = _cmd_queue.pop_front()
		var req_id: String = msg.get("req_id", "?")
		var tool: String = msg.get("tool", "")
		var params: Dictionary = msg.get("params", {})
		var resp: Dictionary = _executor.execute(tool, params)
		resp["req_id"] = req_id
		_send_response(resp)

func _send_response(resp: Dictionary) -> void:
	if _client and _client.is_connected_to_host():
		var text := JSON.stringify(resp) + "\n"
		_client.put_data(text.to_utf8_buffer())