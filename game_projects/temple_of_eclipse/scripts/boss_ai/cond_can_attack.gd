extends ConditionLeaf

func tick(actor: Node, blackboard: Blackboard) -> int:
	if actor.attack_timer <= 0.0:
		return SUCCESS
	return FAILURE