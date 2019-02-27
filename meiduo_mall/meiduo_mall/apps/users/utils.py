def jwt_response_payload_handler(token,user=None,request=None):
    """自定义jwt认证成功返回数据"""
    return {
        'token':token,
        'user_id':user.id,
        'username':user.username
    }

#自定义Django的认证系统后端
import  re
from  .models import User
from  django.contrib.auth.backends import ModelBackend


def get_user_by_account(acccount):  #account形参
    """account用户名或者手机号"""
    try:
        if re.match(r'^1[3-9]\d{9}$',acccount):
            user = User.objects.get(mobile=acccount)
        else:
            user = User.objects.get(username =acccount)
    except User.DoesNotExist:
        user=None

    return  user

#定义了这个方法,到了 user = get_user_by_account(username)才执行,username作为参数，方法被调用～～

class UsernameMobileAuthBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        """根据用户名或者手机号进行用户的认证
        根据用户名或者手机号查询用户
        """
        user = get_user_by_account(username)
        if user and user.check_password(password):
            return  user