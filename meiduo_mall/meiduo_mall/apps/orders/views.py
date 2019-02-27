from decimal import Decimal
from django.shortcuts import render
from django_redis import get_redis_connection
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import GenericAPIView, CreateAPIView
from rest_framework.permissions import IsAuthenticated

from goods.models import SKU

from .serializers import OrderSettlementSerializer, SaveOrderSerializer
# Create your views here.


# POST /orders/
# class OrderCommitView(GenericAPIView):
class OrderCommitView(CreateAPIView):
    serializer_class = SaveOrderSerializer
    permission_classes = [IsAuthenticated]

    # def post(self, request):
    #     """
    #     订单创建:
    #     1. 获取参数并进行参数校验(address, pay_method)
    #     2. 保存订单信息
    #     3. 返回应答，订单创建成功
    #     """
    #     # 1. 获取参数并进行参数校验(address, pay_method)
    #     serializer = self.get_serializer(data=request.data)
    #     serializer.is_valid(raise_exception=True)
    #
    #     # 2. 保存订单信息
    #     serializer.save()
    #
    #     # 3. 返回应答，订单创建成功
    #     return  Response(serializer.data)


# GET /orders/settlement/
class OrderSettlementView(APIView):
    """
    订单结算
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        订单结算信息获取:
        1. 从redis中获取用户所要购买的商品的id和对应数量count
        2. 根据商品id获取对应商品的信息
        3. 序列化数据并返回
        """
        # 1. 从redis中获取用户所要购买的商品的id和对应数量count
        user = request.user
        redis_conn = get_redis_connection('cart')

        # 获取用户购物车中所有商品的id和对应数量count
        cart_key = 'cart_%s' % user.id
        # {
        #     b'<sku_id>': b'<count>',
        #     ...
        # }
        redis_cart = redis_conn.hgetall(cart_key)

        # 处理数据
        cart_dict = {}
        for sku_id, count in redis_cart.items():
            cart_dict[int(sku_id)] = int(count)

        # 获取用户购物车中被选中的商品的id
        cart_selected_key = 'cart_selected_%s' % user.id
        # set(b'1', b'3', ...)
        sku_ids = redis_conn.smembers(cart_selected_key)

        # 2. 根据商品id获取对应商品的信息
        skus = SKU.objects.filter(id__in=sku_ids)

        for sku in skus:
            # 给sku对象增加属性count，用来记录该商品所要购买的数量count
            sku.count = cart_dict[sku.id]

        # 运费
        freight = Decimal(10)

        # 3. 序列化数据并返回
        res_dict = {
            'freight': freight,
            'skus': skus
        }
        serializer = OrderSettlementSerializer(res_dict)
        return Response(serializer.data)
