from rest_framework import serializers

from .models import Area


class AreaSerializer(serializers.ModelSerializer):
    """行政区划信息序列化器"""
    class Meta:
        model = Area
        fields = ('id', 'name')


class SubAreaSerializer(serializers.ModelSerializer):
    # 使用指定的序列化器将子级地区进行序列化
    subs = AreaSerializer(label='子级地区', many=True)

    class Meta:
        model = Area
        fields = ('id', 'name', 'subs')
