extends Node
## InputAdapter：输入抽象层。
## 游戏逻辑通过本节点读取输入，不直接调 Input.xxx。
## 二级自动化测试时，测试脚本注入 mock 输入（start_mocking + set_mock_action），驱动角色。

var _mock: Dictionary = {}
var _mocking: bool = false


func is_pressed(action: String) -> bool:
	if _mocking:
		return _mock.get(action, false)
	return Input.is_action_pressed(action)


func just_pressed(action: String) -> bool:
	if _mocking:
		return _mock.get(action, false)
	return Input.is_action_just_pressed(action)


func just_released(action: String) -> bool:
	if _mocking:
		return not _mock.get(action, false)
	return Input.is_action_just_released(action)


func get_vector(neg_x: String, pos_x: String, neg_y: String, pos_y: String) -> Vector2:
	return Vector2(
		float(is_pressed(pos_x)) - float(is_pressed(neg_x)),
		float(is_pressed(pos_y)) - float(is_pressed(neg_y))
	)


func start_mocking() -> void:
	_mocking = true
	_mock.clear()


func set_mock_action(action: String, pressed: bool) -> void:
	_mock[action] = pressed


func stop_mocking() -> void:
	_mocking = false
	_mock.clear()