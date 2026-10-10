# 云服务器部署指南（IP 直接访问，无需域名）

本项目为 FastAPI + SQLite 的单体应用，无构建步骤，最低配服务器（1核1G）即可运行。

## 一、准备

- 一台 Linux 云服务器（Ubuntu 22.04/24.04 或 Debian 12 为例），能 SSH 登录
- 本地未提交的改动先 commit 并 push 到 GitHub，服务器上 clone 的是远端仓库

## 二、服务器上的操作

### 1. 拉取代码到 /opt

```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip git
sudo git clone https://github.com/Absoler/menstrual-tracker.git /opt/menstrual-tracker
```

### 2. 创建运行用户并安装依赖

```bash
sudo useradd --system --home /opt/menstrual-tracker --shell /usr/sbin/nologin tracker
cd /opt/menstrual-tracker
sudo python3 -m venv .venv
sudo .venv/bin/pip install -r requirements.txt
# 数据目录需要可写（SQLite 数据库与密钥都存在这里）
sudo mkdir -p data && sudo chown -R tracker:tracker /opt/menstrual-tracker
```

### 3. 安装 systemd 服务（开机自启、崩溃自动重启）

```bash
sudo cp deploy/menstrual-tracker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now menstrual-tracker
sudo systemctl status menstrual-tracker   # 看到 active (running) 即成功
```

之后查看日志 / 重启服务：

```bash
sudo journalctl -u menstrual-tracker -f    # 实时日志
sudo systemctl restart menstrual-tracker   # 更新代码后重启
```

### 4. 放行端口

两处都要放行 **8000/tcp**：

- 云控制台的**安全组 / 防火墙规则**（阿里云、腾讯云等默认只开 22 和 3389）
- 服务器系统防火墙（若启用了 ufw：`sudo ufw allow 8000/tcp`）

### 5. 访问

浏览器打开 `http://服务器公网IP:8000`，注册账号即可使用。

## 三、日常维护

### 更新版本

```bash
cd /opt/menstrual-tracker && sudo git pull
sudo systemctl restart menstrual-tracker
```

### 备份与迁移

数据全部在 `data/` 目录（`tracker.db` + `secret.key`）：

```bash
# 在服务器上打包（本地再用 scp/sftp 下载）
sudo tar czf tracker-backup.tar.gz -C /opt/menstrual-tracker data
```

换服务器时把 `data/` 目录放到新部署的同一位置即可完整迁移。

## 四、安全须知（IP + HTTP 的固有限制）

- 没有域名就无法签发免费 TLS 证书，登录密码会**明文经过公网**。个人自用可接受；
  若在意，可在安全组里把 8000 端口的来源限制为你自己的出口 IP，只允许你访问。
- `data/secret.key` 泄露等于他人可伪造登录令牌，不要把它提交进 git 或泄露出去。
- SQLite 并发写入能力有限，个人 / 少量用户使用没有问题，不要当公共服务开放注册。
