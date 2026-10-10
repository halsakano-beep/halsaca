import { expect, test } from 'claude-code/testing'

const COMPOSE = { model: 'm', promptModel: 'm', surfaces: [], tools: [], outputStyle: null, traits: [] } as const
const BASE = { id: 'intro', text: 'base', scope: 'shared' } as const

test('切のあいだはシステムプロンプトに手を出さない', async ($, on) => {
  on('prompt.compose', () => ({ sections: [BASE] }))

  const { sections } = await $.prompt.compose(COMPOSE)
  expect(sections.map(s => s.id)).toEqual(['intro'])
})

test('/oribe on で織部の一節が末尾に入り、off で消える', async ($, on) => {
  on('prompt.compose', () => ({ sections: [BASE] }))
  on('command.run', () => ({}))

  await $.command.run({ command: 'oribe', args: 'on' })
  const turnedOn = await $.prompt.compose(COMPOSE)
  expect(turnedOn.sections.map(s => s.id)).toEqual(['intro', 'oribe:mode'])

  await $.command.run({ command: 'oribe', args: 'off' })
  const turnedOff = await $.prompt.compose(COMPOSE)
  expect(turnedOff.sections.map(s => s.id)).toEqual(['intro'])
})

test('引数なしの /oribe は入と切を交互に切り替える', async ($, on) => {
  on('prompt.compose', () => ({ sections: [BASE] }))
  on('command.run', () => ({}))

  const first = await $.command.run({ command: 'oribe' })
  expect(first.text).toContain('入')
  const second = await $.command.run({ command: 'oribe' })
  expect(second.text).toContain('切')
})
