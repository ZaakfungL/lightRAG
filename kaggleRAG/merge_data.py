#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据合并脚本：将metadata.csv中的ref_url根据ref_id合并到test_Q_filled.csv中
"""

import pandas as pd
import os

def merge_ref_url():
    """合并ref_url字段到test_Q_filled.csv"""

    # 文件路径
    test_file = 'test_Q_filled.csv'
    metadata_file = 'metadata.csv'
    output_file = 'test_Q_filled_with_url.csv'

    try:
        # 读取CSV文件，处理可能的编码问题
        print("正在读取CSV文件...")

        # 尝试不同的编码方式读取文件
        encodings = ['utf-8', 'gbk', 'gb2312', 'latin1', 'iso-8859-1']

        df_test = None
        df_metadata = None

        # 读取test_Q_filled.csv
        for encoding in encodings:
            try:
                df_test = pd.read_csv(test_file, encoding=encoding)
                print(f"成功使用 {encoding} 编码读取 test_Q_filled.csv")
                break
            except UnicodeDecodeError:
                continue

        if df_test is None:
            raise ValueError("无法读取 test_Q_filled.csv，尝试了多种编码方式")

        # 读取metadata.csv
        for encoding in encodings:
            try:
                df_metadata = pd.read_csv(metadata_file, encoding=encoding)
                print(f"成功使用 {encoding} 编码读取 metadata.csv")
                break
            except UnicodeDecodeError:
                continue

        if df_metadata is None:
            raise ValueError("无法读取 metadata.csv，尝试了多种编码方式")

        print(f"test_Q_filled.csv 行数: {len(df_test)}")
        print(f"metadata.csv 行数: {len(df_metadata)}")

        # 创建ref_id到url的映射字典
        # metadata.csv中的id对应test_Q_filled.csv中的ref_id
        ref_url_mapping = dict(zip(df_metadata['id'], df_metadata['url']))

        # 处理ref_id字段，返回对应的URL列表
        def get_ref_urls(ref_ids):
            """根据ref_id列表获取对应的URL列表"""
            if pd.isna(ref_ids):
                return None

            # 处理is_blank特殊情况
            if ref_ids == 'is_blank':
                return 'is_blank'

            # 如果是字符串格式，如"['han2024']"或"['cottier2024', 'li2025a']"
            if isinstance(ref_ids, str):
                # 使用ast.literal_eval安全地解析列表字符串
                import ast
                try:
                    ref_list = ast.literal_eval(ref_ids)
                    if isinstance(ref_list, list):
                        # 为每个ref_id查找对应的URL
                        url_list = []
                        for ref_id in ref_list:
                            url = ref_url_mapping.get(ref_id, None)
                            url_list.append(url)
                        return url_list
                    elif isinstance(ref_list, str):
                        # 单个ref_id的情况
                        return [ref_url_mapping.get(ref_list, None)]
                except:
                    # 如果解析失败，尝试手动去除方括号和引号
                    cleaned_ref = ref_ids.strip("[]'\"")
                    if cleaned_ref:
                        return [ref_url_mapping.get(cleaned_ref, None)]
            return None

        # 根据ref_id列表获取对应的URL列表
        df_test['ref_url'] = df_test['ref_id'].apply(get_ref_urls)

        # 重新排列列顺序，将ref_url放在ref_id右边
        columns = df_test.columns.tolist()
        ref_id_index = columns.index('ref_id')
        # 移除ref_url从当前位置，然后插入到ref_id后面
        columns.remove('ref_url')
        columns.insert(ref_id_index + 1, 'ref_url')
        df_test = df_test[columns]

        # 保存合并后的文件，强制使用UTF-8编码
        df_test.to_csv(output_file, index=False, encoding='utf-8')
        print(f"\n合并完成！输出文件: {output_file}")

        # 显示统计信息
        total_rows = len(df_test)
        matched_urls = df_test['ref_url'].notna().sum()
        print(f"总记录数: {total_rows}")
        print(f"成功匹配URL的记录数: {matched_urls}")
        print(f"匹配率: {matched_urls/total_rows*100:.1f}%")

        # 显示前几行示例
        print("\n前5行数据预览:")
        print(df_test[['id', 'ref_id', 'ref_url']].head())

        return True

    except FileNotFoundError as e:
        print(f"错误: 找不到文件 {e.filename}")
        return False
    except Exception as e:
        print(f"错误: {str(e)}")
        return False

if __name__ == "__main__":
    merge_ref_url()