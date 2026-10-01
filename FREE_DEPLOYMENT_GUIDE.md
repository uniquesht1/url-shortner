# 100% Free Lifetime Deployment Guide

This project can be deployed completely free forever using free-tier cloud services:

| Component | Free Cloud Provider | Free Tier Allowance |
| :--- | :--- | :--- |
| **PostgreSQL** | [Neon.tech](https://neon.tech) / [Supabase](https://supabase.com) | 0.5 GB storage, serverless, always free |
| **Redis** | [Upstash](https://upstash.com) | 10,000 commands/day, serverless Redis with TLS |
| **RabbitMQ** | [CloudAMQP](https://www.cloudamqp.com/) ("Little Lemur") | 1,000,000 msgs/month, 20 connections max |
| **Compute (API + Worker + UI)** | [Render.com](https://render.com) / [Koyeb](https://koyeb.com) | 1 Free Web Service (Docker / Python) |

---

## Step 1: Create Free Cloud Infrastructure (5 minutes)

### 1. PostgreSQL (Neon)
1. Go to [neon.tech](https://neon.tech) and create a free project.
2. Copy your connection string:
   ```text
   postgresql://user:password@ep-sample-123.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
   *(Our code automatically converts `postgresql://` and `postgres://` to `postgresql+psycopg2://` with `pool_pre_ping=True`).*

### 2. Redis (Upstash)
1. Go to [upstash.com](https://upstash.com) and create a free Redis database.
2. In the database details, copy the `rediss://...` connection string:
   ```text
   rediss://default:your_token@us1-sample.upstash.io:6379
   ```

### 3. RabbitMQ (CloudAMQP)
1. Go to [cloudamqp.com](https://www.cloudamqp.com/) and create a free team.
2. Click **Create New Instance** and select **Little Lemur (Free)**.
3. Copy the AMQP connection string:
   ```text
   amqps://user:password@lemur.cloudamqp.com/vhost
   ```
   *(Our new `RabbitMQPublisher` connection-reuse ensures you only use **1** of your 20 free connections).*

---

## Step 2: Deploy to Render / Koyeb (Single Free Web Service)

Because free tiers give **1 free web container**, our app supports running both the FastAPI web server and the background RabbitMQ analytics worker inside that single container!

### Deploying on Render:
1. Push this repository to your GitHub.
2. Go to [render.com](https://render.com) -> **New** -> **Web Service**.
3. Select your GitHub repository.
4. Set the following:
   - **Environment**: `Docker` (or `Python 3`)
   - **Plan**: `Free`
5. Under **Environment Variables**, add:
   ```env
   DATABASE_URL=postgresql://user:password@ep-sample-123.neon.tech/neondb?sslmode=require
   REDIS_URL=rediss://default:your_token@us1-sample.upstash.io:6379
   RABBITMQ_URL=amqps://user:password@lemur.cloudamqp.com/vhost
   RUN_WORKER_IN_BACKGROUND=true
   INSTANCE_NAME=cloud-api
   ```
6. Click **Deploy Web Service**!

Render will build the Dockerfile and launch your app. When it boots:
- FastAPI serves the sleek dark UI at your public URL (`https://your-app.onrender.com`).
- The Snowflake ID generator creates unique IDs.
- Clicks pre-warm your Upstash Redis cache.
- The background thread consumes click events from CloudAMQP and writes analytics to Neon PostgreSQL.

---

## Step 3 (Alternative): 100% Free Lifetime VM (Oracle Cloud)

If you prefer running the entire multi-container Docker cluster (`api1`, `api2`, `nginx`, `postgres`, `redis`, `rabbitmq`, `worker`):
1. Sign up for [Oracle Cloud Always Free](https://www.oracle.com/cloud/free/).
2. Launch a free **Ampere ARM VM** (up to 4 OCPUs, 24 GB RAM for life).
3. Clone your repo onto the VM and run:
   ```bash
   docker compose up -d
   ```
4. Point your domain or public IP to port 80!
