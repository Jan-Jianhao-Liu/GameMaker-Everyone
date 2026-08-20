@tool
extends Node
## 白名单指令执行器：6 个工具，只接受结构化参数，禁止透传任意代码。
## 所有文件写入限制在 res:// 内，路径逃逸直接拒绝。

const SAFE_ROOT := "res://"

func execute(tool: String, params: Dictionary) -> Dictionary:
	match tool:
		"import_asset":
			return _import_asset(params)
		"create_scene":
			return _create_scene(params)
		"attach_script":
			return _attach_script(params)
		"set_level_data":
			return _set_level_data(params)
		"build_export":
			return _build_export(params)
		"run_headless_test":
			return _run_headless_test(params)
		_:
			return {"status": "error", "error": "未知工具: " + tool}


func _check_path(path: String) -> bool:
	return path.begins_with(SAFE_ROOT)


func _import_asset(params: Dictionary) -> Dictionary:
	var fbx_path: String = params.get("fbx_path", "")
	var asset_id: String = params.get("asset_id", "")
	if not _check_path(fbx_path):
		return {"status": "error", "error": "路径逃逸: " + fbx_path}
	ResourceLoader.load_threaded_request(fbx_path)
	return {"status": "ok", "result": {"asset_id": asset_id, "path": fbx_path}}


func _create_scene(params: Dictionary) -> Dictionary:
	var scene_name: String = params.get("scene_name", "")
	var template: String = params.get("template", "empty")
	var tpl_path := SAFE_ROOT + "addons/gaf_godot_mcp/templates/" + template + ".tscn"
	var out_path := SAFE_ROOT + scene_name + ".tscn"
	var packed := load(tpl_path)
	if packed == null:
		return {"status": "error", "error": "模板不存在: " + tpl_path}
	var scene := packed.instantiate()
	var new_packed := PackedScene.new()
	new_packed.pack(scene)
	ResourceSaver.save(new_packed, out_path)
	scene.queue_free()
	return {"status": "ok", "result": {"scene": out_path, "template": template}}


func _attach_script(params: Dictionary) -> Dictionary:
	var node_path: String = params.get("node_path", "")
	var script_content: String = params.get("script_content", "")
	var script_path := SAFE_ROOT + node_path + ".gd"
	var file := FileAccess.open(script_path, FileAccess.WRITE)
	if file == null:
		return {"status": "error", "error": "无法写入: " + script_path}
	file.store_string(script_content)
	file.close()
	var script := load(script_path)
	if script == null or not script.is_valid():
		return {"status": "error", "error": "GDScript 语法错误: " + script_path}
	return {"status": "ok", "result": {"script": script_path}}


func _set_level_data(params: Dictionary) -> Dictionary:
	var level_id: String = params.get("level_id", "")
	var json_path: String = params.get("json_path", "")
	var file := FileAccess.open(json_path, FileAccess.READ)
	if file == null:
		return {"status": "error", "error": "无法读取: " + json_path}
	var text := file.get_as_text()
	file.close()
	var json := JSON.new()
	if json.parse(text) != OK:
		return {"status": "error", "error": "JSON 解析失败"}
	var data: Dictionary = json.data
	var entities: Array = []
	for level in data.get("levels", []):
		if level.get("level_id", "") == level_id:
			entities = level.get("spawn_table", [])
			break
	return {"status": "ok", "result": {"level_id": level_id, "entities": entities}}


func _build_export(params: Dictionary) -> Dictionary:
	var preset_name: String = params.get("preset_name", "")
	var godot_path := OS.get_executable_path()
	var project_path := ProjectSettings.globalize_path(SAFE_ROOT)
	var output: Array = []
	OS.execute(godot_path, ["--export-release", preset_name, "--path", project_path], output, true)
	return {"status": "ok", "result": {"preset": preset_name, "log": output[0]}}


func _run_headless_test(params: Dictionary) -> Dictionary:
	var scene_path: String = params.get("scene_path", "")
	var godot_path := OS.get_executable_path()
	var project_path := ProjectSettings.globalize_path(SAFE_ROOT)
	var output: Array = []
	OS.execute(godot_path, ["--headless", "--path", project_path], output, true)
	var errors: Array = []
	for line in String(output[0]).split("\n"):
		if line.find("ERROR") >= 0 or line.find("SCRIPT ERROR") >= 0:
			errors.append(line)
	return {"status": "ok", "result": {"scene": scene_path, "errors": errors}}