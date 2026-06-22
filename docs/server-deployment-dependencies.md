# 服务器部署依赖说明

这份说明用于在腾讯云服务器更新后端功能时补齐必要依赖。部署代码时请只更新代码文件和依赖文件，不要覆盖服务器上的 `.env`、`data/users.db`、`data/reports/` 等运行数据。

## Python 依赖

后端虚拟环境中安装：

```bash
cd /root/AI-Elderly-Care-Health-Report-Multi-Agent-System
.venv/bin/python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

`requirements.txt` 中包含当前服务器运行所需的核心依赖：

- FastAPI / Uvicorn：后端服务
- OpenAI：大模型回复与报告生成
- edge-tts：晓晓语音合成
- google-cloud-speech：语音识别能力
- reportlab / fonttools：PDF 导出和 TTC 中文字体集合处理
- pypdf：PDF 文档读取
- pydantic / python-dotenv / python-multipart：接口与配置基础能力

## 系统依赖

PDF 导出中文内容时需要服务器安装中文字体。OpenCloudOS / CentOS 系服务器可先尝试：

```bash
dnf install -y fontconfig google-noto-sans-cjk-fonts
fc-cache -fv
```

如果系统没有 `dnf` 或找不到该字体包，可改用：

```bash
yum install -y fontconfig google-noto-sans-cjk-fonts
fc-cache -fv
```

如果仍然找不到字体包，需要手动安装任一可用中文字体，例如 Noto Sans CJK、Source Han Sans、WenQuanYi Micro Hei，并确保 `fc-list` 能列出中文字体。

## 验证命令

安装完成后可在服务器执行：

```bash
cd /root/AI-Elderly-Care-Health-Report-Multi-Agent-System
.venv/bin/python - <<'PY'
import edge_tts
import openai
import reportlab
print("Python dependencies ok")
PY
```

检查后端服务：

```bash
systemctl restart ai-elderly-care.service
systemctl status ai-elderly-care.service --no-pager
curl --noproxy '*' -i http://127.0.0.1:18080/docs
```

检查语音合成：

```bash
curl --noproxy '*' -i -X POST http://127.0.0.1:18080/tts/synthesize \
  -H "Content-Type: text/plain" \
  --data "你好，这是晓晓语音测试。" \
  -o /tmp/xiaoxiao.mp3
ls -lh /tmp/xiaoxiao.mp3
```
