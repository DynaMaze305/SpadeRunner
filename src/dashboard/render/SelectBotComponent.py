from dashboard.render.DashboardComponent import DashboardComponent
import json

class SelectedBotComponent(DashboardComponent):
    def __init__(self, bots):
        """
        bots: list of dicts like:
        [
            {"label": "Bot 1", "bot_id": "bot_1"},
            {"label": "Bot 2", "bot_id": "bot_2"}
        ]
        """
        self.bots = bots

    def render_html(self):
        options = "".join(
            f'<option value="{b["bot_id"]}">{b["label"]}</option>'
            for b in self.bots
        )

        return f"""
        <div class="selected-bot-box">
            <h2>Selected Bot</h2>

            <div id="selected-bot-name" class="selected-bot-name">None</div>
            
            <select id="botSelector" class="bot-selector">
                {options}
            </select>

        </div>
        """

    def render_css(self):
        return """
        .selected-bot-box {
            background: #222;
            color: white;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            width: -moz-available;
            margin-bottom: 20px;
        }

        .bot-selector {
            width: 100%;
            padding: 6px;
            margin-top: 10px;
            border-radius: 5px;
            background: #333;
            color: white;
            border: 1px solid #555;
        }

        .selected-bot-name {
            font-size: 22px;
            font-weight: bold;
            margin-top: 15px;
        }
        """

    def render_js(self):
        bots_json = json.dumps(self.bots)

        return f"""
            // ### Select Bot Component (render js) ###
            let selectedBot = null;
            const botList = {bots_json};

            function updateSelectedBotDisplay(bot) {{
                document.getElementById("selected-bot-name").innerText = bot || "None";
            }}

            async function selectBot(bot) {{
                selectedBot = bot;
                updateSelectedBotDisplay(bot);

                await fetch("/api/select_bot", {{
                    method: "POST",
                    headers: {{"Content-Type": "application/json"}},
                    body: JSON.stringify({{ bot }})
                }});

                if (typeof loadAnalogData === "function") loadAnalogData();
                if (typeof loadDigitalData === "function") loadDigitalData();
                if (typeof loadMotionData === "function") loadMotionData();
                if (typeof loadBatteryData === "function") loadBatteryData();
            }}

            document.addEventListener("DOMContentLoaded", () => {{
                const sel = document.getElementById("botSelector");

                sel.addEventListener("change", e => {{
                    selectBot(e.target.value);
                }});

                // Auto-select first bot
                if (botList.length > 0) {{
                    selectBot(botList[0].bot_id);
                    sel.value = botList[0].bot_id;
                }}
            }});
        """

    def update_js(self):
        return """
            // ### Select Bot Component (update js) ###
            if (msg.bot !== selectedBot) {
                console.log("Not selelceted bot")
                break;
            }
"""