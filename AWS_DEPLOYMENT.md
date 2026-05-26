# AWS Deployment Guide — AI Action Assistant

## Architecture

```
Users
  ↓
CloudFront (HTTPS + CDN)
  ↓
S3 (static/login.html, signup.html, dashboard.html)
  ↓  (API calls to)
EC2 Ubuntu 22.04 — Nginx → Gunicorn → FastAPI (Docker)
  ↓                    ↓
RDS PostgreSQL     EBS Volume (/data/chromadb)
```

---

## Phase 1 — EC2 Instance Setup

### 1.1 Launch EC2

- AMI: Ubuntu 22.04 LTS
- Instance type: t3.medium (4GB RAM — required for sentence-transformers)
- Storage: 30GB gp3 root volume
- Security Group inbound rules:
  - Port 22   (SSH)     — your IP only
  - Port 80   (HTTP)    — 0.0.0.0/0
  - Port 443  (HTTPS)   — 0.0.0.0/0
  - Port 8000 (FastAPI) — your IP only (for direct testing)

### 1.2 Attach EBS Volume for ChromaDB

```bash
# In AWS Console: EC2 → Volumes → Create Volume
# Size: 10GB gp3, same AZ as your EC2
# Attach to EC2 as /dev/xvdf

# On EC2:
sudo mkfs.ext4 /dev/xvdf
sudo mkdir -p /data/chromadb
sudo mount /dev/xvdf /data/chromadb

# Persist mount across reboots
echo '/dev/xvdf /data/chromadb ext4 defaults,nofail 0 2' | sudo tee -a /etc/fstab

sudo chown -R ubuntu:ubuntu /data/chromadb
```

### 1.3 Install Docker on EC2

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin
sudo usermod -aG docker ubuntu
newgrp docker
```

---

## Phase 2 — RDS PostgreSQL Setup

### 2.1 Create RDS Instance

- Engine: PostgreSQL 15
- Template: Free tier (db.t3.micro)
- DB name: `aiassistant`
- Username: `aiuser`
- Password: (strong password — save it)
- VPC: same VPC as EC2
- Security Group: allow port 5432 from EC2 security group only

### 2.2 Get Connection String

```
DATABASE_URL=postgresql://aiuser:yourpassword@your-rds-endpoint.rds.amazonaws.com:5432/aiassistant
```

---

## Phase 3 — Deploy Backend on EC2

### 3.1 Clone and configure

```bash
git clone https://github.com/YOUR_USERNAME/ai-action-assistant.git
cd ai-action-assistant
cp .env.example .env
nano .env   # fill in all values
```

### 3.2 Key .env values for AWS

```env
ENVIRONMENT=production
DATABASE_URL=postgresql://aiuser:yourpassword@your-rds-endpoint.rds.amazonaws.com:5432/aiassistant
CHROMA_DB_PATH=/data/chromadb
UPLOAD_DIR=/tmp/uploads
JWT_SECRET_KEY=your-strong-random-secret-here

GROQ_API_KEY_PRIMARY=your_key
NEWS_API_KEY=your_key
OPENWEATHER_API_KEY=your_key
EMAIL_USER=your_gmail@gmail.com

# CORS — add your CloudFront URL after Phase 4
ALLOWED_ORIGINS=https://your-cloudfront-id.cloudfront.net,http://localhost:8000

# Google OAuth — add your EC2 domain
GOOGLE_CREDENTIALS_FILE=credentials.json
GOOGLE_TOKEN_FILE=token.pickle
```

### 3.3 Encode Google auth files

```bash
python scripts/encode_token.py
# Copy GOOGLE_TOKEN_B64 and GOOGLE_CREDENTIALS_B64 values into .env
```

### 3.4 Build and run Docker container

```bash
docker build -t ai-action-assistant .

docker run -d \
  --name ai-assistant \
  --restart unless-stopped \
  -p 8000:8000 \
  -v /data/chromadb:/data/chromadb \
  -v /tmp/uploads:/tmp/uploads \
  --env-file .env \
  ai-action-assistant
```

### 3.5 Verify

```bash
curl http://localhost:8000/health
# Should return: {"status":"ok","environment":"aws",...}
```

---

## Phase 4 — Nginx + HTTPS on EC2

### 4.1 Install Nginx and Certbot

```bash
sudo apt-get install -y nginx certbot python3-certbot-nginx
```

### 4.2 Point your domain to EC2

In your DNS provider (or Route 53):
- Create A record: `api.yourdomain.com` → EC2 public IP

### 4.3 Deploy Nginx config

```bash
sudo cp nginx.conf /etc/nginx/sites-available/ai-action-assistant
sudo ln -s /etc/nginx/sites-available/ai-action-assistant /etc/nginx/sites-enabled/
sudo nginx -t

# Get free SSL certificate
sudo certbot --nginx -d api.yourdomain.com

sudo systemctl reload nginx
```

### 4.4 Test HTTPS

```bash
curl https://api.yourdomain.com/health
```

---

## Phase 5 — S3 Frontend Deployment

### 5.1 Create S3 bucket

```bash
aws s3 mb s3://ai-assistant-frontend --region us-east-1
aws s3 website s3://ai-assistant-frontend \
  --index-document login.html \
  --error-document login.html
```

### 5.2 Set bucket policy (public read)

```bash
aws s3api put-bucket-policy --bucket ai-assistant-frontend --policy '{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": "*",
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::ai-assistant-frontend/*"
  }]
}'
```

### 5.3 Configure API_BASE_URL in frontend files

Before uploading, add this line to each HTML file just before `</head>`:

```html
<script>window.API_BASE_URL = 'https://api.yourdomain.com';</script>
```

Or use the sed command:

```bash
for f in static/login.html static/signup.html static/dashboard.html; do
  sed -i 's|</head>|<script>window.API_BASE_URL="https://api.yourdomain.com";</script></head>|' $f
done
```

### 5.4 Upload frontend files

```bash
aws s3 sync static/ s3://ai-assistant-frontend/ \
  --exclude "*" \
  --include "*.html" \
  --cache-control "no-cache"
```

---

## Phase 6 — CloudFront Distribution

### 6.1 Create distribution

```bash
aws cloudfront create-distribution --distribution-config '{
  "CallerReference": "ai-assistant-'$(date +%s)'",
  "Origins": {
    "Quantity": 1,
    "Items": [{
      "Id": "S3-ai-assistant-frontend",
      "DomainName": "ai-assistant-frontend.s3-website-us-east-1.amazonaws.com",
      "CustomOriginConfig": {
        "HTTPPort": 80, "HTTPSPort": 443,
        "OriginProtocolPolicy": "http-only"
      }
    }]
  },
  "DefaultCacheBehavior": {
    "TargetOriginId": "S3-ai-assistant-frontend",
    "ViewerProtocolPolicy": "redirect-to-https",
    "CachePolicyId": "658327ea-f89d-4fab-a63d-7e88639e58f6",
    "Compress": true
  },
  "DefaultRootObject": "login.html",
  "Enabled": true,
  "Comment": "AI Action Assistant Frontend"
}'
```

Or create via AWS Console:
- CloudFront → Create Distribution
- Origin: S3 website endpoint
- Default root object: `login.html`
- Viewer protocol: Redirect HTTP to HTTPS

### 6.2 Update CORS on backend

Add your CloudFront URL to `ALLOWED_ORIGINS` in `.env` on EC2:

```env
ALLOWED_ORIGINS=https://d1234abcd.cloudfront.net,https://app.yourdomain.com
```

Then restart the container:

```bash
docker restart ai-assistant
```

### 6.3 Update Google OAuth Console

In Google Cloud Console → OAuth 2.0 Client:
- Authorized JavaScript origins: `https://d1234abcd.cloudfront.net`
- Authorized redirect URIs: `https://api.yourdomain.com/auth/google/callback`

---

## Phase 7 — AWS Secrets Manager (Production Hardening)

Store all secrets in AWS Secrets Manager instead of .env file:

```bash
# Store each secret
aws secretsmanager create-secret \
  --name "ai-assistant/GROQ_API_KEY_PRIMARY" \
  --secret-string "your_key_here"

aws secretsmanager create-secret \
  --name "ai-assistant/JWT_SECRET_KEY" \
  --secret-string "$(openssl rand -hex 32)"

aws secretsmanager create-secret \
  --name "ai-assistant/DATABASE_URL" \
  --secret-string "postgresql://aiuser:pass@endpoint:5432/aiassistant"
```

For ECS deployments, reference secrets in `ecs-task-definition.json` (already configured).

---

## Phase 8 — Auto-restart and Monitoring

### 8.1 Docker auto-restart (already set with --restart unless-stopped)

```bash
# Check container status
docker ps
docker logs ai-assistant --tail 50 -f
```

### 8.2 CloudWatch logs (ECS only — EC2 uses file logs)

Logs are written to `/app/logs/app.log` on EC2 and stdout for ECS.

### 8.3 EC2 instance health check script

```bash
# /home/ubuntu/healthcheck.sh
#!/bin/bash
STATUS=$(curl -s http://localhost:8000/health | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
if [ "$STATUS" != "ok" ]; then
  docker restart ai-assistant
  echo "$(date): Restarted container — status was $STATUS" >> /var/log/ai-assistant-health.log
fi
```

```bash
chmod +x /home/ubuntu/healthcheck.sh
# Run every 5 minutes
(crontab -l; echo "*/5 * * * * /home/ubuntu/healthcheck.sh") | crontab -
```

---

## Cost Estimate (AWS Free Tier / Credits)

| Service         | Spec              | Monthly Cost |
|-----------------|-------------------|-------------|
| EC2 t3.medium   | 2 vCPU, 4GB RAM   | ~$15–20     |
| RDS db.t3.micro | PostgreSQL 15     | ~$15        |
| EBS gp3 10GB    | ChromaDB volume   | ~$1         |
| S3              | Frontend files    | ~$0.01      |
| CloudFront      | CDN + HTTPS       | ~$1–2       |
| **Total**       |                   | **~$32–38** |

AWS credits cover several months of this setup.

---

## Quick Reference — Useful Commands

```bash
# Rebuild and redeploy after code changes
docker build -t ai-action-assistant . && docker stop ai-assistant && docker rm ai-assistant
docker run -d --name ai-assistant --restart unless-stopped \
  -p 8000:8000 \
  -v /data/chromadb:/data/chromadb \
  -v /tmp/uploads:/tmp/uploads \
  --env-file .env \
  ai-action-assistant

# View logs
docker logs ai-assistant -f

# Check health
curl https://api.yourdomain.com/health

# Upload updated frontend to S3
aws s3 sync static/ s3://ai-assistant-frontend/ --include "*.html" --cache-control "no-cache"

# Invalidate CloudFront cache after frontend update
aws cloudfront create-invalidation \
  --distribution-id YOUR_DIST_ID \
  --paths "/*"
```
