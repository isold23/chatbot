# encoding:utf-8

import json
import os
from common.log import logger
import argparse

# constant definition
OPENAI_API_KEY = "OPENAI_API_KEY"


def load_config():
    global config
    config_path = "./config.json"
    if not os.path.exists(config_path):
        raise Exception('配置文件不存在，请根据config-template.json模板创建config.json文件')

    config_str = read_file(config_path)
    # 将json字符串反序列化为dict类型
    config = json.loads(config_str)
    logger.info("[INIT] load config: {}".format(config))


def get_root():
    return os.path.dirname(os.path.abspath(__file__))


def read_file(path):
    with open(path, mode='r', encoding='utf-8') as f:
        return f.read()


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug",
                        "-d",
                        type=bool,
                        default=False,
                        required=False,
                        help="Whether enable debug mode.")
    parser.add_argument("--ip_addr",
                        "-a",
                        type=str,
                        default="127.0.0.1",
                        required=False,
                        help="Web server listen address.")
    parser.add_argument("--port",
                        "-p",
                        type=int,
                        default=9081,
                        required=False,
                        help="Web server listen port.")
    parser.add_argument("--config_file",
                        "-c",
                        type=str,
                        required=False,
                        help='Config file path.')
    args = parser.parse_args()
    return args


def get_args_from_env():
    env_args = {}
    env_args[OPENAI_API_KEY] = os.getenv('OPENAI_API_KEY')
    # module_name = os.getenv('LIST_VARS').split(";")[0]
    return env_args


class ConfigParser:

    def __init__(self):
        self._args = get_args()
        self._env_args = get_args_from_env()
        self.debug_mode = self._args.debug
        self.ip_addr = self._args.ip_addr
        self.port = self._args.port
        self.api_key = self._env_args.get(OPENAI_API_KEY)
        self.expires_in_seconds = 3600
        self.rate_limit_chatgpt = 60
        self.clear_memory_commands = "xjieoajgojksakgaj"
        self.clear_all_memory_commands = "ajiojgwijjsag"
        self.conversation_max_tokens = 1024
        self.character_desc = ""


config = ConfigParser()


def get_config():
    return config