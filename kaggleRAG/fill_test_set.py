#!/usr/bin/env python3
"""
测试集RAG填充脚本

功能：
1. 读取test_Q.csv测试集问题
2. 使用增强的LightRAG系统进行查询
3. 应用重试机制和答案解析
4. 保存填充结果到test_Q_filled.csv

使用方法：
  python fill_test_set.py                           # 处理所有测试问题
  python fill_test_set.py 10                        # 处理前10个问题
  python fill_test_set.py 10 50                     # 从第50题开始处理10个问题
  python fill_test_set.py 0 50                      # 从第50题开始处理所有剩余问题

参数说明：
  第一个参数：问题数量（0表示处理所有剩余问题）
  第二个参数：起始问题编号（从1开始，1表示第1个问题）
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
            timeout=300  # 增加到5分钟超时
        )

        if response.status_code == 200:
            data = response.json()
            return data.get("response", "")
        else:
            print(f"   ❌ 查询失败 {question_id}: {response.status_code}")
            return f"查询失败: HTTP {response.status_code}"

    except requests.exceptions.Timeout as e:
        print(f"   ❌ 查询超时 {question_id}: {e}")
        return f"查询超时: {str(e)}"
    except requests.exceptions.ConnectionError as e:
        print(f"   ❌ 连接错误 {question_id}: {e}")
        return f"连接错误: {str(e)}"
    except Exception as e:
        print(f"   ❌ 查询异常 {question_id}: {e}")
        return f"查询异常: {str(e)}"


class TestSetFiller:
    """测试集填充器"""

    def __init__(self, api_url: str = "http://localhost:9621"):
        self.api_url = api_url
        self.parser = AnswerParser()

    def fill_single_question(
        self,
        question_id: str,
        question_text: str,
        answer_unit: str = "",
        max_retries: int = 3,
        request_delay: float = 2.0
    ) -> RAGAnswer:
        """
        填充单个问题的答案，带重试机制

        Args:
            question_id: 问题ID
            question_text: 问题文本
            answer_unit: 预期答案单位
            max_retries: 最大重试次数
            request_delay: 请求间隔时间（秒）

        Returns:
            填充结果
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

    def fill_test_set(
        self,
        test_df: pd.DataFrame,
        request_delay: float = 2.0
    ) -> List[RAGAnswer]:
        """
        填充测试集

        Args:
            test_df: 测试数据DataFrame
            request_delay: 请求间隔时间（秒）

        Returns:
            填充结果列表
        """
        results = []
        total = len(test_df)

        for i, (_, row) in enumerate(test_df.iterrows()):
            question_id = row['id']
            question_text = row['question']
            answer_unit = row.get('answer_unit', '')  # 从测试集获取预期答案单位

            unit_display = answer_unit if answer_unit and answer_unit.lower() != 'is_blank' else '无'
            print(f"[{i+1}/{total}] {question_id} (单位: {unit_display})")

            # 填充问题
            result = self.fill_single_question(question_id, question_text, answer_unit, request_delay=request_delay)
            results.append(result)

            # 问题之间的间歇时间（避免API限速）
            if i < total - 1:  # 最后一个问题不需要等待
                time.sleep(request_delay)

        return results


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
            start_question = int(sys.argv[2])
            if start_question < 1:
                start_question = 1
        except ValueError:
            start_question = 1
    else:
        start_question = 1

    print(f"问题数量: {num_questions if num_questions else '全部'}, 起始问题: {start_question}")

    # 读取测试数据
    try:
        df = pd.read_csv("test_Q.csv")
        print(f"总问题数: {len(df)}")
    except FileNotFoundError:
        print("错误: 找不到 test_Q.csv 文件")
        return

    # 确定处理范围 (转换为0-based索引)
    start_index = start_question - 1  # 转换为0-based索引

    if num_questions is None:
        if start_question > 1:
            test_df = df.iloc[start_index:]
        else:
            test_df = df
    else:
        end_index = start_index + num_questions
        if start_index >= len(df):
            test_df = df
        elif end_index > len(df):
            test_df = df.iloc[start_index:]
        else:
            test_df = df.iloc[start_index:end_index]

    print(f"实际处理: {len(test_df)} 个问题 (第{start_question}题开始)")
    print("-" * 30)

    filler = TestSetFiller()
    results = filler.fill_test_set(test_df, request_delay=2.0)

    # 转换结果为DataFrame
    print("\n处理结果...")
    rag_data = []
    for result in results:
        # 处理ref_id：空列表转换为"is_blank"
        ref_id_str = "is_blank" if not result.ref_id else result.ref_id

        rag_data.append({
            'id': result.id,
            'question': result.question,
            'answer': result.answer,
            'answer_value': result.answer_value,
            'answer_unit': result.answer_unit,
            'ref_id': ref_id_str,
            'supporting_materials': result.supporting_materials,
            'explanation': result.explanation
        })

    rag_df = pd.DataFrame(rag_data)

    # 保存CSV
    output_file = "test_Q_filled.csv"
    rag_df.to_csv(output_file, index=False, encoding='utf-8')
    print(f"已保存到: {output_file}")

    # 统计结果
    total = len(results)
    successful = sum(1 for r in results if r.answer != "查询失败")
    failed = total - successful

    print(f"\n填充统计:")
    print(f"总问题数: {total}")
    print(f"成功填充: {successful}")
    print(f"失败填充: {failed}")
    print(f"成功率: {successful/total:.2%}")


if __name__ == "__main__":
    main()