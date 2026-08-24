extends Node

signal memory_loaded(entries: Array)
signal memory_appended(entry: Dictionary)

@export var memory_path: String = "user://npc_memory/"
@export var max_entries: int = 200

var _entries: Array[Dictionary] = []
var _file_path: String = ""

func _ready() -> void:
	var dir := DirAccess.open("user://")
	if not dir.dir_exists("npc_memory"):
		dir.make_dir("npc_memory")

func set_npc_id(npc_id: String) -> void:
	_file_path = memory_path + npc_id + ".jsonl"
	_load()

func _load() -> void:
	_entries.clear()
	if not FileAccess.file_exists(_file_path):
		return
	var f := FileAccess.open(_file_path, FileAccess.READ)
	while not f.eof_reached():
		var line := f.get_line()
		if line.strip_edges() == "":
			continue
		var entry := JSON.parse_string(line)
		if entry != null and entry is Dictionary:
			_entries.append(entry)
	f.close()
	if _entries.size() > max_entries:
		_entries = _entries.slice(-max_entries)
	memory_loaded.emit(_entries)

func append(role: String, content: String, metadata: Dictionary = {}) -> void:
	var entry := {
		"ts": Time.get_unix_time_from_system(),
		"role": role,
		"content": content,
		"metadata": metadata,
	}
	_entries.append(entry)
	if _entries.size() > max_entries:
		_entries = _entries.slice(-max_entries)
	_save()
	memory_appended.emit(entry)

func _save() -> void:
	var f := FileAccess.open(_file_path, FileAccess.WRITE)
	for entry in _entries:
		f.store_line(JSON.stringify(entry))
	f.close()

func get_recent(n: int = 10) -> Array[Dictionary]:
	return _entries.slice(-n) if _entries.size() > n else _entries.duplicate()

func get_context_string(n: int = 10) -> String:
	var recent := get_recent(n)
	var parts: Array[String] = []
	for entry in recent:
		var role: String = entry.get("role", "unknown")
		var content: String = entry.get("content", "")
		parts.append("%s: %s" % [role, content])
	return "\n".join(parts)

func clear() -> void:
	_entries.clear()
	if FileAccess.file_exists(_file_path):
		DirAccess.remove_absolute(_file_path)