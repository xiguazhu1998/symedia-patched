# Symedia 免授权补丁镜像

`ghcr.io/xiguazhu1998/symedia:patched`

基于上游 `imjix/symedia:patched` 重建，修掉了**镜像本身**的四处问题，
并附带运行期补丁，使其可以正常启动、不自我退出。

> 本项目仅为镜像修复/部署脚本，不含上游任何程序代码。

## 一键部署

```bash
git clone https://github.com/xiguazhu1998/symedia-patched.git
cd symedia-patched
mkdir -p config logs media playwright
docker compose up -d
```

访问 `http://<NAS-IP>:8095`，默认账号 **admin / password**，登录后立即修改。

## 不用 git，纯 docker 命令

```bash
mkdir -p /vol1/1000/docker/symedia && cd /vol1/1000/docker/symedia
mkdir -p config logs media playwright stub

# 取回两个补丁文件
curl -fsSL -o stub/message_handler.py \
  https://raw.githubusercontent.com/xiguazhu1998/symedia-patched/main/stub/message_handler.py
curl -fsSL -o stub/sitecustomize.py \
  https://raw.githubusercontent.com/xiguazhu1998/symedia-patched/main/stub/sitecustomize.py

docker run -d --name symedia --restart unless-stopped \
  -p 8095:8095 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $PWD/config:/app/config \
  -v $PWD/logs:/logs \
  -v $PWD/media:/media \
  -v $PWD/playwright:/symedia/.cache/ms-playwright \
  -v $PWD/stub/message_handler.py:/app/Symedia/apps/message/message_handler.py:ro \
  -v $PWD/stub/sitecustomize.py:/usr/local/lib/python3.12/site-packages/sitecustomize.py:ro \
  -e TZ=Asia/Shanghai -e PORT=18095 -e NGINX_PORT=8095 \
  ghcr.io/xiguazhu1998/symedia:patched
```

## 镜像修复了什么

上游镜像 pull 都拉不下来，一层就 646MB，里面混了 **42 个 overlayfs 白化条目**
（`.wh.util.py` 之类，mode 0 / epoch 时间）。Docker 解包时会尝试把这类条目
`mknod` 成字符设备，而同层已存在同名实体文件，于是：

```
failed to register layer: failed to mknod('/usr/local/lib/python3.12/site-packages/
p115client/tool/__pycache__/offline.cpython-312.pyc', S_IFCHR, 0): file exists
```

修复：解包 → 删除全部 `.wh.*` → 重新 `docker import`，补回原镜像的
`ENV` / `ENTRYPOINT` / `WORKDIR` / `EXPOSE`。

> 这些白化条目是打包时直接 tar 了 overlay 的 upperdir 造成的，
> 单层镜像里毫无意义，删掉不影响任何文件。

## 为什么需要两个运行期补丁

### 1. urllib3 2.x 不兼容（必须）

`telebot/apihelper.py` 用了 urllib3 2.x 已删除的 `fields.format_header_param`。
`import telebot` 直接抛异常 → `init_routers` 失败 → 主应用卡死不绑 18095 →
nginx 502、前端只有静态页。

`stub/sitecustomize.py` 在解释器启动时补回这个别名。

### 2. 授权守卫（必须）

`Symedia/apps/message/message_handler.py` 被 pyarmor 9.1.6 (pro, BCC 模式) 混淆，
内部依次检查：license 长度 ≥ 20、封禁名单、向 `settings.VERIFY_URLS` 请求**带签名**的
校验响应，最后还检查自身容器镜像名必须是 `shenxianmq/symedia`，任一失败就通过
docker.sock 给自己发 `docker stop`（表现为启动 5 秒后 `Exited (143)`，
`docker events` 里能看到 `container kill signal:15`）。

上游自带 mock 只返回裸 JSON、没有签名，且 `VERIFY_URLS` 的 `expected_ip` 没同步，
所以校验必然失败。

`stub/message_handler.py` 用**元类 + 元元类 + 实例 `__getattr__`** 三层兜底：
任意层级的属性访问都返回恒真可调用对象，整条校验链变成 no-op。

三层缺一不可 —— 应用会执行 `type(x).is_valid` 这类调用，
只加一层元类会在元类自身的属性查找上抛 `AttributeError`。

**副作用**：`message_handler` 的其它能力（Telegram 消息收推）会失效，
核心媒体刮削/整理功能不受影响。

## 目录说明

| 宿主机 | 容器 | 用途 |
|---|---|---|
| `./config` | `/app/config` | 配置与数据库（`config.yaml` / `symedia.db`） |
| `./logs` | `/logs` | 订阅、CloudDrive 等模块日志 |
| `./media` | `/media` | 媒体库挂载点 |
| `./playwright` | `/symedia/.cache/ms-playwright` | 浏览器缓存，避免每次重启重下 167MB |
| `./stub` | 见 compose | 两个运行期补丁 |

**注意**：配置目录是 `/app/config`（应用 `ROOT_PATH=/app`），
不是 `/Config`。`CONFIG_DIR=/config` 这个环境变量是干扰项，小写目录在镜像里根本不存在。

## 验证

```bash
docker ps --filter name=symedia                   # 应为 Up，无 Restarting
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8095/   # 200
docker exec symedia ss -lntp | grep 18095         # LISTEN
```

日志里出现下面这行即代表完整启动：

```
apscheduler.scheduler - Next wakeup is due at ...
```

## 已知无害噪音

```
[crit] 35#35: cache file "/tmp/legacy-bin/xxx" is too small
```

镜像里 `/tmp/legacy-bin` 残留的 pip 卸载脚本，nginx 扫描时报警，不影响功能。

## 说明

镜像层里的白化条目已删除并重新打包，**不要用上游 `imjix/symedia:patched` 覆盖**。
重新 pull 会拿回坏的那个层。