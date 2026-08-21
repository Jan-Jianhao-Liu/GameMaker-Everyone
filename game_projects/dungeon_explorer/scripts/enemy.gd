extends CharacterBody3D

const SPEED = 2.5
const ATTACK_RANGE = 1.5
const ATTACK_COOLDOWN = 1.5
const DAMAGE = 10

var health: int = 50
var max_health: int = 50
var attack_timer: float = 0.0
var is_alive: bool = true
var target: CharacterBody3D = null

@onready var navigation_region: NavigationRegion3D = get_parent().get_node_or_null("NavigationRegion3D")

func _ready() -> void:
	add_to_group("enemies")

func set_target(t: CharacterBody3D) -> void:
	target = t

func _physics_process(delta: float) -> void:
	if not is_alive or not target or target.health <= 0:
		return

	var to_target := target.global_position - global_position
	var dist := to_target.length()

	if dist > ATTACK_RANGE:
		var dir := to_target.normalized()
		velocity = dir * SPEED
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
		var dist := global_position.distance_to(target.global_position)
		if dist <= ATTACK_RANGE + 0.5:
			target.take_damage(DAMAGE)

func take_damage(amount: int) -> void:
	if not is_alive:
		return
	health = max(0, health - amount)
	if health <= 0:
		_die()

func _die() -> void:
	is_alive = false
	if target and target.has_method("add_score"):
		target.add_score(100)
	var tween := create_tween()
	tween.tween_property(self, "scale", Vector3.ZERO, 0.3)
	tween.tween_callback(queue_free)