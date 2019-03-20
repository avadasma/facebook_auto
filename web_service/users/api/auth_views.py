# -*- coding: utf-8 -*-

from django.contrib.auth import authenticate
from utils.request_utils import pretreatment, response_as_json_without_auth

# Created by: guangda.lee
# Created on: 2019/3/20
# Function:


# 用户登录验证
@response_as_json_without_auth
@pretreatment
def auth(request, data):
    user = authenticate(username=data['username'], password=data['password'])
    if user:
        return {
            'category': {
                'id': user.user.category.category,
                'name': user.user.category.name
            },
            'fullname': user.last_name,
            'email': user.email,
            'enable_tasks': user.user.enable_tasks
        }, 200
    return {}, 401
