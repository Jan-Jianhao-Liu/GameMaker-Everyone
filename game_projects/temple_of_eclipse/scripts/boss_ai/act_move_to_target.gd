extends ActionLeaf

func tick(actor: Node, blackboard: Blackboard) -> int:
	if not actor.target:
		return FAILURE
	actor._update_phase()
	var to_target := actor.target.global_position - actor.global_position
	var dist := to_target.length()
	var current_speed := actor._get_current_speed()
	if actor.is_slamming or actor.is_special:
		actor.velocity = Vector3.ZERO
		actor.move_and_slide()
		return RUNNING
	if dist > actor.ATTACK_RANGE:
		actor.velocity = to_target.normalized() * current_speed
		actor.move_and_slide()
		if actor.get_node_or_null("Model"):
			actor.get_node("Model").look_at(actor.target.global_position)
		return RUNNING
	actor.velocity = Vector3.ZERO
	actor.move_and_slide()
	return SUCCESS