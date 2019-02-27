#定义任务函数 文件名tasks固定
from  celery_tasks.main import celery_app
from  .yuntongxun.sms import  CCP
import  logging
#发送短信模板ID
SMS_CODE_TEMP_ID = 1

#获取日志器
logger = logging.getLogger('django')

@celery_app.task(name='send_sms_code')
def send_sms_code(mobile,sms_code,expires):
    print('发送短信的任务函数被调用:mobile:%s sms_code:%s%'%(mobile,sms_code))
    try:
        res = CCP().send_template_sms(mobile, [sms_code, expires],SMS_CODE_TEMP_ID)
    except Exception as e:
        logger.error('发送验证码短信[异常][mobile:%s,message:%s]'%(mobile,e))
    else:
        if res == 0:
            logger.info('发送验证码短信[正常][mobile:%s]' % (mobile))
        else:
            logger.info('发送验证码短信[失败][mobile:%s]' % (mobile))

