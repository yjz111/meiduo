import pickle
import base64
from django.shortcuts import render
from django_redis import get_redis_connection
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from .serializers import CartSerializer, CartSKUSerializer, CartDeleteSerializer,CartSelectAllSerializer
from . import constants

from goods.models import SKU
# Create your views here.


# POST /cart/
class CartView(APIView):
    """
    购物车记录:
    """
    # permission_classes = [IsAuthenticated]

    def perform_authentication(self, request):
        """重写方法，跳过认证过程"""
        pass

    def delete(self, request):
        """
        购物车记录删除:
        1. 获取sku_id并进行参数校验
        2. 获取user
        3. 删除购物车中记录
            3.1 如果用户已登录，删除redis中用户的购物车记录
            3.2 如果用户未登录，删除cookie中用户的购物车记录
        4. 返回应答
        """
        # 1. 获取sku_id并进行参数校验
        serializer = CartDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sku_id = serializer.validated_data['sku_id']

        # 2. 获取user
        try:
            user = request.user
        except Exception:
            user = None

        # 3. 删除购物车中记录
        if user is not None and user.is_authenticated:
            # 3.1 如果用户已登录，删除redis中用户的购物车记录
            redis_conn = get_redis_connection('cart')
            pl = redis_conn.pipeline()

            # 删除redis中对应的购物车记录 hash
            cart_key = 'cart_%s' % user.id
            pl.hdel(cart_key, sku_id)

            # 删除sku_id被勾选，清除redis对应商品勾选状态
            cart_selected_key = 'cart_selected_%s' % user.id
            pl.srem(cart_selected_key, sku_id)

            pl.execute()

            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            # 3.2 如果用户未登录，删除cookie中用户的购物车记录
            response = Response(status=status.HTTP_204_NO_CONTENT)
            # 3.2 如果用户未登录，更新cookie中用户的购物车记录
            cookie_cart = request.COOKIES.get('cart')  # None

            if cookie_cart is None:
                return response

            # 解析cookie中购物车数据
            cart_dict = pickle.loads(base64.b64decode(cookie_cart))  # {}

            if not cart_dict:
                return response

            # 删除redis购物车记录
            if sku_id in cart_dict:
                del cart_dict[sku_id]
                cookie_data = base64.b64encode(pickle.dumps(cart_dict)).decode()  # str
                response.set_cookie('cart', cookie_data, expires=constants.CART_COOKIE_EXPIRES)

            # 4. 返回应答
            return response

    def put(self, request):
        """
        购物车记录更新:
        1. 获取参数并进行校验(sku_id, count(更新结果), selected(更新的选中状态))
        2. 获取user
        3. 保存购物车更新信息
            3.1 如果用户已登录，更新redis中用户的购物车记录
            3.2 如果用户未登录，更新cookie中用户的购物车记录
        4. 返回应答
        """
        # 1. 获取参数并进行校验(sku_id, count, selected)
        serializer = CartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sku_id = serializer.validated_data['sku_id']
        count = serializer.validated_data['count']
        selected = serializer.validated_data['selected']

        # 2. 获取user
        try:
            user = request.user
        except Exception:
            user = None

        # 3. 保存购物车更新信息
        if user is not None and user.is_authenticated:
            # 3.1 如果用户已登录，更新redis中用户的购物车记录
            redis_conn = get_redis_connection('cart')
            pl = redis_conn.pipeline()

            # 设置购物车中对应商品数量 hash
            cart_key = 'cart_%s' % user.id
            pl.hset(cart_key, sku_id, count)

            # 设置购物车中对应商品勾选状态 set
            cart_selected_key = 'cart_selected_%s' % user.id

            if selected:
                # 勾选
                pl.sadd(cart_selected_key, sku_id)
            else:
                # 不勾选
                pl.srem(cart_selected_key, sku_id)

            pl.execute()

            # 返回应答
            return Response(serializer.data)
        else:
            response = Response(serializer.data)
            # 3.2 如果用户未登录，更新cookie中用户的购物车记录
            cookie_cart = request.COOKIES.get('cart') # None

            if cookie_cart is None:
                return response

            # 解析cookie中购物车数据
            cart_dict = pickle.loads(base64.b64decode(cookie_cart)) # {}

            if not cart_dict:
                return response

            # 更新cookie中购物车对应商品的数量和选中状态
            cart_dict[sku_id] = {
                'count': count,
                'selected': selected
            }

            # 4. 返回应答
            cookie_data = base64.b64encode(pickle.dumps(cart_dict)).decode()  # str
            response.set_cookie('cart', cookie_data, expires=constants.CART_COOKIE_EXPIRES)
            return response

    def get(self, request):
        """
        购物车记录显示:
        1. 获取user
        2. 获取用户的购物车记录数据
            2.1 如果用户已登录，从redis中获取用户的购物车记录
            2.2 如果用户未登录，从cookie中获取用户的购物车记录
        3. 根据用户购物车商品id查询对应商品信息
        4. 序列化数据并返回
        """
        # 1. 获取user
        try:
            user = request.user
        except Exception:
            user = None

        # 2. 获取用户的购物车记录数据
        if user is not None and user.is_authenticated:
            # 2.1 如果用户已登录，从redis中获取用户的购物车记录
            redis_conn = get_redis_connection('cart')

            # 获取用户购物车中商品id和对应数量 hash
            cart_key = 'cart_%s' % user.id

            # {
            #     b'<sku_id>': b'<count>',
            #     ...
            # }
            redis_cart = redis_conn.hgetall(cart_key) # dict

            # 获取用户购物车中勾选商品 set
            cart_selected_key = 'cart_selected_%s' % user.id
            # (b'<sku_id>', ...)
            redis_cart_selected = redis_conn.smembers(cart_selected_key) # set

            # 组织数据
            # {
            #     '<sku_id>': {
            #         'count': '<count>',
            #         'selected': '<selected>'
            #     },
            #     ...
            # }
            cart_dict = {}

            for sku_id, count in redis_cart.items():
                cart_dict[int(sku_id)] = {
                    'count': int(count),
                    'selected': sku_id in redis_cart_selected
                }
        else:
            # 2.2 如果用户未登录，从cookie中获取用户的购物车记录
            cookie_cart = request.COOKIES.get('cart')

            # 解析购物车cookie中的数据
            if cookie_cart:
                cart_dict = pickle.loads(base64.b64decode(cookie_cart))
            else:
                cart_dict = {}

        # 3. 根据用户购物车商品id查询对应商品信息
        sku_ids = cart_dict.keys()
        skus = SKU.objects.filter(id__in=sku_ids)

        for sku in skus:
            # 给sku对象增加两个属性count和selected
            # 分别保存用户购物车添加的对应商品的数量和勾选状态
            sku.count = cart_dict[sku.id]['count']
            sku.selected = cart_dict[sku.id]['selected']

        # 4. 序列化数据并返回
        serializer = CartSKUSerializer(skus, many=True)
        return Response(serializer.data)

    def post(self, request):
        """
        购物车记录增加：
        1. 获取参数并进行参数校验(sku_id, count, selected)
        2. 保存用户的购物车记录
            2.1 如果用户已登录，在redis中保存用户的购物车记录
            2.2 如果用户未登录，在cookie中保存用户的购物车记录
        3. 返回应答
        """
        # 1. 获取参数并进行参数校验(sku_id, count, selected)
        serializer = CartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sku_id = serializer.validated_data['sku_id']
        count = serializer.validated_data['count']
        selected = serializer.validated_data['selected']

        # 获取登录user
        try:
            user = request.user
        except Exception:
            user = None

        # 2. 保存用户的购物车记录
        if user is not None and user.is_authenticated:
            # 如果用户已登录，在redis中保存用户的购物车记录
            redis_conn = get_redis_connection('cart')
            pl = redis_conn.pipeline()

            # 保存用户添加的商品id和数量 hash
            cart_key = 'cart_%s' % user.id

            # 如果购物车已经添加过某个商品，对应数量需要进行累加
            # 如果购物车没有添加过某个商品，直接设置一个新的数据
            pl.hincrby(cart_key, sku_id, count)

            # 保存商品勾选状态 set
            cart_selected_key = 'cart_selected_%s' % user.id
            if selected:
                # 勾选
                pl.sadd(cart_selected_key, sku_id)

            pl.execute()

            # 3. 返回应答
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            # 如果用户未登录，在cookie中保存用户的购物车记录
            cookie_cart = request.COOKIES.get('cart')

            # 解析购物车cookie中的数据
            if cookie_cart:
                cart_dict = pickle.loads(base64.b64decode(cookie_cart))
            else:
                cart_dict = {}

            # 保存购物车信息
            if sku_id in cart_dict:
                count += cart_dict[sku_id]['count']

            cart_dict[sku_id] = {
                'count': count,
                'selected': selected
            }

            # 返回应答，设置购物车cookie
            response = Response(serializer.data, status=status.HTTP_201_CREATED)
            cookie_data = base64.b64encode(pickle.dumps(cart_dict)).decode() # str
            response.set_cookie('cart', cookie_data, expires=constants.CART_COOKIE_EXPIRES)
            return response


class CartSelectAllView(APIView):
    """购物车全选"""
    def perform_authentication(self, request):
        """重写父类的用户验证方法，不进入视图前就检查JWT"""
        pass

    def put(self,request):
        serializer = CartSelectAllSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        selected = serializer.validated_data['selected']

        try:
            user = request.user
        except Exception:
            user = None

        if user is not None and user.is_authenticated:
            #用户已经登陆，在redis中保存
            redis_conn = get_redis_connection('cart')
            cart = redis_conn.hgetall('cart_%s'%user.id)
            sku_id_list = cart.keys()


            if selected:
                # 全选
                redis_conn.sadd('cart_selected_%s' % user.id, *sku_id_list)
            else:
                # 取消全选
                redis_conn.srem('cart_selected_%s' % user.id, *sku_id_list)
            return Response({'message': 'OK'})
        else:
            # cookie
            cart = request.COOKIES.get('cart')

            response = Response({'message': 'OK'})

            if cart is not None:
                cart = pickle.loads(base64.b64decode(cart.encode()))
                for sku_id in cart:
                    cart[sku_id]['selected'] = selected
                cookie_cart = base64.b64encode(pickle.dumps(cart)).decode()
                # 设置购物车的cookie
                # 需要设置有效期，否则是临时cookie
                response.set_cookie('cart', cookie_cart, max_age=constants.CART_COOKIE_EXPIRES)

            return response
