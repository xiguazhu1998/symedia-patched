"""Symedia 运行时兼容补丁 —— 挂载到 site-packages/sitecustomize.py

镜像里 telebot（pyTelegramBotAPI）用的是旧版 urllib3 API：

    # telebot/apihelper.py:18
    format_header_param = fields.format_header_param

但 urllib3 2.x 已把该符号重命名为 format_header_param_rfc2231 并删除了旧名，
导致 `import telebot` 抛 AttributeError → Symedia 的 init_routers 失败 →
主应用永远不绑定 18095 端口 → nginx 反向代理 502、前端只剩静态页。

这里在解释器启动早期（sitecustomize 由 site 模块自动导入）补回这个别名。
"""
import urllib3.fields as _fields

if not hasattr(_fields, "format_header_param"):

    def _format_header_param(name, value):
        return _fields.format_header_param_rfc2231(name, value)

    _fields.format_header_param = _format_header_param
