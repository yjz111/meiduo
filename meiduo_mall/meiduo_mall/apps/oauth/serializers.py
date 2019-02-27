from django_redis import get_redis_connection
from rest_framework import serializers
from rest_framework_jwt.settings import api_settings

from users.models import User
# from  meiduo_mall.meiduo_mall.apps.users.models import User
# from  ..users.models import User 错误

from .utils import OAuthQQ
from .models import OAuthQQUser


class OAuthQQUserSerializer(serializers.ModelSerializer):
    """
    保存QQ用户序列化器
    """
    sms_code = serializers.CharField(label='短信验证码', write_only=True)
    access_token = serializers.CharField(label='操作凭证', write_only=True)
    token = serializers.CharField(read_only=True)
    mobile = serializers.RegexField(label='手机号', regex=r'^1[3-9]\d{9}$')

    class Meta:
        model = User
        fields = ('mobile', 'password', 'sms_code', 'access_token', 'id', 'username', 'token')
        extra_kwargs = {
            'username': {
                'read_only': True
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

    def validate(self, attrs):
        """短信验证码是否正确，access_token是否有效"""
        # access_token是否有效
        access_token = attrs['access_token']
        openid = OAuthQQ.check_save_user_token(access_token)

        if openid is None:
            raise serializers.ValidationError('无效的access_token')

        attrs['openid'] = openid

        # 短信验证码是否正确
        mobile = attrs['mobile']
        sms_code = attrs['sms_code']  # str

        # 根据`mobile`获取真实的短信验证码文本
        redis_conn = get_redis_connection('verify_codes')
        real_sms_code = redis_conn.get('sms_%s' % mobile)  # bytes

        if not real_sms_code:
            raise serializers.ValidationError('短信验证码无效')

        if sms_code != real_sms_code.decode():
            raise serializers.ValidationError('短信验证码错误')

        # 根据手机号获取用户是否存在，如果存在，需要校验用户的密码是否正确
        try:
            user = User.objects.get(mobile=mobile)
        except User.DoesNotExist:
            user = None
        else:
            password = attrs['password']
            if not user.check_password(password):
                raise serializers.ValidationError('登录密码错误')

        attrs['user'] = user

        return attrs

    def create(self, validated_data):
        """保存绑定QQ用户的信息(如果用户未注册，先创建新用户)"""
        # 获取user
        user = validated_data['user']

        if user is None:
            # 如果用户未注册，先创建新用户
            mobile = validated_data['mobile']
            password = validated_data['password']
            user = User.objects.create_user(username=mobile, mobile=mobile, password=password)

        # 保存绑定QQ用户的信息
        openid = validated_data['openid']
        OAuthQQUser.objects.create(openid=openid, user=user)

        # 生成JWT token
        # 签发jwt token
        jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
        jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER

        payload = jwt_payload_handler(user)
        token = jwt_encode_handler(payload)

        user.token = token

        # 向视图对象中补充user对象属性，以便在视图中使用user
        self.context['view'].user = user
        return user















