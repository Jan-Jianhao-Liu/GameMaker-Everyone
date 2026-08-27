extends CharacterBody3D

const SPEED = 6.0
const DASH_SPEED = 15.0
const ATTACK_COOLDOWN = 0.4
const MAGIC_COST = 20
const DODGE_COOLDOWN = 1.0

var health: int = 100
var max_health: int = 100
var mana: int = 100
var max_mana: int = 100
var score: int = 0
var attack_timer: float = 0.0
var dodge_timer: float = 0.0
var magic_timer: float = 0.0
var is_dodging: bool = false
var dodge_dir: Vector3 = Vector3.ZERO
var yaw: float = 0.0
var pitch: float = -0.3
var hit_flash: float = 0.0

@onready var camera: Camera3D = $Camera3D
@onready var model: Node3D = $Model
@onready var attack_area: Area3D = $AttackArea

signal health_changed(h: int, mh: int)
signal mana_changed(m: int, mm: int)
signal score_changed(s: int)
signal player_died
signal damage_dealt(amount: int, pos: Vector3)
signal player_damaged(amount: int)
signal magic_cast(pos: Vector3)
signal attack_slash(pos: Vector3, dir: Vector3)

func _ready() -> void:
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	camera.current = true
	emit_signal("health_changed", health, max_health)
	emit_signal("mana_changed", mana, max_mana)
	emit_signal("score_changed", score)

func _input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		yaw -= event.relative.x * 0.003
		pitch = clamp(pitch - event.relative.y * 0.003, -1.2, 0.5)
	if event is InputEventKey and event.keycode == KEY_ESCAPE and event.pressed:
		if Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
			Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
		else:
			Input.mouse_mode = Input.MOUSE_MODE_CAPTURED

func _physics_process(delta: float) -> void:
	if health <= 0:
		return

	if hit_flash > 0:
		hit_flash -= delta
		if model:
			model.visible = int(hit_flash * 20) % 2 == 0

	var forward := Input.get_vector("move_left", "move_right", "move_forward", "move_back")
	var move_dir := Vector3(forward.x, 0, forward.y)
	var cos_y := cos(yaw)
	var sin_y := sin(yaw)
	var rotated_dir := Vector3(
		move_dir.x * cos_y - move_dir.z * sin_y, 0,
		move_dir.x * sin_y + move_dir.z * cos_y
	)

	if is_dodging:
		velocity = dodge_dir * DASH_SPEED
		dodge_timer -= delta
		if dodge_timer <= 0:
			is_dodging = false
	else:
		velocity = rotated_dir * SPEED

	move_and_slide()

	if rotated_dir.length() > 0.1 and model and not is_dodging:
		var target_angle := atan2(rotated_dir.x, rotated_dir.z)
		model.rotation.y = lerp_angle(model.rotation.y, target_angle, delta * 12.0)

	if attack_timer > 0:
		attack_timer -= delta
	if magic_timer > 0:
		magic_timer -= delta

	if Input.is_action_just_pressed("attack") and attack_timer <= 0:
		_perform_attack()
	if Input.is_action_just_pressed("magic") and magic_timer <= 0 and mana >= MAGIC_COST:
		_perform_magic()
	if Input.is_action_just_pressed("dodge") and not is_dodging:
		_perform_dodge(rotated_dir)

	mana = min(max_mana, mana + int(delta * 10))
	emit_signal("mana_changed", mana, max_mana)
	_update_camera()

func _update_camera() -> void:
	var cam_offset := Vector3(0, 4, -6)
	var cos_y := cos(yaw)
	var sin_y := sin(yaw)
	var rotated_offset := Vector3(
		cam_offset.x * cos_y - cam_offset.z * sin_y, cam_offset.y,
		cam_offset.x * sin_y + cam_offset.z * cos_y
	)
	camera.position = position + rotated_offset
	camera.look_at(position + Vector3(0, 1.5, 0))

func _perform_attack() -> void:
	attack_timer = ATTACK_COOLDOWN
	if model:
		var tween := create_tween()
		tween.tween_property(model, "rotation:y", model.rotation.y + 1.2, 0.12)
		tween.tween_property(model, "rotation:y", model.rotation.y - 0.6, 0.15)
		tween.tween_property(model, "rotation:y", model.rotation.y, 0.1)
	var slash_dir := Vector3(sin(yaw), 0, cos(yaw))
	emit_signal("attack_slash", global_position + Vector3(0, 1, 0) + slash_dir * 1.5, slash_dir)
	var bodies := attack_area.get_overlapping_bodies()
	for body in bodies:
		if body.has_method("take_damage") and body != self:
			body.take_damage(30)
			emit_signal("damage_dealt", 30, body.global_position)

func _perform_magic() -> void:
	mana -= MAGIC_COST
	magic_timer = 0.6
	emit_signal("mana_changed", mana, max_mana)
	var magic_pos := global_position + Vector3(0, 1, 0) + Vector3(sin(yaw), 0, cos(yaw)) * 2
	emit_signal("magic_cast", magic_pos)
	for body in get_tree().get_nodes_in_group("enemies"):
		if body.is_alive and global_position.distance_to(body.global_position) < 6:
			body.take_damage(40)
			emit_signal("damage_dealt", 40, body.global_position)

func _perform_dodge(dir: Vector3) -> void:
	is_dodging = true
	dodge_timer = 0.3
	dodge_dir = dir.normalized() if dir.length() > 0.1 else Vector3(sin(yaw), 0, cos(yaw))

func take_damage(amount: int) -> void:
	if is_dodging:
		return
	health = max(0, health - amount)
	hit_flash = 0.3
	emit_signal("health_changed", health, max_health)
	emit_signal("player_damaged", amount)
	if health <= 0:
		emit_signal("player_died")

func heal(amount: int) -> void:
	health = min(max_health, health + amount)
	emit_signal("health_changed", health, max_health)

func add_score(points: int) -> void:
	score += points
	emit_signal("score_changed", score)