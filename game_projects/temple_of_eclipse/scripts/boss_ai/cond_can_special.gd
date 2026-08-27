extends ConditionLeaf

func tick(actor: Node, blackboard: Blackboard) -> int:
	if actor.special_timer <= 0.0 and not actor.is_special and not actor.is_slamming:
		return SUCCESS
	return FAILURE