#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Created by Charles on 19-3-15
# Function: 养号任务入口

import time
import random
from .workers import app
import scripts
from celery import Task
from config import logger
from scripts import mobile_auto_feed


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

TaskResult = {
    'status': 'failed',        # 'failed', 'succeed'
    'err_msg': '',
    'account_status': '',  # valid, invalid, verifying
    'account_configure': {}         # {
    #     'last_post': '',
    #     'last_login': '',
    #     'last_chat': '',
    #     'last_farming': '',
    #     'last_comment': '',
    #     'last_edit': '',
    #     'phone_number': '',
    #     'profile_path': ''
    # }
}

# inputs = {
#     'task': {
#         'task_id': task_id,
#         'configure': json.loads(task_configure) if task_configure else {},
#     },
#     'account': {
#         'account': account,
#         'password': password,
#         'email': email,
#         'email_pwd': email_pwd,
#         'gender': gender,
#         'phone_number': phone_number,
#         'birthday': birthday,
#         'national_id': national_id,
#         'name': name,
#         'active_area': active_area,
#         'active_browser': active_browser,
#         'profile_path': profile_path,
#         'configure': json.loads(account_configure) if account_configure else {}
#     }
# }

@app.task(base=BaseTask, bind=True, max_retries=1, time_limit=1200)
def fb_auto_feed(self, inputs):
    logger.info('----------fb_auto_feed task running, inputs=\r\n{}'.format(inputs))
    logger.info(inputs)
    try:
        # 分步执行任务
        driver = mobile_auto_feed.start_chrom()
        time.sleep(60)
        account = inputs.get('account').get('account')
        # account = inputs['account']['account']
        password = inputs.get('password').get('password')
        account_configure = account.get('configure', {})#last
        lst_login = account_configure['last_login']
        # if lst_login <fsfa:
        #     return
        mobile_auto_feed.auto_login(driver=driver, account=account, password=password)
        account_configure['last_login'] = '2018-03-15 18:21:06'
        time.sleep(15)
        mobile_auto_feed.user_messages(driver=driver)
        time.sleep(22)
        mobile_auto_feed.local_surface(driver=driver)
        TaskResult['status'] ='succeed'

        TaskResult['account_configure'] = account_configure

        return TaskResult
        # a = random.randint(1, 100)
        # if a % 3 == 1:
        #     TaskResult['status'] = 'failed'
        #     TaskResult['err_msg'] = 'a % 3 == 1'
        #     return TaskResult
        # if a % 2 == 0:
        #     logger.exception('fb_auto_feed')
        #     a = a / 0
        #     return TaskResult
        # res = scripts.auto_feed(inputs)
    except Exception as e:
        logger.exception('fb_auto_feed catch exception.')
        # self.retry(countdown=10 ** self.request.retries)
        TaskResult['status'] = 'failed'
        TaskResult['err_msg'] = str(e)

    return TaskResult


@app.task(base=BaseTask, bind=True, max_retries=1, time_limit=300)
def fb_click_farming(self, inputs):
    logger.info('fb_click_farming task running')

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

    return {'status': 'succeed', 'err_msg': 'click farming good'}


# from celery import chain, signature
# r = chain(fb_auto_feed.s({}), fb_click_farming.s({}))
# r.apply_async()

