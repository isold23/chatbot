import argparse
from common.log import logger
from common import const
from flask import Flask, request, jsonify
import openai
import os
from config import get_config
from bot.bot_factory import create_bot
import xmltodict
from wxmp.wxmp_main import process_wxmp_request
import threading
import traceback
import requests
import json

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
                
            request_json = request.get_json()
            if len(request_json) == 0:
                return jsonify({"code": 301, "msg": "empty request"})
            if "query" not in request_json or not isinstance(request_json["query"], str):
                return jsonify({"code": 301, "msg": "empty query"})
            if "session_id" not in request_json or not isinstance(request_json["session_id"], str):
                return jsonify({"code": 301, "msg": "empty session id"})

            try:
                #构建请求chatgpt的query
                query = request_json["query"]
                session_id = request_json["session_id"]
                msgtype = request_json.get('msgtype', "text").upper()
                msgtype = "IMAGE_RAW" if query.startswith(("画","draw","Draw","帮我画")) else msgtype

                context = dict()
                context['session_id'] = session_id
                context['type'] = msgtype

                #请求chatgpt 
                response = self._bot.reply(query, context)
                # 返回结果到客户端
                return jsonify({"code": 200, "msg": "success", "data": response, "msgtype": msgtype})
            except Exception:
                traceback.print_exc()
                return jsonify({"code": 302, "msg": "internal error"})
        
        @self._app.route("/openai/session/chat-completion-v2", methods=["POST"])
        def session_chat_completion_v2():
            if self._debug_mode:
                debug_request(request)

            request_json = request.get_json()
            if len(request_json) == 0:
                return jsonify({"code": 301, "msg": "empty request"})
            if "query" not in request_json or not isinstance(request_json["query"], str):
                return jsonify({"code": 301, "msg": "empty query"})
            if "session_id" not in request_json or not isinstance(request_json["session_id"], str):
                return jsonify({"code": 301, "msg": "empty session id"})

            try:
                #构建请求chatgpt的query
                query = request_json["query"]
                session_id = request_json["session_id"]
                msgtype = request_json.get('msgtype', "text").upper()
                response = None
                if msgtype == "IMAGE_SD" :
                    height = request_json["height"]
                    width = request_json["width"]
                    steps = request_json["steps"]
                    #请求Stable Diffusion
                    response = request_sd_image(query, height, width, steps)
                else :
                    msgtype = "IMAGE_RAW" if query.startswith(("画","draw","Draw","帮我画")) else msgtype

                    context = dict()
                    context['session_id'] = session_id
                    context['type'] = msgtype

                    #请求chatgpt
                    response = self._bot.reply(query, context)

                # 返回结果到客户端
                return jsonify({"code": 200, "msg": "success", "data": response, "msgtype": msgtype})
            except Exception:
                traceback.print_exc()
                return jsonify({"code": 302, "msg": "internal error"})

        @self._app.route("/openai/session/wechat/chat-completion", methods=["GET"])
        def do_wechat_check():
            logger.info("echostr +++ {}".format(request.args.get("echostr")))
            #return jsonify({"code": 200, "msg": "success", "data": request.args.get("echostr")})
            return request.args.get("echostr"), 200

        @self._app.route("/openai/session/wechat/chat-completion", methods=["POST"])
        def session_wechat_chat_completion():
            if self._debug_mode:
                debug_request(request)

            request_json = xmltodict.parse(request.data)['xml']
            threading.Thread(target=process_wxmp_request, args=(request_json, self._bot)).start()
            return "success", 200
        
        def request_sd_image(prompt, height, width, steps):
            url = "http://106.75.25.171:8989/sdapi/v1/txt2img"
            body = {
                "prompt": prompt,
                "negativePrompt": " (worst quality, low quality:1.4), EasyNegative, multiple views, multiple panels, blurry, watermark, letterbox, text, (nsfw, See-through:1.1),(extra fingers), (extra hands),(mutated hands and finger), (ugly eyes:1.2),mutated hands, (fused fingers), (too many fingers), (((long neck))),naked,nsfw,",
                "height": height,
                "width": width,
                "steps": steps,
                "samplerName": "DPM++ 2M Karras",
                "sdModelCheckpoint": "camelliamix_25d_v10.safetensors"
            }

            res = requests.post(url=url, data=json.dumps(body), headers={'content-type':'application/json'})
            return res.json()['images'][0]


    def run(self):
        self._app.run(host=self._ip_addr,
                      port=self._port,
                      debug=self._debug_mode)

    def __call__(self, environ, start_response):
        return self._app(environ, start_response)


# 启动 Flask 应用程序
if __name__ == "__main__":
    ChatServer(get_config()).run()
