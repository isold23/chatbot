import json
import time
import threading
import os
import sys
sys.path.append(os.getcwd())
from common.log import logger
from common.singleton import SingletonC
from config import get_config
import requests
from flask import jsonify
import traceback


@SingletonC
class WxmpToken(object):
    def __init__(self, expire_time=None):
        self.timestamp = None
        self.token = None
        self.timeout = 600 if expire_time is None else expire_time
        self.is_running = True
        threading.Thread(target=self._auto_get_token).start()

    def get_token(self):
        return self.token

    def _auto_get_token(self):
        logger.info("starting get wx token, appid={} secret={}".format(get_config().appid, get_config().secret))
        while self.is_running:
            #初始化
            if self.timestamp is None or self.token is None:
                oldtoken = self.token
                self.token = self._get_access_token()
                self.timestamp = time.time()
                logger.info("get newtoken={} oldtoken={} time={}".format(self.token, oldtoken, self.timestamp))
                time.sleep(1.0/100)
                continue
            else:
                nowtime = time.time()
                timediff = nowtime - self.timestamp
                #过期了
                if (timediff > self.timeout):
                    tmp_token = self._get_access_token() 
                    #拿到相同的token了
                    if tmp_token == self.token:
                        logger.info("get same token, do nothing")
                        pass
                    else:
                        logger.info("get newtoken={} oldtoken={} time={}".format(tmp_token, self.token, self.timestamp))
                        self.token = tmp_token
                        self.timestamp = nowtime
            #1s检查一次
            time.sleep(1)

    # 获取access_token
    def _get_access_token(self):
        try:
            appid = get_config().appid
            secret = get_config().secret
            url = 'https://api.weixin.qq.com/cgi-bin/token'
            params = {
                'grant_type': 'client_credential',
                'appid': appid,
                'secret': secret
            }
            response = requests.get(url, params=params)
            access_token = json.loads(response.text)['access_token']
            return access_token
        except Exception as e:
            logger.info("_get_access_token error")
            return None

    def close(self):
        self.is_running = False

wxToken = WxmpToken()
def get_wxmp_token():
    while True:
        token = wxToken.get_token()
        if token:
            return token
        time.sleep(1)

def post_respons2wxmp(res=None, touser=None):
    if not(res and touser):
        return False
    access_token = get_wxmp_token()
    url='https://api.weixin.qq.com/cgi-bin/message/custom/send?access_token=' + access_token + "&charset=utf-8";
    body={
        "touser": touser, 
        "msgtype": "text", 
        "text": {
            "content": res
            }
    }
    headers = {'content-type': 'charset=utf8'}
    #text=requests.post(url=url, json=json.loads(json.dumps(res, ensure_ascii=False), encoding='utf-8'))
    res = requests.post(url=url, data=bytes(json.dumps(body, ensure_ascii=False), encoding='utf-8'))
    logger.info("post msg to wxmp, status={}".format(res)) 
    return True

def post_img_respons2wxmp(image_url=None, touser=None):
    if not(image_url and touser):
        return False
    access_token = get_wxmp_token()
    try:
        local_path = '/var/tmp/' + touser + '_' + str(int(time.time() * 1000)) + '.png'
        download_image(image_url, local_path)
        media_id = img_upload(local_path)
        delete_image(local_path)
    except Exception as e:
        logger.info('error processing image:'.format(e))
        return False

    url='https://api.weixin.qq.com/cgi-bin/message/custom/send?access_token=' + access_token
    body = {
        "touser": touser,
        "msgtype": "image",
        "image": {
            "media_id": media_id
        }
    }
    #headers = {'content-type': 'charset=utf8'}
    res = requests.post(url=url, data=bytes(json.dumps(body, ensure_ascii=False), encoding='utf-8'))
    logger.info("post img msg to wxmp, status={}".format(res)) 
    return True

def do_wechat_chat_completion(request_json, bot):
    #parameter constant
    logger.info("begin process request_json={}".format(request_json))

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

    context = dict()
    context['session_id'] = session_id
    context['type'] = request_json.get("MsgType", "TEXT").upper()
    context['type'] = "IMAGE" if query.startswith("画") else context['type']

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

def img_upload(local_path):
    access_token = get_wxmp_token()
    url = "https://api.weixin.qq.com/cgi-bin/media/upload?access_token=%s&type=%s" % (access_token, "image")
    files = {'media': open('{}'.format(local_path), 'rb')}
    res = requests.post(url, files=files)
    content = json.loads(res.content.decode())
    logger.info("upload image, res={}content={}".format(res, content))
    return content['media_id']

def download_image(img_url, local_path):
    with open(local_path, "wb") as f:
        f.write(requests.get(img_url).content)

def delete_image(local_path):
    if not local_path:
        return
    os.remove(local_path)

def get_welcome_words():
    return '''
嗨，你好！我是全世界最聪明的聊天机器人“机器知心”，接下来我会一直陪着你解答你的任何问题。
你可以问我一些简单的问题，比如：外星人真实存在吗？
或者，你可以跟我玩一些文字游戏，比如：“我希望你表现得像西游记中的唐三藏。我希望你像唐三藏一样回应和回答。不要写任何解释。必须以唐三藏的语气和知识范围为基础。我的第一句话是'你好'。”
你也可以向我提出画图的问题，只要以“画”开头提问就好了，比如：“画一只正在玩球的金毛”、“画一个写作业的小学生”。

我可以担任数学老师、小说家、编剧、说唱歌手、诗人、哲学家、画家、程序员、医生等多达5000个角色，只需要你能为我定制好角色的原型！
现在开始来愉快地玩耍吧~~
'''


if __name__ == '__main__':
    wxToken = WxmpToken()
    post_respons2wxmp(get_welcome_words(), "oiJo_5lGFN1xwiQtvFxT2W_7N6v8")
    #print (get_welcome_words())
