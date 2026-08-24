extends Node3D

const COLUMN_SCENE := "res://assets/models/column.fbx"
const STATUE_SCENE := "res://assets/models/statue.fbx"
const ARCH_SCENE := "res://assets/models/arch.fbx"
const ALTAR_SCENE := "res://assets/models/altar.fbx"
const DECORATIVE_PILLAR_SCENE := "res://assets/models/decorative_pillar.fbx"
const TORCH_SCENE := "res://assets/models/torch.fbx"
const ADVENTURER_SCENE := "res://assets/models/adventurer.fbx"
const STONE_GUARDIAN_SCENE := "res://assets/models/stone_guardian.fbx"
const FLAME_WRAITH_SCENE := "res://assets/models/flame_wraith.fbx"
const BOSS_SCENE := "res://assets/models/boss.fbx"

var player: CharacterBody3D = null
var enemies: Array = []
var boss: CharacterBody3D = null
var torches: Array = []
var particles: Array = []
var game_time: float = 0.0
var boss_spawned: bool = false
var enemies_killed: int = 0
var total_enemies: int = 0

signal boss_appeared
signal boss_health_changed(h: int, mh: int)
signal game_won
signal game_lost
signal enemy_count_changed(killed: int, total: int)

func _ready() -> void:
	_build_temple_architecture()
	_spawn_player()
	_spawn_enemies()
	_setup_lighting()
	_setup_ambient_particles()

func _process(delta: float) -> void:
	game_time += delta
	_update_torch_flicker(delta)
	_update_particles(delta)
	if not boss_spawned and enemies_killed >= total_enemies:
		_spawn_boss()
	if player and player.health <= 0 and not _game_over_emitted:
		_game_over_emitted = true
		emit_signal("game_lost")

var _game_over_emitted: bool = false

func _build_temple_architecture() -> void:
	var floor_mesh := BoxMesh.new()
	floor_mesh.size = Vector3(60, 1, 60)
	var floor_mat := StandardMaterial3D.new()
	floor_mat.albedo_color = Color(0.15, 0.12, 0.1)
	floor_mat.roughness = 0.9
	floor_mesh.material = floor_mat
	var floor := MeshInstance3D.new()
	floor.mesh = floor_mesh
	floor.position = Vector3(0, -0.5, 0)
	floor.name = "Floor"
	add_child(floor)

	var ceil_mesh := BoxMesh.new()
	ceil_mesh.size = Vector3(60, 1, 60)
	var ceil_mat := StandardMaterial3D.new()
	ceil_mat.albedo_color = Color(0.08, 0.06, 0.05)
	ceil_mat.roughness = 0.95
	ceil_mesh.material = ceil_mat
	var ceiling := MeshInstance3D.new()
	ceiling.mesh = ceil_mesh
	ceiling.position = Vector3(0, 8, 0)
	ceiling.name = "Ceiling"
	add_child(ceiling)

	for i in range(4):
		for j in range(4):
			if i == 0 or i == 3 or j == 0 or j == 3:
				var col := _load_model(COLUMN_SCENE)
				col.position = Vector3((i - 1.5) * 12, 0, (j - 1.5) * 12)
				col.name = "Column_%d_%d" % [i, j]
				add_child(col)

	for i in range(3):
		var arch := _load_model(ARCH_SCENE)
		arch.position = Vector3(0, 0, (i - 1) * 12 - 6)
		arch.rotation.y = PI / 2
		arch.scale = Vector3(1.2, 1.2, 1.2)
		add_child(arch)
		var arch2 := _load_model(ARCH_SCENE)
		arch2.position = Vector3((i - 1) * 12, 0, -6)
		arch2.scale = Vector3(1.2, 1.2, 1.2)
		add_child(arch2)

	var statue_positions := [
		Vector3(-10, 0, -10), Vector3(10, 0, -10),
		Vector3(-10, 0, 10), Vector3(10, 0, 10),
		Vector3(-15, 0, 0), Vector3(15, 0, 0)
	]
	for pos in statue_positions:
		var statue := _load_model(STATUE_SCENE)
		statue.position = pos
		add_child(statue)
		statue.look_at(Vector3(0, pos.y, 0))

	for i in range(8):
		var angle := (i / 8.0) * TAU
		var dp := _load_model(DECORATIVE_PILLAR_SCENE)
		dp.position = Vector3(cos(angle) * 20, 0, sin(angle) * 20)
		add_child(dp)
		dp.look_at(Vector3(0, 0, 0))
		dp.rotation.y += PI

	var altar := _load_model(ALTAR_SCENE)
	altar.position = Vector3(0, 0, -18)
	altar.scale = Vector3(1.5, 1.5, 1.5)
	add_child(altar)

	var altar2 := _load_model(ALTAR_SCENE)
	altar2.position = Vector3(0, 0, 18)
	altar2.scale = Vector3(1.5, 1.5, 1.5)
	add_child(altar2)

	var wall_thickness := 0.5
	var wall_height := 8.0
	var wall_mat := StandardMaterial3D.new()
	wall_mat.albedo_color = Color(0.12, 0.1, 0.08)
	wall_mat.roughness = 0.9
	for i in range(4):
		var wall := MeshInstance3D.new()
		var wall_mesh := BoxMesh.new()
		wall_mesh.material = wall_mat
		wall.mesh = wall_mesh
		if i == 0:
			wall_mesh.size = Vector3(48, wall_height, wall_thickness)
			wall.position = Vector3(0, wall_height / 2, -24)
		elif i == 1:
			wall_mesh.size = Vector3(48, wall_height, wall_thickness)
			wall.position = Vector3(0, wall_height / 2, 24)
		elif i == 2:
			wall_mesh.size = Vector3(wall_thickness, wall_height, 48)
			wall.position = Vector3(-24, wall_height / 2, 0)
		else:
			wall_mesh.size = Vector3(wall_thickness, wall_height, 48)
			wall.position = Vector3(24, wall_height / 2, 0)
		wall.name = "Wall_%d" % i
		add_child(wall)

func _load_model(path: String) -> Node3D:
	var res := load(path)
	if res is PackedScene:
		return res.instantiate()
	var node := Node3D.new()
	var mesh_inst := MeshInstance3D.new()
	var box := BoxMesh.new()
	box.size = Vector3(1, 1, 1)
	mesh_inst.mesh = box
	node.add_child(mesh_inst)
	return node

func _spawn_player() -> void:
	var player_node := CharacterBody3D.new()
	var player_script := load("res://scripts/player.gd")
	player_node.set_script(player_script)

	var col := CollisionShape3D.new()
	var cap := CapsuleShape3D.new()
	cap.radius = 0.5
	cap.height = 1.8
	col.shape = cap
	player_node.add_child(col)

	var cam := Camera3D.new()
	cam.name = "Camera3D"
	cam.fov = 70
	player_node.add_child(cam)

	var model_holder := Node3D.new()
	model_holder.name = "Model"
	var player_model := _load_model(ADVENTURER_SCENE)
	model_holder.add_child(player_model)
	player_node.add_child(model_holder)

	var attack_area := Area3D.new()
	attack_area.name = "AttackArea"
	var attack_col := CollisionShape3D.new()
	var attack_box := BoxShape3D.new()
	attack_box.size = Vector3(3, 2, 3)
	attack_col.shape = attack_box
	attack_area.add_child(attack_col)
	player_node.add_child(attack_area)

	player_node.position = Vector3(0, 1, 12)
	player = player_node
	add_child(player)

	player.health_changed.connect(_on_player_health_changed)
	player.mana_changed.connect(_on_player_mana_changed)
	player.score_changed.connect(_on_player_score_changed)
	player.player_died.connect(_on_player_died)
	player.damage_dealt.connect(_on_damage_dealt)
	player.magic_cast.connect(_on_magic_cast)
	player.attack_slash.connect(_on_attack_slash)

func _spawn_enemies() -> void:
	var guardian_positions := [
		Vector3(-8, 1, -5), Vector3(8, 1, -5),
		Vector3(-12, 1, 0), Vector3(12, 1, 0),
		Vector3(-6, 1, 8), Vector3(6, 1, 8)
	]
	for pos in guardian_positions:
		var enemy := _create_enemy(STONE_GUARDIAN_SCENE, pos, 80, 15, 3.0)
		enemies.append(enemy)

	var wraith_positions := [
		Vector3(-15, 1, -15), Vector3(15, 1, -15),
		Vector3(0, 1, -12), Vector3(-18, 1, 5)
	]
	for pos in wraith_positions:
		var enemy := _create_enemy(FLAME_WRAITH_SCENE, pos, 60, 20, 4.0)
		enemies.append(enemy)

	total_enemies = enemies.size()
	emit_signal("enemy_count_changed", enemies_killed, total_enemies)

func _create_enemy(model_path: String, pos: Vector3, hp: int, dmg: int, spd: float) -> CharacterBody3D:
	var enemy_node := CharacterBody3D.new()
	var enemy_script := load("res://scripts/enemy.gd")
	enemy_node.set_script(enemy_script)

	var col := CollisionShape3D.new()
	var cap := CapsuleShape3D.new()
	cap.radius = 0.6
	cap.height = 2.0
	col.shape = cap
	enemy_node.add_child(col)

	var model_holder := Node3D.new()
	model_holder.name = "Model"
	var enemy_model := _load_model(model_path)
	model_holder.add_child(enemy_model)
	enemy_node.add_child(model_holder)

	enemy_node.position = pos
	enemy_node.health = hp
	enemy_node.max_health = hp

	if enemy_node.has_method("set_target") and player:
		enemy_node.set_target(player)

	enemy_node.tree_exited.connect(_on_enemy_killed.bind(enemy_node))
	add_child(enemy_node)
	return enemy_node

func _on_enemy_killed(enemy_node: CharacterBody3D) -> void:
	if enemy_node in enemies:
		enemies.erase(enemy_node)
		enemies_killed += 1
		emit_signal("enemy_count_changed", enemies_killed, total_enemies)

func _spawn_boss() -> void:
	boss_spawned = true
	var boss_node := CharacterBody3D.new()
	var boss_script := load("res://scripts/boss.gd")
	boss_node.set_script(boss_script)

	var col := CollisionShape3D.new()
	var cap := CapsuleShape3D.new()
	cap.radius = 1.5
	cap.height = 4.0
	col.shape = cap
	boss_node.add_child(col)

	var model_holder := Node3D.new()
	model_holder.name = "Model"
	var boss_model := _load_model(BOSS_SCENE)
	model_holder.add_child(boss_model)
	boss_node.add_child(model_holder)

	boss_node.position = Vector3(0, 2, -18)
	boss_node.scale = Vector3(2, 2, 2)
	boss_node.is_boss = true

	if boss_node.has_method("set_target") and player:
		boss_node.set_target(player)

	boss_node.tree_exited.connect(_on_boss_defeated)
	boss = boss_node
	add_child(boss_node)

	var tween := create_tween()
	tween.tween_property(boss_node, "position:y", 2, 0.0)
	emit_signal("boss_appeared")
	if boss_node.has_signal("boss_health_changed"):
		boss_node.boss_health_changed.connect(_on_boss_health_changed)

func _on_boss_defeated() -> void:
	emit_signal("game_won")

func _on_boss_health_changed(h: int, mh: int) -> void:
	emit_signal("boss_health_changed", h, mh)

func _setup_lighting() -> void:
	var ambient := DirectionalLight3D.new()
	ambient.light_energy = 0.15
	ambient.light_color = Color(0.4, 0.3, 0.5)
	ambient.rotation.x = -PI / 4
	add_child(ambient)

	var fog := Environment.new()
	fog.fog_enabled = true
	fog.fog_light_color = Color(0.05, 0.03, 0.08)
	fog.fog_light_energy = 1.0
	fog.fog_density = 0.04
	fog.ambient_light_color = Color(0.1, 0.08, 0.15)
	fog.ambient_light_energy = 0.3
	var world_env := WorldEnvironment.new()
	world_env.environment = fog
	add_child(world_env)

	var torch_positions := [
		Vector3(-10, 0, -10), Vector3(10, 0, -10),
		Vector3(-10, 0, 10), Vector3(10, 0, 10),
		Vector3(-15, 0, 0), Vector3(15, 0, 0),
		Vector3(0, 0, -18), Vector3(0, 0, 18),
		Vector3(-6, 0, 0), Vector3(6, 0, 0)
	]
	for pos in torch_positions:
		var torch := _load_model(TORCH_SCENE)
		torch.position = pos
		add_child(torch)

		var light := OmniLight3D.new()
		light.position = pos + Vector3(0, 2.5, 0)
		light.light_color = Color(1.0, 0.6, 0.2)
		light.light_energy = 2.5
		light.omni_range = 12.0
		light.name = "TorchLight"
		add_child(light)
		torches.append({"light": light, "base_energy": 2.5, "phase": randf() * TAU})

		var flame := GPUParticles3D.new()
		flame.position = pos + Vector3(0, 2.2, 0)
		flame.amount = 15
		flame.lifetime = 0.5
		var flame_mat := ParticleProcessMaterial.new()
		flame_mat.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
		flame_mat.emission_sphere_radius = 0.1
		flame_mat.direction = Vector3(0, 1, 0)
		flame_mat.spread = 10
		flame_mat.initial_velocity_min = 0.5
		flame_mat.initial_velocity_max = 1.5
		flame_mat.scale_min = 0.2
		flame_mat.scale_max = 0.5
		flame_mat.color = Color(1.0, 0.5, 0.1, 0.8)
		flame.process_material = flame_mat
		add_child(flame)

func _update_torch_flicker(delta: float) -> void:
	for torch_data in torches:
		var light: OmniLight3D = torch_data["light"]
		var base: float = torch_data["base_energy"]
		var phase: float = torch_data["phase"]
		torch_data["phase"] = phase + delta * 8
		light.light_energy = base + sin(phase) * 0.4 + randf_range(-0.2, 0.2)

func _setup_ambient_particles() -> void:
	var dust := GPUParticles3D.new()
	dust.position = Vector3(0, 4, 0)
	dust.amount = 80
	dust.lifetime = 4.0
	var dust_mat := ParticleProcessMaterial.new()
	dust_mat.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_BOX
	dust_mat.emission_box_extents = Vector3(20, 3, 20)
	dust_mat.direction = Vector3(0, 0, 0)
	dust_mat.spread = 180
	dust_mat.initial_velocity_min = 0.1
	dust_mat.initial_velocity_max = 0.3
	dust_mat.scale_min = 0.05
	dust_mat.scale_max = 0.1
	dust_mat.color = Color(0.6, 0.5, 0.4, 0.3)
	dust_mat.gravity = Vector3.ZERO
	dust.process_material = dust_mat
	add_child(dust)
	particles.append(dust)

func _update_particles(delta: float) -> void:
	pass

func _on_player_health_changed(h: int, mh: int) -> void:
	pass

func _on_player_mana_changed(m: int, mm: int) -> void:
	pass

func _on_player_score_changed(s: int) -> void:
	pass

func _on_player_died() -> void:
	emit_signal("game_lost")

func _on_damage_dealt(amount: int, pos: Vector3) -> void:
	_spawn_damage_number(pos, amount, Color(1, 0.9, 0.2))
	_spawn_hit_particles(pos)

func _on_magic_cast(pos: Vector3) -> void:
	_spawn_magic_particles(pos)

func _on_attack_slash(pos: Vector3, dir: Vector3) -> void:
	_spawn_slash_particles(pos, dir)

func _spawn_damage_number(pos: Vector3, amount: int, color: Color) -> void:
	var label := Label3D.new()
	label.text = str(amount)
	label.font_size = 48
	label.modulate = color
	label.position = pos + Vector3(0, 1, 0)
	label.no_depth_test = true
	add_child(label)
	var tween := create_tween()
	tween.tween_property(label, "position:y", pos.y + 3, 0.8)
	tween.parallel().tween_property(label, "modulate:a", 0.0, 0.8)
	tween.tween_callback(label.queue_free)

func _spawn_hit_particles(pos: Vector3) -> void:
	var particles_node := GPUParticles3D.new()
	particles_node.position = pos
	particles_node.amount = 12
	particles_node.lifetime = 0.3
	var mat := ParticleProcessMaterial.new()
	mat.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
	mat.emission_sphere_radius = 0.2
	mat.direction = Vector3(0, 1, 0)
	mat.spread = 180
	mat.initial_velocity_min = 2
	mat.initial_velocity_max = 4
	mat.scale_min = 0.1
	mat.scale_max = 0.2
	mat.color = Color(1, 0.8, 0.3)
	mat.gravity = Vector3(0, -5, 0)
	particles_node.process_material = mat
	add_child(particles_node)
	var tween := create_tween()
	tween.tween_interval(0.4)
	tween.tween_callback(particles_node.queue_free)

func _spawn_magic_particles(pos: Vector3) -> void:
	var particles_node := GPUParticles3D.new()
	particles_node.position = pos
	particles_node.amount = 40
	particles_node.lifetime = 0.8
	var mat := ParticleProcessMaterial.new()
	mat.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
	mat.emission_sphere_radius = 0.5
	mat.direction = Vector3(0, 1, 0)
	mat.spread = 180
	mat.initial_velocity_min = 1
	mat.initial_velocity_max = 3
	mat.scale_min = 0.2
	mat.scale_max = 0.4
	mat.color = Color(0.3, 0.6, 1.0, 0.8)
	mat.gravity = Vector3(0, -2, 0)
	particles_node.process_material = mat
	add_child(particles_node)

	var light := OmniLight3D.new()
	light.position = pos
	light.light_color = Color(0.3, 0.6, 1.0)
	light.light_energy = 5.0
	light.omni_range = 8.0
	add_child(light)
	var tween := create_tween()
	tween.tween_property(light, "light_energy", 0.0, 0.8)
	tween.tween_callback(light.queue_free)
	tween.tween_interval(0.5)
	tween.tween_callback(particles_node.queue_free)

func _spawn_slash_particles(pos: Vector3, dir: Vector3) -> void:
	var particles_node := GPUParticles3D.new()
	particles_node.position = pos
	particles_node.amount = 8
	particles_node.lifetime = 0.2
	var mat := ParticleProcessMaterial.new()
	mat.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
	mat.emission_sphere_radius = 0.3
	mat.direction = dir
	mat.spread = 30
	mat.initial_velocity_min = 3
	mat.initial_velocity_max = 5
	mat.scale_min = 0.1
	mat.scale_max = 0.2
	mat.color = Color(0.9, 0.9, 1.0, 0.8)
	particles_node.process_material = mat
	add_child(particles_node)
	var tween := create_tween()
	tween.tween_interval(0.3)
	tween.tween_callback(particles_node.queue_free)