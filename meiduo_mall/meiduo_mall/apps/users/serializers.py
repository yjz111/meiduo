import re
from django.core.mail import send_mail
from django.conf import settings
from django_redis import get_redis_connection
from rest_framework import serializers
from rest_framework_jwt.settings import api_settings
from  . import  constants
from .models import User,Address
from  goods.models import SKU

class EmailSerializer(serializers.ModelSerializer):
    # serializers.EmailField

    class Meta:
        model = User
        fields = ('id', 'email')

    def update(self, instance, validated_data):
        """保存用户的邮箱信息并且给用户的邮箱发送激活邮件"""
        # 保存用户的邮箱信息
        email = validated_data['email']
        instance.email = email
        instance.save()

        # TODO: 给用户的邮箱发送激活邮件
        # 发送的激活邮件中需要包含一个激活链接:
        # http://www.meiduo.site:8080/success_verify_email.html?user_id=<user_id>
        # 使用itsdangerous对用户的信息进行加密，生成token，把token放在链接中
        # http://www.meiduo.site:8080/success_verify_email.html?token=<token>
        verify_url = instance.generate_verify_email_url()

        # 发送邮件
        # subject = "美多商城邮箱验证"
        # html_message = '<p>尊敬的用户您好！</p>' \
        #                '<p>感谢您使用美多商城。</p>' \
        #                '<p>您的邮箱为：%s 。请点击此链接激活您的邮箱：</p>' \
        #                '<p><a href="%s">%s<a></p>' % (email, verify_url, verify_url)
        # send_mail(subject, '', settings.EMAIL_FROM, [email], html_message=html_message)

        # 发出发送邮件的任务
        from celery_tasks.email.tasks import send_verify_email
        send_verify_email.delay(email, verify_url)

        return instance


class UserDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'mobile', 'email', 'email_active')


class CreateUserSerializer(serializers.ModelSerializer):
    password2 = serializers.CharField(label='确认密码', write_only=True)
    sms_code = serializers.CharField(label='短信验证码', write_only=True)
    allow = serializers.CharField(label='同意协议', write_only=True)
    token = serializers.CharField(label='登录状态token', read_only=True)  # 增加token字段

    class Meta:
        model = User
        fields = ('id', 'username', 'password', 'mobile', 'password2', 'sms_code', 'allow', 'token')
        extra_kwargs = {
            'username': {
                'min_length': 5,
                'max_length': 20,
                'error_messages': {
                    'min_length': '仅允许5-20个字符的用户名',
                    'max_length': '仅允许5-20个字符的用户名',
                }
            },
            'password': {
                'write_only': True,
                'min_length': 8,
                'max_length': 20,
                'error_messages': {
                    'min_length': '仅允许8-20个字符的密码',
                    'max_length': '仅允许8-20个字符的密码',
                }
            }
        }

    def validate_mobile(self, value):
        """手机号是否合法"""
        if not re.match(r'^1[3-9]\d{9}$', value):
            raise serializers.ValidationError('手机号不合法')

        return value

    def validate_allow(self, value):
        """是否同意协议"""
        if value != 'true':
            raise serializers.ValidationError('请同意协议')

        return value

    def validate(self, attrs):
        """两次密码是否一致，短信验证码是否正确"""
        # 两次密码是否一致
        password = attrs['password']
        password2 = attrs['password2']

        if password != password2:
            raise serializers.ValidationError('两次密码不一致')

        # 短信验证码是否正确
        mobile = attrs['mobile']
        sms_code = attrs['sms_code'] # str

        # 根据`mobile`获取真实的短信验证码文本
        redis_conn = get_redis_connection('verify_codes')
        real_sms_code = redis_conn.get('sms_%s' % mobile) # bytes

        if not real_sms_code:
            raise serializers.ValidationError('短信验证码无效')

        if sms_code != real_sms_code.decode():
            raise serializers.ValidationError('短信验证码错误')

        return attrs

    def create(self, validated_data):
        """创建新用户并保存注册用户信息"""
        # 清除无用的数据
        del validated_data['password2']
        del validated_data['sms_code']
        del validated_data['allow']

        # 创建新用户
        user = super().create(validated_data)

        # 对注册用户的密码进行加密
        password = validated_data['password']
        user.set_password(password)
        user.save()

        # 签发一个JWT token信息
        jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
        jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER

        payload = jwt_payload_handler(user) # 产生payload
        token = jwt_encode_handler(payload) # 生成一个token

        # 给user对象增加一个属性token，用来保存JWT token信息
        user.token = token

        return user




class UserAddressSerializer(serializers.ModelSerializer):
    """
    用户地址序列化器
    """
    province = serializers.StringRelatedField(read_only=True)
    city = serializers.StringRelatedField(read_only=True)
    district = serializers.StringRelatedField(read_only=True)
    province_id = serializers.IntegerField(label='省ID', required=True)
    city_id = serializers.IntegerField(label='市ID', required=True)
    district_id = serializers.IntegerField(label='区ID', required=True)

    class Meta:
        model = Address
        exclude = ('user', 'is_deleted', 'create_time', 'update_time')

    def validate_mobile(self, value):
        """
        验证手机号
        """
        if not re.match(r'^1[3-9]\d{9}$', value):
            raise serializers.ValidationError('手机号格式错误')
        return value

    def create(self, validated_data):
        """
        保存
        """
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

class AddressTitleSerializer(serializers.ModelSerializer):
    """地址标题"""
    class Meta:
        model = Address
        fields = ('title',)



class AddUserBrowseHistorySerializer(serializers.Serializer):
    sku_id = serializers.IntegerField(label='商品SKU编号')

    def validate_sku_id(self, value):
        """商品是否存在"""
        try:
            sku = SKU.objects.get(id=value)
        except SKU.DoesNotExist:
            raise serializers.ValidationError('商品不存在')

        return value

    def create(self, validated_data):
        """在redis中保存用户的历史浏览记录"""
        # 获取用户浏览的商品id
        sku_id = validated_data['sku_id']

        # 获取登录用户user
        user = self.context['request'].user

        # 获取redis链接
        redis_conn = get_redis_connection('history')
        pl = redis_conn.pipeline()
        history_key = 'history_%s' % user.id

        # 保存用户的历史浏览记录
        # 去重
        pl.lrem(history_key, 0, sku_id)

        # 左侧加入
        pl.lpush(history_key, sku_id)

        # 截取
        pl.ltrim(history_key, 0, constants.USER_BROWSING_HISTORY_COUNTS_LIMIT-1)

        pl.execute()

        return validated_data

