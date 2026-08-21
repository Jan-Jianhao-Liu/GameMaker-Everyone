extends CharacterBody3D

const SPEED = 5.0
const ATTACK_RANGE = 2.0
const ATTACK_COOLDOWN = 0.5

var health: int = 100
var max_health: int = 100
var score: int = 0
var attack_timer: float = 0.0
var is_attacking: bool = false
var yaw: float = 0.0
var pitch: float = -0.3

@onready var camera: Camera3D = $Camera3D
@onready var attack_area: Area3D = $AttackArea
@onready var model: Node3D = $Model

signal health_changed(health: int, max_health: int)
signal score_changed(score: int)
signal player_died
signal attack_hit(target: Node)

func _ready() -> void:
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	emit_signal("health_changed", health, max_health)
	emit_signal("score_changed", score)

func _input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		yaw -= event.relative.x * 0.003
		pitch = clamp(pitch - event.relative.y * 0.003, -1.2, 0.5)
	if event is InputEventKey and event.keycode == KEY_ESCAPE:
		if Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
			Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
		else:
			Input.mouse_mode = Input.MOUSE_MODE_CAPTURED

func _physics_process(delta: float) -> void:
	if health <= 0:
		return

	var forward := Input.get_vector("move_left", "move_right", "move_forward", "move_back")
	var move_dir := Vector3.ZERO
	move_dir.x = forward.x
	move_dir.z = forward.y

	var cos_y := cos(yaw)
	var sin_y := sin(yaw)
	var rotated_dir := Vector3(
		move_dir.x * cos_y - move_dir.z * sin_y,
		0,
		move_dir.x * sin_y + move_dir.z * cos_y
	)

	velocity = rotated_dir * SPEED
	move_and_slide()

	if rotated_dir.length() > 0.1 and model:
		var target_angle := atan2(rotated_dir.x, rotated_dir.z)
		model.rotation.y = lerp_angle(model.rotation.y, target_angle, delta * 10.0)

	if attack_timer > 0:
		attack_timer -= delta
		if attack_timer <= 0:
			is_attacking = false

	if Input.is_action_just_pressed("attack") and attack_timer <= 0:
		_perform_attack()

	_update_camera()

func _update_camera() -> void:
	if not camera:
		return
	var cam_offset := Vector3(0, 3, -5)
	var cos_y := cos(yaw)
	var sin_y := sin(yaw)
	var rotated_offset := Vector3(
		cam_offset.x * cos_y - cam_offset.z * sin_y,
		cam_offset.y,
		cam_offset.x * sin_y + cam_offset.z * cos_y
	)
	camera.position = position + rotated_offset
	camera.look_at(position + Vector3(0, 1, 0))

func _perform_attack() -> void:
	is_attacking = true
	attack_timer = ATTACK_COOLDOWN
	if model:
		var tween := create_tween()
		tween.tween_property(model, "rotation:y", model.rotation.y + 0.5, 0.15)
		tween.tween_property(model, "rotation:y", model.rotation.y - 0.5, 0.15)
		tween.tween_property(model, "rotation:y", model.rotation.y, 0.1)

	var bodies := attack_area.get_overlapping_bodies()
	for body in bodies:
		if body.has_method("take_damage") and body != self:
			body.take_damage(25)
			emit_signal("attack_hit", body)

func take_damage(amount: int) -> void:
	health = max(0, health - amount)
	emit_signal("health_changed", health, max_health)
	if health <= 0:
		emit_signal("player_died")

func heal(amount: int) -> void:
	health = min(max_health, health + amount)
	emit_signal("health_changed", health, max_health)

func add_score(points: int) -> void:
	score += points
	emit_signal("score_changed", score)