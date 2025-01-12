import json
import time
import threading
import os
import sys
sys.path.append(os.getcwd())
from common.log import logger
from common.singleton import SingletonC
from config import get_config
import traceback
from wxmp.wxmp_post2user import post_img_respons2wxmp, post_respons2wxmp

def process_wxmp_request(request_json, bot):
    #parameter constant
    logger.info("begin process request_json={}".format(request_json))
    can_process_type = ['text', 'event']
    if not request_json.get('MsgType', None) in can_process_type:
        logger.info("cannot process this msgtype")
        return

    #对关注请求特殊处理
    try:
        #关注
        if request_json["MsgType"] == "event" and request_json["Event"] == "subscribe":
            post_respons2wxmp(get_welcome_words(), request_json["FromUserName"])
            logger.info("handle subscribe event, return welcome words")
            return

        #取关
        if request_json["MsgType"] == "event" and request_json["Event"] == "unsubscribe":
            return
    except Exception as error:
        logger.info("handler subscribe/unsubscribe reqeust error")
        return

    session_id = request_json["FromUserName"]
    query = request_json["Content"]

    #标注请求类型，文字还是画图，有可能有更复杂的
    context = dict()
    context['session_id'] = session_id
    context['type'] = request_json.get("MsgType", "TEXT").upper()
    context['type'] = "IMAGE" if (query.startswith("画") or query.startswith("帮我画")) else context['type']

    response = None
    retry = 3
    while retry > 0:
        retry -= 1
        try:
            response = bot.reply(query, context)
            # 从响应中获取结果
        except Exception as error:
            logger.info("get openai err=".format(error))
            continue
        if response:
            break
    logger.info("end peocess request, ans:{}".format(response))
    toUserName = request_json["FromUserName"]
    #fromUserName = request_json["ToUserName"] 
    if not response:
        response = "发生未知错误，系统正在修复中，请稍后重试..."

    if context['type'] == "TEXT":
        post_respons2wxmp(response, toUserName)
        return
    if context['type'] == "IMAGE":
        post_img_respons2wxmp(response, toUserName)
        return
    

def get_welcome_words():
    return '''
嗨，你好！我是全世界最聪明的聊天机器人“机器知心”，接下来我会一直陪着你解答你的任何问题。
你可以问我一些简单的问题，比如：外星人真实存在吗？
或者，你可以跟我玩一些文字游戏，比如：“我希望你表现得像西游记中的唐三藏。我希望你像唐三藏一样回应和回答。不要写任何解释。必须以唐三藏的语气和知识范围为基础。我的第一句话是'你好'。”
你也可以向我提出画图的问题，只要以“画”开头提问就好了，比如：“画一只正在玩球的金毛”、“画一个写作业的小学生”。

我可以担任数学老师、小说家、编剧、说唱歌手、诗人、哲学家、画家、程序员、医生等多达5000个角色，只需要你能为我定制好角色的原型！
现在开始来愉快地玩耍吧~~
'''