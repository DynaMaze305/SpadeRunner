from dashboard.render.DashboardComponent import DashboardComponent

class ImageDisplayComponent(DashboardComponent):
    def render_html(self):
        return """
        <div class="image-display-box">
            <h2>Camera</h2>
            <img id="camera-frame" class="camera-frame" src="" alt="No image yet">
        </div>
        """

    def render_css(self):
        return """
        .image-display-box {
            background: #222;
            padding: 15px;
            border-radius: 10px;
            color: white;
            width: 400px;
            text-align: center;
        }

        .camera-frame {
            width: 100%;
            border-radius: 8px;
            border: 1px solid #444;
            background: #000;
        }
        """

    def render_js(self):
        return """
        function updateCameraFrame(b64) {
            const img = document.getElementById("camera-frame");
            img.src = "data:image/jpeg;base64," + b64;
        }
        """

    def update_js(self):
        # Called inside WS handler when msg.type == "image_frame"
        return """
        if (msg.type === "image_frame") {
            updateCameraFrame(msg.values);
            return;
        }
        """
