import socket
from performance_app import create_app


def get_local_ip():
    """自动获取本机局域网 IP 地址"""
    try:
        # 创建一个 UDP socket，连接到一个公网地址（不会实际发送数据）
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
        return local_ip
    except Exception:
        # 失败时回退到 localhost
        return "127.0.0.1"


app = create_app()

if __name__ == "__main__":
    host = get_local_ip()
    print(f" * Starting server on {host}:5000")
    app.run(debug=True, host=host)
