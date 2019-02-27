from django.shortcuts import render
from rest_framework.generics import ListAPIView
from rest_framework.filters import OrderingFilter
from drf_haystack.viewsets import HaystackViewSet

from .serializers import SKUSerializer, SKUIndexSerializer
from .models import SKU
# Create your views here.


# /skus/search/?text=搜索关键字
class SKUSearchViewSet(HaystackViewSet):
    """商品搜索视图集"""
    index_models = [SKU]
    serializer_class = SKUIndexSerializer

# GET /categories/(?P<category_id>\d+)/skus/?page=xxx&page_size=xxx&ordering=xxx
# 商品列表信息
# 1. 返回指定第三级分类下所有的SKU商品
# 2. 分页
# 3. 排序
class SKUListView(ListAPIView):
    serializer_class = SKUSerializer

    filter_backends = [OrderingFilter]
    # 指定排序字段
    ordering_fields = ('create_time', 'price', 'sales')

    def get_queryset(self):
        # 获取category_id
        category_id = self.kwargs['category_id']

        # 获取category_id分类下所有商品信息
        skus = SKU.objects.filter(category_id=category_id, is_launched=True)

        return skus

