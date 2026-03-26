import pexpect
from pydantic import BaseModel


class RunCode(BaseModel):
    """Class thực thi các lệnh shell và xử lý output.

    Class này kế thừa từ BaseModel của Pydantic và cung cấp các phương thức
    để thực thi một chuỗi các lệnh shell, xử lý output và timeout.

    Attributes:
        timeout (int): Thời gian chờ tối đa (giây) cho mỗi lệnh, mặc định là 60s
        commands (list): Danh sách các lệnh shell cần thực thi
    """

    timeout: int = 60
    commands: list

    def execute_cmd(self):
        """Thực thi tuần tự các lệnh shell trong danh sách commands.

        Phương thức này thực thi từng lệnh trong danh sách commands, xử lý output
        và quản lý process giữa các lệnh. Nó có thể:
        - Thực thi lệnh mới với timeout
        - Gửi lệnh tới process đang chạy
        - Thu thập output từ các lệnh

        Returns:
            str: Output tổng hợp từ tất cả các lệnh đã thực thi, đã được strip()
        """
        output = ""
        process = None

        for i, command in enumerate(self.commands):
            # output += f'Command: {command.strip()}\n'
            if process is None:
                result = self.run_cmd_with_timeout(command)
            else:
                process.sendline(command.strip())

                try:
                    process.expect(pexpect.EOF, timeout=self.timeout)
                    output += f"Response : {process.before.decode()}\n"

                except pexpect.exceptions.TIMEOUT:
                    if i == len(self.commands) - 1:
                        output += f"Response : {process.before.decode()}\n"
                result = process

            if isinstance(result, str):
                output += result
                process = None
            elif isinstance(result, pexpect.spawn):
                process = result

        return output.strip()

    def run_cmd_with_timeout(self, command: str):
        """Thực thi một lệnh shell đơn lẻ với timeout.

        Phương thức này tạo một process mới để thực thi lệnh shell và xử lý các
        trường hợp timeout hoặc lỗi.

        Args:
            command (str): Lệnh shell cần thực thi

        Returns:
            Union[str, pexpect.spawn]: 
                - Nếu lệnh hoàn thành: trả về output dạng string
                - Nếu timeout: trả về process đang chạy
                - Nếu có lỗi: trả về thông báo lỗi dạng string
        """
        cmd = command.strip()
        output = ""
        try:
            process = pexpect.spawn(cmd, timeout=self.timeout)
            try:
                process.expect(pexpect.EOF, timeout=self.timeout)
                output += f"Response: {process.before.decode()}\n"
                return output
            except pexpect.exceptions.TIMEOUT:
                return process

        except Exception as e:
            return f"Exception occurred: {str(e)}"
