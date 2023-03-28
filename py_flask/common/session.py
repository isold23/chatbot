# encoding:utf-8

from bot.bot import Bot
from common.log import logger
from common.token_bucket import TokenBucket
from common.expired_dict import ExpiredDict
from common.wxmp_request_limiter import WxmpRequestLimiter
import openai
import time

class Session(object):
    def __init__(self, config_parser):
        logger.info("Session init...")
        self._all_sessions = dict()
        if config_parser.expires_in_seconds > 0:
            self._all_sessions = ExpiredDict(config_parser.expires_in_seconds)
        self._max_tokens = config_parser.conversation_max_tokens
        if self._max_tokens <= 0:
            self._max_tokens = 1024
        self._character_desc = config_parser.character_desc
        self.wxmp_request_limiter = WxmpRequestLimiter()

    def build_session_query(self, query, session_id, msgtype="text"):
        '''
        build query with conversation history
        e.g.  [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Who won the world series in 2020?", "timestamp": 1679971605, "type": "text/image"},
            {"role": "assistant", "content": "The Los Angeles Dodgers won the World Series in 2020."},
            {"role": "user", "content": "Where was it played?"}
        ]
        :param query: query content
        :param session_id: session id
        :return: query content with conversaction
        '''
        session = self._all_sessions.get(session_id, [])
        is_limited = self.wxmp_request_limiter.do_limit(session_id, session)
        if is_limited: #没有限额了
            return None

        if len(session) == 0:
            system_prompt = self._character_desc
            system_item = {'role': 'system', 'content': system_prompt}
            session.append(system_item)
            self._all_sessions[session_id] = session
        user_item = {'role': 'user', 'content': query, "timestamp": int(time.time()), "type": msgtype}
        session.append(user_item)
        return session

    def save_session(self, answer, session_id, total_tokens):
        session = self._all_sessions.get(session_id)
        if session:
            # append conversation
            gpt_item = {'role': 'assistant', 'content': answer}
            session.append(gpt_item)

        # discard exceed limit conversation
        self.discard_exceed_conversation(session, self._max_tokens,
                                         total_tokens)

    def discard_exceed_conversation(self, session, max_tokens, total_tokens):
        dec_tokens = int(total_tokens)
        logger.debug("prompt tokens used={},max_tokens={}".format(dec_tokens,max_tokens))
        while dec_tokens > max_tokens:
            # pop first conversation
            if len(session) > 3:
                session.pop(1)
                session.pop(1)
            else:
                break
            dec_tokens = dec_tokens - max_tokens

    def clear_session(self, session_id):
        self._all_sessions[session_id] = []

    def clear_all_session(self):
        self._all_sessions.clear()