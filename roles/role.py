import traceback
from typing import Any, ClassVar
from pydantic import Field, BaseModel
from actions.plan_summary import PlannerSummary
from actions.planner import Planner
from actions.write_code import WriteCode
from actions.write_report import WriteReport
from db.models.plan_model import Plan
from db.repository.plan_repository import get_planner_by_id, add_plan_to_db
from db.repository.task_repository import add_task_to_plan
from prompts.prompt import DeepPentestPrompt
from server.chat.chat import _chat
import time
import traceback
from utils.log_common import build_logger
import sys
import re
from config.config import Configs
import json
from utils.log_common import RoleType
from utils.check_foundryOutput import check_and_print_foundry_output
from actions.refiner import Refiner
logger = build_logger()


class Role(BaseModel):
    name: str
    goal: str
    tools: str
    prompt: ClassVar
    max_interactions: int = 5
    previous_summary: PlannerSummary = Field(default_factory=PlannerSummary)
    planner: Planner = Field(default_factory=Planner)
    refine: Refiner = Field(default_factory=Refiner)
    chat_counter: int = 0
    plan_chat_id: str = ""
    react_chat_id: str = ""
    console: Any = None
    flag_found: bool = False

    def get_summary(self, history_planner_ids, session_id=None):
        self.console.print(
            f"===========================> [session ID:] {session_id}",
            style="bold green",
        )
        self.previous_summary = PlannerSummary(history_planner_ids=history_planner_ids)
        return self.previous_summary.get_summary(session_id=session_id)

    def put_message(self, message):
        if (
            self.planner
            and self.planner.current_plan
            and hasattr(self.planner.current_plan, "tasks")
            and self.planner.current_plan.tasks
            and isinstance(self.planner.current_plan.tasks, list)
        ):
            add_task_to_plan(self.planner.current_plan.tasks)
        if self.flag_found:
            self.console.print(
                "[bold yellow]Flag found. Finalizing current phase and generating summary...[/bold yellow]"
            )

            # 1. Ensure the current plan is added to history before summarizing
            if (
                self.planner
                and self.planner.current_plan
                and self.planner.current_plan.id
            ):
                if self.planner.current_plan.id not in message.history_planner_ids:
                    message.history_planner_ids.append(self.planner.current_plan.id)
                    self.console.print(
                        f"Added final planner ID {self.planner.current_plan.id} to history."
                    )
            # 2. Create the final summary, including the flag discovery
            self.get_summary(message.history_planner_ids, session_id=message.id)
            self.console.print(
                "[bold green]Summary including the flag discovery has been generated and saved.[/bold green]"
            )

            # 3. Switch role to Remediator
            message.current_role_name = RoleType.REMEDIATOR.value
            self.console.print(
                f"Transitioning to role: [bold cyan]{message.current_role_name}[/bold cyan]"
            )

            # 4. Clear the current planner so the next role starts fresh
            message.current_planner_id = ""
        else:
            # If no flag is found, subclasses handle the flow
            pass

    def _react(self,session, session_id,next_task):
        try:
            self.chat_counter += 1
            # Check if current_plan and current_task exist
            if (
                not self.planner.current_plan
                or not self.planner.current_plan.current_task
            ):
                self.console.print(
                    "[red]Error: No current plan or task available.[/red]"
                )
                return None
       
            writer = WriteCode(
                next_task=next_task,
                action=self.planner.current_plan.current_task.action,
            )
            result = writer.run()
            self.console.print(
                "---------- Execute Result ---------", style="bold green"
            )
            logger.info(result.response)
            self.console.print(
                "---------- Execute Result End ---------", style="bold green"
            )

            self.console.print(f"[bold yellow]Current Role: {self.name}[/bold yellow]")
            if self.name == "Smart Contract Vulnerability Exploiter":
                if check_and_print_foundry_output(session_id, result.response) == "yes":
                    self.console.print(
                        "[bold yellow]Foundry output detected. Calling refine action...[/bold yellow]"
                    )
                    
                    # Initialize refiner with current plan if not already initialized
                    if not hasattr(self, 'refine') or self.refine is None:
                        self.console.print("[bold blue]Initializing refiner with current plan...[/bold blue]")
                        self.refine = Refiner(
                            current_plan=self.planner.current_plan,
                            init_description=session.init_description,
                            session_id=session_id  # Add session_id to refiner
                        )
                    
                    # Ensure refiner has access to current plan and session_id
                    if self.refine.current_plan is None:
                        self.refine.current_plan = self.planner.current_plan
                        
                    if not self.refine.session_id:
                        self.refine.session_id = session_id
                    
                    # Validate refiner is properly initialized before proceeding
                    if not self.refine.current_plan or not self.refine.current_plan.react_chat_id:
                        self.console.print("[bold red]Error: Refiner not properly initialized. Using planner instead.[/bold red]")
                        # Fall back to regular planner if refiner can't be initialized
                        self.planner.current_plan.current_task.code = result.context["code"]
                        if len(result.response) >= 8192:
                            response, _ = _chat(
                                query=DeepPentestPrompt.summary_result + str(result.response),
                                summary=False,
                            )
                            logger.info(f"result summary: {response}")
                            result.response = response
                        return self.planner.update_plan(result.response)
                    
                    self.planner.current_plan.current_task.code = result.context["code"]
                    if len(result.response) >= 8192:
                        response, _ = _chat(
                            query=DeepPentestPrompt.summary_result + str(result.response),
                            summary=False,
                        )
                        logger.info(f"result summary: {response}")
                        result.response = response
                    
                    return self.refine.update_refine(result.response)
                else:
                    # No Foundry output, use regular planner
                    self.planner.current_plan.current_task.code = result.context["code"]
                    if len(result.response) >= 8192:
                        response, _ = _chat(
                            query=DeepPentestPrompt.summary_result + str(result.response),
                            summary=False,
                        )
                        logger.info(f"result summary: {response}")
                        result.response = response

                    return self.planner.update_plan(result.response)
            else:
                # For non-Exploiter roles, use regular planner
                self.planner.current_plan.current_task.code = result.context["code"]
                if len(result.response) >= 8192:
                    response, _ = _chat(
                        query=DeepPentestPrompt.summary_result + str(result.response),
                        summary=False,
                    )
                    logger.info(f"result summary: {response}")
                    result.response = response

                return self.planner.update_plan(result.response)
                
        except Exception as e:
            print(e)
            print(traceback.format_exc())

    def _plan(self, session):
        try:
            if session.current_planner_id != "":
                # if self.name == "Smart Contract Vulnerability Exploiter":
                #     self.refine = Refiner(
                #         current_plan=get_planner_by_id(session.current_planner_id),
                #         init_description=session.init_description,
                #     )
                # else:
                self.planner = Planner(
                    current_plan=get_planner_by_id(session.current_planner_id),
                    init_description=session.init_description,
                )
            else:
                with self.console.status(
                    "[bold green] Initializing DeepPentest Sessions..."
                ) as status:
                    try:
                        # context = self.get_summary(session.history_planner_ids, session_id=session.id)
                        context = self.get_summary(
                            session.history_planner_ids, session_id=session.id
                        )
                        print(f"DEBUG: session.id = {session.id}")

                        (text_0, self.plan_chat_id) = _chat(
                            query=self.prompt.init_plan_prompt.format(
                                init_description=session.init_description,
                                goal=self.goal,
                                tools=self.tools,
                                context=context,
                                name=self.name,  # Add the missing name parameter
                            )
                        )
                        (text_1, self.react_chat_id) = _chat(
                            query=self.prompt.init_reasoning_prompt
                        )
                    except Exception as e:
                        self.console.print(
                            f"Failed to initialize chat sessions: {e}", style="bold red"
                        )
                        # self.console.print(f"Error type: {type(e)}", style="bold red")
                        # import traceback

                        # self.console.print(
                        #     f"Full traceback: {traceback.format_exc()}", style="bold red"
                        # )
                        
                        # GPT-specific error messages
                        if "rate_limit" in str(e).lower():
                            self.console.print("[bold yellow]Rate limit exceeded. Wait before retrying.[/bold yellow]")
                        elif "invalid_api_key" in str(e).lower():
                            self.console.print("[bold red]Invalid OpenAI API key. Check model_config.yaml[/bold red]")
                        elif "model_not_found" in str(e).lower():
                            self.console.print("[bold red]Model not found. Use valid model name like gpt-4o-mini[/bold red]")
                        
                        return None
                plan = Plan(
                    goal=self.goal,
                    plan_chat_id=self.plan_chat_id,
                    react_chat_id=self.react_chat_id,
                    current_task_sequence=0,
                )
                plan = add_plan_to_db(plan)
                self.console.print("Plan Initialized.", style="bold green")
                session.current_planner_id = plan.id
                self.planner = Planner(
                    current_plan=plan,
                    init_description=session.init_description,
                )
                
                if self.name == "Smart Contract Vulnerability Exploiter":
                    self.refine = Refiner(
                        current_plan=plan,
                        init_description=session.init_description
                    )

            # Ensure planner is properly initialized before planning
            if not self.planner or not self.planner.current_plan:
                self.console.print("[red]Error: Planner not properly initialized.[/red]")
                return None

            return self.planner.plan()
        except Exception as e:
            print(e)
            print(traceback.format_exc())
            return None

    def run(self, session):
        # Set max_interactions to 30 for Exploiter role
        if self.name == "Smart Contract Vulnerability Exploiter":
            self.max_interactions = 30
            
        next_task = self._plan(session)
        if next_task is None:
            self.console.print("[red]Failed to initialize plan. Exiting.[/red]")
            # Force role transition if no plan generated
            self.put_message(session)
            return
            
        while self.chat_counter < self.max_interactions:
            logger.info(f"\n[INTERACTIONS : ]{self.chat_counter} ========================================================>")
            # Also print to stdout so bash script can capture it
            print(f"[INTERACTIONS : ]{self.chat_counter} ========================================================>")
            self.console.print(f"[INTERACTIONS : ]{self.chat_counter} ========================================================>", style="bold magenta")
            
            next_task = self._react(session, session.id, next_task)
            
            if next_task == "FLAG_FOUND":
                break
            if next_task is None:
                self.console.print(f"[bold blue]No more tasks. {self.name} phase completed.[/bold blue]")
                break
                
        self.put_message(session)