extends Node3D

signal dialogue_started(npc_name: String)
signal dialogue_ended(npc_name: String)
signal line_received(text: String)

@export var npc_name: String = "NPC"
@export var npc_persona: String = "你是一个神秘的幽冥神殿守卫，说话简短且带有古风。"
@export var interaction_range: float = 3.0
@export var prompt_label_path: NodePath = NodePath("")

var _llm: Node = null
var _memory: Node = null
var _player: Node = null
var _is_talking: bool = false

func _ready() -> void:
	_llm = $LLMClient
	_memory = $NpcMemory
	_memory.set_npc_id(npc_name)
	_llm.response_received.connect(_on_llm_response)
	_llm.request_failed.connect(_on_llm_error)

func interact(player: Node) -> void:
	if _is_talking:
		return
	_player = player
	_is_talking = true
	dialogue_started.emit(npc_name)
	var context := _memory.get_context_string(5)
	var prompt := "玩家靠近了你。"
	if context != "":
		prompt = "对话历史:\n%s\n\n%s" % [context, prompt]
	_memory.append("user", "玩家靠近了%s" % npc_name)
	_llm.generate(prompt, npc_persona)

func say(text: String) -> void:
	_memory.append("assistant", text)
	line_received.emit(text)

func end_dialogue() -> void:
	_is_talking = false
	_player = null
	dialogue_ended.emit(npc_name)

func _on_llm_response(text: String) -> void:
	say(text)

func _on_llm_error(error: String) -> void:
	say("...（沉默）")
	push_warning("NPC LLM 错误: %s" % error)

func can_interact(player: Node) -> bool:
	return not _is_talking and global_position.distance_to(player.global_position) <= interaction_range