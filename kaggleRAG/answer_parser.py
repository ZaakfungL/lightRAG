"""
RAG答案解析模块
用于解析大模型返回的结构化文本答案，支持正则表达式提取和Pydantic验证
"""

import re
import json
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, validator


class RAGAnswer(BaseModel):
    """RAG答案数据模型"""
    id: str = Field(..., description="问题ID")
    question: str = Field(..., description="问题文本")
    answer: str = Field(..., description="答案内容")
    answer_value: str = Field(default="is_blank", description="标准化的数值或分类值")
    answer_unit: str = Field(default="is_blank", description="单位")
    ref_id: List[str] = Field(default_factory=list, description="参考文档ID列表")
    supporting_materials: str = Field(default="is_blank", description="支撑材料")
    explanation: str = Field(default="is_blank", description="解释说明")

    @validator('ref_id', pre=True)
    def parse_ref_id(cls, v):
        """解析ref_id字段，支持多种格式"""
        if isinstance(v, str):
            # 处理字符串格式的ref_id
            v = v.strip()
            if v == "is_blank" or not v:
                return []

            # 处理["id1","id2"]格式
            if v.startswith('[') and v.endswith(']'):
                try:
                    return json.loads(v)
                except:
                    pass

            # 处理逗号分隔的格式
            if ',' in v:
                return [item.strip().strip('"\'') for item in v.split(',')]

            # 处理单个ID
            return [v.strip().strip('"\'')]

        return v if v else []

    @validator('answer_value', pre=True)
    def parse_answer_value(cls, v):
        """处理answer_value字段"""
        if isinstance(v, str):
            return v.strip()
        return str(v) if v is not None else "is_blank"

    @validator('answer_unit', pre=True)
    def parse_answer_unit(cls, v):
        """处理answer_unit字段"""
        if isinstance(v, str):
            return v.strip()
        return str(v) if v is not None else "is_blank"

    @validator('supporting_materials', pre=True)
    def parse_supporting_materials(cls, v):
        """处理supporting_materials字段"""
        if isinstance(v, str):
            return v.strip()
        return str(v) if v is not None else "is_blank"

    @validator('explanation', pre=True)
    def parse_explanation(cls, v):
        """处理explanation字段"""
        if isinstance(v, str):
            return v.strip()
        return str(v) if v is not None else "is_blank"


class AnswerParser:
    """答案解析器"""

    def __init__(self):
        # 定义各个字段的正则表达式模式
        self.patterns = {
            'answer': re.compile(r'Answer:\s*(.+?)(?=\n(?:Answer Value|Answer Unit|Reference ID|Supporting Materials|Explanation)|$)', re.IGNORECASE | re.DOTALL),
            'answer_value': re.compile(r'Answer Value:\s*(.+?)(?=\n(?:Answer Unit|Reference ID|Supporting Materials|Explanation)|$)', re.IGNORECASE | re.DOTALL),
            'answer_unit': re.compile(r'Answer Unit:\s*(.+?)(?=\n(?:Reference ID|Supporting Materials|Explanation)|$)', re.IGNORECASE | re.DOTALL),
            'ref_id': re.compile(r'Reference ID:\s*(.+?)(?=\n(?:Supporting Materials|Explanation)|$)', re.IGNORECASE | re.DOTALL),
            'supporting_materials': re.compile(r'Supporting Materials:\s*(.+?)(?=\n(?:Explanation)|$)', re.IGNORECASE | re.DOTALL),
            'explanation': re.compile(r'Explanation:\s*(.+?)$', re.IGNORECASE | re.DOTALL),
        }

        # 备用模式（更宽松的匹配）
        self.fallback_patterns = {
            'answer': re.compile(r'(?:(?:Answer|答案)[:\s]*)\s*(.+?)(?=\n(?:Answer|Answer Value|答案|答案值|Reference|参考|Supporting|支撑|Explanation|解释)|$)', re.IGNORECASE | re.DOTALL),
            'answer_value': re.compile(r'(?:(?:Answer Value|答案值)[:\s]*)\s*(.+?)(?=\n(?:Answer Unit|答案单位|Reference|参考|Supporting|支撑|Explanation|解释)|$)', re.IGNORECASE | re.DOTALL),
            'answer_unit': re.compile(r'(?:(?:Answer Unit|答案单位)[:\s]*)\s*(.+?)(?=\n(?:Reference|参考|Supporting|支撑|Explanation|解释)|$)', re.IGNORECASE | re.DOTALL),
            'ref_id': re.compile(r'(?:(?:Reference ID|参考ID|参考文献)[:\s]*)\s*(.+?)(?=\n(?:Supporting|支撑|Explanation|解释)|$)', re.IGNORECASE | re.DOTALL),
            'supporting_materials': re.compile(r'(?:(?:Supporting Materials|支撑材料|引用|材料)[:\s]*)\s*(.+?)(?=\n(?:Explanation|解释)|$)', re.IGNORECASE | re.DOTALL),
            'explanation': re.compile(r'(?:(?:Explanation|解释)[:\s]*)\s*(.+?)$', re.IGNORECASE | re.DOTALL),
        }

    def parse_answer(self, response_text: str, question_id: str, question_text: str) -> Optional[RAGAnswer]:
        """
        解析大模型返回的答案文本

        Args:
            response_text: 大模型返回的原始文本
            question_id: 问题ID
            question_text: 问题文本

        Returns:
            解析后的RAGAnswer对象，解析失败返回None
        """
        if not response_text or not response_text.strip():
            print(f"问题 {question_id}: 收到空响应")
            return None

        # 清理文本
        cleaned_text = response_text.strip()

        # 尝试JSON格式（向后兼容）
        json_result = self._try_parse_json(cleaned_text, question_id, question_text)
        if json_result:
            return json_result

        # 解析各个字段
        parsed_data = {}
        debug_info = f"问题 {question_id}: 解析调试信息:\n"

        for field_name, pattern in self.patterns.items():
            match = pattern.search(cleaned_text)
            if match:
                value = match.group(1).strip()
                # 清理多余空白字符
                value = re.sub(r'\s+', ' ', value)
                parsed_data[field_name] = value
                debug_info += f"  {field_name}: '{value[:50]}...' (成功)\n"
            else:
                # 尝试备用模式
                fallback_pattern = self.fallback_patterns.get(field_name)
                if fallback_pattern:
                    fallback_match = fallback_pattern.search(cleaned_text)
                    if fallback_match:
                        value = fallback_match.group(1).strip()
                        value = re.sub(r'\s+', ' ', value)
                        parsed_data[field_name] = value
                        debug_info += f"  {field_name}: '{value[:50]}...' (备用模式成功)\n"
                    else:
                        debug_info += f"  {field_name}: 解析失败\n"
                        parsed_data[field_name] = "is_blank"
                else:
                    debug_info += f"  {field_name}: 解析失败\n"
                    parsed_data[field_name] = "is_blank"

        # 特殊处理：如果所有字段都解析失败，但有"Unable to answer"文本
        if all(value == "is_blank" for value in parsed_data.values()) and "unable to answer" in cleaned_text.lower():
            parsed_data['answer'] = "Unable to answer with confidence based on the provided documents."
            debug_info += f"  检测到无法回答文本，设置默认答案\n"

        # 智能容错：尝试从文本中提取有用信息
        if parsed_data.get('answer', 'is_blank') == 'is_blank':
            # 尝试直接提取第一行作为答案
            lines = cleaned_text.split('\n')
            if lines and len(lines[0].strip()) > 10:  # 第一行有足够内容
                potential_answer = lines[0].strip()
                if potential_answer and not potential_answer.startswith('{') and not potential_answer.startswith('Answer:'):
                    parsed_data['answer'] = potential_answer
                    debug_info += f"  使用第一行作为答案: '{potential_answer[:50]}...' (智能容错)\n"

        # 如果至少有answer字段，就创建对象
        if parsed_data.get('answer', 'is_blank') != 'is_blank':
            try:
                answer_obj = RAGAnswer(
                    id=question_id,
                    question=question_text,
                    answer=parsed_data.get('answer', 'is_blank'),
                    answer_value=parsed_data.get('answer_value', 'is_blank'),
                    answer_unit=parsed_data.get('answer_unit', 'is_blank'),
                    ref_id=parsed_data.get('ref_id', []),
                    supporting_materials=parsed_data.get('supporting_materials', 'is_blank'),
                    explanation=parsed_data.get('explanation', 'is_blank')
                )
                return answer_obj

            except Exception as e:
                print(f"问题 {question_id}: 创建RAGAnswer对象失败: {e}")
                print(debug_info)
                return None
        else:
            print(f"问题 {question_id}: 所有字段解析失败")
            print(debug_info)
            print(f"原始响应前200字符: {cleaned_text[:200]}...")
            return None

    def _try_parse_json(self, text: str, question_id: str, question_text: str) -> Optional[RAGAnswer]:
        """
        尝试解析JSON格式（向后兼容）

        Args:
            text: 待解析的文本
            question_id: 问题ID
            question_text: 问题文本

        Returns:
            解析成功返回RAGAnswer对象，失败返回None
        """
        # 查找JSON对象
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if not json_match:
            return None

        try:
            json_data = json.loads(json_match.group(0))
            # 转换为RAGAnswer对象
            return RAGAnswer(
                id=question_id,
                question=question_text,
                answer=json_data.get('answer', 'is_blank'),
                answer_value=json_data.get('answer_value', 'is_blank'),
                answer_unit=json_data.get('answer_unit', 'is_blank'),
                ref_id=json_data.get('ref_id', []),
                supporting_materials=json_data.get('supporting_materials', 'is_blank'),
                explanation=json_data.get('explanation', 'is_blank')
            )
        except json.JSONDecodeError:
            return None

    def _validate_answer_quality(self, answer: RAGAnswer) -> bool:
        """
        验证答案质量

        Args:
            answer: RAGAnswer对象

        Returns:
            验证通过返回True，否则返回False
        """
        # 检查是否有有效的答案内容
        if not answer.answer or answer.answer == "is_blank":
            return False

        # 检查是否无法回答
        if "unable to answer" in answer.answer.lower():
            return False

        return True

    def extract_field_value(self, text: str, field_name: str) -> str:
        """
        从文本中提取特定字段的值

        Args:
            text: 待解析的文本
            field_name: 字段名称

        Returns:
            提取的字段值，未找到返回空字符串
        """
        pattern = self.patterns.get(field_name.lower())
        if not pattern:
            return ""

        match = pattern.search(text)
        if match:
            return match.group(1).strip()
        return ""


# 便捷函数
def parse_rag_response(response_text: str, question_id: str, question_text: str) -> Optional[RAGAnswer]:
    """
    便捷函数：解析RAG响应

    Args:
        response_text: 大模型返回的文本
        question_id: 问题ID
        question_text: 问题文本

    Returns:
        解析后的RAGAnswer对象
    """
    parser = AnswerParser()
    return parser.parse_answer(response_text, question_id, question_text)


def format_answer_for_csv(answer: RAGAnswer) -> List[str]:
    """
    将RAGAnswer对象格式化为CSV行数据

    Args:
        answer: RAGAnswer对象

    Returns:
        CSV行数据列表
    """
    return [
        answer.id,
        answer.question,
        answer.answer,
        answer.answer_value,
        answer.answer_unit,
        json.dumps(answer.ref_id) if answer.ref_id else "[]",
        answer.supporting_materials,
        answer.explanation
    ]