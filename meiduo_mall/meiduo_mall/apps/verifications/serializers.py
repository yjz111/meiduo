from rest_framework import  serializers
from  django_redis import  get_redis_connection

class CheckImageCodeSerializer(serializers.Serializer):
    """图片验证码序列化器"""
    image_code_id = serializers.UUIDField()
    text = serializers.CharField(max_length=4,min_length=4)
    # 使用序列化器进行反序列化时，需要对数据进行验证后，才能获取验证成功的数据或保存成模型类对象。
    # 在序列化器中需要同时对多个字段进行比较验证时，可以定义validate方法来验证
    def validate(self, attrs):
        #获取图片验证码和用户输入的图片验证码
        image_code_id = attrs['image_code_id']
        text = attrs['text'] #str

        #判断60s内是否给用户的手机号发送过短信
        redis_conn = get_redis_connection('verify_codes')
        mobile = self.context['mobile']

        send_flag = redis_conn.get('send_flag_%s'%mobile)

        if send_flag:
            raise serializers.ValidationError("短信发送过于频繁")

        #根据image_code_id从redis中获取真实的图片验证码文本
        real_image_code = redis_conn.get('img_%s'%image_code_id) #bytes

        #判断图片验证码是否存在
        if not real_image_code:
            raise serializers.ValidationError('图片验证码无效')

        #将redis中的图片验证码删除防止重复使用
        try:
            redis_conn.delete('img_%s'%image_code_id)
        except Exception as  e:
            pass

        #进行比对.
        real_image_code = real_image_code.decode()
        if text.lower() !=real_image_code.lower():
            raise  serializers.ValidationError('图片验证码错误')

        return  attrs



