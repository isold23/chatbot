import json
import time
import threading
import sys
#sys.path.append("./")
from urllib import parse, request
from config import get_config
from common.log import logger
from common.singleton import SingletonC
import requests
import xmltodict
from flask import jsonify

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
                self.token = self._get_wxCode_token()
                self.timestamp = time.time()
                logger.info("get newtoken={} oldtoken={} time={}".format(self.token, oldtoken, self.timestamp))
                time.sleep(1.0/100)
                continue
            else:
                nowtime = time.time()
                timediff = nowtime - self.timestamp
                #过期了
                if (timediff > self.timeout):
                    tmp_token = self._get_wxCode_token() 
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

    def _get_wxCode_token(self):
        try:
            appid = get_config().appid
            secret = get_config().secret
            textmod = {"grant_type": "client_credential",
                "appid": appid,
                "secret": secret
            }
            textmod = parse.urlencode(textmod)
            header_dict = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Trident/7.0; rv:11.0) like Gecko'}
            url = 'https://api.weixin.qq.com/cgi-bin/token'
            req = request.Request(url='%s%s%s' % (url, '?', textmod), headers=header_dict)
            res = request.urlopen(req)
            res = res.read().decode(encoding='utf-8')
            res = json.loads(res)
            access_token = res["access_token"]
            print('res:', res)
            print('access_token:', access_token)
            return access_token
        except Exception as e:
            print('error:', e)
            return None
        
    def close(self):
        self.is_running = False

wxToken = WxmpToken()
def get_wxmp_token():
    return wxToken.get_token()


def post_respons2wxmp(res=None, touser=None):
    if not(res and touser):
        return False
    retry = 10
    while(get_wxmp_token() is None and retry > 0):
        time.sleep(1)
        retry -= 1

    url='https://api.weixin.qq.com/cgi-bin/message/custom/send?access_token=' + get_wxmp_token() + "&charset=utf-8";
    body={
        "touser": touser, 
        "msgtype": "text", 
        "text": {
            "content": res
            }
    }
    headers = {'content-type': 'charset=utf8'}
    #text=requests.post(url=url, json=json.loads(json.dumps(res, ensure_ascii=False), encoding='utf-8'))
    text=requests.post(url=url, data=bytes(json.dumps(body, ensure_ascii=False), encoding='utf-8'))
    logger.info("post msg to wxmp, status={}".format(text)) 
    return True

def post_img_respons2wxmp(res=None, touser=None):
    if not(res and touser):
        return False
    retry = 10
    while(get_wxmp_token() is None and retry > 0):
        time.sleep(1)
        retry -= 1
    media_id = Upload_Media_Img(res)

    url='https://api.weixin.qq.com/cgi-bin/message/custom/send?access_token=' + get_wxmp_token() + "&charset=utf-8";
    body={
        "touser": touser, 
        "msgtype": "image", 
        "text": {
            "content": res
            }
    }
    headers = {'content-type': 'charset=utf8'}
    #text=requests.post(url=url, json=json.loads(json.dumps(res, ensure_ascii=False), encoding='utf-8'))
    text=requests.post(url=url, data=bytes(json.dumps(body, ensure_ascii=False), encoding='utf-8'))
    logger.info("post msg to wxmp, status={}".format(text)) 
    return True

def do_wechat_chat_completion(request_json, bot):
    #parameter constant
    logger.info("begin process request_json={}".format(request_json))

    if request_json["MsgType"] == "event":
        logger.info("handle subscribe event, return")
        return ""
    session_id = request_json["FromUserName"]
    query = request_json["Content"]

    context = dict()
    context['session_id'] = session_id
    context['type'] = request_json.get("MsgType", "TEXT").upper()

    response = None
    result = ""
    retry = 3
    while retry > 0:
        retry -= 1
        try:
            response = bot.reply(query, context)
            # 从响应中获取结果
            result = response
        except Exception as error:
            logger.info("get openai err=".format(error))
            continue
        if result:
            break
    logger.info("end peocess request, ans:{}".format(result))
    toUserName = request_json["FromUserName"]
    fromUserName = request_json["ToUserName"] 
    if not result:
        result = "发生未知错误，系统正在修复中，请稍后重试..."

    if context['type'] == "TEXT":
        post_respons2wxmp(result, toUserName)
        return
    if context['type'] == "IMAGE":
        post_img_respons2wxmp(result, toUserName)
        return

def Upload_Media_Img(image_content):
    access_token = get_wxmp_token()
    url = "https://api.weixin.qq.com/cgi-bin/material/add_material?access_token=" + access_token +"&type=image"
    # 上传文件
    params = {"access_token": access_token,
              "type":"image"}
    #test.jpg为本地要上传的素材
    res = requests.post(url, files=image_content)
    res = json.loads(str(res.content, 'utf8'))
    logger.info("upload image res={}", res)
    media_id = res["media_id"]
    
    #返回素材ID
    return media_id

if __name__ == '__main__':
    post_respons2wxmp("test中文", "oiJo_5lGFN1xwiQtvFxT2W_7N6v8")
