from rest_framework import serializers

from goods.models import SKU


class CartDeleteSerializer(serializers.Serializer):
    """
    删除购物车数据序列化器
    """
    sku_id = serializers.IntegerField(label='商品id', min_value=1)

    def validate_sku_id(self, value):
        try:
            sku = SKU.objects.get(id=value)
        except SKU.DoesNotExist:
            raise serializers.ValidationError('商品不存在')

        return value


class CartSKUSerializer(serializers.ModelSerializer):
    count = serializers.IntegerField(label='数量')
    selected = serializers.BooleanField(label='勾选状态')

    class Meta:
        model = SKU
        fields = ('id', 'name', 'price', 'default_image_url', 'count', 'selected')


class CartSerializer(serializers.Serializer):
    """购物车序列化器类"""
    sku_id = serializers.IntegerField(label='商品SKU_ID', min_value=1)
    count = serializers.IntegerField(label='数量', min_value=1)
    selected = serializers.BooleanField(label='是否勾选', default=True)

    def validate(self, attrs):
        """商品是否存在，库存是否足够"""
        # 商品是否存在
        sku_id = attrs['sku_id']

        try:
            sku = SKU.objects.get(id=sku_id)
        except SKU.DoesNotExist:
            raise serializers.ValidationError('商品不存在')

        # 库存是否足够
        count = attrs['count']
        if count > sku.stock:
            raise serializers.ValidationError('商品库存不足')

        return attrs

class CartSelectAllSerializer(serializers.Serializer):
    """购物车全选"""
    selected = serializers.BooleanField(label='全选')
