"""
带重试机制的RAG查询模块
提供Pydantic验证和自动重试功能
"""

import asyncio
import time
from typing import Dict, Any, Optional, List, Callable
from answer_parser import AnswerParser, RAGAnswer, parse_rag_response


class RAGRetryQuery:
    """带重试机制的RAG查询器"""

    def __init__(
        self,
        rag_instance,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        quality_threshold: float = 0.7
    ):
        """
        初始化RAG查询器

        Args:
            rag_instance: RAG实例，需要支持查询方法
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）
            quality_threshold: 质量阈值（0-1）
        """
        self.rag = rag_instance
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.quality_threshold = quality_threshold
        self.parser = AnswerParser()

    async def query_with_retry(
        self,
        question: str,
        question_id: str,
        prompt_template: str = None,
        **kwargs
    ) -> Optional[RAGAnswer]:
        """
        带重试机制的查询（仅在格式解析失败时重试）

        Args:
            question: 问题文本
            question_id: 问题ID
            prompt_template: 可选的提示词模板
            **kwargs: 其他查询参数

        Returns:
            成功返回RAGAnswer对象，失败返回None
        """
        last_response = None
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                print(f"问题 {question_id}: 第 {attempt + 1}/{self.max_retries + 1} 次尝试")

                # 执行RAG查询
                if prompt_template:
                    response = await self.rag.aquery(
                        question,
                        param={"prompt_template": prompt_template},
                        **kwargs
                    )
                else:
                    response = await self.rag.aquery(question, **kwargs)

                last_response = response

                # 解析响应
                parsed_answer = self.parser.parse_answer(response, question_id, question)

                if parsed_answer:
                    # 格式正确，直接返回（不进行质量评分重试）
                    quality_score = self._calculate_quality_score(parsed_answer)
                    print(f"问题 {question_id}: 解析成功，质量评分: {quality_score:.2f}")
                    return parsed_answer
                else:
                    print(f"问题 {question_id}: 格式解析失败，需要重试")
                    if attempt < self.max_retries:
                        retry_delay = self.retry_delay * (attempt + 1)
                        print(f"问题 {question_id}: {retry_delay}秒后重试...")
                        await asyncio.sleep(retry_delay)
                        continue
                    else:
                        print(f"问题 {question_id}: 达到最大重试次数，返回解析失败记录")
                        return self._create_failure_record(question_id, question, last_response, "格式解析失败")

            except Exception as e:
                last_error = e
                print(f"问题 {question_id}: 查询异常: {e}")
                if attempt < self.max_retries:
                    retry_delay = self.retry_delay * (attempt + 1)
                    print(f"问题 {question_id}: {retry_delay}秒后重试...")
                    await asyncio.sleep(retry_delay)
                    continue

        # 所有重试都失败了
        print(f"问题 {question_id}: 所有重试均失败")
        if last_error:
            print(f"问题 {question_id}: 最后错误: {last_error}")

        # 返回失败记录
        return self._create_failure_record(question_id, question, last_response, last_error)

    def _calculate_quality_score(self, answer: RAGAnswer) -> float:
        """
        计算答案质量评分

        Args:
            answer: RAGAnswer对象

        Returns:
            质量评分 (0-1)
        """
        score = 0.0
        max_score = 1.0

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

        return min(score, max_score)

    def _create_failure_record(
        self,
        question_id: str,
        question: str,
        last_response: str = None,
        last_error: Exception = None
    ) -> RAGAnswer:
        """
        创建失败记录

        Args:
            question_id: 问题ID
            question: 问题文本
            last_response: 最后的响应文本
            last_error: 最后的错误信息

        Returns:
            失败记录的RAGAnswer对象
        """
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


class BatchRAGQuery:
    """批量RAG查询处理器"""

    def __init__(
        self,
        rag_instance,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        quality_threshold: float = 0.7,
        concurrent_limit: int = 5
    ):
        """
        初始化批量查询处理器

        Args:
            rag_instance: RAG实例
            max_retries: 最大重试次数
            retry_delay: 重试延迟
            quality_threshold: 质量阈值
            concurrent_limit: 并发限制
        """
        self.rag = rag_instance
        self.query_processor = RAGRetryQuery(
            rag_instance, max_retries, retry_delay, quality_threshold
        )
        self.concurrent_limit = concurrent_limit
        self.semaphore = asyncio.Semaphore(concurrent_limit)

    async def process_batch(
        self,
        questions: List[Dict[str, str]],
        prompt_template: str = None,
        progress_callback: Callable = None
    ) -> List[RAGAnswer]:
        """
        批量处理问题

        Args:
            questions: 问题列表，每个元素包含 {'id': str, 'question': str}
            prompt_template: 提示词模板
            progress_callback: 进度回调函数

        Returns:
            处理结果列表
        """
        total_questions = len(questions)
        results = []

        async def process_single_question(question_data):
            async with self.semaphore:
                question_id = question_data['id']
                question_text = question_data['question']

                try:
                    result = await self.query_processor.query_with_retry(
                        question_text,
                        question_id,
                        prompt_template
                    )

                    if progress_callback:
                        await progress_callback(question_id, len(results), total_questions, True)

                    return result

                except Exception as e:
                    print(f"问题 {question_id}: 处理异常: {e}")

                    if progress_callback:
                        await progress_callback(question_id, len(results), total_questions, False)

                    return self.query_processor._create_failure_record(
                        question_id, question_text, last_error=e
                    )

        # 创建所有任务
        tasks = [process_single_question(q) for q in questions]

        # 等待所有任务完成
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理异常结果
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                question_id = questions[i]['id']
                print(f"问题 {question_id}: 任务异常: {result}")
                processed_results.append(
                    self.query_processor._create_failure_record(
                        question_id, questions[i]['question'], last_error=result
                    )
                )
            else:
                processed_results.append(result)

        return processed_results

    def get_statistics(self, results: List[RAGAnswer]) -> Dict[str, Any]:
        """
        获取处理统计信息

        Args:
            results: 处理结果列表

        Returns:
            统计信息字典
        """
        total = len(results)
        successful = sum(1 for r in results if r.answer != "查询失败")
        failed = total - successful

        # 计算平均质量评分
        processor = self.query_processor
        quality_scores = [processor._calculate_quality_score(r) for r in results if r.answer != "查询失败"]
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0

        return {
            "total": total,
            "successful": successful,
            "failed": failed,
            "success_rate": successful / total if total > 0 else 0,
            "average_quality_score": avg_quality,
            "quality_threshold": self.query_processor.quality_threshold
        }


# 便捷函数
async def query_rag_with_retry(
    rag_instance,
    question: str,
    question_id: str,
    max_retries: int = 3,
    **kwargs
) -> Optional[RAGAnswer]:
    """
    便捷函数：带重试的RAG查询

    Args:
        rag_instance: RAG实例
        question: 问题文本
        question_id: 问题ID
        max_retries: 最大重试次数
        **kwargs: 其他参数

    Returns:
        查询结果
    """
    query_processor = RAGRetryQuery(rag_instance, max_retries)
    return await query_processor.query_with_retry(question, question_id, **kwargs)