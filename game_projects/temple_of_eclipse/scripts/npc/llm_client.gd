extends Node

signal response_received(text: String)
signal response_streamed(chunk: String)
signal request_failed(error: String)

@export var endpoint: String = "http://127.0.0.1:11434/api/generate"
@export var model: String = "my-qwen4b-no-think:latest"
@export var temperature: float = 0.7
@export var max_tokens: int = 256

var _http: HTTPRequest = null

func _ready() -> void:
	_http = HTTPRequest.new()
	_http.use_threads = true
	add_child(_http)
	_http.request_completed.connect(_on_request_completed)

func generate(prompt: String, system_prompt: String = "") -> void:
	var body := {
		"model": model,
		"prompt": prompt,
		"stream": false,
		"options": {
			"temperature": temperature,
			"num_predict": max_tokens,
		},
	}
	if system_prompt != "":
		body["system"] = system_prompt
	var json := JSON.stringify(body)
	var headers := PackedStringArray(["Content-Type: application/json"])
	var err := _http.request(endpoint, headers, HTTPClient.METHOD_POST, json)
	if err != OK:
		request_failed.emit("HTTP 请求失败: %d" % err)

func _on_request_completed(result: int, code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	if result != HTTPRequest.RESULT_SUCCESS:
		request_failed.emit("请求失败: result=%d" % result)
		return
	if code != 200:
		request_failed.emit("HTTP %d" % code)
		return
	var text := body.get_string_from_utf8()
	var json := JSON.parse_string(text)
	if json == null or not json.has("response"):
		request_failed.emit("无效响应")
		return
	response_received.emit(json["response"])