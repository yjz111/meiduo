
from celery import Celery

# 为celery使用django配置文件进行设置
import os
if not os.getenv('DJANGO_SETTINGS_MODULE'):
    os.environ['DJANGO_SETTINGS_MODULE'] = 'meiduo_mall.settings.dev'

# 创建Celery类的对象
# celery_app = Celery('celery_tasks', broker='redis://172.16.179.139:6379/3')
celery_app = Celery('celery_tasks')#里面就是个字符窜，随意

# 加载配置
celery_app.config_from_object('celery_tasks.config')

# 自动加载当前celery中的任务
celery_app.autodiscover_tasks(['celery_tasks.sms', 'celery_tasks.email','celery_tasks.html'])

