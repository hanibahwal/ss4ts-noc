import { Component } from 'react'


export default class AppErrorBoundary extends Component {
  constructor(props) {
    super(props)

    this.state = {
      hasError: false,
    }
  }


  static getDerivedStateFromError() {
    return {
      hasError: true,
    }
  }


  componentDidCatch(error, errorInfo) {
    console.error(
      'Unhandled application error:',
      error,
      errorInfo,
    )
  }


  handleReload = () => {
    window.location.reload()
  }


  render() {
    if (!this.state.hasError) {
      return this.props.children
    }

    return (
      <main
        className="app-error-boundary"
        role="alert"
        aria-live="assertive"
      >
        <section className="app-error-boundary__card">
          <div
            className="app-error-boundary__icon"
            aria-hidden="true"
          >
            !
          </div>

          <div className="app-error-boundary__content">
            <p className="app-error-boundary__eyebrow">
              خطأ غير متوقع
            </p>

            <h1>
              تعذر عرض التطبيق
            </h1>

            <p>
              حدث خطأ أثناء تحميل الواجهة.
              أعد تحميل الصفحة للمتابعة.
            </p>
          </div>

          <button
            type="button"
            className="app-error-boundary__action"
            onClick={this.handleReload}
          >
            إعادة تحميل الصفحة
          </button>
        </section>
      </main>
    )
  }
}
