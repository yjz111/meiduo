from celery import  Celery

#为celery使用django配置文件进行设置
import  os

if not os.getenv('DJANGO_SETTINGS_MODULE'):
    os.environ['DJANGO_SETTING_MODULE'] = 'meiduo_mall.setting.dev'


#创建Celery类的对象,指定中间人(也可以在配置文件中指定)
# celery_app = Celery('celery_tasks',broker='redis://127.0.0.1:6379/3')#里面就是个字符窜，随意
celery_app = Celery('celery_tasks')#里面就是个字符窜，随意

#加载配置
celery_app.config_from_object('celery_tasks.config')

#自动加载当前celery中的任务
celery_app.autodiscover_tasks(['celery_tasks.sms'])