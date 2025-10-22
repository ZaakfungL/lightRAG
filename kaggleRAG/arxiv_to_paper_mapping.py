#!/usr/bin/env python3
"""
创建arXiv ID到论文ID的映射表
基于已知的trainQA数据中的映射关系
"""

# 基于trainQA.csv中的已知映射关系
ARXIV_TO_PAPER_MAPPING = {
    # ML.ENERGY 相关
    "2505.06371": "chung2025",

    # GShard 相关
    "2104.10350": "patterson2021",

    # LLaMA 相关
    "2405.01814": "chen2024",

    # 其他论文
    "2310.03003": "samsi2024",
    "1907.10597": "schwartz2019",
    "2304.03271": "li2025b",
    "2108.06738": "wu2021b",
    "2206.05229": "strubell2019",
    "2501.05899": "khan2025",
    "2504.17674": "luccioni2025b",
    "2405.21015": "erben2023",
    "2506.15572": "ebert2024",
    "2504.06307": "khan2025",
    "2023-amazon-sustainability-report": "amazon2023",
    "2412.06288": "han2024",
    "2111.00364": "zschache2025",
    "2211.06318": "luccioni2025a",
    "2306.03163": "erben2023",
    "2309.03852": "wu2021a",
    "2408.04693": "xia2024",
    "2404.07413": "shen2024",
    "2404.11816": "jegham2025",
    "2504.11816": "jegham2025",
    "2410.06681": "ebert2024",
    "1906.02243": "strubell2019",
    "2503.05804": "chung2025",
    "2504.06307": "khan2025",
    "2501.16548": "li2025b",
    "2504.11816": "jegham2025",
    "2311.16863": "luccioni2025b",
    "2505.09598": "chung2025",
    "2505.06371": "chung2025"
}

def get_paper_id_from_arxiv(arxiv_id: str) -> str:
    """
    从arXiv ID获取论文ID

    Args:
        arxiv_id: arXiv ID (如 2505.06371)

    Returns:
        论文ID (如 chung2025)
    """
    return ARXIV_TO_PAPER_MAPPING.get(arxiv_id, "")

def add_mapping(arxiv_id: str, paper_id: str):
    """
    添加新的映射关系

    Args:
        arxiv_id: arXiv ID
        paper_id: 论文ID
    """
    ARXIV_TO_PAPER_MAPPING[arxiv_id] = paper_id

if __name__ == "__main__":
    print("可用的arXiv ID到论文ID映射:")
    for arxiv_id, paper_id in sorted(ARXIV_TO_PAPER_MAPPING.items()):
        print(f"{arxiv_id} -> {paper_id}")

    print(f"\n总计: {len(ARXIV_TO_PAPER_MAPPING)} 个映射关系")