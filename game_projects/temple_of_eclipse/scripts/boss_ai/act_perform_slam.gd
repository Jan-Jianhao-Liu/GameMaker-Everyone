extends ActionLeaf

func tick(actor: Node, blackboard: Blackboard) -> int:
	actor._perform_slam()
	return SUCCESS