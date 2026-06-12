export function registerElementComponents(app, components) {
  components.forEach((component) => {
    app.component(component.name, component)
  })
}
