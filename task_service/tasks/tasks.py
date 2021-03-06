#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Created by Charles on 19-3-15
# Function: 相关任务响应函数


"""
所有任务响应函数入口在此定义
"""

import time
import datetime
import random
import subprocess
import re
from celery import Task
from start_worker import app
from config import logger
from executor.facebook.mobile_actions import FacebookMobileActions
from executor.facebook.pc_actions import FacebookPCActions
from executor.facebook.exception import FacebookExceptionProcessor
from tasks.task_help import TaskHelper


class BaseTask(Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error('celery task on_failed, task_id={}, args={}, kwargs={}, exception={}, exception info={}. '
                     .format(task_id, args, kwargs, exc, einfo))

    def on_success(self, retval, task_id, args, kwargs):
        logger.info('celery task on_success, task_id={}, retval={}. '.format(task_id, retval))


# 处理beat的定时任务, 暂不用
# @app.task(ignore_result=True)
# def execute_fb_auto_feed():
#     inputs = {}
#     app.send_task('tasks.tasks.fb_auto_feed', args=(inputs,),
#                   queue='feed_account', routing_key='for_feed_account')


@app.task(base=BaseTask, bind=True, max_retries=1, time_limit=1200)
def fb_auto_feed(self, inputs):
    logger.info('----------fb_auto_feed task running, inputs=\r\n{}'.format(inputs))
    try:
        last_login = None
        last_chat = None
        last_post = None
        last_add_friend = None
        cookies = None
        fb_actions = None
        tsk_hlp = TaskHelper(inputs)

        if not tsk_hlp.is_inputs_valid():
            logger.error('inputs not valid, inputs={}'.format(inputs))
            return tsk_hlp.make_result(err_msg='inputs invalid.')

        if not tsk_hlp.is_should_login():
            logger.warning('is_should_login return False, task id={}, account={}'.format(tsk_hlp.task_id, tsk_hlp.account))
            return tsk_hlp.make_result(err_msg='is_should_login return False')

        if tsk_hlp.is_in_verifying():
            logger.warning('is_in_verifying return True, task id={}, account={}'.format(tsk_hlp.task_id, tsk_hlp.account))
            return tsk_hlp.make_result(err_msg='is_in_verifying return True')

        # 根据账号携带的finger_print 信息来决定启动pc或者mobile
        if tsk_hlp.active_browser.get("device", ""):
            chrome_env = "mobile"
            fb_actions = FacebookMobileActions(account_info=tsk_hlp.account_info,
                                                finger_print=tsk_hlp.active_browser,
                                                headless=tsk_hlp.headless)
        else:
            chrome_env = "pc"
            fb_actions = FacebookPCActions(account_info=tsk_hlp.account_info,
                                                finger_print=tsk_hlp.active_browser,
                                                headless=tsk_hlp.headless)


        # 分步执行任务
        # 启动浏览器
        ret = fb_actions.start_chrome()
        if not ret:
            logger.error('start chrome failed.')
            return tsk_hlp.make_result()

        fb_exp = FacebookExceptionProcessor(fb_actions.driver, env=chrome_env, account=fb_actions.account,
                                            gender=fb_actions.gender)
        fb_actions.set_exception_processor(fb_exp)
        account = tsk_hlp.account
        password = tsk_hlp.password
        ret, err_code = fb_actions.login()
        if not ret:
            msg = 'login failed, account={}, password={}, err_code={}'.format(account, password, err_code)
            logger.error(msg)
            tsk_hlp.screenshots(fb_actions.driver, err_code=err_code)
            return tsk_hlp.make_result(err_code=err_code, err_msg=msg)

        last_login = datetime.datetime.now()
        cookies = fb_actions.get_cookies()
        logger.info('login succeed. account={}, password={}, cookies={}'.format(account, password, cookies))

        ret, err_code = fb_actions.browse_home()
        if not ret:
            msg = 'home_browsing, account={}, err_code={}'.format(account, err_code)
            logger.error(msg)
            tsk_hlp.screenshots(fb_actions.driver, err_code=err_code)
            return tsk_hlp.make_result(err_code=err_code, err_msg=msg, last_login=last_login, cookies=cookies)

        tsk_hlp.random_sleep()
        # if tsk_hlp.random_select():
        ret, err_code = fb_actions.browse_user_center(limit=random.randint(2, 5))
        if not ret:
            err_msg = 'user_home failed, err_code={}'.format(err_code)
            tsk_hlp.screenshots(fb_actions.driver, err_code=err_code)
            return tsk_hlp.make_result(err_code=err_code, err_msg=err_msg, last_login=last_login, cookies=cookies)

        # 账号是否可以继续用作其他用途
        if not tsk_hlp.is_should_use():
            logger.info("account can not be used!! login counts={}".format(tsk_hlp.login_counts))
            return tsk_hlp.make_result(True, last_login=last_login, cookies=cookies)

        tsk_hlp.random_sleep()
        if tsk_hlp.is_should_add_friend():
            fks = tsk_hlp.get_friend_keys(1)
            if fks:
                ret, err_code = fb_actions.add_friends(search_keys=fks, limit=random.randint(1, 3))
                if not ret:
                    err_msg = 'add_friends failed, err_code={}'.format(err_code)
                    tsk_hlp.screenshots(fb_actions.driver, err_code=err_code)
                    return tsk_hlp.make_result(err_code=err_code, err_msg=err_msg, last_login=last_login, cookies=cookies)
                last_add_friend = datetime.datetime.now()

        tsk_hlp.random_sleep()
        msgs = tsk_hlp.get_chat_msgs()
        if msgs:
            ret, err_code = fb_actions.chat(contents=msgs, friends=random.randint(1, 3))
            if not ret:
                msg = "send_message failed, err_code={}".format(err_code)
                tsk_hlp.screenshots(fb_actions.driver, err_code=msg)
                return tsk_hlp.make_result(err_code=err_code, err_msg=msg, last_login=last_login, cookies=cookies)

            last_chat = datetime.datetime.now()

        tsk_hlp.random_sleep()
        if tsk_hlp.is_should_post():
            send_state = tsk_hlp.get_posts()
            if send_state and send_state.get('post', ''):
                ret, err_code = fb_actions.post_status(contents=send_state)
                if not ret:
                    msg = "send_facebook_state failed, err_code={}".format(err_code)
                    tsk_hlp.screenshots(fb_actions.driver, err_code=err_code)
                    return tsk_hlp.make_result(err_code=err_code, err_msg=msg, last_login=last_login, cookies=cookies)
                last_post = datetime.datetime.now()

        tsk_hlp.random_sleep(20, 100)
        logger.info('-----task fb_auto_feed succeed. account={}'.format(account))
    except Exception as e:
        err_msg = 'fb_auto_feed catch exception. e={}'.format(str(e))
        logger.exception(err_msg)
        # self.retry(countdown=10 ** self.request.retries)
        return tsk_hlp.make_result(err_msg=err_msg)
    finally:
        if fb_actions:
            fb_actions.quit()
    return tsk_hlp.make_result(True, last_login=last_login, last_chat=last_chat,
                               last_post=last_post, last_add_friend=last_add_friend, cookies=cookies)


@app.task(base=BaseTask, bind=True, max_retries=3, time_limit=300)
def switch_vps_ip(self, inputs):
    logger.info('--------switch_vps_ip')
    try:
        tsk_hlp = TaskHelper(inputs)

        subprocess.call("pppoe-stop", shell=True)
        time.sleep(3)
        subprocess.call('pppoe-start', shell=True)
        time.sleep(3)
        pppoe_restart = subprocess.Popen('pppoe-status', shell=True, stdout=subprocess.PIPE, encoding='utf-8')

        pppoe_restart.wait(timeout=5)
        pppoe_log = str(pppoe_restart.communicate()[0])
        adsl_ip = re.findall(r'inet (.+?) peer ', pppoe_log)[0]
        logger.info('switch_vps_ip succeed. new ip address : {}'.format(adsl_ip))
    except Exception as e:
        err_msg = 'switch_vps_ip catch exception={}'.format(str(e))
        logger.exception(err_msg)
        return tsk_hlp.make_result(err_msg=err_msg)

    logger.info('')
    return tsk_hlp.make_result(ret=True)


@app.task(base=BaseTask, bind=True, max_retries=1, time_limit=300)
def fb_click_farming(self, inputs):
    logger.info('fb_click_farming task running')
    tsk_hlp = TaskHelper(inputs)
    # time.sleep(3)
    # 更新任务状态为running
    # self.update_state(state="running")

    # do something here
    time.sleep(70)

    a = random.randint(1, 100)
    if a % 3 == 2:
        return {'status': 'failed', 'err_msg': 'click farming 3-2 failed'}

    if a % 3 == 1:
        logger.exception('fb_auto_feed')
        a = a/0

    return tsk_hlp.make_result(ret=True)


# from celery import chain, signature
# r = chain(fb_auto_feed.s({}), fb_click_farming.s({}))
# r.apply_async()

