extends ConditionLeaf

func tick(actor: Node, blackboard: Blackboard) -> int:
	if not actor.is_alive or not actor.target or actor.target.health <= 0:
		return FAILURE
	return SUCCESS