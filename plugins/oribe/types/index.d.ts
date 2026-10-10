export type OribeMode = boolean

declare module 'claude-code' {
  interface PluginState {
    oribe: { isOn: OribeMode }
  }
}
