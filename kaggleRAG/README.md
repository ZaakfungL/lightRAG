# LightRAG准确性测试工具

这个工具用于测试LightRAG在问答任务上的准确性，基于`train_QA.csv`数据集。

## 功能特性

- 🚀 自动化测试LightRAG查询准确度
- 📊 多维度评估指标（答案相似度、参考文献准确度）
- 📝 详细的测试报告和统计信息
- 🔧 灵活的配置选项
- 📋 完整的日志记录

## 文件结构

```
kaggleRAG/
├── train_QA.csv                    # 测试数据集
├── test_lightrag_accuracy.py       # 主要测试脚本
├── run_test.sh                     # 简化运行脚本
├── README.md                       # 使用说明
└── results/                        # 测试结果输出目录
    ├── lightrag_test_results_*.csv    # 详细结果CSV
    ├── lightrag_test_statistics_*.json # 统计信息JSON
    └── lightrag_full_results_*.json    # 完整结果JSON
```

## 快速开始

### 1. 环境准备

确保LightRAG API服务正在运行：
```bash
lightrag-server
```

### 2. 安装依赖

```bash
pip3 install requests pandas
```

### 3. 运行测试

#### 方式一：使用简化脚本（推荐）

测试前10个样本：
```bash
./run_test.sh
```

测试指定数量的样本：
```bash
./run_test.sh 20
```

测试全部样本：
```bash
./run_test.sh all
```

#### 方式二：直接运行Python脚本

```bash
python3 test_lightrag_accuracy.py
```

### 4. 查看结果

测试完成后，结果会保存在`results/`目录中：
- `lightrag_test_results_*.csv`: 包含每个问题的详细测试结果
- `lightrag_test_statistics_*.json`: 总体统计信息
- `lightrag_full_results_*.json`: 完整的测试数据

## 核心功能说明

### 1. 数据处理

- 自动读取`train_QA.csv`文件
- 提取`id`和`question`作为查询输入
- 处理`answer_value`和`ref_id`作为评估标准

### 2. LightRAG查询

- 使用`/query`端点进行查询
- 查询格式：`{id}: {question}`
- 默认使用`mix`模式，包含参考文献
- 自动提取答案和参考文献信息

### 3. 评估指标

#### 答案相似度 (Answer Similarity)
- 计算预测答案与标准答案的文本相似度
- 支持包含关系检查和词汇重叠度计算
- 分数范围：0-1

#### 参考文献准确度 (Reference Accuracy)
- 从文件路径中提取arXiv ID
- 比较预测参考文献与标准参考文献的匹配度
- 分数范围：0-1

#### 准确率统计
- 答案准确率：相似度 > 0.5 的样本比例
- 参考文献准确率：准确度 > 0.5 的样本比例

### 4. 结果输出

#### 控制台输出
```
=====================================
测试完成 - 最终统计结果
=====================================
总样本数: 10
成功查询数: 10
失败查询数: 0
平均答案相似度: 0.654
答案准确率 (相似度>0.5): 0.700
平均参考文献准确度: 0.234
参考文献准确率 (准确度>0.5): 0.300
=====================================
```

#### CSV结果文件
包含每个测试样本的详细信息：
- 问题ID和内容
- 标准答案和预测答案
- 相似度分数
- 参考文献对比
- 查询时间
- 错误信息（如有）

## 配置选项

在`test_lightrag_accuracy.py`中可以修改以下配置：

```python
# API配置
api_base_url = "http://localhost:9621"

# 查询参数
payload = {
    "query": f"{question_id}: {question}",
    "mode": "mix",                    # 查询模式
    "include_references": True,       # 包含参考文献
    "response_type": "Multiple Paragraphs",
    "top_k": 10                      # 检索数量
}

# 测试配置
max_samples = 10                    # 测试样本数
output_dir = "./results"           # 输出目录
```

## 故障排除

### 1. API服务连接失败
```bash
Error: 无法连接到API服务
```
**解决方案：**
- 确保LightRAG服务正在运行：`lightrag-server`
- 检查服务地址：`http://localhost:9621`

### 2. CSV文件读取失败
```bash
Error: 加载CSV文件失败
```
**解决方案：**
- 确保`train_QA.csv`文件存在
- 检查文件格式是否正确

### 3. 依赖包缺失
```bash
ModuleNotFoundError: No module named 'requests'
```
**解决方案：**
```bash
pip3 install requests pandas
```

### 4. 查询超时
如果查询经常超时，可以：
- 减少并发数量
- 增加超时时间
- 检查LLM服务状态

## 高级用法

### 自定义评估逻辑

可以修改`calculate_answer_similarity`和`evaluate_reference_accuracy`方法来实现自定义的评估逻辑。

### 批量测试

对于大规模测试，建议：
1. 分批运行（每次50-100个样本）
2. 监控API服务状态
3. 保存中间结果

### 结果分析

使用pandas分析结果：
```python
import pandas as pd

# 读取结果
df = pd.read_csv('results/lightrag_test_results_*.csv')

# 分析答案相似度分布
print(df['answer_similarity'].describe())

# 查找低分样本
low_score = df[df['answer_similarity'] < 0.3]
print(low_score[['id', 'question', 'ground_truth_answer', 'predicted_answer']])
```

## 贡献

欢迎提交Issue和Pull Request来改进这个测试工具！

## 许可证

本项目遵循LightRAG的许可证。