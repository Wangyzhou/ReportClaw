import type { ReportVersion } from '../types'

export const reportVersions: ReportVersion[] = [
  { id: 'v3', version: 3, createdAt: '2026-04-20 14:30', wordCount: 4520, status: 'final' },
  { id: 'v2', version: 2, createdAt: '2026-04-20 13:15', wordCount: 3890, status: 'reviewed' },
  { id: 'v1', version: 1, createdAt: '2026-04-20 12:00', wordCount: 3200, status: 'draft' },
]

export const sampleReport = `# 鹿晗关晓彤舆情分析报告

## 一、事件概述

近期，鹿晗与关晓彤相关话题再次引发社交媒体广泛关注。本报告基于多渠道数据采集，对相关舆情进行系统分析。[ref:chunk_001]

## 二、数据来源与方法

本次分析覆盖以下平台数据：
- 微博热搜及评论数据 [ref:chunk_002]
- 抖音短视频互动数据
- 知乎讨论话题

## 三、舆情趋势分析

### 3.1 传播热度曲线

舆情在4月15日达到峰值，随后逐步回落。[ref:chunk_003]

### 3.2 情感分析

正面情感占比 42%，中性 35%，负面 23%。[ref:chunk_004]

## 四、结论与建议

建议品牌方密切关注后续舆情走向，及时调整公关策略。
`
