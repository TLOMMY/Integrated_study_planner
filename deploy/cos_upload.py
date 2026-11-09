#!/usr/bin/env python3
"""
把备份文件上传到腾讯云 COS（异地备份）。由 backup.sh 在每日备份后调用，install.sh 安装为
/usr/local/bin/xueyeguanjia-cos-upload。只用标准库，系统自带的 python3 就能运行。

  xueyeguanjia-cos-upload [--env /etc/xueyeguanjia/backend.env] 文件...

配置从 backend.env 读取（同名环境变量优先）：COS_SECRET_ID、COS_SECRET_KEY、COS_REGION、COS_BUCKET，
可选 COS_BACKUP_PREFIX（默认 backup/）。没配置时打印提示并以 0 退出，不影响本地备份。
签名算法见腾讯云文档「请求签名」（q-sign-algorithm=sha1）。
"""

import argparse
import base64
import hashlib
import hmac
import http.client
import os
import sys
import time
from urllib.parse import quote

KEYS = ("COS_SECRET_ID", "COS_SECRET_KEY", "COS_REGION", "COS_BUCKET", "COS_BACKUP_PREFIX")
SIGN_SECONDS = 600
TIMEOUT = 120


def read_env(path):
    """读 KEY=VALUE 格式的 env 文件；同名环境变量优先。"""
    values = {}
    if path and os.path.isfile(path):
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key, value = key.strip(), value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                    value = value[1:-1]
                if key in KEYS:
                    values[key] = value
    for key in KEYS:
        if os.environ.get(key):
            values[key] = os.environ[key]
    return values


def _encode(value):
    return quote(str(value), safe="-_.~")


def _hmac_sha1(key, message):
    return hmac.new(key.encode("utf-8"), message.encode("utf-8"), hashlib.sha1).hexdigest()


def sign(secret_id, secret_key, method, path, headers, now=None):
    """生成 Authorization 头。headers 里的每一项都参与签名。"""
    start = int(now if now is not None else time.time()) - 60
    key_time = f"{start};{start + SIGN_SECONDS}"
    items = sorted((_encode(k.lower()), _encode(v)) for k, v in headers.items())
    header_list = ";".join(k for k, _ in items)
    header_string = "&".join(f"{k}={v}" for k, v in items)
    http_string = f"{method.lower()}\n{path}\n\n{header_string}\n"
    string_to_sign = f"sha1\n{key_time}\n{hashlib.sha1(http_string.encode('utf-8')).hexdigest()}\n"
    signature = _hmac_sha1(_hmac_sha1(secret_key, key_time), string_to_sign)
    return (f"q-sign-algorithm=sha1&q-ak={secret_id}&q-sign-time={key_time}&q-key-time={key_time}"
            f"&q-header-list={header_list}&q-url-param-list=&q-signature={signature}")


def upload(config, file_path, connection=None):
    """上传一个文件，返回对象键；失败抛 RuntimeError。connection 只在测试时传入。"""
    with open(file_path, "rb") as handle:
        data = handle.read()
    prefix = config.get("COS_BACKUP_PREFIX", "backup/").strip("/")
    key = f"{prefix}/{os.path.basename(file_path)}" if prefix else os.path.basename(file_path)
    path = "/" + key
    host = f"{config['COS_BUCKET']}.cos.{config['COS_REGION']}.myqcloud.com"
    headers = {
        "Host": host,
        "Content-Length": str(len(data)),
        # COS 收到后校验 MD5，传输中损坏会直接拒收
        "Content-MD5": base64.b64encode(hashlib.md5(data).digest()).decode("ascii"),
        "Content-Type": "application/octet-stream",
    }
    headers["Authorization"] = sign(config["COS_SECRET_ID"], config["COS_SECRET_KEY"], "PUT", path, headers)
    conn = connection or http.client.HTTPSConnection(host, timeout=TIMEOUT)
    try:
        conn.request("PUT", quote(path, safe="/-_.~"), body=data, headers=headers)
        response = conn.getresponse()
        body = response.read()[:500].decode("utf-8", "replace")
    except OSError as error:
        raise RuntimeError(f"连接 COS 失败：{error}") from None
    finally:
        conn.close()
    if not 200 <= response.status < 300:
        raise RuntimeError(f"COS 返回 {response.status}：{body}")
    return key


def main(argv=None):
    parser = argparse.ArgumentParser(description="上传备份文件到腾讯云 COS")
    parser.add_argument("--env", default="/etc/xueyeguanjia/backend.env", help="backend.env 路径")
    parser.add_argument("files", nargs="+")
    args = parser.parse_args(argv)

    config = read_env(args.env)
    missing = [k for k in KEYS[:4] if not config.get(k)]
    if missing:
        print(f"未配置 COS（缺少 {', '.join(missing)}），跳过异地备份")
        return 0
    failed = False
    for file_path in args.files:
        try:
            key = upload(config, file_path)
            print(f"已上传到 COS：{config['COS_BUCKET']}/{key}")
        except (RuntimeError, OSError) as error:
            failed = True
            print(f"上传 {os.path.basename(file_path)} 失败：{error}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
