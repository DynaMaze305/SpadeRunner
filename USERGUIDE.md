# **SpadeRunner - User Guide for Deployment & Execution (Docker + AlphaBot2)**

## **1. Overview**
SpadeRunner uses Docker to run three main components:

- **app** - the main application (local test mode)
- **alphabot** - the runtime environment for the AlphaBot2 robot
- **prosody** - an optional XMPP server for local testing
- **local** - a local execution environment simulating the robot

Two scripts automate deployment and execution:

- **run_docker.sh** - runs the system locally or on the robot
- **deploy_code.sh** - deploys the codebase to a selected AlphaBot2 or runs locally

---

## **2. File Structure**

```
compose.yaml
run_docker.sh
deploy_code.sh
.env.template
.env (generated)
Dockerfile
Dockerfile.AlphaBot2
Dockerfile.local
prosody/
received_photos/
calibration_photos/
navigation_photos/
logger_state/
```

---

## **3. Docker Services (compose.yaml)**

### **3.1 prosody**
Used only for **local testing** of XMPP communication.

- Ports exposed: 5222, 5269, 5280  
- Config/data stored in `prosody-config` and `prosody-data`

### **3.2 alphabot**
Execution environment for **AlphaBot2 hardware**.

- Uses `Dockerfile.AlphaBot2`
- Mounts the same folders as `app`
- No exposed ports (runs on the robot)

### **3.3 local**
Simulates the AlphaBot2 environment **on your PC**.

- Uses `Dockerfile.local`
- Exposes port **8080**

### **3.4 app (old)**
For test.

- Mounts the full project directory
- Exposes port **8080**
- Loads environment variables from `.env`

---

## **4. Deploying Code (deploy_code.sh)**

`deploy_code.sh` prepares the `.env` file and optionally deploys the full project to a robot via SSH/rsync.

---

### **4.1 Deployment Workflow**

#### **Step 1 — Load configuration**
The script loads `.env` and `.env.template`.

#### **Step 2 — Choose robot**
You are asked:

```
Select bot to deploy on (1 or 3):
```

This selects:
- `REMOTE_HOST_1` or `REMOTE_HOST_3`

#### **Step 3 — Choose XMPP coordinator**
```
Select XMPP coordinator the bot will connect to (1-2):
```
Note: You can use `p` to generate a local prosody deployement working with the `--test-prosody` option

This selects:
- `XMPP_DOMAIN_1` or `XMPP_DOMAIN_2`


#### **Step 4 — Generate .env**
The script creates `.env.temp` from `.env.template` and fills:

- `{{REMOTE_HOST}}`
- `{{XMPP_DOMAIN}}`
- `{{ROBOT_NUM}}`
- `{{REMOTE_MODE}}` (LOCAL or REMOTE)

You are asked:

```
Do you want to update .env file? (y/n)
```

If yes the `.env.temp` becomes `.env`.

#### **Step 5 — Deploy (optional)**
If you choose **not local**, the script warns:

```
WARNING: This will DELETE files on the remote side that are not present locally.
Proceed with deployment? (y/n)
```

If confirmed, it runs:

```
rsync -avz --delete -e "ssh -p <port>" local/ remote:/path/
```
Note: You can exclude file or change option by modifying the `RYSNC_OPT`into the `.env` file.

---

## **5. Running the System (run_docker.sh)**

`run_docker.sh` provides four modes:

| Mode | Command | Description |
|------|---------|-------------|
| **Test mode** | `./run_docker.sh --test` | Runs the app locally (no robot) |
| **Test + Prosody** | `./run_docker.sh --test-prosody` | Runs app + local XMPP server |
| **Local mode** | `./run_docker.sh --local` | Runs the robot agent locally |
| **AlphaBot mode** | `./run_docker.sh --alphabot` | Runs the robot agent on the AlphaBot2 |

### **5.1 What the script does**
1. Removes old containers/images  
2. Starts Prosody if requested  
3. Runs either:
   - `app` (test mode)
   - `local` (local robot simulation)
   - `alphabot` (real robot)

### **4.2 Examples**

#### **Run the app locally**
```
./run_docker.sh --test
```

#### **Run the app + local XMPP server**
```
./run_docker.sh --test-prosody
```

#### **Run the robot agent locally**
```
./run_docker.sh --local
```

#### **Run on the AlphaBot2**
```
./run_docker.sh --alphabot
```

---

## **6. Typical Usage Scenarios**

### **6.1 Local development**
1. Run deployment script:
   ```
   ./deploy_code.sh
   ```
   Choose:
   - Bot: any
   - Coordinator: any
   - Local: **y**

2. Run the app:
   ```
   ./run_docker.sh --test
   ```

---

### **6.2 Telemetry local run**
1. Deploy locally:
   ```
   ./deploy_code.sh
   ```
   Choose "local" mode.

2. Run:
   ```
   ./run_docker.sh --local
   ```

---

### **6.3 Run on AlphaBot2**
1. Run:
   ```
   ./deploy_code.sh
   ```
   Choose:
   - Bot: **1 or 3**
   - Coordinator: **1 or 2**
   - Local: **n**
   - Confirm deployment

2. On the robot, run:
   ```
   ./run_docker.sh --alphabot
   ```

---

## **7. Environment Variables**

The `.env.template` defines placeholders:

| Variable | Meaning |
|----------|---------|
| `REMOTE_HOST` | IP of the AlphaBot2 |
| `XMPP_DOMAIN` | XMPP server domain |
| `ROBOT_NUM` | Robot ID |
| `REMOTE_MODE` | LOCAL or REMOTE |

The deployment script fills these automatically.

---

## **8. Logs**

- Deployment logs: `deploy.log`
- Docker logs:
  ```
  docker logs spaderunner-app
  docker logs spaderunner-agent
  docker logs spaderunner-prosody
  ```

---

## **9. Troubleshooting**

### **Docker containers not starting**
```
docker ps -a
docker logs <container>
```

### **Prosody not reachable**
Ensure ports 5222/5269/5280 are not blocked.

### **Robot not responding**
Check:
- SSH connectivity
- `.env` values
- XMPP coordinator availability
