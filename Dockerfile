# Sử dụng image Kali Linux mới nhất làm nền tảng
FROM kalilinux/kali-rolling

# Đặt thư mục làm việc mặc định trong container
WORKDIR /root

# Sao chép file sources.list tùy chỉnh vào trong image để đảm bảo dùng mirror ổn định
COPY sources.list /etc/apt/sources.list

# Thiết lập biến môi trường để apt không hỏi các câu hỏi tương tác
ENV DEBIAN_FRONTEND=noninteractive

# Cập nhật và cài đặt các phụ thuộc hệ thống cần thiết
# Gộp các lệnh cài đặt để tối ưu hóa kích thước image
RUN apt-get update && \
    apt-get install -y \
    openssh-server \
    python3 \
    python3-pip \
    python3-venv \
    pipx \
    build-essential \
    libssl-dev \
    libffi-dev \
    curl \
    wget \
    git \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Tạo các thư mục cần thiết cho tmpfs mounts
RUN mkdir -p /root/.local /root/.cache /root/.local/bin /root/.local/lib /root/.local/share

# Cấu hình SSH
RUN echo 'root:root' | chpasswd && \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config

# Lệnh sẽ chạy khi container khởi động
CMD service ssh start && tail -f /dev/null