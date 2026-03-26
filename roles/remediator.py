from pyexpat.errors import messages
from typing import ClassVar
from prompts.remediator_prompt import RemediatorPrompt
from roles.role import Role
from actions.write_report import WriteReport
from utils.log_common import RoleType
import traceback
from db.repository.task_repository import add_task_to_plan

from actions.staticReport import StatisticsReport 

from db.repository.message_repository import get_conversation_messages
from db.repository.sessionsummary_repository import get_session_summaries_by_session_id
from utils.log_common import build_logger
import os
from datetime import datetime
            
import json
import csv

class Remediator(Role):
    name: str = "Remediator"
    goal: str = (
        "Analyze exploitation results and generate a comprehensive vulnerability report with actionable remediation steps."
    )
    tools: str = (
        ""
    )
    prompt: ClassVar[RemediatorPrompt] = RemediatorPrompt
    session_id: str = None
    def __init__(self, console, max_interactions=5, session_id=None, **kwargs):
        super().__init__(**kwargs)
        self.console = console
        self.max_interactions = max_interactions
        self.session_id = session_id

    def run(self, message):
        self.console.print("[bold blue]Remediation - add_task_to_plan.[/bold blue]")
        self.console.print("[bold blue]Remediation report has been recorded.[/bold blue]")
        session_id = self.session_id or getattr(message, "id", None)
        if session_id:
            messages = get_session_summaries_by_session_id(session_id)
        else:
            messages = []
        try:
            report_writer = WriteReport(plan_chat_id=session_id)
            report = report_writer.run(init_description="Comprehensive smart contract vulnerability assessment and remediation", result=messages)
            self.console.print("[bold green]Remediation Report:[/bold green]")
            self.console.print(report)
            reports_dir = "reports"
            os.makedirs(reports_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_short = session_id[:8] if session_id else "unknown"
            filename = f"remediationANDreport_{timestamp}_{session_short}.md"
            file_path = os.path.join(reports_dir, filename)
            
            # Write report to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"# Report\n\n")
                f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"**Session ID:** {session_id}\n\n")
                f.write("---\n\n")
                f.write(report)
            
            self.console.print(f"[bold green]Report saved to: {file_path}[/bold green]")
            
            logger = build_logger("session_summary")
            logger.info(f"Saving summary for session_id: {session_id}")
            logger.info(f"Report saved to file: {file_path}")
            logger = build_logger("session_summary")

        except Exception as e:
            self.console.print(f"[red]Failed to generate remediation report: {e}[/red]")
            print(traceback.format_exc())

        self.put_message(message)
        
