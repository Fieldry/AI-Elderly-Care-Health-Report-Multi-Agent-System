# PageIndex RAG 接入说明

## 1. 如何使用

当前项目已经把 `PageIndex` 封装成了一个可单独使用的 `RAG Agent`。

相关文件：

- `backend/code/rag/agent.py`
- `backend/code/rag_agent_cli.py`

支持两类操作：

1. **建立索引**
2. **基于索引检索**

### 1.1 建立索引

在 `backend` 目录下执行：

```bash
.venv/bin/python code/rag_agent_cli.py build <文档或目录路径> --output <索引输出路径>
```

例如：

```bash
.venv/bin/python code/rag_agent_cli.py build data/guidelines/中国健康老年人标准.pdf --output data/rag_indexes/中国健康老年人标准_index.json
```

### 1.2 查询索引

```bash
.venv/bin/python code/rag_agent_cli.py query "<你的问题>" --index <索引文件路径> --top-k 3
```

例如：

```bash
.venv/bin/python code/rag_agent_cli.py query "中国健康老年人应满足哪些要求？" --index data/rag_indexes/中国健康老年人标准_index.json --top-k 3
```

如果想看完整 JSON 结果：

```bash
.venv/bin/python code/rag_agent_cli.py query "中国健康老年人应满足哪些要求？" --index data/rag_indexes/中国健康老年人标准_index.json --top-k 3 --json
```

---

## 2. 如何与目前的项目流程接入

当前项目的主流程在：

- `backend/code/multi_agent_system_v2.py`

接入方式是：

1. 先由 `PageIndexRAGAgent` 加载索引；
2. 在主流程中完成：
   - 状态判定
   - 风险预测
   - 因素分析
3. 然后执行一轮 **RAG 知识检索**；
4. 把检索结果注入：
   - `ActionPlanAgent`
   - `ReportAgentV2`

也就是说，它现在是以一个**独立知识检索 Agent** 的形式接入原有多 Agent 流程的。

### 2.1 开启方式

在 `backend/.env` 中配置：

```env
RAG_ENABLED=true
RAG_INDEX_PATH=data/rag_indexes/中国健康老年人标准_index.json
RAG_TOP_K=3
```

如果需要指定 RAG 使用的模型，也可以加：

```env
RAG_MODEL=deepseek-chat
```

### 2.2 接入后的流程

启用后，主流程会变成：

1. 状态判定
2. 风险预测
3. 因素分析
4. 知识检索（RAG）
5. 行动计划生成
6. 优先级排序
7. 审核
8. 报告生成

如果 `RAG_ENABLED=false`，则不会执行第 4 步。

---

## 3. 从建立索引到使用的完整流程

### 第一步：准备知识文档

把要索引的文档放到项目中，例如：

- `backend/data/guidelines/中国健康老年人标准.pdf`

### 第二步：建立索引

进入后端目录：

```bash
cd backend
```

执行：

```bash
.venv/bin/python code/rag_agent_cli.py build data/guidelines/中国健康老年人标准.pdf --output data/rag_indexes/中国健康老年人标准_index.json
```

建立完成后会得到：

- `backend/data/rag_indexes/中国健康老年人标准_index.json`

### 第三步：单独测试检索

```bash
.venv/bin/python code/rag_agent_cli.py query "评估标准中躯体健康、心理健康、社会健康的评分阈值是什么？" --index data/rag_indexes/中国健康老年人标准_index.json --top-k 5
```

### 第四步：接入主流程

修改 `backend/.env`：

```env
RAG_ENABLED=true
RAG_INDEX_PATH=data/rag_indexes/中国健康老年人标准_index.json
RAG_TOP_K=3
```

### 第五步：启动后端

```bash
cd backend
.venv/bin/python api/server.py
```

或者使用你当前项目已有的启动方式。

### 第六步：正常调用原有报告流程

后端收到生成报告请求后，会自动：

1. 加载 RAG 索引；
2. 按当前用户画像生成检索 query；
3. 检索出相关知识片段；
4. 把知识片段注入行动建议和报告生成阶段。

---

## 4. 一些使用实例

### 实例 1：对单个 PDF 建立索引

```bash
cd backend
.venv/bin/python code/rag_agent_cli.py build data/guidelines/中国健康老年人标准.pdf --output data/rag_indexes/中国健康老年人标准_index.json
```

### 实例 2：查询“健康老年人应满足哪些要求”

```bash
.venv/bin/python code/rag_agent_cli.py query "中国健康老年人应满足哪些要求？" --index data/rag_indexes/中国健康老年人标准_index.json --top-k 3
```

适合查看标准正文中的核心判定条款。

### 实例 3：查询“评分阈值”

```bash
.venv/bin/python code/rag_agent_cli.py query "评估标准中躯体健康、心理健康、社会健康的评分阈值是什么？" --index data/rag_indexes/中国健康老年人标准_index.json --top-k 5
```

适合命中：

- `评估标准`
- `附录Ａ（规范性） 中国健康老年人评估表`

### 实例 4：接入主流程使用

`backend/.env`：

```env
RAG_ENABLED=true
RAG_INDEX_PATH=data/rag_indexes/中国健康老年人标准_index.json
RAG_TOP_K=3
```

启动后端后，原来的报告流程会自动多出一轮知识检索，不需要改单独的接口调用方式。

### 实例 5：更换为其他知识文档

如果后续要换成其他指南，只需要重新建索引并替换路径：

```bash
.venv/bin/python code/rag_agent_cli.py build data/guidelines/其他指南.pdf --output data/rag_indexes/其他指南_index.json
```

然后更新：

```env
RAG_INDEX_PATH=data/rag_indexes/其他指南_index.json
```

即可继续复用同一套项目流程。
