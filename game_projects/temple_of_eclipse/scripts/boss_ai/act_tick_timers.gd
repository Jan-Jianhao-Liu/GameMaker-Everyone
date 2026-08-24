extends ActionLeaf

func tick(actor: Node, blackboard: Blackboard) -> int:
	if actor.attack_timer > 0.0:
		actor.attack_timer -= get_process_delta_time()
	actor.slam_timer -= get_process_delta_time()
	actor.special_timer -= get_process_delta_time()
	if actor.hit_flash > 0:
		actor.hit_flash -= get_process_delta_time()
		actor.visible = int(actor.hit_flash * 20) % 2 == 0
	return SUCCESS