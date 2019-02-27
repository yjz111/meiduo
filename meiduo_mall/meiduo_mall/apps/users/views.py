from django.shortcuts import render
from django_redis import get_redis_connection
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.generics import GenericAPIView, CreateAPIView, RetrieveAPIView, UpdateAPIView
from rest_framework.mixins import CreateModelMixin, RetrieveModelMixin, UpdateModelMixin
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework import mixins
from rest_framework.viewsets import GenericViewSet
from  rest_framework_jwt.views import ObtainJSONWebToken

from cart.utils import merge_cart_cookie_to_redis
from .models import User
from .serializers import CreateUserSerializer, UserDetailSerializer, EmailSerializer
from . import serializers
from . import constants
from goods.models import SKU
from goods.serializers import SKUSerializer
from  rest_framework_jwt.views import  ObtainJSONWebToken

# Create your views here.

class UserAuthorizeView(ObtainJSONWebToken):
    """用户认证"""
    def post(self, request, *args, **kwargs):
        #调用父类方法，获取drf jwt扩展默认的认证用户处理结果
        response = super().post(request,*args,**kwargs)

        #仿照drf jwt扩展对于用户登陆的认证方式，判断用户是否认证登录成功
        #如果用户登录认证成功，则合并购物车

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data.get('user')
            response = merge_cart_cookie_to_redis(request,user,response)


        return response



# /browse_histories/
# class UserBrowseHistoryView(GenericAPIView):
class UserBrowseHistoryView(CreateAPIView):
    """
    历史浏览记录
    """
    serializer_class = serializers.AddUserBrowseHistorySerializer
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        获取用户的历史浏览记录:
        1. 获取登录user
        2. 从redis中获取对应用户的浏览记录
        3. 根据浏览记录中商品id获取对应商品的信息
        4. 序列化商品的数据并返回
        """
        # 1. 获取登录user
        user = request.user

        # 2. 从redis中获取对应用户的浏览记录
        redis_conn = get_redis_connection('history')
        history_key = 'history_%s' % user.id

        sku_ids = redis_conn.lrange(history_key, 0, 4) # [b'1', b'2', b'3']

        # 3. 根据浏览记录中商品id获取对应商品的信息
        skus = []

        for sku_id in sku_ids:
            sku = SKU.objects.get(id=sku_id)
            skus.append(sku)

        # 4. 序列化商品的数据并返回
        serializer = SKUSerializer(skus, many=True)
        return Response(serializer.data)

    # def post(self, request):
    #     """
    #     保存用户的历史浏览记录:
    #     1. 获取sku_id并进行校验(是否传递，商品是否存在)
    #     2. 在redis中保存用户的历史浏览记录
    #     3. 返回应答
    #     """
    #     # 1. 获取sku_id并进行校验(是否传递，商品是否存在)
    #     serializer = self.get_serializer(data=request.data)
    #     serializer.is_valid(raise_exception=True)
    #
    #     # 2. 在redis中保存用户的历史浏览记录
    #     serializer.save()
    #
    #     # 3. 返回应答
    #     return Response(serializer.data, status=status.HTTP_201_CREATED)


class AddressViewSet(mixins.CreateModelMixin, mixins.UpdateModelMixin, GenericViewSet):
    """
    用户地址新增与修改
    """
    serializer_class = serializers.UserAddressSerializer
    permissions = [IsAuthenticated]

    def get_queryset(self):
        return self.request.user.addresses.filter(is_deleted=False)

    # GET /addresses/
    def list(self, request, *args, **kwargs):
        """
        用户地址列表数据
        """
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        user = self.request.user
        return Response({
            'user_id': user.id,
            'default_address_id': user.default_address_id,
            'limit': constants.USER_ADDRESS_COUNTS_LIMIT,
            'addresses': serializer.data,
        })

    # POST /addresses/
    def create(self, request, *args, **kwargs):
        """
        保存用户地址数据
        """
        # 检查用户地址数据数目不能超过上限
        count = request.user.addresses.count()
        if count >= constants.USER_ADDRESS_COUNTS_LIMIT:
            return Response({'message': '保存地址数据已达到上限'}, status=status.HTTP_400_BAD_REQUEST)

        return super().create(request, *args, **kwargs)

    # delete /addresses/<pk>/
    def destroy(self, request, *args, **kwargs):
        """
        处理删除
        """
        address = self.get_object()

        # 进行逻辑删除
        address.is_deleted = True
        address.save()

        return Response(status=status.HTTP_204_NO_CONTENT)

    # put /addresses/pk/status/
    @action(methods=['put'], detail=True)
    def status(self, request, pk=None):
        """
        设置默认地址
        """
        address = self.get_object()
        request.user.default_address = address
        request.user.save()
        return Response({'message': 'OK'}, status=status.HTTP_200_OK)

    # put /addresses/pk/title/
    # 需要请求体参数 title
    @action(methods=['put'], detail=True)
    def title(self, request, pk=None):
        """
        修改标题
        """
        address = self.get_object()
        serializer = serializers.AddressTitleSerializer(instance=address, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


# GET /emails/verification/?token=xxx
class VerifyEmailView(APIView):
    """
    激活用户的邮箱:
    1. 获取token并对token进行校验(token是否传递，token是否有效)
    2. 将用户的邮箱设置为激活状态
    3. 返回应答
    """
    def get(self, request):
        #  1. 获取token并对token进行校验(token是否传递，token是否有效)
        token = request.query_params.get('token')
        if not token:
            return Response({'message': '缺少token信息'}, status=status.HTTP_400_BAD_REQUEST)

        # 校验token是否有效
        user = User.check_verify_email_token(token)
        if user is None:
            return Response({'message': '无效的token信息'}, status=status.HTTP_400_BAD_REQUEST)

        # 2. 将用户的邮箱设置为激活状态
        user.email_active = True
        user.save()

        # 3. 返回应答
        return Response({'message': 'OK'})


# PUT /email/
# class EmailView(UpdateModelMixin, GenericAPIView):
class EmailView(UpdateAPIView):
    """
    设置用户的邮箱:
    1. 获取邮箱并进行校验(邮箱是否传递，邮箱格式是否正确)
    2. 保存用户的邮箱信息并且给用户的邮箱发送激活邮件
    3. 返回应答，设置邮箱成功
    """
    permission_classes = [IsAuthenticated]
    serializer_class = EmailSerializer

    def get_object(self):
        """返回登录用户"""
        # self.request
        return self.request.user

    # def put(self, request):
    #     # # 获取登录用户
    #     # # user = request.user
    #     # user = self.get_object()
    #     #
    #     # # 1. 获取邮箱并进行校验(邮箱是否传递，邮箱格式是否正确)
    #     # # serializer = EmailSerializer(user, data=request.data)
    #     # serializer = self.get_serializer(user, data=request.data)
    #     # serializer.is_valid(raise_exception=True)
    #     #
    #     # # 2. 保存用户的邮箱信息并且给用户的邮箱发送激活邮件
    #     # user = serializer.save()
    #     #
    #     # # 3. 返回应答，设置邮箱成功
    #     # return Response(serializer.data)
    #
    #     return self.update(request)


# GET /user/
# class UserDetailView(RetrieveModelMixin, GenericAPIView):
class UserDetailView(RetrieveAPIView):
    """
    获取用户的个人信息:
    1. 获取当前登录用户
    2. 把用户的信息序列化进行返回
    """
    serializer_class = UserDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        """返回登录用户"""
        return self.request.user


    # def get(self, request):
    #     # # 1. 获取当前登录用户
    #     # # user = request.user
    #     # user = self.get_object()
    #     #
    #     # # 2. 把用户的信息序列化进行返回
    #     # # serializer = UserDetailSerializer(user)
    #     # serializer = self.get_serializer(user)
    #     # return Response(serializer.data)
    #
    #     return self.retrieve(request)


# POST /users/
# class UserView(APIView):
# class UserView(CreateModelMixin, GenericAPIView):
class UserView(CreateAPIView):
    """
    用户注册:
    1. 获取参数并进行参数校验(完整性校验，手机号是否合法，是否同意协议，两次密码是否一致，短信验证码是否正确)
    2. 创建新用户并保存注册用户信息
    3. 返回应答，注册成功
    """
    serializer_class = CreateUserSerializer

    # def post(self, request):
    #     # # 1. 获取参数并进行参数校验(完整性校验，手机号是否合法，是否同意协议，两次密码是否一致，短信验证码是否正确)
    #     # # serializer = CreateUserSerializer(data=request.data)
    #     # serializer = self.get_serializer(data=request.data)
    #     # serializer.is_valid(raise_exception=True) # 400
    #     #
    #     # # 2. 创建新用户并保存注册用户信息
    #     # user = serializer.save()
    #     #
    #     # # 3. 返回应答，注册成功
    #     # # serializer = CreateUserSerializer(user)
    #     # serializer = self.get_serializer(user)
    #     # return Response(serializer.data, status=status.HTTP_201_CREATED)
    #
    #     return self.create(request)


# GET mobiles/(?P<mobile>1[3-9]\d{9})/count/
class MobileCountView(APIView):
    """
    手机号数量
    """
    def get(self, request, mobile):
        """
        获取指定手机号数量
        """
        count = User.objects.filter(mobile=mobile).count()

        data = {
            'mobile': mobile,
            'count': count
        }

        return Response(data)


# GET usernames/(?P<username>\w{5,20})/count/
class UsernameCountView(APIView):
    """
    用户名数量
    """
    def get(self, request, username):
        """
        获取指定用户名数量
        """
        count = User.objects.filter(username=username).count()

        data = {
            'username': username,
            'count': count
        }

        return Response(data)
