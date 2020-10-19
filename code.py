
import requests
import json
import time
from datetime import datetime
from mail import SendEmail
import base64
import hashlib

CONFIG_FILE = "config.json" # 配置文件
DEFAULT_INTERVAL = 10  # 默认 10 分钟扫描一次
DEFAULT_TIME_DELTA = 2 # 默认只推送最近 2 天的消息

def md5(content:str, ts=None):
    content = content.encode('utf-8')
    crypt_field = hashlib.md5(content)
    if ts:
        ts = ts.encode('utf-8')
        crypt_field.update(ts)
    return crypt_field.hexdigest()

def get_config(file):
    try:
        # 如果有配置文件
        with open(file, 'r') as file_obj:
            config = json.loads(file_obj.read())
        return config
    except FileNotFoundError:
        # 没有配置文件，进行初始化
        print("初始化中，请先完善信息")
        user_name = input("学习通账号：")
        password = input("学习通密码：")
        qq = input("接收消息的 QQ 号：")
        config = {
            'user_name': user_name,
            'password': password,
            'qq': qq,
            'interval': 10,
            'time_delta': 2
        }
        print("正在生成 config.json 文件，具体配置可以在其中修改")
        with open(file, 'a') as file_obj:
            json.dump(config, file_obj)
        return config

class XueXiTongMessageTrans():

    READ_ITEMS_FILE = "read_msg.json" # 存放已阅览消息的 id

    def __init__(self, user_name: str, password: str, qq: str, other_config: dict):
        self.user_name = user_name
        self.password = password
        self.qq = qq
        self.WATCH_TIME_INTERVAL = other_config['interval']
        self.TIME_DELTA = other_config['time_delta']
        self.visited_items = self.get_read_items()
        self.data = self.get_items()
        self.email_sender = SendEmail("学习通消息通知")

    def get_crypt_user(self):
        password = str(base64.b64encode(self.password.encode('utf-8')))
        return {
            'uname': self.user_name,
            'password': password[2:len(password)-1]
        }

    def get_cookies(self):
        """
            需要的 Cookies 字段为
                fid
                _d
                UID
                vc3
            fid=xxx;
            _d=160303033xxxx;
            UID=103194xxx;
            vc3=xxxJBRbWTRtevhuICV9V0Yp8fr6zl%2FPi%2BDPdgafchZMf904ECvfqsryiX7O8M9%2BiEmGhf4mqqdT6%2FHzDuJNgXZXY07vvm096RrKWf88PaucZ1Kcmunbq0I1DCcD99EAHujAkVolTzjD%2FCC2OXcH6FeXn3R0AMR8y82eIeEitndU%3D3847ebbce53753ff6b3c482291b09xxx
        """
        user = self.get_crypt_user()
        data = {
            **user,
            'fid': -1,
            'refer': 'http%3A%2F%2Fi.chaoxing.com',
            't': 'true'
        }
        req = requests.post('https://passport2.chaoxing.com/fanyalogin', data=data)
        cookies_obj = req.cookies._cookies['.chaoxing.com']['/']
        cookies = f"fid={cookies_obj['fid'].value}; _d={cookies_obj['_d'].value}; UID={cookies_obj['UID'].value}; vc3={cookies_obj['vc3'].value}"
        return cookies

    def get_items(self):
        # 获取学习通消息
        params = {
            "type": 2,
            "notice_type": '',
            "lastValue": '',
            "folderUUID": '',
            "kw": '',
            "startTime": '',
            "endTime": '',
            "gKw": '',
            "gName": ''
        }

        headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.121 Safari/537.36 Edg/85.0.564.70",
            "Cookie": self.get_cookies()
        }

        req = requests.post('http://notice.chaoxing.com/pc/notice/getNoticeList',
                            data=params,
                            headers=headers)
        return json.loads(req.content)

    def watch_items(self):

        def match_time(cur_time: datetime, pre_time: datetime):
            # 判断时间之差是否大于 TIME_DELTA，大于 TIME_DELTA 说明第一条消息已经是很早之前的消息，
            # 之后就没必要去判断其他消息
            return (cur_time - pre_time).days <= self.TIME_DELTA

        def send_email(email_sender: SendEmail, content: str):
            qq_email = f"{self.qq}@qq.com"
            email_sender.send(content, '', [qq_email])

        items = self.data["notices"]["list"]
        first_item_time = datetime.strptime(
            items[0]["completeTime"], "%Y-%m-%d %H:%M:%S")
        current_time = datetime.today()

        assert match_time(current_time, first_item_time), '\n\n无最新消息\n\n'

        for item in items:
            id = item["idCode"]
            item_time = datetime.strptime(
                item["completeTime"], "%Y-%m-%d %H:%M:%S")
            if match_time(current_time, item_time) and \
                    id not in self.visited_items:
                print("收到新消息!")
                content = item["content"]
                send_email(self.email_sender, content)
                self.visited_items.append(id)
            else:
                break
        self.set_read_items()
        print("\n\n消息扫描完毕, 扫描完成时间 {}\n\n".
              format(datetime.today()))

        self.email_sender.quit()

    def get_read_items(self):
        try:
            with open(self.READ_ITEMS_FILE, 'r') as file_obj:
                data = json.load(file_obj)
        except Exception:
            with open(self.READ_ITEMS_FILE, 'a'):
                pass
            return []
        return data

    def set_read_items(self):
        with open(self.READ_ITEMS_FILE, 'w') as file_obj:
            json.dump(self.visited_items, file_obj)


config = get_config(CONFIG_FILE)

interval = config.get('interval') or DEFAULT_INTERVAL
time_delta = config.get('time_delta') or DEFAULT_TIME_DELTA

while True:
    try:
        message_trans = XueXiTongMessageTrans(
            config['user_name'],
            config['password'],
            config['qq'],
            {
                'interval': interval,
                'time_delta': time_delta
            }
        )
        message_trans.watch_items()
    except Exception as e:
        print(e)
    time.sleep(interval * 60)

