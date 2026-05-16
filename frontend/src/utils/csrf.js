export function getCsrfToken() {
  return (
    window.SETTINGS_INITIAL?.csrfToken ||
    document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
    document.querySelector('[name=csrf]')?.value ||
    document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)?.[1] ||
    ''
  )
}
