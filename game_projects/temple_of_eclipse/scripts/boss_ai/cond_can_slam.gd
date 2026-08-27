extends ConditionLeaf

func tick(actor: Node, blackboard: Blackboard) -> int:
	if actor.slam_timer <= 0.0 and not actor.is_slamming and not actor.is_special:
		return SUCCESS
	return FAILURE