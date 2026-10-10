import { Component, type ErrorInfo, type ReactNode } from 'react'

interface State {
  failed: boolean
}

/**
 * The map needs WebGL. If it cannot start (old hardware, locked-down
 * browsers), say so instead of blanking the page; the route list still works.
 */
export class MapErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { failed: false }

  static getDerivedStateFromError(): State {
    return { failed: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Map failed to render', error, info.componentStack)
  }

  render() {
    if (!this.state.failed) return this.props.children
    return (
      <div
        role="alert"
        className="flex h-full items-center justify-center bg-slate-100 p-6 text-center"
      >
        <div className="max-w-sm">
          <p className="font-semibold text-slate-800">The map could not be displayed</p>
          <p className="mt-1 text-sm text-slate-600">
            Your browser may not support WebGL. Route comparisons and every checkpoint are still
            listed in the panel.
          </p>
        </div>
      </div>
    )
  }
}
