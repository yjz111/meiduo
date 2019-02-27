from django.shortcuts import render

# Create your views here.
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView, ListAPIView, RetrieveAPIView
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.viewsets import ReadOnlyModelViewSet

from .serializers import AreaSerializer, SubAreaSerializer
from .models import Area
# Create your views here.
from  rest_framework_extensions.cache.mixins import CacheResponseMixin

class AreaViewSet(CacheResponseMixin,ReadOnlyModelViewSet):
    pagination_class = None #区划信息不分页
    """地区视图集"""
    def get_queryset(self):
        if self.action == 'list':
            return Area.objects.filter(parent=None)
        else:
            return Area.objects.all()

    def get_serializer_class(self):
        if self.action == 'list':
            return AreaSerializer
        else:
            return SubAreaSerializer


# # GET /areas/(?P<pk>\d+)/
# # class SubAreaView(RetrieveModelMixin, GenericAPIView):
# class SubAreaView(RetrieveAPIView):
#     """
#     获取地区信息的同时将其子级地区一并返回:
#     1. 根据pk获取对应地区
#     2. 将地区进行序列化(将其子级地区一并进行序列化)并返回
#     """
#     queryset = Area.objects.all()
#     serializer_class = SubAreaSerializer
#
#     # def get(self, request, pk):
#     #     # # 1. 根据pk获取对应地区
#     #     # area = self.get_object()
#     #     #
#     #     # # 2. 将地区进行序列化(将其子级地区一并进行序列化)并返回
#     #     # serializer = self.get_serializer(area)
#     #     # return Response(serializer.data)
#     #
#     #     return self.retrieve(request)
#
#
# #  GET /areas/
# # class AreaView(ListModelMixin, GenericAPIView):
# class AreaView(ListAPIView):
#     """
#     获取所有省级地址的信息:
#     1. 获取所有省级地区的信息
#     2. 将省级地区的信息序列化并返回
#     """
#     serializer_class = AreaSerializer
#     queryset = Area.objects.filter(parent=None)
#
#     # def get(self, request):
#     #     # # 1. 获取所有省级地区的信息
#     #     # areas = self.get_queryset()
#     #     #
#     #     # # 2. 将省级地区的信息序列化并返回
#     #     # serializer = self.get_serializer(areas, many=True)
#     #     # return Response(serializer.data)
#     #
#     #     return self.list(request)