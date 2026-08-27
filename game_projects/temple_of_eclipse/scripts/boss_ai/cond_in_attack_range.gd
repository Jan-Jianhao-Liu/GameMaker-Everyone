extends ConditionLeaf

func tick(actor: Node, blackboard: Blackboard) -> int:
	if not actor.target:
		return FAILURE
	var dist := actor.global_position.distance_to(actor.target.global_position)
	if dist <= actor.ATTACK_RANGE:
		return SUCCESS
	return FAILURE