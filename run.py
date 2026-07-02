import socket
from performance_app import create_app


def get_local_ip():
    """自动获取本机局域网 IP 地址，优先获取以太网 IP"""
    try:
        # 方法1：尝试获取 10.x.x.x 网段的 IP（以太网）
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # 不实际发送数据，只获取本地地址
            s.settimeout(0)
            try:
                # 尝试连接到本地网关
                s.connect(("10.12.133.97", 80))
                local_ip = s.getsockname()[0]
                if local_ip.startswith("10."):
                    return local_ip
            except:
                pass

        # 方法2：回退到连接外网获取IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            # 如果不是 10.x.x.x 网段，继续尝试其他方法
            if local_ip.startswith("10."):
                return local_ip
    except Exception:
        pass

    # 方法3：遍历所有网络接口
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        if local_ip.startswith("10."):
            return local_ip
    except Exception:
        pass

    # 最后回退到 localhost
    return "127.0.0.1"


app = create_app()

if __name__ == "__main__":
    host = get_local_ip()
    print(f" * Starting server on {host}:5000")
    app.run(debug=True, host=host)
