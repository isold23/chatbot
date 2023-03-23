import argparse
from common.log import logger
from common import const
from flask import Flask, request, jsonify
import openai
import os
from config import get_config
from bot.bot_factory import create_bot


class ChatServer:

    def __init__(self, config_parser):
        logger.info("Chat server is init...")
        self._app = Flask(__name__)
        self._debug_mode = config_parser.debug_mode
        self._ip_addr = config_parser.ip_addr
        self._port = config_parser.port
        self._bot = create_bot(const.CHATGPT, config_parser)

        def debug_request(req):
            print("----- get headers:")
            print(req.headers)
            print("----- get body")
            print(req.data)
            print("----- get form:")
            print(req.form)
            print("----- get json:")
            print(request.get_json())

        @self._app.route("/openai/text-completion", methods=["POST"])
        def text_completion():
            if self._debug_mode:
                debug_request(request)

            #parameter constant
            PROMPT = "prompt"

            request_json = request.get_json()
            if len(request_json) == 0:
                return jsonify({"code": 301, "msg": "empty request"})
            if PROMPT not in request_json:
                return jsonify({"code": 301, "msg": "empty prompt"})

            prompt = request_json[PROMPT]

            if len(prompt) == 0:
                return jsonify({"code": 301, "msg": "empty prompt"})

            response = None
            result = ""
            try:
                # 调用 OpenAI API
                response = openai.Completion.create(
                    engine="text-davinci-003",
                    prompt=prompt,
                    max_tokens=1024,
                    n=1,
                    stop=None,
                    temperature=0.2,
                )
                # 从响应中获取结果
                result = response.choices[0].text.strip()
            except Exception:
                if self._debug_mode:
                    print(response)
                return jsonify({"code": 302, "msg": "internal error"})

            return jsonify({"code": 200, "msg": "success", "data": result})

        @self._app.route("/openai/chat-completion", methods=["POST"])
        def chat_completion():
            if self._debug_mode:
                debug_request(request)

            #parameter constant
            CHAT_HISTORY = "chat_history"

            request_json = request.get_json()
            if len(request_json) == 0:
                return jsonify({"code": 301, "msg": "empty request"})
            if CHAT_HISTORY not in request_json:
                return jsonify({"code": 301, "msg": "empty chat history"})
            chat_history = request_json[CHAT_HISTORY]

            response = None
            result = ""
            try:
                # 调用 OpenAI API
                response = openai.ChatCompletion.create(model="gpt-3.5-turbo",
                                                        messages=chat_history,
                                                        temperature=0.2,
                                                        max_tokens=1024,
                                                        top_p=1,
                                                        frequency_penalty=0,
                                                        presence_penalty=0,
                                                        stop=None)
                # 从响应中获取结果
                result = response.choices[0].message.content
            except Exception:
                if self._debug_mode:
                    print(response)
                return jsonify({"code": 302, "msg": "internal error"})

            # 返回结果到客户端
            return jsonify({"code": 200, "msg": "success", "data": result})

        @self._app.route("/openai/session/chat-completion", methods=["POST"])
        def session_chat_completion():
            if self._debug_mode:
                debug_request(request)

            #parameter constant
            QUERY = "query"
            DEVICE_ID = "device_id"

            request_json = request.get_json()
            if len(request_json) == 0:
                return jsonify({"code": 301, "msg": "empty request"})
            if QUERY not in request_json or not isinstance(
                    request_json[QUERY], str):
                return jsonify({"code": 301, "msg": "empty query"})
            if DEVICE_ID not in request_json or not isinstance(
                    request_json[DEVICE_ID], str):
                return jsonify({"code": 301, "msg": "empty device_id"})

            query = request_json[QUERY]
            device_id = request_json[DEVICE_ID]

            context = dict()
            context['device_id'] = device_id

            response = None
            result = ""
            try:
                response = self._bot.reply(query, context)
                # 从响应中获取结果
                result = response.choices[0].message.content
            except Exception:
                if self._debug_mode:
                    print(response)
                return jsonify({"code": 302, "msg": "internal error"})

            # 返回结果到客户端
            return jsonify({"code": 200, "msg": "success", "data": result})

    def run(self):
        self._app.run(host=self._ip_addr,
                      port=self._port,
                      debug=self._debug_mode)


# 启动 Flask 应用程序
if __name__ == "__main__":
    ChatServer(get_config()).run()
