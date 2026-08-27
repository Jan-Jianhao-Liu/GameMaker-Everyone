extends CharacterBody3D

const SPEED = 3.0
const ATTACK_RANGE = 2.0
const ATTACK_COOLDOWN = 1.8
const DAMAGE = 15

var health: int = 80
var max_health: int = 80
var attack_timer: float = 0.0
var is_alive: bool = true
var target: CharacterBody3D = null
var hit_flash: float = 0.0
var is_boss: bool = false
var boss_phase: int = 1

func set_target(t: CharacterBody3D) -> void:
	target = t

func _ready() -> void:
	add_to_group("enemies")

func _physics_process(delta: float) -> void:
	if not is_alive or not target or target.health <= 0:
		return
	if hit_flash > 0:
		hit_flash -= delta
		visible = int(hit_flash * 20) % 2 == 0

	var to_target := target.global_position - global_position
	var dist := to_target.length()
	if dist > ATTACK_RANGE:
		velocity = to_target.normalized() * SPEED
		move_and_slide()
		if $Model:
			$Model.look_at(target.global_position)
	else:
		velocity = Vector3.ZERO
		move_and_slide()
		if attack_timer <= 0:
			_perform_attack()
	if attack_timer > 0:
		attack_timer -= delta

func _perform_attack() -> void:
	attack_timer = ATTACK_COOLDOWN
	if target and target.has_method("take_damage"):
		if global_position.distance_to(target.global_position) <= ATTACK_RANGE + 0.8:
			target.take_damage(DAMAGE)

func take_damage(amount: int) -> void:
	if not is_alive:
		return
	health = max(0, health - amount)
	hit_flash = 0.2
	if health <= 0:
		_die()

func _die() -> void:
	is_alive = false
	if target and target.has_method("add_score"):
		target.add_score(150 if is_boss else 100)
	var tween := create_tween()
	tween.tween_property(self, "scale", Vector3.ZERO, 0.4)
	tween.tween_callback(queue_free)