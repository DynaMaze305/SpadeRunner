from dashboard.render.DashboardComponent import DashboardComponent

class PageComponent(DashboardComponent):
    def render_css(self):
        return """
            body { background:#111; color:#eee; font-family:Arial; padding:20px; }
            h1 { color:#4fc3f7; }
            .box { background:#222; padding:10px; margin:10px 0; border-radius:8px; }
            """