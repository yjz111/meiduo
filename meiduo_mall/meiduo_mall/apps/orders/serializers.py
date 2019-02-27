from datetime import datetime

from decimal import Decimal
from django.db import transaction
from django_redis import get_redis_connection
from  rest_framework import  serializers
from  goods.models import SKU
from  .models import OrderInfo, OrderGoods


class CartSKUSerializer(serializers.ModelSerializer):
    """购物车商品数据序列化器"""
    count = serializers.IntegerField(label='数量')
    class Meta:
        model = SKU
        fields = ('id','name','default_image_url','price','count')

class OrderSettlementSerializer(serializers.Serializer):
    """订单结算数据序列化器"""
    freight = serializers.DecimalField(label='运费',max_digits=10,decimal_places=2)
    skus = CartSKUSerializer(many=True)

class SaveOrderSerializer(serializers.ModelSerializer):
    """下单数据序列化器"""
    class Meta:
        model = OrderInfo
        fields = ('order_id','address','pay_method')
        read_only_fields = ('order_id',)
        extra_kwargs={
            'address':{
                'write_only':True,
                'required':True,
            },
            'pay_method':{
                'write_only':True,
                'required':True
            }
        }

    def create(self, validated_data):
        """保存订单信息(订单并发解决: 乐观'锁')"""
        # 获取address和pay_method
        address = validated_data['address']
        pay_method = validated_data['pay_method']

        # 组织订单参数
        user = self.context['request'].user

        # 订单id: 格式:(年月日时分秒)+用户id
        order_id = datetime.now().strftime('%Y%m%d%H%M%S') + '%010d' % user.id

        # 运费
        freight = Decimal(10)

        # 订单商品的总数目和总金额
        total_count = 0
        total_amount = Decimal(0)

        # 订单状态
        # if pay_method == OrderInfo.PAY_METHODS_ENUM['CASH']:
        #     status = OrderInfo.ORDER_STATUS_ENUM['UNSEND']
        # else:
        #     status = OrderInfo.ORDER_STATUS_ENUM['UNPAID']

        status = OrderInfo.ORDER_STATUS_ENUM['UNSEND'] if pay_method == OrderInfo.PAY_METHODS_ENUM['CASH'] else \
        OrderInfo.ORDER_STATUS_ENUM['UNPAID']

        # 从redis中获取用户要购买的商品id set
        redis_conn = get_redis_connection('cart')
        cart_selected_key = 'cart_selected_%s' % user.id
        # (b'<sku_id>', b'<sku_id>', ...)
        sku_ids = redis_conn.smembers(cart_selected_key)

        # 从redis中获取用户购物车商品的id和对应数量count hash
        cart_key = 'cart_%s' % user.id
        # {
        #     b'<sku_id>': b'<count>',
        #     ...
        # }
        cart_dict = redis_conn.hgetall(cart_key)

        with transaction.atomic():
            # 凡是在with语句块中，涉及到数据库操作的代码，都会放在同一个事务中

            # 设置一个mysql事务保存点
            sid = transaction.savepoint()

            try:
                # TODO: 向订单信息表中添加一条数据
                order = OrderInfo.objects.create(
                    order_id=order_id,
                    user=user,
                    address=address,
                    total_count=total_count,
                    total_amount=total_amount,
                    freight=freight,
                    pay_method=pay_method,
                    status=status
                )

                # TODO: 订单中包含几个商品，就需要向订单商品表中添加几条数据。
                for sku_id in sku_ids:
                    # 获取sku_id商品购买的数量
                    count = cart_dict[sku_id]
                    count = int(count)

                    for i in range(3):
                        # 根据sku_id获取对应的商品
                        # select * from tb_sku where id=<sku_id>;
                        sku = SKU.objects.get(id=sku_id)

                        # 商品库存量
                        if count > sku.stock:
                            # 商品库存不足，将mysql事务回滚到sid保存点
                            transaction.savepoint_rollback(sid)
                            raise serializers.ValidationError('商品库存不足')

                        # 保存商品原始库存
                        origin_stock = sku.stock
                        new_stock = origin_stock - count
                        new_sales = sku.sales + count

                        # 模拟订单并发
                        # print('user: %s times: %s stock: %s' % (user.id, i, origin_stock))
                        # import time
                        # time.sleep(10)

                        # 商品库存减少，销量增加
                        # update tb_sku
                        # set stock=<new_stock>, sales=<new_sales>
                        # where id=<sku_id> and stock=<orgin_stock>;
                        res = SKU.objects.filter(id=sku_id, stock=origin_stock). \
                            update(stock=new_stock, sales=new_sales)

                        if res == 0:
                            if i == 2:
                                # 尝试了3次，下单仍然失败
                                transaction.savepoint_rollback(sid)
                                raise serializers.ValidationError('下单失败2')

                            # 更新失败，需要重新进行尝试
                            continue

                        # 向订单商品表中添加一条记录
                        OrderGoods.objects.create(
                            order=order,
                            sku=sku,
                            count=count,
                            price=sku.price
                        )

                        # 累加计算订单中商品的总数量和总金额
                        total_count += count
                        total_amount += count * sku.price

                        # 更新成功，跳出循环
                        break

                # 更新order中订单商品总数量和订单总金额
                order.total_count = total_count
                order.total_amount = total_amount + freight
                order.save()
            except serializers.ValidationError:
                # 继续向外抛出异常
                raise
            except Exception as e:
                # 订单保存出错，将mysql事务回滚到sid保存点
                transaction.savepoint_rollback(sid)
                raise serializers.ValidationError('下单失败1')

        # TODO: 清除购物车中对应记录
        pl = redis_conn.pipeline()
        pl.hdel(cart_key, *sku_ids)
        pl.srem(cart_selected_key, *sku_ids)
        pl.execute()

        return order

    def create_1(self, validated_data):
        """保存订单信息(订单并发解决: 悲观锁)"""
        # 获取address和pay_method
        address = validated_data['address']
        pay_method = validated_data['pay_method']

        # 组织订单参数
        user = self.context['request'].user

        # 订单id: 格式:(年月日时分秒)+用户id
        order_id = datetime.now().strftime('%Y%m%d%H%M%S') + '%010d' % user.id

        # 运费
        freight = Decimal(10)

        # 订单商品的总数目和总金额
        total_count = 0
        total_amount = Decimal(0)

        # 订单状态
        # if pay_method == OrderInfo.PAY_METHODS_ENUM['CASH']:
        #     status = OrderInfo.ORDER_STATUS_ENUM['UNSEND']
        # else:
        #     status = OrderInfo.ORDER_STATUS_ENUM['UNPAID']

        status = OrderInfo.ORDER_STATUS_ENUM['UNSEND'] if pay_method == OrderInfo.PAY_METHODS_ENUM['CASH'] else \
        OrderInfo.ORDER_STATUS_ENUM['UNPAID']

        # 从redis中获取用户要购买的商品id set
        redis_conn = get_redis_connection('cart')
        cart_selected_key = 'cart_selected_%s' % user.id
        # (b'<sku_id>', b'<sku_id>', ...)
        sku_ids = redis_conn.smembers(cart_selected_key)

        # 从redis中获取用户购物车商品的id和对应数量count hash
        cart_key = 'cart_%s' % user.id
        # {
        #     b'<sku_id>': b'<count>',
        #     ...
        # }
        cart_dict = redis_conn.hgetall(cart_key)

        with transaction.atomic():
            # 凡是在with语句块中，涉及到数据库操作的代码，都会放在同一个事务中

            # 设置一个mysql事务保存点
            sid = transaction.savepoint()

            try:
                # TODO: 向订单信息表中添加一条数据
                order = OrderInfo.objects.create(
                    order_id=order_id,
                    user=user,
                    address=address,
                    total_count=total_count,
                    total_amount=total_amount,
                    freight=freight,
                    pay_method=pay_method,
                    status=status
                )

                # TODO: 订单中包含几个商品，就需要向订单商品表中添加几条数据。
                for sku_id in sku_ids:
                    # 获取sku_id商品购买的数量
                    count = cart_dict[sku_id]
                    count = int(count)

                    # 根据sku_id获取对应的商品
                    # select * from tb_sku where id=<sku_id>;
                    # sku = SKU.objects.get(id=sku_id)

                    # select * from tb_sku where id=<sku_id> for update;
                    print('user: %s try get lock' % user.id)
                    sku = SKU.objects.select_for_update().get(id=sku_id)
                    print('user: %s get locked' % user.id)

                    # 商品库存量
                    if count > sku.stock:
                        # 商品库存不足，将mysql事务回滚到sid保存点
                        transaction.savepoint_rollback(sid)
                        raise serializers.ValidationError('商品库存不足')

                    # 模拟订单并发
                    # print('user: %s' % user.id)
                    import time
                    time.sleep(10)

                    # 商品库存减少，销量增加
                    # update tb_sku
                    # set stock=<new_stock>, sales=<new_sales>
                    # where id=<sku_id>;
                    sku.stock -= count
                    sku.sales += count
                    sku.save()

                    # 向订单商品表中添加一条记录
                    OrderGoods.objects.create(
                        order=order,
                        sku=sku,
                        count=count,
                        price=sku.price
                    )

                    # 累加计算订单中商品的总数量和总金额
                    total_count += count
                    total_amount += count * sku.price

                # 更新order中订单商品总数量和订单总金额
                order.total_count = total_count
                order.total_amount = total_amount + freight
                order.save()
            except serializers.ValidationError:
                # 继续向外抛出异常
                raise
            except Exception as e:
                # 订单保存出错，将mysql事务回滚到sid保存点
                transaction.savepoint_rollback(sid)
                raise serializers.ValidationError('下单失败1')

        # TODO: 清除购物车中对应记录
        pl = redis_conn.pipeline()
        pl.hdel(cart_key, *sku_ids)
        pl.srem(cart_selected_key, *sku_ids)
        pl.execute()

        return order