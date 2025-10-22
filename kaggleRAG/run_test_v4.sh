#!/bin/bash

# LightRAG准确性测试运行脚本 V4 - 完整参考文献映射修复版
# 使用方法: ./run_test_v4.sh [测试样本数]

set -e

# 配置参数
CSV_PATH="./train_QA.csv"
OUTPUT_DIR="./results"
PYTHON_SCRIPT="test_lightrag_accuracy_v4.py"
MAX_SAMPLES=${1:-10}  # 默认测试10个样本，传入"all"测试全部

echo "======================================"
echo "LightRAG准确性测试脚本 V4"
echo "(完整参考文献映射修复版)"
echo "======================================"

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到python3"
    exit 1
fi

# 检查必要的Python包
echo "检查Python依赖..."
python3 -c "import requests, pandas" 2>/dev/null || {
    echo "安装必要的Python包..."
    pip3 install requests pandas
}

# 检查CSV文件
if [ ! -f "$CSV_PATH" ]; then
    echo "错误: 找不到CSV文件 $CSV_PATH"
    exit 1
fi

# 检查LightRAG API服务
echo "检查LightRAG API服务..."
if ! curl -s http://localhost:9621/health > /dev/null; then
    echo "错误: LightRAG API服务未运行"
    echo "请先启动LightRAG服务: lightrag-server"
    exit 1
fi

echo "API服务正常运行"

# 创建输出目录
mkdir -p "$OUTPUT_DIR"

# 运行测试
echo "开始测试..."
if [ "$MAX_SAMPLES" = "all" ]; then
    echo "测试全部样本"
    python3 "$PYTHON_SCRIPT" all
else
    echo "测试前 $MAX_SAMPLES 个样本"
    python3 "$PYTHON_SCRIPT" $MAX_SAMPLES
fi

echo "测试完成! 结果保存在 $OUTPUT_DIR 目录中"
echo ""
echo "生成的文件:"
echo "- lightrag_output_v4_*.csv: LightRAG输出表格（完整参考文献映射）"
echo "- lightrag_full_results_v4_*.csv: 完整结果表格（包含评分）"
echo "- lightrag_statistics_v4_*.json: 统计信息"
echo ""
echo "V4版本修复内容:"
echo "✅ 正确的ref_id映射: 2505.06371.md -> chung2025"
echo "✅ 正确的ref_url映射: 2505.06371.md -> https://arxiv.org/abs/2505.06371"
echo "✅ 支持29个预定义的arXiv ID到论文ID映射"
echo "✅ 完整的参考文献解析和替换逻辑"