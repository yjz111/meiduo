import random
import logging
from django.shortcuts import render
from django.http import HttpResponse

from rest_framework.views import APIView
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from django_redis import get_redis_connection

from meiduo_mall.libs.captcha.captcha import captcha
from meiduo_mall.libs.yuntongxun.sms import CCP
# from users.models import User
from . import constants
from .serializers import CheckImageCodeSerializer
# Create your views here.

# 获取日志器
logger = logging.getLogger('django')


# GET /sms_codes/(?P<mobile>1[3-9]\d{9})/?image_code_id=xxx&text=xxx
class SMSCodeView(APIView):
    """
    短信验证码:
    1. 获取参数并进行校验(参数完整性，图片验证码是否正确)
    2. 发送短信验证码
    3. 返回应答，发送短信成功
    """
    def get(self, request, mobile):
        # self.kwargs['mobile']
        # 1. 获取参数并进行校验(参数完整性，图片验证码是否正确)
        serializer = CheckImageCodeSerializer(data=request.query_params, context={'mobile': mobile})
        serializer.is_valid(raise_exception=True)

        # 2. 发送短信验证码
        # 2.1 随机生成6位数字
        sms_code = '%06d' % random.randint(0, 999999)
        logger.info('短信验证码为: %s' % sms_code)

        # 2.2 在redis中存储短信验证码内容，以`手机号`为key，以`短信验证码内容`为value
        redis_conn = get_redis_connection('verify_codes')
        # redis管道
        pipeline = redis_conn.pipeline()

        pipeline.setex('sms_%s' % mobile, constants.SMS_CODE_REDIS_EXPIRES, sms_code)
        # 设置给用户手机号发送短信的标记(60s有效)
        pipeline.setex('send_flag_%s' % mobile, constants.SEND_SMS_CODE_INTERVAL, 1)

        # 一次性执行管道中的所有命令
        pipeline.execute()

        # 2.3 使用云通讯发送短信验证码
        expires = constants.SMS_CODE_REDIS_EXPIRES // 60
        # try:
        #     res = CCP().send_template_sms(mobile, [sms_code, expires], constants.SMS_CODE_TEMP_ID)
        # except Exception as e:
        #     logger.error(e)
        #     return Response({'message': '发送短信异常'})
        #
        # if res != 0:
        #     return Response({'message': '发送短信失败'})

        #发出短信任务
        from celery_tasks.sms.tasks import  send_sms_code
        send_sms_code.delay(mobile,sms_code,expires)

        # 3. 返回应答，发送短信成功
        return Response({'message': '发送短信成功'})


# GET /image_codes/(?P<image_code_id>[\w-]+)/
class ImageCodeView(APIView):
    """
    图片验证码：
    1. 使用captcha生成图片验证码
    2. 使用redis保存图片验证码文本，以uuid为key，以验证码文本为value
    3. 返回验证码图片
    """
    def get(self, request, image_code_id):
        # 1. 使用captcha生成图片验证码
        text,image = captcha.generate_captcha()
        logger.info('图片验证码为: %s' % text)

        # 2. 使用redis保存图片验证码文本，以uuid为key，以验证码文本为value
        redis_conn = get_redis_connection('verify_codes')
        # redis_conn.setex('key', 'expires', 'value')
        redis_conn.setex('img_%s' % image_code_id, constants.IMAGE_CODE_REDIS_EXPIRES, text)

        # 3. 返回验证码图片
        return HttpResponse(image, content_type='image/jpg')