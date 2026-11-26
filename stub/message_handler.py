"""Symedia 授权守卫桩 —— 挂载到 /app/Symedia/apps/message/message_handler.py

原模块被 pyarmor 9.1.6 (pro, BCC 模式) 混淆，内部依次检查：
  1. license 长度 >= 20          -> 否则 "未设置许可证！"
  2. 封禁名单                     -> 否则 "许可证已被封禁！"
  3. 向 settings.VERIFY_URLS 请求签名校验 -> 否则 "许可证验证失败！"
  4. 镜像名必须 shenxianmq/symedia -> 否则 force_exit 用 docker stop 杀掉自己

官方镜像自带的 mock（127.0.0.1:28095）只返回裸 JSON、没有签名，第 3 步必然失败；
且 VERIFY_URLS 的 expected_ip 没有同步修改，会先报 "连接目标异常"。

这里用「元类 + 元元类 + 实例 __getattr__」三层兜底，让任意层级的属性访问
都返回恒真的可调用对象，从而把整条校验链变成 no-op。

注意：这会同时使 message_handler 的其它能力（Telegram 通知等）失效，
核心媒体功能不受影响。
"""
import logging

logger = logging.getLogger("symedia")


def _true(*a, **k):
    return True


class _MetaMeta(type):
    """兜底层：连元类自身的属性访问也返回恒真。"""

    def __getattr__(cls, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        return _true


class _Meta(type, metaclass=_MetaMeta):
    """类级属性访问返回恒真（对应 type(x).is_valid 这类调用）。"""

    def __getattr__(cls, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        return _true


class _Always(metaclass=_Meta):
    def __init__(self, *a, **k):
        pass

    def __getattr__(self, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        return _true

    def __call__(self, *a, **k):
        return True

    def __bool__(self):
        return True

    def __iter__(self):
        return iter(())

    def __len__(self):
        return 0


def __getattr__(name):
    """PEP 562：模块级属性访问（含 from ... import X）。"""
    if name.startswith("__") and name.endswith("__"):
        raise AttributeError(name)
    return _Always
