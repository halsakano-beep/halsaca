import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

const isOn = atom({ plugin: 'oribe', key: 'isOn' } as const, false)

export const ORIBE_TEXT = [
  '# 織部モード',
  '案・提案・文章・設計を出すときは、まず素直で整った案を示し、そのあとに「破格の一案」をひとつだけ添える。',
  '破格の一案は、前提・順序・尺度・視点のどれかを意図的に歪めたもの。奇をてらうだけの思いつきではなく、歪めたことで何が見えるかを一行で言い添える。',
  '整った案を崩す必要はない。歪みは添えるもので、主役を奪わない。',
  '事実確認、コードの修正、手順の実行など、歪めると害になる場面では破格の一案を出さない。',
].join('\n')

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'oribe',
      description: '織部モードの切り替え（破格の一案を添える）',
      argumentHint: '[on|off]',
      immediate: true,
    })

    return next(e)
  })

  on('command.run', { command: 'oribe' }, async ($, e) => {
    const arg = (e.args ?? '').trim()
    const now = await read($, isOn)
    const turnedOn = arg === 'on' ? true : arg === 'off' ? false : !now
    await update($, isOn, () => turnedOn)
    $.ui.status(turnedOn ? '織部' : undefined)

    return { text: turnedOn ? '織部モード：入。整った案の横に、歪めた一案を添えます。' : '織部モード：切。' }
  })

  on('prompt.compose', async ($, e, next) => {
    const result = await next(e)

    if (!(await read($, isOn))) {
      return result
    }

    return {
      ...result,
      sections: [...result.sections, { id: 'oribe:mode', text: ORIBE_TEXT, scope: 'session' as const }],
    }
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (e.props.hasSurvey || !(await read($, isOn))) {
      return next(e)
    }

    const { Box, Button, Text } = $.ui.resolve(e)

    return (
      <Box>
        <Text color="yellow">▲ 破格 </Text>
        <Text dimColor>織部モード中 </Text>
        <Button key="off" label="切る" onPress={async () => {
            await update($, isOn, () => false)
            $.ui.status(undefined)
          }} />
      </Box>
    )
  })
}
