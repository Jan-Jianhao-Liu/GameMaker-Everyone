extends Node3D

const MAX_LEVEL = 3
const ENEMIES_PER_LEVEL = [3, 5, 7]
const ROOM_SIZE = 10.0

var current_level: int = 1
var enemies_remaining: int = 0
var player: CharacterBody3D
var game_over: bool = false
var game_won: bool = false
var start_time: float = 0.0

@onready var player_node: CharacterBody3D = $Player
@onready var ui: Control = $UI
@onready var health_bar: ProgressBar = $UI/TopBar/HealthBar
@onready var health_label: Label = $UI/TopBar/HealthLabel
@onready var score_label: Label = $UI/TopBar/ScoreLabel
@onready var level_label: Label = $UI/TopBar/LevelLabel
@onready var enemies_label: Label = $UI/TopBar/EnemiesLabel
@onready var message_panel: Panel = $UI/MessagePanel
@onready var message_label: Label = $UI/MessagePanel/MessageLabel
@onready var message_button: Button = $UI/MessagePanel/MessageButton

func _ready() -> void:
	start_time = Time.get_ticks_msec() / 1000.0
	player = player_node
	player.health_changed.connect(_on_health_changed)
	player.score_changed.connect(_on_score_changed)
	player.player_died.connect(_on_player_died)
	_start_level(current_level)
	message_button.pressed.connect(_on_message_button)

func _start_level(level: int) -> void:
	for enemy in get_tree().get_nodes_in_group("enemies"):
		enemy.queue_free()
	for pickup in get_tree().get_nodes_in_group("pickups"):
		pickup.queue_free()

	_build_room(level)
	_spawn_enemies(level)
	_spawn_pickups(level)

	enemies_remaining = ENEMIES_PER_LEVEL[level - 1]
	level_label.text = "关卡: %d / %d" % [level, MAX_LEVEL]
	enemies_label.text = "敌人: %d" % enemies_remaining

	if level > 1:
		_show_message("关卡 %d" % level, "进入第 %d 关！敌人数量: %d" % [level, ENEMIES_PER_LEVEL[level - 1]], "开始")

func _build_room(level: int) -> void:
	for child in get_children():
		if child.is_in_group("room_geometry"):
			child.queue_free()

	var floor_node := CSGBox3D.new()
	floor_node.size = Vector3(ROOM_SIZE * 2, 0.2, ROOM_SIZE * 2)
	floor_node.position = Vector3(0, -0.1, 0)
	var floor_mat := StandardMaterial3D.new()
	floor_mat.albedo_color = Color(0.2, 0.2, 0.25)
	floor_node.material = floor_mat
	floor_node.add_to_group("room_geometry")
	add_child(floor_node)

	var wall_mat := StandardMaterial3D.new()
	wall_mat.albedo_color = Color(0.35, 0.3, 0.25)
	var wall_height := 4.0
	var wall_thickness := 0.3
	var half := ROOM_SIZE

	var wall_configs := [
		Vector3(0, wall_height/2, half),
		Vector3(0, wall_height/2, -half),
		Vector3(half, wall_height/2, 0),
		Vector3(-half, wall_height/2, 0),
	]
	var wall_sizes := [
		Vector3(ROOM_SIZE * 2, wall_height, wall_thickness),
		Vector3(ROOM_SIZE * 2, wall_height, wall_thickness),
		Vector3(wall_thickness, wall_height, ROOM_SIZE * 2),
		Vector3(wall_thickness, wall_height, ROOM_SIZE * 2),
	]

	for i in range(4):
		var wall := CSGBox3D.new()
		wall.size = wall_sizes[i]
		wall.position = wall_configs[i]
		wall.material = wall_mat
		wall.add_to_group("room_geometry")
		add_child(wall)

	var light := DirectionalLight3D.new()
	light.position = Vector3(0, 8, 0)
	light.rotation.x = -PI / 4
	light.light_energy = 0.8
	light.add_to_group("room_geometry")
	add_child(light)

	var ambient := OmniLight3D.new()
	ambient.position = Vector3(0, 3, 0)
	ambient.light_energy = 1.5

	ambient.add_to_group("room_geometry")
	add_child(ambient)

func _spawn_enemies(level: int) -> void:
	var count: int = ENEMIES_PER_LEVEL[level - 1]
	for i in range(count):
		var enemy := CharacterBody3D.new()
		enemy.script = preload("res://scripts/enemy.gd")

		var collision := CollisionShape3D.new()
		var shape := BoxShape3D.new()
		shape.size = Vector3(0.8, 1.2, 0.8)
		collision.shape = shape
		enemy.add_child(collision)

		var model := CSGBox3D.new()
		model.size = Vector3(0.8, 1.2, 0.8)
		var mat := StandardMaterial3D.new()
		mat.albedo_color = Color(0.8, 0.2, 0.2)
		model.material = mat
		model.name = "Model"
		enemy.add_child(model)

		var angle: float = (float(i) / count) * TAU
		var radius := ROOM_SIZE * 0.6
		enemy.position = Vector3(cos(angle) * radius, 0.6, sin(angle) * radius)

		add_child(enemy)
		enemy.set_target(player)

func _spawn_pickups(level: int) -> void:
	for i in range(2 + level):
		var pickup := Area3D.new()
		pickup.add_to_group("pickups")

		var col := CollisionShape3D.new()
		var sphere := SphereShape3D.new()
		sphere.radius = 0.5
		col.shape = sphere
		pickup.add_child(col)

		var mesh := CSGSphere3D.new()
		mesh.radius = 0.3
		var mat := StandardMaterial3D.new()
		mat.albedo_color = Color(1.0, 0.84, 0.0)
		mat.emission_enabled = true
		mat.emission = Color(0.5, 0.4, 0.0)
		mesh.material = mat
		pickup.add_child(mesh)

		var angle: float = (float(i) / (2 + level)) * TAU + PI
		var radius := ROOM_SIZE * 0.4
		pickup.position = Vector3(cos(angle) * radius, 0.5, sin(angle) * radius)

		pickup.body_entered.connect(func(body):
			if body == player:
				player.heal(20)
				player.add_score(50)
				pickup.queue_free()
		)

		add_child(pickup)

func _on_health_changed(h: int, max_h: int) -> void:
	health_bar.value = float(h) / max_h * 100
	health_label.text = "HP: %d / %d" % [h, max_h]

func _on_score_changed(s: int) -> void:
	score_label.text = "得分: %d" % s

func _on_player_died() -> void:
	game_over = true
	_show_message("游戏结束", "你被击败了！\n最终得分: %d" % player.score, "重新开始")

func _on_enemy_killed() -> void:
	enemies_remaining -= 1
	enemies_label.text = "敌人: %d" % enemies_remaining
	if enemies_remaining <= 0:
		if current_level >= MAX_LEVEL:
			game_won = true
			var elapsed := Time.get_ticks_msec() / 1000.0 - start_time
			_show_message("胜利！", "你征服了所有关卡！\n最终得分: %d\n用时: %.1f 秒" % [player.score, elapsed], "再玩一次")
		else:
			current_level += 1
			_start_level(current_level)

func _process(delta: float) -> void:
	if not game_over and not game_won:
		var enemies := get_tree().get_nodes_in_group("enemies")
		var alive_count := 0
		for e in enemies:
			if e.is_alive:
				alive_count += 1
		if alive_count != enemies_remaining:
			enemies_remaining = alive_count
			enemies_label.text = "敌人: %d" % enemies_remaining
			if enemies_remaining <= 0:
				_on_enemy_killed()

func _show_message(title: String, body: String, btn_text: String) -> void:
	message_label.text = "%s\n\n%s" % [title, body]
	message_button.text = btn_text
	message_panel.visible = true

func _on_message_button() -> void:
	message_panel.visible = false
	if game_over or game_won:
		get_tree().reload_current_scene()