#定义任务函数 文件名tasks固定
from  celery_tasks.main import celery_app

@celery_app.task(name='send_sms_code')
def send_sms_code(a,b):
    print('发送短信的任务函数被调用:a:%s b:%s'%(a,b))