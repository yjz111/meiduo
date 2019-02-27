from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_jwt.settings import api_settings

from cart.utils import merge_cart_cookie_to_redis
from .utils import OAuthQQ
from .exceptions import QQAPIError
from .models import OAuthQQUser
from .serializers import OAuthQQUserSerializer
# Create your views here.


# GET /oauth/qq/user/?code=xxx
class QQAuthUserView(APIView):
    def post(self, request):
        """绑定QQ用户:
        1. 获取参数并进行参数校验(完整性校验，短信验证码是否正确，access_token是否有效)
        2. 保存绑定QQ用户的信息(如果用户未注册，先创建新用户)
        3. 生成JWT token并返回
        """
        # 1. 获取参数并进行参数校验(完整性校验，短信验证码是否正确，access_token是否有效)
        serializer = OAuthQQUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # 2. 保存绑定QQ用户的信息(如果用户未注册，先创建新用户)
        user = serializer.save()

        # 3.返回
        serializer = OAuthQQUserSerializer(user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

        # 合并购物车
        response = merge_cart_cookie_to_redis(request, user, response)
        return  response

    def get(self, request):
        """
        获取qq用户的openid并进行处理:
        1. 获取code并进行校验
        2. 根据code请求QQ服务器获取access_token
        3. 根据access_token请求QQ服务器获取openid

        4. 根据openid判断该QQ用户是否已经绑定过本网站用户
            4.1 如果绑定过，直接生成jwt token，登录成功
            4.2 如果未绑定，自己生成一个token(保存openid信息)并返回
        """
        # 1. 获取code并进行校验
        code = request.query_params.get('code')

        if not code:
            return Response({'message': '缺少code'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 2. 根据code请求QQ服务器获取access_token
            oauth = OAuthQQ()
            access_token = oauth.get_access_token(code)
            # 3. 根据access_token请求QQ服务器获取openid
            openid = oauth.get_openid(access_token)
        except QQAPIError as e:
            return Response({'message': 'QQ登录异常'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        # 4. 根据openid判断该QQ用户是否已经绑定过本网站用户
        try:
            qq_user = OAuthQQUser.objects.get(openid=openid)
        except OAuthQQUser.DoesNotExist:
            # 4.2 如果未绑定，自己生成一个token(保存openid信息)并返回
            token = OAuthQQ.generate_save_user_token(openid)
            return Response({'access_token': token})
        else:
            # 4.1 如果绑定过，直接生成jwt token，登录成功
            jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
            jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER

            user = qq_user.user
            payload = jwt_payload_handler(user)  # 产生payload
            token = jwt_encode_handler(payload)  # 生成一个token

            # 返回
            response = Response({
                'token': token,
                'user_id': user.id,
                'username': user.username
            })

            #合并购物车
            response=merge_cart_cookie_to_redis(request,user,response)
            return response


# GET /oauth/qq/authorization/?next=xxx
class QQAuthURLView(APIView):
    """获取qq登录网址"""
    def get(self, request):
        # 获取next参数
        next = request.query_params.get('next', '/')

        # 创建OAuthQQ对象
        oauth = OAuthQQ(state=next)

        # 获取qq登录网址
        login_url = oauth.get_login_url()

        # 返回应答
        return Response({'login_url': login_url})