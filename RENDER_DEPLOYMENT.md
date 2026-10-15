# Deploying Autonomous Sales Agent on Render

This guide walks you through deploying the **Autonomous Sales Agent** on [Render](https://render.com).

The application consists of:
- **Backend**: FastAPI with LangGraph, MongoDB Atlas (Motor/Beanie), WebSockets, and Cal.com integration.
- **Frontend**: A React 19 Shadow DOM widget and an interactive landing page showcasing the AI Sales Engineer.
- Both are served seamlessly from a single web service on Render, avoiding any CORS or WebSocket cross-domain issues.

---

## 📋 Prerequisites

Before starting, ensure you have:
1. A **[Render Account](https://render.com)**.
2. A **[GitHub](https://github.com)** repository containing this project code.
3. A **[MongoDB Atlas](https://www.mongodb.com/cloud/atlas)** cluster connection string (`MONGODB_URI`).
4. At least one **LLM API Key**:
   - `OPENROUTER_API_KEY` (Recommended for GPT-4o-mini via OpenRouter) **OR**
   - `OPENAI_API_KEY` (OpenAI direct key)
5. *(Optional)* **Cal.com API Key** (`CAL_API_KEY`) for live calendar scheduling.
6. *(Optional)* **SMTP Credentials** (`SMTP_EMAIL`, `SMTP_PASSWORD`) for email notifications and OTP dispatch (Gmail App Password).

---

## ⚠️ Critical: MongoDB Atlas Network Access

Render uses dynamic IP addresses for web services. If you do not configure MongoDB Atlas Network Access, the deployment will hang or fail to connect:

1. Open your **[MongoDB Atlas Dashboard](https://cloud.mongodb.com/)**.
2. Go to **Security** → **Network Access** in the left sidebar.
3. Click **+ Add IP Address**.
4. Choose **Allow Access from Anywhere** (`0.0.0.0/0`).
5. Click **Confirm**.

---

## 🚀 Option 1: 1-Click Blueprint Deployment (Recommended)

This repository includes a `render.yaml` blueprint configured with production defaults, Docker multi-stage build, and health checks.

1. **Push your code to GitHub**:
   ```bash
   git add .
   git commit -m "Configure production deployment for Render"
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
   git push -u origin master # or main
   ```

2. Go to the **[Render Dashboard](https://dashboard.render.com/)**.
3. Click **New +** → **Blueprint**.
4. Connect your GitHub repository.
5. Render will automatically detect `render.yaml`.
6. Fill in the required environment variables prompted on screen (`MONGODB_URI`, `OPENAI_API_KEY` or `OPENROUTER_API_KEY`, etc.).
7. Click **Apply**. Render will automatically build the multi-stage Docker container and deploy the service.

---

## 🐳 Option 2: Manual Docker Web Service

If you prefer to configure the Web Service manually via the Render UI:

1. In Render Dashboard, click **New +** → **Web Service**.
2. Select **Build and deploy from a Git repository** and connect your repository.
3. Configure the service settings:
   - **Name**: `aanandi-sales-agent` (or your choice)
   - **Region**: Select closest to your users (e.g., `Oregon`, `Frankfurt`, `Singapore`)
   - **Language / Runtime**: **Docker**
   - **Dockerfile Path**: `./Dockerfile`
   - **Instance Type**:
     - *Starter* ($7/mo) is recommended because it includes dedicated RAM for PyTorch/audio models.
     - *Free* (512 MB RAM) is supported; our resilient code defers heavy model loading to prevent startup crashes.
4. Set **Health Check Path** to `/health`.
5. Add the **Environment Variables** (see table below).
6. Click **Create Web Service**.

---

## 🐍 Option 3: Native Python Web Service (Without Docker)

If you prefer running in Render's native Python runtime:

1. In Render Dashboard, click **New +** → **Web Service**.
2. Connect your repository.
3. Configure:
   - **Runtime**: **Python 3**
   - **Build Command**: `./build.sh`
   - **Start Command**: `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Set **Health Check Path** to `/health`.
5. Add the **Environment Variables** (see table below).
6. Click **Create Web Service**.

---

## 🔑 Environment Variables Reference

Configure these in the Render Web Service under **Environment**:

| Variable | Required | Description | Example |
| :--- | :---: | :--- | :--- |
| `PORT` | Auto | Render sets this automatically (defaults to 10000) | `10000` |
| `MONGODB_URI` | **Yes** | MongoDB Atlas connection string | `mongodb+srv://user:pass@cluster0.xxx.mongodb.net/aanandi_sales?retryWrites=true&w=majority` |
| `DATABASE_NAME` | No | Database name in MongoDB | `aanandi_sales` |
| `OPENROUTER_API_KEY` | Conditional | OpenRouter API Key for GPT-4o-mini reasoning | `sk-or-v1-...` |
| `OPENAI_API_KEY` | Conditional | OpenAI API Key (used if OpenRouter not provided) | `sk-...` |
| `CAL_API_KEY` | No | Cal.com API key for calendar bookings | `cal_live_...` |
| `CAL_EVENT_TYPE_ID` | No | Cal.com Event Type ID | `7297448` |
| `CAL_TIME_ZONE` | No | Timezone for booking schedule | `Asia/Kolkata` |
| `SMTP_EMAIL` | No | Gmail address for dispatching OTPs and lead alerts | `your_email@gmail.com` |
| `SMTP_PASSWORD` | No | Gmail 16-character App Password | `xxxx xxxx xxxx xxxx` |
| `SMTP_SERVER` | No | SMTP Server Host | `smtp.gmail.com` |
| `SMTP_PORT` | No | SMTP TLS Port | `587` |
| `SMTP_FROM_EMAIL` | No | Sender email address | `your_email@gmail.com` |
| `BOOKING_NOTIFICATION_EMAIL`| No | Team inbox receiving confirmed bookings | `team@company.com` |
| `RECEPTIONIST_EMAIL` | No | Receptionist email for lead inquiries | `receptionist@company.com`|
| `TECH_TEAM_EMAIL` | No | Technical team email for architecture/intake alerts | `tech@company.com` |
| `RAZORPAY_KEY_ID` | No | Razorpay Key ID (demo mode active if omitted) | `rzp_live_...` |
| `RAZORPAY_KEY_SECRET` | No | Razorpay Key Secret | `your_secret` |

---

## ✅ Post-Deployment Verification Checklist

Once Render shows **"Live"**:

1. **Verify Health Check**:
   Open in your browser:
   ```
   https://<your-render-url>.onrender.com/health
   ```
   Expected response:
   ```json
   { "status": "ok", "service": "Aanandi Sales API Gateway", "timestamp": "..." }
   ```

2. **Verify Interactive Showcase Landing Page**:
   Visit:
   ```
   https://<your-render-url>.onrender.com/
   ```
   You should see the Aanandi TechnoSoft landing page with the AI Sales widget in the bottom-right corner.

3. **Verify AI Agent WebSocket Stream**:
   - Click the chat bubble launcher.
   - Send: `"Hi, what platforms have you built?"`
   - Confirm the agent streams back its portfolio and suggests follow-up questions.

4. **Verify Swagger API Documentation**:
   Visit:
   ```
   https://<your-render-url>.onrender.com/docs
   ```

---

## 🌐 Embedding the Widget on External Websites

Once your Render service is deployed, you can embed the sales widget on **any** external website (WordPress, Shopify, Webflow, custom HTML) by adding these two tags before `</body>`:

```html
<!-- 1. Mount the agent with your Render URL -->
<aanandi-agent
  api-base="https://<your-render-url>.onrender.com"
  theme="dark"
></aanandi-agent>

<!-- 2. Load the self-contained widget script -->
<script src="https://<your-render-url>.onrender.com/widget.min.js"></script>
```

---

## 🛠️ Troubleshooting

- **Build failed: `npm: not found`**: Ensure you are using the **Docker** runtime option or that `build.sh` is executed in a Node+Python environment.
- **MongoDB connection timeout**: Verify that MongoDB Atlas Network Access has `0.0.0.0/0` added.
- **WebSocket connection closed immediately**: Ensure the browser URL starts with `https://` (which connects via `wss://`). Render handles SSL termination automatically.
- **Service spins down on Render Free Tier**: Render free web services go to sleep after 15 minutes of inactivity. The first request may take 30-50 seconds to wake up. Upgrading to the **Starter Plan** ($7/mo) ensures 24/7 uptime without sleep.
