# Design context

Read by the `hig-*` skills before they ask questions.

- **Product:** the live dashboard for this pipeline: a Streamlit 1.66 web app on
  Streamlit Community Cloud. Not a native Apple app, so apply HIG principles
  (hierarchy, clarity, content over chrome, system type and color, accessibility)
  rather than platform components.
- **Audience:** a hiring manager or data-engineering interviewer giving it about a
  minute. First job: show a real, live, observable pipeline. Analysis comes second.
- **Pages:** Overview (default), Pipeline health, Operations, with top navigation.
- **Modes:** light and dark, following the viewer's system setting.
- **Accessibility target:** WCAG AA. Status is never color alone.
- **Where the decisions live:** `docs/superpowers/specs/2026-10-22-dashboard-redesign-design.md`
  (what and why), `.streamlit/config.toml` (theme tokens), `dashboard/style.css`
  (the only stylesheet).
