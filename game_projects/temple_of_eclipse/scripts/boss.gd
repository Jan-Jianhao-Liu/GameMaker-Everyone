extends CharacterBody3D

const SPEED_PHASE1 = 2.0
const SPEED_PHASE2 = 3.5
const SPEED_PHASE3 = 5.0
const ATTACK_RANGE = 4.0
const ATTACK_COOLDOWN_P1 = 2.5
const ATTACK_COOLDOWN_P2 = 1.8
const ATTACK_COOLDOWN_P3 = 1.2
const DAMAGE_P1 = 20
const DAMAGE_P2 = 25
const DAMAGE_P3 = 35

var health: int = 500
var max_health: int = 500
var attack_timer: float = 0.0
var is_alive: bool = true
var target: CharacterBody3D = null
var hit_flash: float = 0.0
var is_boss: bool = true
var boss_phase: int = 1
var special_timer: float = 5.0
var slam_timer: float = 3.0
var is_slamming: bool = false
var is_special: bool = false
var enraged: bool = false
var _bt: Node = null

signal boss_health_changed(h: int, mh: int)
signal boss_phase_changed(phase: int)
signal boss_slam(pos: Vector3)
signal boss_special(pos: Vector3, radius: float)

func set_target(t: CharacterBody3D) -> void:
	target = t

func _ready() -> void:
	add_to_group("enemies")
	add_to_group("boss")
	emit_signal("boss_health_changed", health, max_health)
	emit_signal("boss_phase_changed", boss_phase)
	_build_behavior_tree()

func _build_behavior_tree() -> void:
	var tree := BeehaveTree.new()
	tree.name = "BossBT"
	tree.actor_node_path = NodePath(".")
	tree.process_thread = BeehaveTree.ProcessThread.PHYSICS
	add_child(tree)

	var root := Sequence.new()
	root.name = "Root"
	tree.add_child(root)

	var tick_timers := ActionLeaf.new()
	tick_timers.name = "TickTimers"
	tick_timers.set_script(load("res://scripts/boss_ai/act_tick_timers.gd"))
	root.add_child(tick_timers)

	var priority := Selector.new()
	priority.name = "Priority"
	root.add_child(priority)

	var special_seq := Sequence.new()
	special_seq.name = "Special"
	var can_special := ConditionLeaf.new()
	can_special.set_script(load("res://scripts/boss_ai/cond_can_special.gd"))
	var do_special := ActionLeaf.new()
	do_special.set_script(load("res://scripts/boss_ai/act_perform_special.gd"))
	special_seq.add_child(can_special)
	special_seq.add_child(do_special)
	priority.add_child(special_seq)

	var slam_seq := Sequence.new()
	slam_seq.name = "Slam"
	var can_slam := ConditionLeaf.new()
	can_slam.set_script(load("res://scripts/boss_ai/cond_can_slam.gd"))
	var do_slam := ActionLeaf.new()
	do_slam.set_script(load("res://scripts/boss_ai/act_perform_slam.gd"))
	slam_seq.add_child(can_slam)
	slam_seq.add_child(do_slam)
	priority.add_child(slam_seq)

	var attack_seq := Sequence.new()
	attack_seq.name = "Attack"
	var in_range := ConditionLeaf.new()
	in_range.set_script(load("res://scripts/boss_ai/cond_in_attack_range.gd"))
	var can_attack := ConditionLeaf.new()
	can_attack.set_script(load("res://scripts/boss_ai/cond_can_attack.gd"))
	var do_attack := ActionLeaf.new()
	do_attack.set_script(load("res://scripts/boss_ai/act_perform_attack.gd"))
	attack_seq.add_child(in_range)
	attack_seq.add_child(can_attack)
	attack_seq.add_child(do_attack)
	priority.add_child(attack_seq)

	var move_seq := Sequence.new()
	move_seq.name = "Move"
	var target_alive := ConditionLeaf.new()
	target_alive.set_script(load("res://scripts/boss_ai/cond_target_alive.gd"))
	var do_move := ActionLeaf.new()
	do_move.set_script(load("res://scripts/boss_ai/act_move_to_target.gd"))
	move_seq.add_child(target_alive)
	move_seq.add_child(do_move)
	priority.add_child(move_seq)

	_bt = tree

func _physics_process(delta: float) -> void:
	if not is_alive or not target or target.health <= 0:
		return
	if _bt and _bt.enabled:
		return
	if hit_flash > 0:
		hit_flash -= delta
		visible = int(hit_flash * 20) % 2 == 0
	_update_phase()
	var to_target := target.global_position - global_position
	var dist := to_target.length()
	var current_speed := _get_current_speed()
	if is_slamming or is_special:
		velocity = Vector3.ZERO
		move_and_slide()
		return
	if dist > ATTACK_RANGE:
		velocity = to_target.normalized() * current_speed
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
	special_timer -= delta
	if special_timer <= 0 and not is_special and not is_slamming:
		_perform_special()
	slam_timer -= delta
	if slam_timer <= 0 and not is_slamming and not is_special:
		_perform_slam()

func _update_phase() -> void:
	var old_phase := boss_phase
	if health <= max_health * 0.3:
		boss_phase = 3
		if not enraged:
			enraged = true
			_enrage()
	elif health <= max_health * 0.6:
		boss_phase = 2
	if boss_phase != old_phase:
		emit_signal("boss_phase_changed", boss_phase)

func _enrage() -> void:
	var tween := create_tween()
	tween.tween_property(self, "scale", scale * 1.2, 0.5)
	tween.tween_property(self, "scale", scale, 0.3)
	if $Model:
		var mat := StandardMaterial3D.new()
		mat.albedo_color = Color(1.2, 0.3, 0.2)
		mat.emission_enabled = true
		mat.emission = Color(1, 0.2, 0.1)
		mat.emission_energy_multiplier = 2.0

func _get_current_speed() -> float:
	match boss_phase:
		1: return SPEED_PHASE1
		2: return SPEED_PHASE2
		3: return SPEED_PHASE3
		_: return SPEED_PHASE1

func _get_current_cooldown() -> float:
	match boss_phase:
		1: return ATTACK_COOLDOWN_P1
		2: return ATTACK_COOLDOWN_P2
		3: return ATTACK_COOLDOWN_P3
		_: return ATTACK_COOLDOWN_P1

func _get_current_damage() -> int:
	match boss_phase:
		1: return DAMAGE_P1
		2: return DAMAGE_P2
		3: return DAMAGE_P3
		_: return DAMAGE_P1

func _perform_attack() -> void:
	attack_timer = _get_current_cooldown()
	if target and target.has_method("take_damage"):
		if global_position.distance_to(target.global_position) <= ATTACK_RANGE + 1.0:
			target.take_damage(_get_current_damage())
			_spawn_attack_effect()

func _perform_slam() -> void:
	is_slamming = true
	slam_timer = 4.0 if boss_phase >= 2 else 5.0
	var windup := 0.8 if boss_phase >= 3 else 1.0
	var tween := create_tween()
	if $Model:
		tween.tween_property($Model, "position:y", -1.0, windup * 0.5)
		tween.tween_property($Model, "position:y", 0.0, windup * 0.3)
	tween.tween_callback(_execute_slam)
	tween.tween_interval(0.3)
	tween.tween_property(self, "is_slamming", false, 0.01)

func _execute_slam() -> void:
	emit_signal("boss_slam", global_position)
	var slam_radius := 6.0 if boss_phase >= 2 else 5.0
	if target and global_position.distance_to(target.global_position) <= slam_radius:
		var slam_damage := _get_current_damage() + 10
		if target.has_method("take_damage"):
			target.take_damage(slam_damage)
	_spawn_slam_particles(slam_radius)

func _perform_special() -> void:
	is_special = true
	special_timer = 8.0 if boss_phase >= 2 else 12.0
	var tween := create_tween()
	if $Model:
		tween.tween_property($Model, "rotation:y", $Model.rotation.y + TAU, 1.0)
	tween.tween_callback(_execute_special)
	tween.tween_interval(0.5)
	tween.tween_property(self, "is_special", false, 0.01)

func _execute_special() -> void:
	var special_radius := 8.0 if boss_phase >= 3 else 6.0
	emit_signal("boss_special", global_position, special_radius)
	if target and global_position.distance_to(target.global_position) <= special_radius:
		var special_damage := _get_current_damage() + 15
		if target.has_method("take_damage"):
			target.take_damage(special_damage)
	_spawn_special_particles(special_radius)

func take_damage(amount: int) -> void:
	if not is_alive:
		return
	health = max(0, health - amount)
	hit_flash = 0.2
	emit_signal("boss_health_changed", health, max_health)
	if health <= 0:
		_die()

func _die() -> void:
	is_alive = false
	if target and target.has_method("add_score"):
		target.add_score(1000)
	_spawn_death_particles()
	var tween := create_tween()
	tween.tween_property(self, "scale", Vector3.ZERO, 1.0)
	tween.tween_callback(queue_free)

func _spawn_attack_effect() -> void:
	var particles_node := GPUParticles3D.new()
	particles_node.position = global_position + Vector3(0, 1, 0)
	particles_node.amount = 10
	particles_node.lifetime = 0.3
	var mat := ParticleProcessMaterial.new()
	mat.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
	mat.emission_sphere_radius = 0.5
	mat.direction = Vector3(0, 1, 0)
	mat.spread = 60
	mat.initial_velocity_min = 2
	mat.initial_velocity_max = 4
	mat.scale_min = 0.2
	mat.scale_max = 0.4
	mat.color = Color(0.8, 0.2, 0.1)
	particles_node.process_material = mat
	get_parent().add_child(particles_node)
	var tween := create_tween()
	tween.tween_interval(0.4)
	tween.tween_callback(particles_node.queue_free)

func _spawn_slam_particles(radius: float) -> void:
	for i in range(16):
		var angle := (i / 16.0) * TAU
		var particles_node := GPUParticles3D.new()
		particles_node.position = global_position + Vector3(cos(angle) * radius, 0, sin(angle) * radius)
		particles_node.amount = 8
		particles_node.lifetime = 0.5
		var mat := ParticleProcessMaterial.new()
		mat.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
		mat.emission_sphere_radius = 0.3
		mat.direction = Vector3(0, 1, 0)
		mat.spread = 30
		mat.initial_velocity_min = 3
		mat.initial_velocity_max = 6
		mat.scale_min = 0.3
		mat.scale_max = 0.6
		mat.color = Color(0.6, 0.3, 0.1)
		mat.gravity = Vector3(0, -8, 0)
		particles_node.process_material = mat
		get_parent().add_child(particles_node)
		var tween := create_tween()
		tween.tween_interval(0.6)
		tween.tween_callback(particles_node.queue_free)

	var shockwave := OmniLight3D.new()
	shockwave.position = global_position + Vector3(0, 0.5, 0)
	shockwave.light_color = Color(1.0, 0.4, 0.1)
	shockwave.light_energy = 8.0
	shockwave.omni_range = radius
	get_parent().add_child(shockwave)
	var tween := create_tween()
	tween.tween_property(shockwave, "light_energy", 0.0, 0.5)
	tween.tween_callback(shockwave.queue_free)

func _spawn_special_particles(radius: float) -> void:
	var particles_node := GPUParticles3D.new()
	particles_node.position = global_position + Vector3(0, 1, 0)
	particles_node.amount = 60
	particles_node.lifetime = 1.0
	var mat := ParticleProcessMaterial.new()
	mat.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
	mat.emission_sphere_radius = radius
	mat.direction = Vector3(0, 1, 0)
	mat.spread = 180
	mat.initial_velocity_min = 2
	mat.initial_velocity_max = 5
	mat.scale_min = 0.3
	mat.scale_max = 0.6
	mat.color = Color(0.5, 0.1, 0.3, 0.9)
	mat.gravity = Vector3(0, -3, 0)
	particles_node.process_material = mat
	get_parent().add_child(particles_node)

	var light := OmniLight3D.new()
	light.position = global_position + Vector3(0, 1, 0)
	light.light_color = Color(0.6, 0.1, 0.4)
	light.light_energy = 10.0
	light.omni_range = radius * 1.5
	get_parent().add_child(light)
	var tween := create_tween()
	tween.tween_property(light, "light_energy", 0.0, 1.0)
	tween.tween_callback(light.queue_free)
	tween.tween_interval(0.8)
	tween.tween_callback(particles_node.queue_free)

func _spawn_death_particles() -> void:
	for i in range(40):
		var angle := (i / 40.0) * TAU
		var particles_node := GPUParticles3D.new()
		particles_node.position = global_position + Vector3(cos(angle) * 2, 1, sin(angle) * 2)
		particles_node.amount = 15
		particles_node.lifetime = 1.5
		var mat := ParticleProcessMaterial.new()
		mat.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
		mat.emission_sphere_radius = 0.5
		mat.direction = Vector3(cos(angle), 1, sin(angle))
		mat.spread = 45
		mat.initial_velocity_min = 4
		mat.initial_velocity_max = 8
		mat.scale_min = 0.3
		mat.scale_max = 0.7
		mat.color = Color(0.4, 0.1, 0.5, 0.9)
		mat.gravity = Vector3(0, -5, 0)
		particles_node.process_material = mat
		get_parent().add_child(particles_node)
		var tween := create_tween()
		tween.tween_interval(1.6)
		tween.tween_callback(particles_node.queue_free)

	var light := OmniLight3D.new()
	light.position = global_position + Vector3(0, 2, 0)
	light.light_color = Color(0.5, 0.1, 0.6)
	light.light_energy = 15.0
	light.omni_range = 20.0
	get_parent().add_child(light)
	var tween := create_tween()
	tween.tween_property(light, "light_energy", 0.0, 2.0)
	tween.tween_callback(light.queue_free)