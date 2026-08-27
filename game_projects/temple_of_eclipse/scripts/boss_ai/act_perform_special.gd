extends ActionLeaf

func tick(actor: Node, blackboard: Blackboard) -> int:
	actor._perform_special()
	return SUCCESS