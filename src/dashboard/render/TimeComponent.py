from dashboard.render.DashboardComponent import DashboardComponent

class RaceTimeComponent(DashboardComponent):
    def render_html(self):
        return """
        <div class="race-time-box">
            <h2>Last Race Time</h2>
            <div>My time:    <div id="race-time-value">--</div></div>
            <div>Total time: <div id="total-time-value">--</div></div>
        </div>
        """

    def render_css(self):
        return """
        .race-time-box {
            background: #222;
            color: white;
            padding: 15px;
            border-radius: 10px;
            width: 200px;
            text-align: center;
            margin-bottom: 20px;
        }

        #race-time-value {
            font-size: 28px;
            font-weight: bold;
            margin-top: 10px;
        }

        #total-time-value {
            font-size: 28px;
            font-weight: bold;
            margin-top: 10px;
        }
        """

    def render_js(self):
        return """
            async function loadRaceTime() {
                const race = await fetch("/api/race_time").then(r => r.json());
                document.getElementById("race-time-value").innerText = race.race_time || "--";

                const total = await fetch("/api/total_time").then(r => r.json());
                document.getElementById("total-time-value").innerText = total.total_time || "--";
            }
        """

    def update_js(self):
        return """
        if (msg.type === "race_time" && msg.bot === selectedBot) {
            document.getElementById("race-time-value").innerText = msg.data;
            return;
        }
        if (msg.type === "total_time" && msg.bot === selectedBot) {
            document.getElementById("total-time-value").innerText = msg.data;
            return;
        }
        """
