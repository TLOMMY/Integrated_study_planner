import { test } from 'node:test'
import assert from 'node:assert/strict'
import { subjectOf } from './subjects.js'

test('按课程名分科', () => {
  const cases = {
    高等数学: 'sci', 线性代数: 'sci', 大学物理: 'sci', 数据结构: 'sci', 程序设计基础: 'sci', 物理实验: 'sci',
    生物信息学: 'bio', 有机化学: 'bio', 生命科学导论: 'bio',
    中国近现代史纲要: 'soc', 马克思主义基本原理: 'soc', 思想道德与法治: 'soc', 经济数学: 'soc', 军事理论: 'soc',
    世界史: 'his', 自然地理: 'his',
    大学英语: 'art', 大学语文: 'art', 美术鉴赏: 'art', 平面设计: 'art',
    体育: 'def', 劳动教育: 'def', '': 'def',
  }
  for (const [name, key] of Object.entries(cases)) assert.equal(subjectOf(name), key, name)
})

test('编辑器里选的分科色优先于课程名', () => {
  assert.equal(subjectOf({ course_name: '高等数学', color: '#A56A6A' }), 'art')
  assert.equal(subjectOf({ course_name: '高等数学', color: '#d5e2ea' }), 'sci')
  // 以前随机分配的颜色不代表科目，按课程名判断
  assert.equal(subjectOf({ course_name: '大学英语', color: '#4F6EF7' }), 'art')
})
