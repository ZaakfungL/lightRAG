#!/usr/bin/env python3
"""
简洁的LightRAG测试脚本

功能：
1. 读取train QA，获取id和question
2. 向LightRAG发送请求获取JSON
3. 使用固定映射表将ref_url映射到ref_id (如 2505.06371.md -> chung2025)
4. 合并保存CSV并进行评分

使用方法：
  python simple_rag_test.py                    # 运行所有问题
  python simple_rag_test.py 5                  # 运行前5个问题
  python simple_rag_test.py 10                 # 运行前10个问题
  python simple_rag_test.py 5 33               # 从第33行开始运行5个问题
  python simple_rag_test.py 10 35              # 从第35行开始运行10个问题
  python simple_rag_test.py 0 33               # 从第33行开始运行所有剩余问题
"""

import pandas as pd
import requests
import json
import time
import sys
from typing import Dict, Any


def query_lightrag(question_id: str, question: str, api_url: str = "http://localhost:9621") -> Dict[str, Any]:
    """
    向LightRAG发送查询请求

    Args:
        question_id: 问题ID
        question: 问题内容
        api_url: API地址

    Returns:
        LightRAG响应JSON
    """
    try:
        payload = {
            "query": question,
            "mode": "naive",
            "chunk_top_k": 3
        }

        response = requests.post(
            f"{api_url}/query",
            json=payload,
            timeout=120
        )

        if response.status_code == 200:
            return response.json()
        else:
            print(f"   ❌ 查询失败 {question_id}: {response.status_code}")
            return {"error": f"API错误: {response.status_code}"}

    except Exception as e:
        print(f"   ❌ 查询异常 {question_id}: {e}")
        return {"error": str(e)}


def parse_rag_response(response: Dict[str, Any], question_id: str) -> Dict[str, Any]:
    """
    解析LightRAG响应

    Args:
        response: LightRAG响应
        question_id: 问题ID

    Returns:
        解析后的字段字典
    """
    try:
        if "error" in response:
            return {
                "rag_answer": f"查询失败: {response['error']}",
                "rag_answer_value": "is_blank",
                "rag_ref_id": "is_blank",
                "rag_answer_unit": "is_blank",
                "rag_supporting_materials": "is_blank",
                "rag_explanation": "is_blank"
            }

        # 解析JSON格式的response
        response_text = response.get("response", "{}")

        try:
            parsed = json.loads(response_text)
            if isinstance(parsed, dict):
                return {
                    "rag_answer": parsed.get("answer", "未知"),
                    "rag_answer_value": parsed.get("answer_value", "is_blank"),
                    "rag_ref_id": parsed.get("ref_id", "is_blank"),
                    "rag_answer_unit": parsed.get("answer_unit", "is_blank"),
                    "rag_supporting_materials": parsed.get("supporting_materials", "is_blank"),
                    "rag_explanation": parsed.get("explanation", "is_blank")
                }
        except json.JSONDecodeError:
            pass

        # 如果解析失败，返回原始响应
        return {
            "rag_answer": response_text,
            "rag_answer_value": "is_blank",
            "rag_ref_id": "is_blank",
            "rag_answer_unit": "is_blank",
            "rag_supporting_materials": "is_blank",
            "rag_explanation": "is_blank"
        }

    except Exception as e:
        print(f"   ⚠️  解析响应失败 {question_id}: {e}")
        return {
            "rag_answer": "解析失败",
            "rag_answer_value": "is_blank",
            "rag_ref_id": "is_blank",
            "rag_answer_unit": "is_blank",
            "rag_supporting_materials": "is_blank",
            "rag_explanation": "is_blank"
        }




def evaluate_results(df: pd.DataFrame) -> Dict[str, Any]:
    """
    评估结果

    Args:
        df: 包含原始答案和RAG答案的DataFrame

    Returns:
        评估结果字典
    """
    total = len(df)
    correct_value = 0
    correct_ref_id = 0

    for _, row in df.iterrows():
        # 评估answer_value
        gt_value = str(row['answer_value']).strip().lower()
        rag_value = str(row['rag_answer_value']).strip().lower()

        if gt_value == rag_value:
            correct_value += 1

        # 评估ref_id (处理列表格式)
        gt_ref_id_raw = str(row['ref_id'])
        if gt_ref_id_raw.startswith('[') and gt_ref_id_raw.endswith(']'):
            # 如果是列表格式，取第一个元素
            try:
                gt_ref_list = eval(gt_ref_id_raw)
                gt_ref_id = str(gt_ref_list[0]).strip(" '\"") if gt_ref_list else "is_blank"
            except:
                gt_ref_id = "is_blank"
        else:
            gt_ref_id = gt_ref_id_raw.strip(" '\" ")

        rag_ref_id_raw = row['rag_ref_id']

        # 处理rag_ref_id可能是列表的情况
        if isinstance(rag_ref_id_raw, list):
            # 如果是列表，转换为字符串表示进行比较
            rag_ref_id_list = [str(item).strip(" '\" ") for item in rag_ref_id_raw]
            rag_ref_id = str(rag_ref_id_list)
        else:
            rag_ref_id = str(rag_ref_id_raw).strip(" '\" ")

        # 比较ref_id
        if gt_ref_id == rag_ref_id:
            correct_ref_id += 1

    return {
        "total_questions": total,
        "correct_answer_value": correct_value,
        "correct_ref_id": correct_ref_id,
        "accuracy_answer_value": correct_value / total if total > 0 else 0,
        "accuracy_ref_id": correct_ref_id / total if total > 0 else 0
    }


def main():
    """主函数"""
    print("🎯 简洁LightRAG测试脚本")
    print("=" * 50)

    # 解析命令行参数
    num_questions = None  # None表示运行所有问题
    start_row = 0  # 起始行数（从0开始）

    if len(sys.argv) > 1:
        try:
            # 第一个参数：问题数量
            num_questions = int(sys.argv[1])
            if num_questions <= 0:
                print("⚠️  问题数量必须大于0，将运行所有问题")
                num_questions = None
        except ValueError:
            print("⚠️  第一个参数格式错误，请输入数字，将运行所有问题")
            num_questions = None

    if len(sys.argv) > 2:
        try:
            # 第二个参数：起始行数
            start_row = int(sys.argv[2])
            if start_row < 0:
                print("⚠️  起始行数不能小于0，将从第0行开始")
                start_row = 0
        except ValueError:
            print("⚠️  第二个参数格式错误，请输入数字，将从第0行开始")
            start_row = 0

    print(f"📋 参数设置: 问题数量={num_questions if num_questions else '全部'}, 起始行数={start_row}")

    # 1. 读取train QA
    print("读取train_QA.csv...")
    df = pd.read_csv("train_QA.csv")
    print(f"   📊 共 {len(df)} 个问题")

    # 根据参数决定处理多少个问题
    if num_questions is None:
        # 运行从start_row开始的所有问题
        if start_row > 0:
            test_df = df.iloc[start_row:]
            print(f"   🧪 从第{start_row}行开始运行所有 {len(test_df)} 个问题")
        else:
            test_df = df
            print(f"   🧪 运行所有 {len(df)} 个问题")
    else:
        # 运行从start_row开始的指定数量问题
        end_row = start_row + num_questions
        if start_row >= len(df):
            print(f"   ⚠️  起始行{start_row}超出范围（总共{len(df)}行），将运行所有问题")
            test_df = df
        elif end_row > len(df):
            test_df = df.iloc[start_row:]
            print(f"   🧪 从第{start_row}行开始运行到末尾，共 {len(test_df)} 个问题")
        else:
            test_df = df.iloc[start_row:end_row]
            print(f"   🧪 从第{start_row}行开始运行 {len(test_df)} 个问题")

    # 2. 处理每个问题
    print("向LightRAG发送查询...")
    results = []

    for i, (index, row) in enumerate(test_df.iterrows()):
        question_id = row['id']
        question = row['question']

        print(f"   🔍 处理第{i+1}个问题 (行{index}): {question_id}")

        # 查询LightRAG
        rag_response = query_lightrag(question_id, question)
        rag_result = parse_rag_response(rag_response, question_id)

        print(f"      RAG ref_id: {rag_result['rag_ref_id']}")
        print(f"      RAG answer: {rag_result['rag_answer'][:100]}...")

        # 保存结果
        results.append(rag_result)

        # 添加延时避免过快请求
        time.sleep(0.5)

    # 3. 合并结果到原DataFrame
    print("合并结果并保存CSV...")
    rag_df = pd.DataFrame(results)

    # 合并到测试数据
    final_df = pd.concat([test_df, rag_df], axis=1)

    # 保存CSV
    output_file = "rag_results.csv"
    final_df.to_csv(output_file, index=False, encoding='utf-8')
    print(f"   ✅ 已保存到: {output_file}")

    # 4. 评分
    print("评分计算...")
    evaluation = evaluate_results(final_df)

    print("\n" + "=" * 50)
    print("📊 评估结果")
    print("=" * 50)
    print(f"总问题数:           {evaluation['total_questions']}")
    print(f"answer_value正确数: {evaluation['correct_answer_value']}")
    print(f"answer_value准确率: {evaluation['accuracy_answer_value']:.2%}")
    print(f"ref_id正确数:       {evaluation['correct_ref_id']}")
    print(f"ref_id准确率:       {evaluation['accuracy_ref_id']:.2%}")
    print("=" * 50)


if __name__ == "__main__":
    main()