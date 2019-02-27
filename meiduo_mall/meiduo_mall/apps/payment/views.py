
import os
from django.shortcuts import render
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from orders.models import OrderInfo
from .models import Payment

from alipay import AliPay
# Create your views here.

# http://www.meiduo.site:8080/pay_success.html?
# charset=utf-8&
# out_trade_no=201808150849020000000002& # 商户订单号
# method=alipay.trade.page.pay.return&
# total_amount=3798.00&
# 签名字符串
# sign=sV1amcuUDYoTRydH0GJYZPEJUFtE%2FcCqJcn51MCYLO6a3J7SPKku%2B%2BK2A7iWpdXyVkJPEqjBQ7JA9UjwHmjyv8KvL2r5ZrcA94ZO50Pr7W%2Bn5n6R8h%2B%2FFvjldWj7WWXowCGpQIK8KeYyuWUQISWba6BhitZFBrmZzljb6PwiBUteZ6oP2axqhNdaxwqpilOddlQhJ0T8RUzCqWEPdZ9s%2FjTXXlOdbEHxLyl4yGMQ%2BnIUXUVJBlteXFHO1Xr4EGpJKAPOdXZoBkYy7vm7jov2BTROtOiSJtQVk1JBc7UZD8pOCz3pv0U9frgyYpLuYxTINSQBpSxs1tEz%2Bn8Es1lRQw%3D%3D&
# trade_no=2018081521001004920200647394& # 支付宝交易号
# auth_app_id=2016090800464054&
# version=1.0&
# app_id=2016090800464054&
# sign_type=RSA2&
# seller_id=2088102174694091&
# timestamp=2018-08-15+09%3A40%3A51


#  PUT /payment/status/?支付宝参数
class PaymentStatusView(APIView):
    """
    支付结果
    """
    def put(self, request):
        """
        保存支付结果:
        1. 验证sign签名
        2. 校验订单是否有效
        3. 保存订单支付结果，更新订单支付状态
        4. 返回应答
        """
        # 1. 验证sign签名
        data = request.query_params.dict() # QueryDict->dict
        signature = data.pop('sign')

        # 创建AliPay实例对象
        alipay = AliPay(
            appid=settings.ALIPAY_APPID,  # 开发者应用APPID
            app_notify_url=None,  # 默认回调url
            app_private_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                              "keys/app_private_key.pem"),
            alipay_public_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                "keys/alipay_public_key.pem"),  # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=settings.ALIPAY_DEBUG  # 默认False，是否使用的是沙箱环境
        )

        success = alipay.verify(data, signature)

        if not success:
            return Response({'message': '非法请求'}, status=status.HTTP_403_FORBIDDEN)

        # 2. 校验订单是否有效
        order_id = request.query_params.get('out_trade_no')
        try:
            order = OrderInfo.objects.get(
                order_id=order_id,
                user=request.user,
                status=OrderInfo.ORDER_STATUS_ENUM['UNPAID'], # 待支付
                pay_method=OrderInfo.PAY_METHODS_ENUM['ALIPAY'], # 支付宝支付方式
            )
        except OrderInfo.DoesNotExist:
            return Response({'message': '无效的订单信息'}, status=status.HTTP_400_BAD_REQUEST)

        # 3. 保存订单支付结果，更新订单支付状态
        trade_id = request.query_params.get('trade_no')

        Payment.objects.create(
            order=order,
            trade_id=trade_id
        )

        # 更新订单支付状态
        order.status = OrderInfo.ORDER_STATUS_ENUM['UNSEND'] # 2
        order.save()

        # 4. 返回应答
        return Response({'trade_id': trade_id})


# GET /orders/(?P<order_id>\d+)/payment/
class PaymentView(APIView):
    """
    订单支付
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        """
        获取支付宝支付链接:
        1. 根据order_id校验订单是否有效
        2. 组织支付宝支付地址和参数
        3. 返回支付宝支付地址
        """
        # 1. 根据order_id校验订单是否有效
        try:
            order = OrderInfo.objects.get(
                order_id=order_id,
                user=request.user,
                status=OrderInfo.ORDER_STATUS_ENUM['UNPAID'], # 待支付
                pay_method=OrderInfo.PAY_METHODS_ENUM['ALIPAY'], # 支付宝支付方式
            )
        except OrderInfo.DoesNotExist:
            return Response({'message': '无效的订单信息'}, status=status.HTTP_400_BAD_REQUEST)

        # 2. 组织支付宝支付地址和参数
        # 创建AliPay实例对象
        alipay = AliPay(
            appid=settings.ALIPAY_APPID, # 开发者应用APPID
            app_notify_url=None,  # 默认回调url
            app_private_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                              "keys/app_private_key.pem"),
            alipay_public_key_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                "keys/alipay_public_key.pem"),  # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=settings.ALIPAY_DEBUG # 默认False，是否使用的是沙箱环境
        )

        # 组织支付参数
        # 电脑网站支付，需要跳转到https://openapi.alipaydev.com/gateway.do? + order_string
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_id, # 商户订单号
            total_amount=str(order.total_amount), # 支付总金额 Decimal
            subject='美多商城%s' % order_id,
            return_url="http://www.meiduo.site:8080/pay_success.html", # 用户支付成功之后回调地址
            notify_url=None  # 可选, 不填则使用默认notify url
        )

        # 3. 返回支付宝支付地址
        pay_url = settings.ALIPAY_URL + '?' + order_string
        return Response({'alipay_url': pay_url})
