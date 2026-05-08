from dashboard.render.DashboardComponent import DashboardComponent

class PageComponent(DashboardComponent):
    def render_css(self):
        return """
            body { background:#111; color:#eee; font-family:Arial; padding:20px; }
            h1 { color:#4fc3f7; }
            .box { background:#222; padding:10px; margin:10px 0; border-radius:8px; }
            """


# ---------------------------------------------------------
#  HTML RENDERS HELPER
# ---------------------------------------------------------
def row(*components_html):
    return (
        '<div style="display:flex; gap:20px; align-items:flex-start;">'
        + "".join(f'<div style="flex:1;">{html}</div>' for html in components_html)
        + "</div>"
    )
