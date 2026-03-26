import re
import time
from typing import List

from click import prompt
from pydantic import BaseModel

from actions.run_code import RunCode
from actions.shell_manager import ShellManager
from config.config import Configs, Mode

from utils.log_common import build_logger
from prompt_toolkit import prompt

logger = build_logger()


class ExecuteResult(BaseModel):
    """Class đại diện cho kết quả thực thi một task.
    
    Attributes:
        context (object): Context của task được thực thi
        response (str): Phản hồi từ việc thực thi task
    """
    context: object
    response: str


class ExecuteTask(BaseModel):
    """Class quản lý việc thực thi các task.
    
    Attributes:
        action (str): Loại hành động cần thực thi
        instruction (str): Chỉ dẫn chi tiết cho hành động
        code (List[str]): Danh sách các lệnh cần thực thi
    """
    action: str
    instruction: str
    code: List[str]

    def parse_response(self) -> list[str]:
        """Phân tích instruction để lấy ra các lệnh thực thi.
        
        Tìm kiếm và trích xuất nội dung nằm giữa các thẻ <execute></execute>
        trong instruction. Làm sạch kết quả bằng cách loại bỏ khoảng trắng thừa.
        
        Returns:
            list[str]: Danh sách các lệnh đã được làm sạch
        """
        initial_matches = re.findall(
            r'<execute>\s*(.*?)\s*</execute>', self.instruction, re.DOTALL
        )

        cleaned_matches = []
        for match in initial_matches:

            if '<execute>' in match:
                inner_match = re.search(r'<execute>\s*(.*?)$', match)
                if inner_match:
                    cleaned_matches.append(inner_match.group(1).strip())
            else:
                cleaned_matches.append(match.strip())

        return cleaned_matches

    def run(self) -> ExecuteResult:
        """Thực thi task dựa trên mode cấu hình.
        
        Kiểm tra mode cấu hình (SemiAuto, Manual, Auto) và thực hiện tác vụ tương ứng:
        - SemiAuto + Shell: Thực thi shell_operation
        - SemiAuto + khác: Yêu cầu nhập lệnh thủ công
        - Manual: Yêu cầu nhập lệnh thủ công
        - Auto: Thực thi shell_operation
        
        Returns:
            ExecuteResult: Kết quả thực thi bao gồm context và response
        """
        if Configs.basic_config.mode == Mode.SemiAuto:
            if self.action == "Shell":
                result = self.shell_operation()
                # result = RunCode(timeout=300, commands=thought).execute_cmd()
                # if result == "":
                #     result = prompt("Since the command takes too long to run, "
                #                         "please enter the manual run command and enter the result.\n> ")
            else:
                result = prompt("Please enter the manual run command and enter the result.\n> ")
        elif Configs.basic_config.mode == Mode.Manual:
            result = prompt("Please enter the manual run command and enter the result.\n> ")
        else:
            result = self.shell_operation()

        return ExecuteResult(context={
            "action": self.action,
            "instruction": self.instruction,
            "code": self.code,
        }, response=result)

    def shell_operation(self):
        """Thực thi các lệnh shell.
        
        Phân tích response để lấy danh sách lệnh, sau đó thực thi từng lệnh một.
        Xử lý các trường hợp đặc biệt như:
        - Prompt yêu cầu mật khẩu
        
        Returns:
            str: Kết quả thực thi các lệnh shell, bao gồm cả lệnh và output
        
        Raises:
            Exception: Khi chưa thiết lập kết nối SSH
        """
        result = ""
        thought = self.parse_response()
        self.code = thought
        logger.info(f"Running {thought}")
        # Execute command list
        shell = ShellManager.get_instance().get_shell()
        try:

            PASSWORD_PROMPTS = [
                'password:',
                'Password for'
                '[sudo] password for',
            ]

            skip_next = False

            for i, command in enumerate(self.code):
                # Skip next command if skip_next is True
                if skip_next:
                    skip_next = False
                    continue

                result += f'Action:{command}\nObservation: '
                output = shell.execute_cmd(command)
                result += output + '\n'
                out_line = output.strip().split('\n')

                last_line = out_line[-1]

                if any(prompt in last_line for prompt in PASSWORD_PROMPTS):
                    if i + 1 < len(self.code):
                        result += f'Action:{self.code[i + 1]}\nObservation: '
                        next_output = shell.execute_cmd(self.code[i + 1])
                        result += next_output + '\n'
                        skip_next = True
                        if any(prompt in next_output.strip().split('\n')[-1] for prompt in PASSWORD_PROMPTS):
                            shell.shell.send('\x03')  # Send Ctrl+C
                            time.sleep(0.5)  # Wait for Ctrl+C to take effect
                            # Clear the previous result
                            result = result.rsplit('Action:', 1)[0] + f'Action:{self.code[i + 1]}\nObservation: '
                            # Resend the second command
                            new_output = shell.execute_cmd(self.code[i + 1])
                            result += new_output + '\n'
                    else:
                        shell.shell.send('\x03')  # Send Ctrl+C for single command case


        except Exception as e:
            print(e)
            result = "Before sending a remote command you need to set-up an SSH connection."
        return result
