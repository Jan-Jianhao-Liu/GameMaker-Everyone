extends Label3D

var lifetime: float = 0.8
var float_speed: float = 2.0
var elapsed: float = 0.0
var start_color: Color = Color(1, 0.9, 0.2)
var crit_color: Color = Color(1, 0.3, 0.1)
var is_crit: bool = false

func _ready() -> void:
	font_size = 48 if not is_crit else 64
	modulate = crit_color if is_crit else start_color
	no_depth_test = true

func _process(delta: float) -> void:
	elapsed += delta
	position.y += float_speed * delta
	var progress := elapsed / lifetime
	modulate.a = 1.0 - progress
	if elapsed >= lifetime:
		queue_free()

func setup(amount: int, crit: bool = false) -> void:
	text = str(amount)
	is_crit = crit