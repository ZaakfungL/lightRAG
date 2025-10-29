#!/usr/bin/env python3
"""
增强的LightRAG测试脚本

功能：
1. 使用新的分点格式提示词，避免JSON格式不稳定问题
2. 通过正则表达式解析结构化答案
3. 使用Pydantic进行数据验证
4. 实现自动重试机制，提高成功率
5. 支持批量处理和进度跟踪

使用方法：
  python enhanced_rag_test.py                    # 运行所有问题
  python enhanced_rag_test.py 5                  # 运行前5个问题
  python enhanced_rag_test.py 5 33               # 从第33行开始运行5个问题
  python enhanced_rag_test.py 0 33               # 从第33行开始运行所有剩余问题
"""

import pandas as pd
import requests
import time
import sys
from typing import Dict, Any, List
from answer_parser import AnswerParser, RAGAnswer


def query_lightrag(question_id: str, question: str, answer_unit: str = "", api_url: str = "http://localhost:9621") -> str:
    """
    向LightRAG发送查询请求，返回原始文本响应

    Args:
        question_id: 问题ID
        question: 问题内容
        answer_unit: 预期答案单位
        api_url: API地址

    Returns:
        LightRAG响应文本
    """
    try:
        payload = {
            "query": question,
            "mode": "mix",
            "top_k": 20,
            "chunk_top_k": 5
        }

        # 如果有预期单位且不是is_blank，添加到用户提示中
        if answer_unit and answer_unit.strip() and answer_unit.lower() != 'is_blank':
            unit_prompt = f"IMPORTANT: The expected answer unit is '{answer_unit}'. Please ensure your answer uses this exact unit format."
            payload["user_prompt"] = unit_prompt

        response = requests.post(
            f"{api_url}/query",
            json=payload,
            timeout=120
        )

        if response.status_code == 200:
            data = response.json()
            return data.get("response", "")
        else:
            print(f"   ❌ 查询失败 {question_id}: {response.status_code}")
            return f"查询失败: HTTP {response.status_code}"

    except Exception as e:
        print(f"   ❌ 查询异常 {question_id}: {e}")
        return f"查询异常: {str(e)}"


class EnhancedRAGTester:
    """增强的RAG测试器"""

    def __init__(self, api_url: str = "http://localhost:9621"):
        self.api_url = api_url
        self.parser = AnswerParser()

    def test_single_question_sync(
        self,
        question_id: str,
        question_text: str,
        answer_unit: str = "",
        max_retries: int = 3,
        request_delay: float = 2.0
    ) -> RAGAnswer:
        """
        同步测试单个问题，带重试机制

        Args:
            question_id: 问题ID
            question_text: 问题文本
            answer_unit: 预期答案单位
            max_retries: 最大重试次数
            request_delay: 请求间隔时间（秒）

        Returns:
            测试结果
        """
        last_response = None
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                # 查询LightRAG
                response_text = query_lightrag(question_id, question_text, answer_unit, self.api_url)
                last_response = response_text

                # 解析响应
                parsed_answer = self.parser.parse_answer(response_text, question_id, question_text)

                if parsed_answer:
                    # 格式正确，直接返回
                    return parsed_answer
                else:
                    # 格式解析失败，需要重试
                    if attempt < max_retries:
                        print(f"  格式错误，重试 ({attempt + 1}/{max_retries})")
                        retry_delay = request_delay * (attempt + 1)
                        time.sleep(retry_delay)
                    else:
                        # 达到最大重试次数
                        return self._create_failure_record(question_id, question_text, last_response, "格式解析失败")

            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    print(f"  异常重试 ({attempt + 1}/{max_retries})")
                    retry_delay = request_delay * (attempt + 1)
                    time.sleep(retry_delay)
                continue

        # 所有重试都失败了
        return self._create_failure_record(question_id, question_text, last_response, last_error)

    def _calculate_quality_score(self, answer: RAGAnswer) -> float:
        """计算答案质量评分"""
        score = 0.0

        # 检查答案是否有效
        if answer.answer and answer.answer != "is_blank":
            score += 0.3

        # 检查是否有参考文档
        if answer.ref_id and answer.ref_id != []:
            score += 0.2

        # 检查answer_value
        if answer.answer_value and answer.answer_value != "is_blank":
            score += 0.2

        # 检查支撑材料
        if answer.supporting_materials and answer.supporting_materials != "is_blank":
            score += 0.15

        # 检查解释
        if answer.explanation and answer.explanation != "is_blank":
            score += 0.15

        return min(score, 1.0)

    def _create_failure_record(
        self,
        question_id: str,
        question: str,
        last_response: str = None,
        last_error: Exception = None
    ) -> RAGAnswer:
        """创建失败记录"""
        error_info = f"查询失败: {str(last_error)}" if last_error else "解析失败"

        return RAGAnswer(
            id=question_id,
            question=question,
            answer="查询失败",
            answer_value="is_blank",
            answer_unit="is_blank",
            ref_id=[],
            supporting_materials=error_info,
            explanation=f"最后响应: {last_response[:200]}..." if last_response and len(last_response) > 200 else (last_response or "无响应")
        )

    def test_batch(
        self,
        test_df: pd.DataFrame,
        request_delay: float = 2.0
    ) -> List[RAGAnswer]:
        """
        批量测试问题

        Args:
            test_df: 测试数据DataFrame
            request_delay: 请求间隔时间（秒）

        Returns:
            测试结果列表
        """
        results = []
        total = len(test_df)

        for i, (_, row) in enumerate(test_df.iterrows()):
            question_id = row['id']
            question_text = row['question']
            answer_unit = row.get('answer_unit', '')  # 从训练集获取预期答案单位

            unit_display = answer_unit if answer_unit and answer_unit.lower() != 'is_blank' else '无'
            print(f"[{i+1}/{total}] {question_id} (单位: {unit_display})")

            # 测试问题
            result = self.test_single_question_sync(question_id, question_text, answer_unit, request_delay=request_delay)
            results.append(result)

            # 问题之间的间歇时间（避免API限速）
            if i < total - 1:  # 最后一个问题不需要等待
                time.sleep(request_delay)

        return results


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
    failed_queries = 0

    for _, row in df.iterrows():
        # 检查查询失败的情况
        rag_answer = str(row['rag_answer']).strip()
        if "查询失败" in rag_answer or "解析失败" in rag_answer:
            failed_queries += 1
            continue

        # 评估answer_value
        gt_value = str(row['answer_value']).strip().lower()
        rag_value = str(row['rag_answer_value']).strip().lower()

        if gt_value == rag_value:
            correct_value += 1

        # 评估ref_id
        gt_ref_id_raw = str(row['ref_id'])
        if gt_ref_id_raw.startswith('[') and gt_ref_id_raw.endswith(']'):
            try:
                gt_ref_list = eval(gt_ref_id_raw)
                gt_ref_id = str(gt_ref_list[0]).strip(" '\"") if gt_ref_list else "is_blank"
            except:
                gt_ref_id = "is_blank"
        else:
            gt_ref_id = gt_ref_id_raw.strip(" '\" ")

        rag_ref_id_raw = row['rag_ref_id']
        if isinstance(rag_ref_id_raw, list):
            rag_ref_id_list = [str(item).strip(" '\" ") for item in rag_ref_id_raw]
            rag_ref_id = str(rag_ref_id_list)
        else:
            rag_ref_id = str(rag_ref_id_raw).strip(" '\" ")

        if gt_ref_id == rag_ref_id:
            correct_ref_id += 1

    return {
        "total_questions": total,
        "failed_queries": failed_queries,
        "successful_queries": total - failed_queries,
        "correct_answer_value": correct_value,
        "correct_ref_id": correct_ref_id,
        "accuracy_answer_value": correct_value / total if total > 0 else 0,
        "accuracy_ref_id": correct_ref_id / total if total > 0 else 0,
        "success_rate": (total - failed_queries) / total if total > 0 else 0
    }




def main():
    """主函数"""
    # 解析命令行参数
    num_questions = None
    start_row = 0

    if len(sys.argv) > 1:
        try:
            num_questions = int(sys.argv[1])
            if num_questions <= 0:
                num_questions = None
        except ValueError:
            num_questions = None

    if len(sys.argv) > 2:
        try:
            start_row = int(sys.argv[2])
            if start_row < 0:
                start_row = 0
        except ValueError:
            start_row = 0

    print(f"问题数量: {num_questions if num_questions else '全部'}, 起始行: {start_row}")

    # 读取数据
    try:
        df = pd.read_csv("train_QA.csv")
        print(f"总问题数: {len(df)}")
    except FileNotFoundError:
        print("错误: 找不到 train_QA.csv 文件")
        return

    # 确定测试范围
    if num_questions is None:
        if start_row > 0:
            test_df = df.iloc[start_row:]
        else:
            test_df = df
    else:
        end_row = start_row + num_questions
        if start_row >= len(df):
            test_df = df
        elif end_row > len(df):
            test_df = df.iloc[start_row:]
        else:
            test_df = df.iloc[start_row:end_row]

    print(f"实际处理: {len(test_df)} 个问题")
    print("-" * 30)

    tester = EnhancedRAGTester()
    results = tester.test_batch(test_df, request_delay=2.0)

    # 转换结果为DataFrame
    print("\n处理结果...")
    rag_data = []
    for result in results:
        # 处理ref_id：空列表转换为"is_blank"
        ref_id_str = "is_blank" if not result.ref_id else result.ref_id

        rag_data.append({
            'rag_answer': result.answer,
            'rag_answer_value': result.answer_value,
            'rag_answer_unit': result.answer_unit,
            'rag_ref_id': ref_id_str,
            'rag_supporting_materials': result.supporting_materials,
            'rag_explanation': result.explanation
        })

    rag_df = pd.DataFrame(rag_data)

    # 合并结果
    final_df = pd.concat([test_df.reset_index(drop=True), rag_df], axis=1)

    # 保存CSV
    output_file = "rag_results_enhanced.csv"
    final_df.to_csv(output_file, index=False, encoding='utf-8')
    print(f"已保存到: {output_file}")

    # 评估结果
    evaluation = evaluate_results(final_df)

    print(f"\n结果统计:")
    print(f"总问题数: {evaluation['total_questions']}")
    print(f"成功查询: {evaluation['successful_queries']}")
    print(f"失败查询: {evaluation['failed_queries']}")
    print(f"查询成功率: {evaluation['success_rate']:.2%}")
    print(f"answer_value准确率: {evaluation['accuracy_answer_value']:.2%}")
    print(f"ref_id准确率: {evaluation['accuracy_ref_id']:.2%}")


if __name__ == "__main__":
    main()