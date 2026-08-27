extends Control

@onready var health_bar: ProgressBar = $TopLeft/HealthBar
@onready var mana_bar: ProgressBar = $TopLeft/ManaBar
@onready var health_label: Label = $TopLeft/HealthLabel
@onready var mana_label: Label = $TopLeft/ManaLabel
@onready var score_label: Label = $TopRight/ScoreLabel
@onready var enemy_label: Label = $TopRight/EnemyLabel
@onready var boss_container: Panel = $BossContainer
@onready var boss_bar: ProgressBar = $BossContainer/BossBar
@onready var boss_label: Label = $BossContainer/BossLabel
@onready var phase_label: Label = $BossContainer/PhaseLabel
@onready var crosshair: CenterContainer = $Crosshair
@onready var message_label: Label = $Center/MessageLabel
@onready var skill_attack: Panel = $BottomBar/SkillAttack
@onready var skill_magic: Panel = $BottomBar/SkillMagic
@onready var skill_dodge: Panel = $BottomBar/SkillDodge

var game_manager: Node3D = null
var player: CharacterBody3D = null
var boss: CharacterBody3D = null

func _ready() -> void:
	boss_container.visible = false
	message_label.text = ""
	_find_game_manager()

func _find_game_manager() -> void:
	await get_tree().process_frame
	for node in get_tree().get_nodes_in_group("game_manager"):
		game_manager = node
		break
	if not game_manager:
		var root := get_tree().current_scene
		if root and root.has_node("GameManager"):
			game_manager = root.get_node("GameManager")
	if game_manager:
		game_manager.boss_appeared.connect(_on_boss_appeared)
		game_manager.boss_health_changed.connect(_on_boss_health_changed)
		game_manager.game_won.connect(_on_game_won)
		game_manager.game_lost.connect(_on_game_lost)
		game_manager.enemy_count_changed.connect(_on_enemy_count_changed)
		await get_tree().process_frame
		if game_manager.player:
			player = game_manager.player
			player.health_changed.connect(_on_health_changed)
			player.mana_changed.connect(_on_mana_changed)
			player.score_changed.connect(_on_score_changed)

func _on_health_changed(h: int, mh: int) -> void:
	health_bar.value = float(h) / float(mh) * 100.0
	health_label.text = "%d / %d" % [h, mh]
	if h < mh * 0.3:
		health_bar.modulate = Color(1, 0.3, 0.3)
	else:
		health_bar.modulate = Color(1, 1, 1)

func _on_mana_changed(m: int, mm: int) -> void:
	mana_bar.value = float(m) / float(mm) * 100.0
	mana_label.text = "%d / %d" % [m, mm]
	if m < 20:
		skill_magic.modulate = Color(0.5, 0.5, 0.5, 0.7)
	else:
		skill_magic.modulate = Color(1, 1, 1, 1)

func _on_score_changed(s: int) -> void:
	score_label.text = "分数: %d" % s

func _on_enemy_count_changed(killed: int, total: int) -> void:
	enemy_label.text = "击杀: %d / %d" % [killed, total]

func _on_boss_appeared() -> void:
	boss_container.visible = true
	boss_container.modulate.a = 0.0
	var tween := create_tween()
	tween.tween_property(boss_container, "modulate:a", 1.0, 0.5)
	message_label.text = "神殿守护者苏醒了！"
	message_label.modulate = Color(1, 0.3, 0.3)
	var tween2 := create_tween()
	tween2.tween_interval(2.5)
	tween2.tween_property(message_label, "modulate:a", 0.0, 1.0)
	tween2.tween_callback(func(): message_label.text = "")
	if game_manager and game_manager.boss:
		boss = game_manager.boss
		if boss.has_signal("boss_phase_changed"):
			boss.boss_phase_changed.connect(_on_boss_phase_changed)

func _on_boss_health_changed(h: int, mh: int) -> void:
	boss_bar.value = float(h) / float(mh) * 100.0
	boss_label.text = "%d / %d" % [h, mh]

func _on_boss_phase_changed(phase: int) -> void:
	match phase:
		1: phase_label.text = "第一阶段"
		2: phase_label.text = "第二阶段 - 狂暴"
		3: phase_label.text = "第三阶段 - 暴怒"
	phase_label.modulate.a = 0.0
	var tween := create_tween()
	tween.tween_property(phase_label, "modulate:a", 1.0, 0.3)
	tween.tween_interval(1.5)
	tween.tween_property(phase_label, "modulate:a", 0.6, 0.5)

func _on_game_won() -> void:
	message_label.text = "胜利！神殿已被净化！"
	message_label.modulate = Color(0.3, 1, 0.5)
	message_label.modulate.a = 1.0
	boss_container.visible = false

func _on_game_lost() -> void:
	message_label.text = "你倒在了幽冥神殿之中..."
	message_label.modulate = Color(1, 0.2, 0.2)
	message_label.modulate.a = 1.0

func _process(delta: float) -> void:
	if player and player.is_dodging:
		skill_dodge.modulate = Color(0.5, 0.5, 0.5, 0.5)
	else:
		skill_dodge.modulate = Color(1, 1, 1, 1)
	if player and player.attack_timer > 0:
		skill_attack.modulate = Color(0.7, 0.7, 0.7, 0.8)
	else:
		skill_attack.modulate = Color(1, 1, 1, 1)