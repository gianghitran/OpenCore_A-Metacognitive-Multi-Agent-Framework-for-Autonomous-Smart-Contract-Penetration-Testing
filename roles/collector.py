from typing import ClassVar

from prompts.collector_prompt import CollectorPrompt
from roles.role import Role
from roles.exploiter import Exploiter
from utils.log_common import RoleType
from roles.remediator import Remediator

class Collector(Role):
    name: str = "Smart Contract Vulnerability Detection Specialist"

    goal: str = (
        "Perform vulnerability identification on the target smart contract. "
        "Discover and identify smart contract vulnerabilities and verify them through slither. "
    )

    tools: str = (
        "Slither, "
    )
    
    prompt: ClassVar[CollectorPrompt] = CollectorPrompt

    def __init__(self, console, max_interactions, **kwargs):
        super().__init__(**kwargs)
        self.console = console
        self.max_interactions = max_interactions

    def put_message(self, message):
        super().put_message(message)
        if not self.flag_found and message.current_role_name == RoleType.COLLECTOR.value:
            if self.planner.current_plan and self.planner.current_plan.id not in message.history_planner_ids:
                message.history_planner_ids.append(self.planner.current_plan.id)
            message.current_role_name = RoleType.EXPLOITER.value
            # message.history_planner_ids.append(self.planner.current_plan.id)
            message.current_planner_id = ''
            Exploiter(console=self.console, max_interactions=self.max_interactions).run(message)